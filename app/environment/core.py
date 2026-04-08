"""
OpenLogistics Environment Engine - Core game logic.
"""
import copy
from typing import Dict, List, Optional
from app.models.models import (
    State, Action, StepOutput, StepInfo, Warehouse, Truck, Order, Route,
    RouteStatus, ActionType, Metrics
)
from app.tasks.registry import get_task
from app.environment.actions import ActionManager
from app.environment.grader import GradeManager

class OpenLogisticsEnv:
    """
    Main environment class implementing the OpenEnv standard.
    """
    
    def __init__(self):
        self.task_config = None
        self._current_state = None
        self.initial_state = None
        self.reward_history = []
        self._done = False
    
    def reset(self, task_id: str, seed: Optional[int] = None) -> State:
        self.task_config = get_task(task_id)
        
        self._current_state = State(
            task_id=task_id,
            time_step=0,
            warehouses=copy.deepcopy(self.task_config.warehouses),
            trucks=copy.deepcopy(self.task_config.trucks),
            orders=copy.deepcopy(self.task_config.orders),
            routes=copy.deepcopy(self.task_config.routes),
            done=False,
            metrics=Metrics(
                total_items=sum(sum(order.items.values()) for order in self.task_config.orders)
            )
        )
        
        self.initial_state = copy.deepcopy(self._current_state)
        self._done = False
        self.reward_history = []
        
        return self.get_state()
    
    def state(self) -> State:
        """Return current environment snapshot."""
        return self.get_state()
    
    def get_state(self) -> State:
        return copy.deepcopy(self._current_state)
    
    def step(self, action: Action) -> StepOutput:
        if self._done:
            return StepOutput(
                state=self.get_state(),
                reward=0.0,
                done=True,
                info=StepInfo(message="Episode already complete. Call reset() to start new episode.")
            )
        
        info = StepInfo()
        total_reward = 0.0
        
        self._process_dynamic_events()
        
        for single_action in action.actions:
            result = ActionManager.execute_action(self._current_state, single_action, info)
            total_reward += result
        
        self._check_deadlines(info)
        
        self._current_state.time_step += 1
        
        self._done = self._check_done()
        self._current_state.done = self._done
        
        if self._done:
            total_reward += self._calculate_end_bonus()
            info.message = f"Episode complete at time {self._current_state.time_step}"
            for order in self._current_state.orders:
                if order.status == "pending":
                    order.status = "failed"
                    self._current_state.metrics.failed_deliveries.append(order.id)
        
        self.reward_history.append(total_reward)
        
        return StepOutput(
            state=self.get_state(),
            reward=total_reward,
            done=self._done,
            info=info
        )
    
    def _process_dynamic_events(self):
        """Process any dynamic events that should occur at current time."""
        if not getattr(self.task_config, "dynamic_events", None):
            return
        
        for event in self.task_config.dynamic_events:
            if event.get("time") == self._current_state.time_step:
                self._current_state.metrics.disruptions.append(event)
                event_type = event.get("type")
                
                if event_type == "route_block":
                    self._block_route(event["from"], event["to"])
                    
                elif event_type == "inventory_loss":
                    self._lose_inventory(event["warehouse"], event["loss_percent"])
                    
                elif event_type == "new_order":
                    new_order = copy.deepcopy(Order(**event["order"])) if isinstance(event["order"], dict) else copy.deepcopy(event["order"])
                    self._current_state.orders.append(new_order)
                    self._current_state.metrics.total_items += sum(new_order.items.values())
                    
                elif event_type == "new_truck":
                    new_truck = copy.deepcopy(Truck(**event["truck"])) if isinstance(event["truck"], dict) else copy.deepcopy(event["truck"])
                    self._current_state.trucks.append(new_truck)
    
    def _block_route(self, from_wh: str, to_wh: str):
        """Block a route between two warehouses."""
        for route in self._current_state.routes:
            if (route.from_warehouse == from_wh and route.to_warehouse == to_wh) or \
               (route.from_warehouse == to_wh and route.to_warehouse == from_wh):
                route.status = RouteStatus.BLOCKED
    
    def _lose_inventory(self, warehouse_id: str, percent: float):
        """Lose a percentage of inventory at a warehouse."""
        for warehouse in self._current_state.warehouses:
            if warehouse.id == warehouse_id:
                for item in warehouse.inventory:
                    warehouse.inventory[item] = int(warehouse.inventory[item] * (1 - percent))
    
    def _check_deadlines(self, info: StepInfo):
        """Check for missed deadlines."""
        for order in self._current_state.orders:
            if order.status == "pending" and self._current_state.time_step > order.deadline:
                info.sla_breaches += 1
    
    def _check_done(self) -> bool:
        """Check if episode is done."""
        if self._current_state.time_step >= getattr(self.task_config, "max_steps", 100):
            return True
        
        pending_orders = [o for o in self._current_state.orders if o.status == "pending"]
        if len(pending_orders) == 0:
            return True
        
        return False
    
    def _calculate_end_bonus(self) -> float:
        """Calculate end-of-episode bonus."""
        total_orders = len(self.task_config.orders)
        completed = len(self._current_state.metrics.completed_deliveries)
        
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
    
    def grade(self) -> Dict:
        """
        Calculate final score (0.0 - 1.0) based on task-specific grading.
        """
        return GradeManager.calculate_grade(self._current_state, self.task_config)
