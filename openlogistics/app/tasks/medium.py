"""
Task 2: Multi-Order Optimization (Medium)
"""
from app.models.models import TaskConfig, Warehouse, Truck, Order, Route, RouteStatus

TASK_MEDIUM_OPTIMIZATION = TaskConfig(
    id="medium_optimization",
    name="Multi-Order Optimization",
    difficulty="medium",
    description="Manage multiple orders efficiently across three warehouses with one blocked route.",
    max_steps=50,
    warehouses=[
        Warehouse(id="W1", position=(0, 0), inventory={"itemA": 100, "itemB": 50}),
        Warehouse(id="W2", position=(10, 0), inventory={"itemA": 0, "itemB": 100}),
        Warehouse(id="W3", position=(5, 10), inventory={"itemA": 50, "itemB": 50}),
    ],
    trucks=[
        Truck(id="T1", capacity=50, current_load=0, location="W1"),
        Truck(id="T2", capacity=50, current_load=0, location="W3"),
    ],
    orders=[
        Order(id="O1", source="W1", destination="W2", items={"itemA": 20}, deadline=20, priority=1),
        Order(id="O2", source="W2", destination="W1", items={"itemB": 30}, deadline=25, priority=1),
        Order(id="O3", source="W3", destination="W2", items={"itemA": 15, "itemB": 10}, deadline=30, priority=2),
        Order(id="O4", source="W1", destination="W3", items={"itemB": 20}, deadline=35, priority=1),
        Order(id="O5", source="W3", destination="W1", items={"itemA": 25}, deadline=40, priority=1),
    ],
    routes=[
        Route(from_warehouse="W1", to_warehouse="W2", distance=10, status=RouteStatus.ACTIVE),
        Route(from_warehouse="W1", to_warehouse="W3", distance=12, status=RouteStatus.BLOCKED),
        Route(from_warehouse="W2", to_warehouse="W3", distance=8, status=RouteStatus.ACTIVE),
    ],
    dynamic_events=[]
)
