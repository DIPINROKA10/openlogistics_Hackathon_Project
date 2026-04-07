"""
API routes for OpenLogistics environment.
"""
from fastapi import APIRouter, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.models.models import (
    ResetRequest, StepRequest, Action, SingleAction,
    State, StepOutput, GradeResponse
)
from app.environment.core import OpenLogisticsEnv
from app.tasks.registry import list_tasks

def get_real_ip(request: Request) -> str:
    """Extract real client IP from proxy headers."""
    if "x-forwarded-for" in request.headers:
        return request.headers["x-forwarded-for"].split(",")[0].strip()
    return get_remote_address(request)

limiter = Limiter(key_func=get_real_ip)
router = APIRouter()

_env: OpenLogisticsEnv = None

def get_env() -> OpenLogisticsEnv:
    """Get or create environment instance."""
    global _env
    if _env is None:
        _env = OpenLogisticsEnv()
    return _env

@router.get("/health")
@limiter.limit("5/second")
async def health_check(request: Request):
    """Health check endpoint."""
    return {"status": "ok", "service": "OpenLogistics"}

@router.get("/tasks")
@limiter.limit("5/second")
async def get_tasks(request: Request):
    """List all available tasks."""
    return {"tasks": list_tasks()}

@router.post("/reset", response_model=State)
@limiter.limit("2/second")
async def reset(request: Request, payload: ResetRequest):
    """Initialize environment for specific task."""
    env = get_env()
    try:
        state = env.reset(payload.task_id, payload.seed)
        return state
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/state", response_model=State)
@limiter.limit("10/second")
async def get_state(request: Request):
    """Get current environment state."""
    env = get_env()
    if env._current_state is None:
        env.reset("easy_delivery")
    return env.state()

@router.post("/step", response_model=StepOutput)
@limiter.limit("10/second")
async def step(request: Request, payload: StepRequest):
    """Execute action(s) and return result."""
    env = get_env()
    action = Action(actions=payload.actions, reasoning=payload.reasoning)
    return env.step(action)

@router.get("/grade", response_model=GradeResponse)
@limiter.limit("5/second")
async def grade(request: Request):
    """Get final score and metrics."""
    env = get_env()
    result = env.grade()
    return GradeResponse(**result)

@router.post("/episode/reset")
@limiter.limit("2/second")
async def episode_reset(request: Request):
    """Reset environment for new episode."""
    global _env
    _env = OpenLogisticsEnv()
    return {"message": "Environment reset successful"}
