"""
Task 3: Crisis Management (Hard)
"""
from app.models.models import TaskConfig, Warehouse, Truck, Order, Route, RouteStatus

TASK_HARD_CRISIS = TaskConfig(
    id="hard_crisis",
    name="Crisis Management",
    difficulty="hard",
    description="Handle a logistics crisis with multiple disruptions and dynamic events.",
    max_steps=100,
    warehouses=[
        Warehouse(id="W1", position=(0, 0), inventory={"itemA": 200, "itemB": 100, "itemC": 50}),
        Warehouse(id="W2", position=(15, 0), inventory={"itemA": 0, "itemB": 150, "itemC": 100}),
        Warehouse(id="W3", position=(7, 12), inventory={"itemA": 100, "itemB": 0, "itemC": 75}),
        Warehouse(id="W4", position=(20, 15), inventory={"itemA": 50, "itemB": 200, "itemC": 0}),
    ],
    trucks=[
        Truck(id="T1", capacity=50, current_load=0, location="W1"),
        Truck(id="T2", capacity=50, current_load=0, location="W2"),
        Truck(id="T3", capacity=50, current_load=0, location="W3"),
    ],
    orders=[
        Order(id="O1", source="W1", destination="W2", items={"itemA": 30}, deadline=20, priority=2),
        Order(id="O2", source="W2", destination="W3", items={"itemB": 40}, deadline=25, priority=1),
        Order(id="O3", source="W3", destination="W4", items={"itemC": 20}, deadline=30, priority=3),
        Order(id="O4", source="W1", destination="W4", items={"itemA": 50}, deadline=35, priority=2),
        Order(id="O5", source="W4", destination="W1", items={"itemB": 30}, deadline=40, priority=1),
        Order(id="O6", source="W2", destination="W1", items={"itemC": 25}, deadline=45, priority=1),
        Order(id="O7", source="W3", destination="W2", items={"itemA": 35}, deadline=50, priority=2),
        Order(id="O8", source="W4", destination="W3", items={"itemB": 45}, deadline=55, priority=1),
        Order(id="O9", source="W1", destination="W3", items={"itemC": 30}, deadline=60, priority=2),
        Order(id="O10", source="W2", destination="W4", items={"itemA": 40}, deadline=70, priority=1),
    ],
    routes=[
        Route(from_warehouse="W1", to_warehouse="W2", distance=15, status=RouteStatus.ACTIVE),
        Route(from_warehouse="W1", to_warehouse="W3", distance=12, status=RouteStatus.BLOCKED),
        Route(from_warehouse="W1", to_warehouse="W4", distance=25, status=RouteStatus.ACTIVE),
        Route(from_warehouse="W2", to_warehouse="W3", distance=10, status=RouteStatus.BLOCKED),
        Route(from_warehouse="W2", to_warehouse="W4", distance=12, status=RouteStatus.ACTIVE),
        Route(from_warehouse="W3", to_warehouse="W4", distance=8, status=RouteStatus.BLOCKED),
    ],
    dynamic_events=[
        {"time": 15, "type": "route_block", "from": "W2", "to": "W4"},
        {"time": 30, "type": "inventory_loss", "warehouse": "W3", "loss_percent": 0.5},
        {"time": 45, "type": "new_order", "order": Order(id="O11", source="W1", destination="W2", items={"itemA": 25}, deadline=55, priority=3)},
        {"time": 60, "type": "route_block", "from": "W1", "to": "W2"},
        {"time": 75, "type": "new_truck", "truck": Truck(id="T4", capacity=50, current_load=0, location="W4")},
    ]
)
