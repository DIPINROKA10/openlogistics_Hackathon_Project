"""
Data models for OpenLogistics environment.
"""
from pydantic import BaseModel, Field
from typing import Dict, List, Optional
from enum import Enum


class RouteStatus(str, Enum):
    ACTIVE = "active"
    BLOCKED = "blocked"


class ActionType(str, Enum):
    LOAD = "load"
    UNLOAD = "unload"
    MOVE = "move"
    DELIVER = "deliver"
    WAIT = "wait"


class Warehouse(BaseModel):
    id: str
    position: tuple[float, float]
    inventory: Dict[str, int] = Field(default_factory=dict)


class Truck(BaseModel):
    id: str
    capacity: int = 50
    current_load: int = 0
    location: str
    load_contents: Dict[str, int] = Field(default_factory=dict)
    target_location: Optional[str] = None
    steps_to_destination: int = 0


class Order(BaseModel):
    id: str
    source: str
    destination: str
    items: Dict[str, int]
    deadline: int
    priority: int = 1
    status: str = "pending"
    fulfilled_items: Dict[str, int] = Field(default_factory=dict)


class Route(BaseModel):
    from_warehouse: str
    to_warehouse: str
    distance: float
    status: RouteStatus = RouteStatus.ACTIVE


class StepInfo(BaseModel):
    delivered: int = 0
    failed_deliveries: int = 0
    cost: float = 0.0
    invalid_actions: int = 0
    sla_breaches: int = 0
    message: str = ""


class State(BaseModel):
    time: int = 0
    warehouses: List[Warehouse] = Field(default_factory=list)
    trucks: List[Truck] = Field(default_factory=list)
    orders: List[Order] = Field(default_factory=list)
    routes: List[Route] = Field(default_factory=list)
    completed_deliveries: List[str] = Field(default_factory=list)
    failed_deliveries: List[str] = Field(default_factory=list)
    total_cost: float = 0.0
    total_delivered: int = 0
    total_items: int = 0
    routes_replanned: int = 0
    disruptions_handled: int = 0
    disruptions: List[Dict] = Field(default_factory=list)


class SingleAction(BaseModel):
    type: ActionType
    truck_id: str
    target: Optional[str] = None
    items: Optional[Dict[str, int]] = None
    order_id: Optional[str] = None


class Action(BaseModel):
    actions: List[SingleAction]
    reasoning: Optional[str] = None


class StepOutput(BaseModel):
    next_state: State
    reward: float = 0.0
    done: bool = False
    info: StepInfo = Field(default_factory=StepInfo)


class TaskConfig(BaseModel):
    id: str
    name: str
    difficulty: str
    description: str
    max_steps: int
    warehouses: List[Warehouse]
    trucks: List[Truck]
    orders: List[Order]
    routes: List[Route]
    dynamic_events: List[Dict] = Field(default_factory=list)


class ResetRequest(BaseModel):
    task_id: str
    seed: Optional[int] = None


class StepRequest(BaseModel):
    actions: List[SingleAction]
    reasoning: Optional[str] = None


class GradeResponse(BaseModel):
    score: float
    delivery_rate: float
    cost_efficiency: float
    time_efficiency: float
    sla_success: float = 0.0
    adaptability: float = 0.0
    efficiency: float = 0.0
