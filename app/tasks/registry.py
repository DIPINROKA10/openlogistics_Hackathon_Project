"""
Task registry for loading task configurations.
"""
from app.tasks.easy import TASK_EASY_DELIVERY
from app.tasks.medium import TASK_MEDIUM_OPTIMIZATION
from app.tasks.hard import TASK_HARD_CRISIS
from app.models.models import TaskConfig

TASKS = {
    "easy_delivery": TASK_EASY_DELIVERY,
    "medium_optimization": TASK_MEDIUM_OPTIMIZATION,
    "hard_crisis": TASK_HARD_CRISIS,
}


def get_task(task_id: str) -> TaskConfig:
    """Get task configuration by ID."""
    if task_id not in TASKS:
        raise ValueError(f"Unknown task: {task_id}. Available tasks: {list(TASKS.keys())}")
    return TASKS[task_id]


def list_tasks() -> list[dict]:
    """List all available tasks."""
    return [
        {
            "id": task.id,
            "name": task.name,
            "difficulty": task.difficulty,
            "description": task.description,
            "max_steps": task.max_steps,
        }
        for task in TASKS.values()
    ]
