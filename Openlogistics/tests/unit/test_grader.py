import pytest
from app.models.models import State, Metrics, Order
from app.environment.grader import GradeManager
from app.tasks.registry import get_task
from app.environment.core import OpenLogisticsEnv

def test_easy_grader():
    task_config = get_task("easy_delivery")
    state = State(
        task_id="easy_delivery",
        time_step=20,
        orders=task_config.orders,
        metrics=Metrics(
            completed_deliveries=["O1"],
            total_delivered=30,
        )
    )
    grade = GradeManager.calculate_grade(state, task_config)
    assert grade["score"] == 1.0
    assert grade["delivery_rate"] == 1.0

def test_medium_grader():
    task_config = get_task("medium_optimization")
    # Simulate partial completion, checking formula math
    # score = 0.5 * DR + 0.3 * CE + 0.2 * TE
    state = State(
        task_id="medium_optimization",
        time_step=30,
        orders=task_config.orders,
        metrics=Metrics(
            completed_deliveries=[],
            total_delivered=0,
            total_cost=0.0
        )
    )
    # DR = 0. CE = 1.0 (no cost / max cost).
    # TE = 1.0 - avg_delay/10.0 => Uncompleted orders will take max delay (10 if clipped?). 
    grade = GradeManager.calculate_grade(state, task_config)
    assert "score" in grade
    assert grade["cost_efficiency"] == 1.0
    
def test_hard_grader():
    task_config = get_task("hard_crisis")
    state = State(
        task_id="hard_crisis",
        time_step=100,
        orders=task_config.orders,
        metrics=Metrics(
            routes_replanned=2,
            total_delivered=160,
            total_cost=100.0,
        )
    )
    grade = GradeManager.calculate_grade(state, task_config)
    assert grade["score"] >= 0.0
    
def test_grade_bounds():
    task_config = get_task("easy_delivery")
    state = State(task_id="easy_delivery", orders=task_config.orders)
    # Extremely bad performance
    state.metrics.total_delivered = -100 # Should clip output to 0.0
    grade = GradeManager.calculate_grade(state, task_config)
    assert grade["score"] == 0.0
