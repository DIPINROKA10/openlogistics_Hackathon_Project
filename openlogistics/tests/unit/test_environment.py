"""
Unit tests for OpenLogistics environment.
"""
import pytest
from app.environment.core import OpenLogisticsEnv
from app.models.models import Action, SingleAction, ActionType


def test_easy_delivery_reset():
    """Test resetting easy delivery task."""
    env = OpenLogisticsEnv()
    state = env.reset("easy_delivery")
    
    assert state is not None
    assert state.time == 0
    assert len(state.warehouses) == 2
    assert len(state.trucks) == 1
    assert len(state.orders) == 1


def test_state_returns_current_state():
    """Test state() method returns current state."""
    env = OpenLogisticsEnv()
    env.reset("easy_delivery")
    
    state = env.state()
    
    assert state is not None
    assert state.time == 0


def test_load_action():
    """Test loading items onto truck."""
    env = OpenLogisticsEnv()
    env.reset("easy_delivery")
    
    action = Action(actions=[
        SingleAction(type=ActionType.LOAD, truck_id="T1", target="W1", items={"itemA": 30})
    ])
    
    result = env.step(action)
    
    assert result is not None
    assert len(result.next_state.trucks) == 1
    truck = result.next_state.trucks[0]
    assert truck.current_load == 30
    assert truck.load_contents.get("itemA", 0) == 30


def test_move_action():
    """Test moving truck."""
    env = OpenLogisticsEnv()
    env.reset("easy_delivery")
    
    load_action = Action(actions=[
        SingleAction(type=ActionType.LOAD, truck_id="T1", target="W1", items={"itemA": 30})
    ])
    env.step(load_action)
    
    move_action = Action(actions=[
        SingleAction(type=ActionType.MOVE, truck_id="T1", target="W2")
    ])
    result = env.step(move_action)
    
    assert result is not None
    truck = result.next_state.trucks[0]
    assert truck.target_location == "W2"


def test_invalid_truck_action():
    """Test action with invalid truck ID."""
    env = OpenLogisticsEnv()
    env.reset("easy_delivery")
    
    action = Action(actions=[
        SingleAction(type=ActionType.LOAD, truck_id="INVALID", target="W1", items={"itemA": 30})
    ])
    
    result = env.step(action)
    
    assert result.info.invalid_actions == 1
    assert result.reward == pytest.approx(-0.1)


def test_invalid_warehouse_action():
    """Test action with invalid warehouse ID."""
    env = OpenLogisticsEnv()
    env.reset("easy_delivery")
    
    action = Action(actions=[
        SingleAction(type=ActionType.LOAD, truck_id="T1", target="INVALID", items={"itemA": 30})
    ])
    
    result = env.step(action)
    
    assert result.info.invalid_actions == 1
    assert result.reward == pytest.approx(-0.1)


def test_wait_action():
    """Test wait action."""
    env = OpenLogisticsEnv()
    env.reset("easy_delivery")
    
    action = Action(actions=[
        SingleAction(type=ActionType.WAIT, truck_id="T1")
    ])
    
    result = env.step(action)
    
    assert result.reward == 0.0
    assert result.next_state.time == 1


def test_grading_easy_delivery():
    """Test grading for easy delivery task."""
    env = OpenLogisticsEnv()
    env.reset("easy_delivery")
    
    env.step(Action(actions=[
        SingleAction(type=ActionType.LOAD, truck_id="T1", target="W1", items={"itemA": 30})
    ]))
    
    for _ in range(10):
        env.step(Action(actions=[
            SingleAction(type=ActionType.MOVE, truck_id="T1", target="W2")
        ]))
    
    result = env.step(Action(actions=[
        SingleAction(type=ActionType.DELIVER, truck_id="T1", order_id="O1")
    ]))
    
    assert result.done == True
    
    grade = env.grade()
    assert grade["score"] >= 0.9


def test_max_steps_limit():
    """Test that episode ends at max steps."""
    env = OpenLogisticsEnv()
    env.reset("easy_delivery")
    
    for _ in range(25):
        result = env.step(Action(actions=[
            SingleAction(type=ActionType.WAIT, truck_id="T1")
        ]))
    
    assert result.done == True


def test_medium_task_configuration():
    """Test medium optimization task configuration."""
    env = OpenLogisticsEnv()
    state = env.reset("medium_optimization")
    
    assert len(state.warehouses) == 3
    assert len(state.trucks) == 2
    assert len(state.orders) == 5
    assert len(state.routes) == 3


def test_hard_task_configuration():
    """Test hard crisis task configuration."""
    env = OpenLogisticsEnv()
    state = env.reset("hard_crisis")
    
    assert len(state.warehouses) == 4
    assert len(state.trucks) == 3
    assert len(state.orders) == 10
    assert len(state.routes) == 6


def test_unknown_task_raises_error():
    """Test that unknown task raises ValueError."""
    env = OpenLogisticsEnv()
    
    with pytest.raises(ValueError):
        env.reset("unknown_task")
