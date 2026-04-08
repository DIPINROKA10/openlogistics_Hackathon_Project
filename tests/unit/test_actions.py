import pytest
from app.models.models import ActionType, SingleAction, StepInfo, Action
from app.environment.core import OpenLogisticsEnv
from app.environment.actions import ActionManager
from app.environment.grader import GradeManager

def test_invalid_load():
    env = OpenLogisticsEnv()
    env.reset("easy_delivery")
    # T1 is at W1. Try to load from W2 (should fail)
    action = SingleAction(type=ActionType.LOAD, truck_id="T1", target="W2", items={"itemA": 10})
    info = StepInfo()
    res = ActionManager.execute_action(env.get_state(), action, info)
    assert info.invalid_actions == 1
    assert res == -0.1

def test_route_block():
    env = OpenLogisticsEnv()
    env.reset("hard_crisis")
    # W1 to W3 is blocked initially.
    action = SingleAction(type=ActionType.MOVE, truck_id="T1", target="W3")
    info = StepInfo()
    state = env.get_state()
    res = ActionManager.execute_action(state, action, info)
    assert info.invalid_actions == 1
    assert state.metrics.routes_replanned == 1

def test_valid_load_and_deliver():
    env = OpenLogisticsEnv()
    env.reset("easy_delivery")
    info = StepInfo()
    state = env._current_state
    
    # Load
    ActionManager.execute_action(state, SingleAction(type=ActionType.LOAD, truck_id="T1", target="W1", items={"itemA": 30}), info)
    assert state.trucks[0].current_load == 30
    
    # Move
    for _ in range(15):
        ActionManager.execute_action(state, SingleAction(type=ActionType.MOVE, truck_id="T1", target="W2"), info)
    
    assert state.trucks[0].location == "W2"
    
    # Deliver
    ActionManager.execute_action(state, SingleAction(type=ActionType.DELIVER, truck_id="T1", order_id="O1"), info)
    
    # Check Grade
    grade = GradeManager.calculate_grade(state, env.task_config)
    assert grade["score"] == 1.0

def test_dynamic_events_coverage():
    env = OpenLogisticsEnv()
    env.reset("hard_crisis")
    # Loop over steps to hit dynamic events and deadlines
    for _ in range(100):
        env.step(Action(actions=[SingleAction(type=ActionType.WAIT, truck_id="T1")]))
    state = env.state()
    assert len(state.metrics.disruptions) > 0
    assert len(state.metrics.failed_deliveries) > 0

def test_other_actions():
    env = OpenLogisticsEnv()
    env.reset("easy_delivery")
    state = env._current_state
    info = StepInfo()
    ActionManager.execute_action(state, SingleAction(type=ActionType.LOAD, truck_id="T1", target="W1", items={"itemA": 30}), info)
    ActionManager.execute_action(state, SingleAction(type=ActionType.UNLOAD, truck_id="T1", target="W1"), info)
    assert state.trucks[0].current_load == 0
    
    # deliver to warehouse
    ActionManager.execute_action(state, SingleAction(type=ActionType.LOAD, truck_id="T1", target="W1", items={"itemA": 30}), info)
    ActionManager.execute_action(state, SingleAction(type=ActionType.DELIVER, truck_id="T1", target="W1"), info)
    assert state.trucks[0].current_load == 0
    
    # adjust load to capacity
    ActionManager.execute_action(state, SingleAction(type=ActionType.LOAD, truck_id="T1", target="W1", items={"itemA": 100}), info)
    assert state.trucks[0].current_load <= state.trucks[0].capacity
