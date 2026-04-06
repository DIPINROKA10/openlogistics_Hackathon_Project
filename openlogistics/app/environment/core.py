"""
OpenLogistics Environment Engine - Core game logic.
"""
import copy
from typing import Dict, List, Optional
from app.models.models import (
    State, Action, StepOutput, StepInfo, Warehouse, Truck, Order, Route,
    RouteStatus, ActionType, Truck
)
from app.tasks.registry import get_task


class OpenLogisticsEnv:
    """
    Main environment class implementing the OpenEnv standard.
    
    Methods:
        reset(task_id) - Initialize environment for specific task
        state() - Return current environment snapshot
        step(action) - Process action and return transition
        grade() - Calculate final score (0.0 - 1.0)
    """
    
    def __init__(self):
        self.task_config = None
        self._current_state = None
        self.initial_state = None
        self.reward_history = []
        self._done = False
    
    def reset(self, task_id: str, seed: Optional[int] = None) -> State:
        """
        Initialize environment for specific task.
        
        Args:
            task_id: ID of the task to load (easy_delivery, medium_optimization, hard_crisis)
            seed: Optional random seed for reproducibility
            
        Returns:
            Initial state of the environment
        """
        self.task_config = get_task(task_id)
        
        self._current_state = State(
            time=0,
            warehouses=copy.deepcopy(self.task_config.warehouses),
            trucks=copy.deepcopy(self.task_config.trucks),
            orders=copy.deepcopy(self.task_config.orders),
            routes=copy.deepcopy(self.task_config.routes),
            completed_deliveries=[],
            failed_deliveries=[],
            total_cost=0.0,
            total_delivered=0,
            total_items=sum(
                sum(order.items.values()) for order in self.task_config.orders
            ),
            routes_replanned=0,
            disruptions_handled=0,
            disruptions=[]
        )
        
        self.initial_state = copy.deepcopy(self._current_state)
        self._done = False
        self.reward_history = []
        
        return self.get_state()
    
    def state(self) -> State:
        """Return current environment snapshot."""
        return self.get_state()
    
    def get_state(self) -> State:
        """Get current state."""
        return copy.deepcopy(self._current_state)
    
    def step(self, action: Action) -> StepOutput:
        """
        Process agent action and return transition.
        
        Args:
            action: Action containing list of actions to execute
            
        Returns:
            StepOutput with next_state, reward, done flag, and info
        """
        if self._done:
            return StepOutput(
                next_state=self.get_state(),
                reward=0.0,
                done=True,
                info=StepInfo(message="Episode already complete. Call reset() to start new episode.")
            )
        
        info = StepInfo()
        total_reward = 0.0
        
        self._process_dynamic_events()
        
        for single_action in action.actions:
            result = self._execute_action(single_action, info)
            total_reward += result
        
        self._check_deadlines(info)
        
        self._current_state.time += 1
        
        self._done = self._check_done()
        
        if self._done:
            total_reward += self._calculate_end_bonus()
            info.message = f"Episode complete at time {self._current_state.time}"
        
        self.reward_history.append(total_reward)
        
        return StepOutput(
            next_state=self.get_state(),
            reward=total_reward,
            done=self._done,
            info=info
        )
    
    def _process_dynamic_events(self):
        """Process any dynamic events that should occur at current time."""
        if not self.task_config.dynamic_events:
            return
        
        for event in self.task_config.dynamic_events:
            if event.get("time") == self._current_state.time:
                self._current_state.disruptions.append(event)
                event_type = event.get("type")
                
                if event_type == "route_block":
                    self._block_route(event["from"], event["to"])
                    
                elif event_type == "inventory_loss":
                    self._lose_inventory(event["warehouse"], event["loss_percent"])
                    
                elif event_type == "new_order":
                    new_order = copy.deepcopy(event["order"])
                    self._current_state.orders.append(new_order)
                    self._current_state.total_items += sum(new_order.items.values())
                    
                elif event_type == "new_truck":
                    new_truck = copy.deepcopy(event["truck"])
                    self._current_state.trucks.append(new_truck)
    
    def _block_route(self, from_wh: str, to_wh: str):
        """Block a route between two warehouses."""
        for route in self._current_state.routes:
            if (route.from_warehouse == from_wh and route.to_warehouse == to_wh) or \
               (route.from_warehouse == to_wh and route.to_warehouse == from_wh):
                route.status = RouteStatus.BLOCKED
    
    def _unblock_route(self, from_wh: str, to_wh: str):
        """Unblock a route between two warehouses."""
        for route in self._current_state.routes:
            if (route.from_warehouse == from_wh and route.to_warehouse == to_wh) or \
               (route.from_warehouse == to_wh and route.to_warehouse == from_wh):
                route.status = RouteStatus.ACTIVE
    
    def _lose_inventory(self, warehouse_id: str, percent: float):
        """Lose a percentage of inventory at a warehouse."""
        for warehouse in self._current_state.warehouses:
            if warehouse.id == warehouse_id:
                for item in warehouse.inventory:
                    warehouse.inventory[item] = int(warehouse.inventory[item] * (1 - percent))
    
    def _execute_action(self, action, info: StepInfo) -> float:
        """Execute a single action and return reward."""
        truck = self._find_truck(action.truck_id)
        if not truck:
            info.invalid_actions += 1
            return -0.1
        
        action_type = action.type
        
        if action_type == ActionType.WAIT:
            return 0.0
        
        elif action_type == ActionType.LOAD:
            return self._execute_load(truck, action, info)
        
        elif action_type == ActionType.UNLOAD:
            return self._execute_unload(truck, action, info)
        
        elif action_type == ActionType.MOVE:
            return self._execute_move(truck, action, info)
        
        elif action_type == ActionType.DELIVER:
            return self._execute_deliver(truck, action, info)
        
        return 0.0
    
    def _execute_load(self, truck: Truck, action, info: StepInfo) -> float:
        """Load items from warehouse into truck."""
        if not action.target:
            info.invalid_actions += 1
            return -0.1
        
        warehouse = self._find_warehouse(action.target)
        if not warehouse:
            info.invalid_actions += 1
            return -0.1
        
        if truck.location != warehouse.id:
            info.invalid_actions += 1
            return -0.1
        
        if not action.items:
            info.invalid_actions += 1
            return -0.1
        
        items_to_load = action.items
        total_load = sum(items_to_load.values())
        
        available_capacity = truck.capacity - truck.current_load
        if total_load > available_capacity:
            items_to_load = self._adjust_items_to_capacity(items_to_load, available_capacity)
            total_load = sum(items_to_load.values())
        
        for item, qty in items_to_load.items():
            if warehouse.inventory.get(item, 0) < qty:
                qty = warehouse.inventory.get(item, 0)
                items_to_load[item] = qty
            
            if qty > 0:
                warehouse.inventory[item] = warehouse.inventory.get(item, 0) - qty
                truck.load_contents[item] = truck.load_contents.get(item, 0) + qty
                truck.current_load += qty
        
        return 0.0
    
    def _adjust_items_to_capacity(self, items: Dict[str, int], capacity: int) -> Dict[str, int]:
        """Adjust items to fit within capacity."""
        total = sum(items.values())
        if total <= capacity:
            return items
        
        ratio = capacity / total
        adjusted = {}
        for item, qty in items.items():
            adjusted[item] = int(qty * ratio)
        
        remaining = capacity - sum(adjusted.values())
        if remaining > 0 and adjusted:
            for item in adjusted:
                adjusted[item] += 1
                remaining -= 1
                if remaining <= 0:
                    break
        
        return adjusted
    
    def _execute_unload(self, truck: Truck, action, info: StepInfo) -> float:
        """Unload items from truck to warehouse."""
        if not action.target:
            info.invalid_actions += 1
            return -0.1
        
        warehouse = self._find_warehouse(action.target)
        if not warehouse:
            info.invalid_actions += 1
            return -0.1
        
        if truck.location != warehouse.id:
            info.invalid_actions += 1
            return -0.1
        
        items_to_unload = action.items if action.items else truck.load_contents
        
        for item, qty in items_to_unload.items():
            if truck.load_contents.get(item, 0) < qty:
                qty = truck.load_contents.get(item, 0)
            
            if qty > 0:
                warehouse.inventory[item] = warehouse.inventory.get(item, 0) + qty
                truck.load_contents[item] = truck.load_contents.get(item, 0) - qty
                truck.current_load -= qty
        
        return 0.0
    
    def _execute_move(self, truck: Truck, action, info: StepInfo) -> float:
        """Move truck towards target warehouse."""
        if not action.target:
            info.invalid_actions += 1
            return -0.1
        
        target = action.target
        
        if truck.location == target:
            return 0.0
        
        route = self._find_route(truck.location, target)
        if not route:
            info.invalid_actions += 1
            return -0.1
        
        if route.status == RouteStatus.BLOCKED:
            info.invalid_actions += 1
            return -0.1
        
        # If already moving, continue moving
        if truck.steps_to_destination > 0:
            truck.steps_to_destination -= 1
            fuel_cost = route.distance * 0.02
            self._current_state.total_cost += fuel_cost
            info.cost += fuel_cost
            
            if truck.steps_to_destination == 0:
                truck.location = target
                truck.target_location = None
            
            return -fuel_cost
        
        # Start moving - set target and steps
        truck.target_location = target
        truck.steps_to_destination = int(route.distance)
        
        fuel_cost = route.distance * 0.02
        self._current_state.total_cost += fuel_cost
        info.cost += fuel_cost
        
        # Move one step immediately
        truck.steps_to_destination -= 1
        if truck.steps_to_destination == 0:
            truck.location = target
            truck.target_location = None
        else:
            # Start moving but not yet arrived
            truck.location = target
        
        return -fuel_cost
    
    def _execute_deliver(self, truck: Truck, action, info: StepInfo) -> float:
        """Deliver items to fulfill an order."""
        if not action.order_id:
            if action.target:
                return self._deliver_to_warehouse(truck, action, info)
            info.invalid_actions += 1
            return -0.1
        
        order = self._find_order(action.order_id)
        if not order:
            info.invalid_actions += 1
            return -0.1
        
        if order.status == "delivered":
            return 0.0
        
        if truck.location != order.destination:
            info.invalid_actions += 1
            return -0.1
        
        total_delivered = 0
        items_to_fulfill = order.items.copy()
        
        for item, qty_needed in items_to_fulfill.items():
            qty_in_truck = truck.load_contents.get(item, 0)
            qty_delivered = min(qty_needed, qty_in_truck)
            
            if qty_delivered > 0:
                truck.load_contents[item] -= qty_delivered
                truck.current_load -= qty_delivered
                order.fulfilled_items[item] = order.fulfilled_items.get(item, 0) + qty_delivered
                total_delivered += qty_delivered
        
        if total_delivered > 0:
            reward = 0.1 * total_delivered
            
            if self._is_order_complete(order):
                order.status = "delivered"
                self._current_state.completed_deliveries.append(order.id)
                self._current_state.total_delivered += total_delivered
                info.delivered += total_delivered
                reward += 0.2
            
            return reward
        
        info.invalid_actions += 1
        return -0.1
    
    def _deliver_to_warehouse(self, truck: Truck, action, info: StepInfo) -> float:
        """Deliver items to a warehouse (not tied to order)."""
        warehouse = self._find_warehouse(action.target)
        if not warehouse or truck.location != warehouse.id:
            info.invalid_actions += 1
            return -0.1
        
        total_unloaded = 0
        for item, qty in list(truck.load_contents.items()):
            if qty > 0:
                warehouse.inventory[item] = warehouse.inventory.get(item, 0) + qty
                total_unloaded += qty
                truck.load_contents[item] = 0
        
        truck.current_load = 0
        
        if total_unloaded > 0:
            return 0.05 * total_unloaded
        
        return 0.0
    
    def _check_deadlines(self, info: StepInfo):
        """Check for missed deadlines."""
        for order in self._current_state.orders:
            if order.status == "pending" and self._current_state.time > order.deadline:
                order.status = "failed"
                self._current_state.failed_deliveries.append(order.id)
                info.failed_deliveries += 1
                info.sla_breaches += 1
    
    def _check_done(self) -> bool:
        """Check if episode is done."""
        if self._current_state.time >= self.task_config.max_steps:
            return True
        
        pending_orders = [o for o in self._current_state.orders if o.status == "pending"]
        if len(pending_orders) == 0:
            return True
        
        return False
    
    def _calculate_end_bonus(self) -> float:
        """Calculate end-of-episode bonus."""
        total_orders = len(self.task_config.orders)
        completed = len(self._current_state.completed_deliveries)
        
        completion_rate = completed / total_orders if total_orders > 0 else 0
        
        if completion_rate == 1.0:
            return 0.5
        elif completion_rate >= 0.8:
            return 0.3
        elif completion_rate >= 0.5:
            return 0.1
        elif completion_rate == 0:
            return -0.5
        
        return 0.0
    
    def _find_truck(self, truck_id: str) -> Optional[Truck]:
        """Find truck by ID."""
        for truck in self._current_state.trucks:
            if truck.id == truck_id:
                return truck
        return None
    
    def _find_warehouse(self, warehouse_id: str) -> Optional[Warehouse]:
        """Find warehouse by ID."""
        for warehouse in self._current_state.warehouses:
            if warehouse.id == warehouse_id:
                return warehouse
        return None
    
    def _find_order(self, order_id: str) -> Optional[Order]:
        """Find order by ID."""
        for order in self._current_state.orders:
            if order.id == order_id:
                return order
        return None
    
    def _find_route(self, from_wh: str, to_wh: str) -> Optional[Route]:
        """Find route between two warehouses."""
        for route in self._current_state.routes:
            if (route.from_warehouse == from_wh and route.to_warehouse == to_wh) or \
               (route.from_warehouse == to_wh and route.to_warehouse == from_wh):
                return route
        return None
    
    def _is_order_complete(self, order: Order) -> bool:
        """Check if an order is fully fulfilled."""
        for item, qty_needed in order.items.items():
            qty_fulfilled = order.fulfilled_items.get(item, 0)
            if qty_fulfilled < qty_needed:
                return False
        return True
    
    def grade(self) -> Dict:
        """
        Calculate final score (0.0 - 1.0) based on task-specific grading.
        
        Returns:
            Dictionary with score and detailed metrics
        """
        task_id = self.task_config.id
        
        total_orders = len(self.task_config.orders)
        completed_orders = len(self._current_state.completed_deliveries)
        
        total_items = sum(sum(order.items.values()) for order in self.task_config.orders)
        delivered_items = self._current_state.total_delivered
        
        delivery_rate = delivered_items / total_items if total_items > 0 else 0
        
        max_cost = sum(route.distance * 2 for route in self.task_config.routes)
        cost_efficiency = max(0, 1 - (self._current_state.total_cost / max_cost)) if max_cost > 0 else 1
        
        failed = len(self._current_state.failed_deliveries)
        on_time = completed_orders
        sla_success = on_time / total_orders if total_orders > 0 else 0
        
        if task_id == "easy_delivery":
            score = delivery_rate
            
        elif task_id == "medium_optimization":
            time_efficiency = 1 - (len(self._current_state.failed_deliveries) / max(1, total_orders - completed_orders))
            score = 0.5 * delivery_rate + 0.3 * cost_efficiency + 0.2 * max(0, time_efficiency)
            
        elif task_id == "hard_crisis":
            disruptions = len([e for e in self.task_config.dynamic_events if e.get("type") == "route_block"])
            adaptability = 1 - (disruptions / max(1, disruptions))
            efficiency = (delivered_items * 2) / (total_items + self._current_state.total_cost) if total_items > 0 else 0
            score = 0.4 * sla_success + 0.3 * max(0, adaptability) + 0.3 * min(1, efficiency)
        
        else:
            score = delivery_rate
        
        score = max(0, min(1, score))
        
        return {
            "score": round(score, 4),
            "delivery_rate": round(delivery_rate, 4),
            "cost_efficiency": round(cost_efficiency, 4),
            "time_efficiency": round(1 - (failed / max(1, total_orders)), 4),
            "sla_success": round(sla_success, 4),
            "total_delivered": delivered_items,
            "total_items": total_items,
            "completed_orders": completed_orders,
            "total_orders": total_orders,
            "failed_orders": failed,
            "total_cost": round(self._current_state.total_cost, 2),
            "episodes_time": self._current_state.time
        }
