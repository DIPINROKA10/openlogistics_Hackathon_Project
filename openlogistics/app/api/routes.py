"""
API routes for OpenLogistics environment.
"""
from fastapi import APIRouter, HTTPException
from app.models.models import (
    ResetRequest, StepRequest, Action, SingleAction,
    State, StepOutput, GradeResponse
)
from app.environment.core import OpenLogisticsEnv
from app.tasks.registry import list_tasks

router = APIRouter()

_env: OpenLogisticsEnv = None


def get_env() -> OpenLogisticsEnv:
    """Get or create environment instance."""
    global _env
    if _env is None:
        _env = OpenLogisticsEnv()
    return _env


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "OpenLogistics"}


@router.get("/tasks")
async def get_tasks():
    """List all available tasks."""
    return {"tasks": list_tasks()}


@router.post("/reset", response_model=State)
async def reset(request: ResetRequest):
    """Initialize environment for specific task."""
    env = get_env()
    try:
        state = env.reset(request.task_id, request.seed)
        return state
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/state", response_model=State)
async def get_state():
    """Get current environment state."""
    env = get_env()
    return env.state()


@router.post("/step", response_model=StepOutput)
async def step(request: StepRequest):
    """Execute action(s) and return result."""
    env = get_env()
    action = Action(actions=request.actions, reasoning=request.reasoning)
    return env.step(action)


@router.get("/grade", response_model=GradeResponse)
async def grade():
    """Get final score and metrics."""
    env = get_env()
    result = env.grade()
    return GradeResponse(**result)


@router.post("/episode/reset")
async def episode_reset():
    """Reset environment for new episode."""
    global _env
    _env = OpenLogisticsEnv()
    return {"message": "Environment reset successful"}
