import gradio as gr
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.environment.core import OpenLogisticsEnv
from app.models.models import Action, SingleAction, ActionType

_env = None

def get_env():
    global _env
    if _env is None:
        _env = OpenLogisticsEnv()
    return _env

def predict(inputs: dict) -> dict:
    """
    Required predict function for HF Spaces validator.
    """
    env = get_env()
    task_id = inputs.get("task_id", "easy_delivery")
    actions_data = inputs.get("actions", [])
    
    if inputs.get("reset", False) or _env is None:
        env = get_env()
        state = env.reset(task_id)
        return {"state": state.model_dump(), "reward": 0, "done": False}
    
    actions = []
    for a in actions_data:
        actions.append(SingleAction(
            type=ActionType(a.get("type", "wait").lower()),
            truck_id=a.get("truck_id", "T1"),
            target=a.get("target"),
            items=a.get("items"),
            order_id=a.get("order_id")
        ))
    
    action = Action(actions=actions, reasoning="")
    result = env.step(action)
    
    return {
        "state": result.state.model_dump() if hasattr(result.state, 'model_dump') else {},
        "reward": result.reward,
        "done": result.done,
        "info": result.info.__dict__ if hasattr(result.info, '__dict__') else {}
    }

def reset_environment(task_id: str = "easy_delivery"):
    """Reset the environment and return initial state."""
    env = get_env()
    state = env.reset(task_id)
    return format_state(state)

def format_state(state):
    """Format state for display."""
    if hasattr(state, 'model_dump'):
        state_dict = state.model_dump()
    else:
        state_dict = {}
    
    output = f"Time Step: {state_dict.get('time_step', 0)}\n"
    output += f"Done: {state_dict.get('done', False)}\n\n"
    
    output += "=== Warehouses ===\n"
    for wh in state_dict.get('warehouses', []):
        output += f"  {wh.get('id')}: {wh.get('position')} - {wh.get('inventory')}\n"
    
    output += "\n=== Trucks ===\n"
    for truck in state_dict.get('trucks', []):
        output += f"  {truck.get('id')} @ {truck.get('location')} - Load: {truck.get('load_contents')}\n"
    
    output += "\n=== Orders ===\n"
    for order in state_dict.get('orders', []):
        status = order.get('status', 'pending')
        output += f"  {order.get('id')}: {order.get('source')} -> {order.get('destination')} [{status}]\n"
    
    return output

def step_game(task_id: str, action_type: str, truck_id: str, target: str, items: str):
    """Execute a single step in the environment."""
    env = get_env()
    
    if not hasattr(env, '_current_state') or env._current_state is None:
        env.reset(task_id)
    
    action_items = []
    if action_type and truck_id:
        action_items.append({
            "type": action_type.lower(),
            "truck_id": truck_id,
            "target": target if target else None
        })
    
    result = predict({
        "task_id": task_id,
        "actions": action_items
    })
    
    return format_state(result.get("state", {})), f"Reward: {result.get('reward', 0):.3f}"

with gr.Blocks(title="OpenLogistics") as demo:
    gr.Markdown("# OpenLogistics\nAI Supply Chain Optimization Environment")
    gr.Markdown("Control trucks to deliver goods from warehouses to customers.")
    
    with gr.Tab("Play"):
        with gr.Row():
            with gr.Column():
                task_dropdown = gr.Dropdown(
                    ["easy_delivery", "medium_optimization", "hard_crisis"],
                    value="easy_delivery",
                    label="Task"
                )
                reset_btn = gr.Button("Reset Environment")
            
            with gr.Column():
                state_display = gr.Textbox(label="Current State", lines=15)
                reward_display = gr.Textbox(label="Reward", lines=2)
        
        with gr.Row():
            action_type = gr.Dropdown(
                ["load", "unload", "move", "deliver", "wait"],
                value="move",
                label="Action Type"
            )
            truck_id = gr.Dropdown(
                ["T1", "T2", "T3"],
                value="T1",
                label="Truck"
            )
            target = gr.Textbox(label="Target (Warehouse/Order ID)", placeholder="e.g., W2 or O1")
        
        step_btn = gr.Button("Execute Action")
        step_btn.click(
            step_game,
            inputs=[task_dropdown, action_type, truck_id, target],
            outputs=[state_display, reward_display]
        )
        
        reset_btn.click(
            reset_environment,
            inputs=[task_dropdown],
            outputs=[state_display]
        )
    
    with gr.Tab("API"):
        gr.Markdown("""
        ## API Endpoints
        
        - `POST /predict` - Main inference endpoint
        - `GET /` - Root
        - `GET /health` - Health check
        
        ### predict() Request Format:
        ```json
        {
            "task_id": "easy_delivery",
            "reset": false,
            "actions": [
                {"type": "move", "truck_id": "T1", "target": "W2"}
            ]
        }
        ```
        """)

demo.launch(server_name="0.0.0.0", server_port=7860)
