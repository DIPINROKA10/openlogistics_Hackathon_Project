from typing import Dict
from app.models.models import State, TaskConfig

class GradeManager:
    @staticmethod
    def calculate_grade(state: State, task_config: TaskConfig) -> Dict:
        task_id = task_config.id
        
        total_orders = len(task_config.orders)
        completed_orders = len(state.metrics.completed_deliveries)
        
        total_items = sum(sum(order.items.values()) for order in task_config.orders)
        delivered_items = state.metrics.total_delivered
        
        delivery_rate = delivered_items / total_items if total_items > 0 else 0.0
        
        max_cost = sum(route.distance * 2 for route in task_config.routes)
        cost_efficiency = max(0.0, 1.0 - (state.metrics.total_cost / max_cost)) if max_cost > 0 else 1.0
        
        total_delay = 0
        on_time_deliveries = 0
        
        for order in state.orders:
            if order.id in state.metrics.completed_deliveries:
                if order.completion_time is not None:
                    delay = max(0, order.completion_time - order.deadline)
                    total_delay += delay
                    if delay <= 0:
                        on_time_deliveries += 1
            else:
                delay = max(0, state.time_step - order.deadline)
                total_delay += min(10, delay) # cap at 10 for uncompleted
                
        avg_delay = (total_delay / total_orders) if total_orders > 0 else 0
        time_efficiency = max(0.0, 1.0 - (avg_delay / 10.0))
        
        sla_success = on_time_deliveries / total_orders if total_orders > 0 else 0.0
        
        adaptability = 0.0
        efficiency = 0.0

        if task_id == "easy_delivery":
            score = delivery_rate
        elif task_id in ["medium_multi", "medium_optimization"]:
            score = 0.5 * delivery_rate + 0.3 * cost_efficiency + 0.2 * time_efficiency
        elif task_id == "hard_crisis":
            disruptions = len([e for e in task_config.dynamic_events if e.get("type") == "route_block"])
            adaptability = (state.metrics.routes_replanned / disruptions) if disruptions > 0 else 1.0
            efficiency = (delivered_items * 2) / (total_items + state.metrics.total_cost) if (total_items + state.metrics.total_cost) > 0 else 0.0
            
            score = 0.4 * sla_success + 0.3 * min(1.0, max(0.0, adaptability)) + 0.3 * min(1.0, max(0.0, efficiency))
        else:
            score = delivery_rate
            
        score = max(0.0, min(1.0, score))
        
        return {
            "score": round(score, 4),
            "delivery_rate": round(delivery_rate, 4),
            "cost_efficiency": round(cost_efficiency, 4),
            "time_efficiency": round(time_efficiency, 4),
            "sla_success": round(sla_success, 4),
            "adaptability": round(adaptability, 4),
            "efficiency": round(efficiency, 4),
            "total_delivered": delivered_items,
            "total_items": total_items,
            "completed_orders": completed_orders,
            "total_orders": total_orders,
            "failed_orders": len(state.metrics.failed_deliveries),
            "total_cost": round(state.metrics.total_cost, 2),
            "episodes_time": state.time_step
        }
