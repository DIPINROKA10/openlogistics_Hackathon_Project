from typing import Dict, List, Optional
from app.models.models import State, ActionType, StepInfo, Truck, Warehouse, Order, SingleAction, RouteStatus

class ActionManager:
    @staticmethod
    def execute_action(state: State, action: SingleAction, info: StepInfo) -> float:
        truck = ActionManager._find_truck(state, action.truck_id)
        if not truck:
            info.invalid_actions += 1
            return -0.1
        
        action_type = action.type
        if action_type == ActionType.WAIT:
            return 0.0
        elif action_type == ActionType.LOAD:
            return ActionManager._execute_load(state, truck, action, info)
        elif action_type == ActionType.UNLOAD:
            return ActionManager._execute_unload(state, truck, action, info)
        elif action_type == ActionType.MOVE:
            return ActionManager._execute_move(state, truck, action, info)
        elif action_type == ActionType.DELIVER:
            return ActionManager._execute_deliver(state, truck, action, info)
        return 0.0

    @staticmethod
    def _execute_load(state: State, truck: Truck, action: SingleAction, info: StepInfo) -> float:
        if not action.target:
            info.invalid_actions += 1
            return -0.1
        warehouse = ActionManager._find_warehouse(state, action.target)
        if not warehouse or truck.location != warehouse.id:
            info.invalid_actions += 1
            return -0.1
        if not action.items:
            info.invalid_actions += 1
            return -0.1
        
        items_to_load = action.items.copy()
        total_load = sum(items_to_load.values())
        available_capacity = truck.capacity - truck.current_load
        
        if total_load > available_capacity:
            items_to_load = ActionManager._adjust_items_to_capacity(items_to_load, available_capacity)
            total_load = sum(items_to_load.values())
        
        for item, qty in items_to_load.items():
            wh_qty = warehouse.inventory.get(item, 0)
            if wh_qty < qty:
                qty = wh_qty
                items_to_load[item] = qty
            
            if qty > 0:
                warehouse.inventory[item] = wh_qty - qty
                truck.load_contents[item] = truck.load_contents.get(item, 0) + qty
                truck.current_load += qty
        return 0.0

    @staticmethod
    def _execute_unload(state: State, truck: Truck, action: SingleAction, info: StepInfo) -> float:
        if not action.target:
            info.invalid_actions += 1
            return -0.1
        warehouse = ActionManager._find_warehouse(state, action.target)
        if not warehouse or truck.location != warehouse.id:
            info.invalid_actions += 1
            return -0.1
        
        items_to_unload = action.items.copy() if action.items else truck.load_contents.copy()
        for item, qty in items_to_unload.items():
            truck_qty = truck.load_contents.get(item, 0)
            if truck_qty < qty:
                qty = truck_qty
            if qty > 0:
                warehouse.inventory[item] = warehouse.inventory.get(item, 0) + qty
                truck.load_contents[item] = truck_qty - qty
                truck.current_load -= qty
        return 0.0

    @staticmethod
    def _execute_move(state: State, truck: Truck, action: SingleAction, info: StepInfo) -> float:
        if not action.target:
            info.invalid_actions += 1
            return -0.1
        target = action.target
        if truck.location == target:
            return 0.0
        
        route = ActionManager._find_route(state, truck.location, target)
        if not route:
            info.invalid_actions += 1
            return -0.1
        if route.status == RouteStatus.BLOCKED:
            info.invalid_actions += 1
            state.metrics.routes_replanned += 1
            return -0.1
        
        if truck.steps_to_destination > 1:
            truck.steps_to_destination -= 1
            fuel_cost = route.distance * 0.02
            state.metrics.total_cost += fuel_cost
            info.cost += fuel_cost
            return -fuel_cost
        
        if truck.steps_to_destination == 1:
            truck.steps_to_destination = 0
            truck.location = target
            truck.target_location = None
            fuel_cost = route.distance * 0.02
            state.metrics.total_cost += fuel_cost
            info.cost += fuel_cost
            return -fuel_cost
            
        truck.target_location = target
        truck.steps_to_destination = int(route.distance)
        fuel_cost = route.distance * 0.02
        state.metrics.total_cost += fuel_cost
        info.cost += fuel_cost
        
        truck.steps_to_destination -= 1
        if truck.steps_to_destination == 0:
            truck.location = target
            truck.target_location = None
        return -fuel_cost

    @staticmethod
    def _execute_deliver(state: State, truck: Truck, action: SingleAction, info: StepInfo) -> float:
        if not action.order_id:
            if action.target:
                return ActionManager._deliver_to_warehouse(state, truck, action, info)
            info.invalid_actions += 1
            return -0.1
            
        order = ActionManager._find_order(state, action.order_id)
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
            if ActionManager._is_order_complete(order):
                order.status = "delivered"
                order.completion_time = state.time_step
                state.metrics.completed_deliveries.append(order.id)
                state.metrics.total_delivered += total_delivered
                info.delivered += total_delivered
                reward += 0.2
            return reward
            
        info.invalid_actions += 1
        return -0.1

    @staticmethod
    def _deliver_to_warehouse(state: State, truck: Truck, action: SingleAction, info: StepInfo) -> float:
        warehouse = ActionManager._find_warehouse(state, action.target)
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

    @staticmethod
    def _adjust_items_to_capacity(items: Dict[str, int], capacity: int) -> Dict[str, int]:
        total = sum(items.values())
        if total <= capacity: return items
        ratio = capacity / total
        adjusted = {item: int(qty * ratio) for item, qty in items.items()}
        remaining = capacity - sum(adjusted.values())
        if remaining > 0 and adjusted:
            for item in adjusted:
                adjusted[item] += 1
                remaining -= 1
                if remaining <= 0: break
        return adjusted

    @staticmethod
    def _find_truck(state: State, truck_id: str) -> Optional[Truck]:
        return next((t for t in state.trucks if t.id == truck_id), None)
        
    @staticmethod
    def _find_warehouse(state: State, warehouse_id: str) -> Optional[Warehouse]:
        return next((w for w in state.warehouses if w.id == warehouse_id), None)
        
    @staticmethod
    def _find_order(state: State, order_id: str) -> Optional[Order]:
        return next((o for o in state.orders if o.id == order_id), None)
        
    @staticmethod
    def _find_route(state: State, from_wh: str, to_wh: str):
        return next((r for r in state.routes if (r.from_warehouse == from_wh and r.to_warehouse == to_wh) or (r.from_warehouse == to_wh and r.to_warehouse == from_wh)), None)

    @staticmethod
    def _is_order_complete(order: Order) -> bool:
        return all(order.fulfilled_items.get(item, 0) >= qty for item, qty in order.items.items())
