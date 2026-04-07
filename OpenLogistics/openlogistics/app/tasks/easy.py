"""
Task 1: Basic Delivery (Easy)
"""
from app.models.models import TaskConfig, Warehouse, Truck, Order, Route, RouteStatus

TASK_EASY_DELIVERY = TaskConfig(
    id="easy_delivery",
    name="Basic Delivery",
    difficulty="easy",
    description="Deliver goods from W1 to W2 within the deadline.",
    max_steps=20,
    warehouses=[
        Warehouse(id="W1", position=(0, 0), inventory={"itemA": 100}),
        Warehouse(id="W2", position=(10, 0), inventory={"itemA": 0}),
    ],
    trucks=[
        Truck(id="T1", capacity=50, current_load=0, location="W1"),
    ],
    orders=[
        Order(
            id="O1",
            source="W1",
            destination="W2",
            items={"itemA": 30},
            deadline=15,
            priority=1
        ),
    ],
    routes=[
        Route(from_warehouse="W1", to_warehouse="W2", distance=10, status=RouteStatus.ACTIVE),
    ],
    dynamic_events=[]
)
