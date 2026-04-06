"""
OpenLogistics Inference Script
LLM-powered agent for logistics optimization.

Requirements:
- API_BASE_URL: API endpoint for LLM
- MODEL_NAME: Model identifier to use
- HF_TOKEN: Hugging Face API key
- OPENAI_API_KEY: OpenAI API key
"""
import os
import sys
import json
import asyncio
from typing import Dict, List, Optional

# Environment variables
API_BASE_URL = os.getenv("API_BASE_URL", "https://api.openai.com/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4")
HF_TOKEN = os.getenv("HF_TOKEN", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

from app.environment.core import OpenLogisticsEnv
from app.models.models import Action, SingleAction, ActionType


# Logging functions
def log_start(task: str, env: str, model: str) -> None:
    """Log start of episode."""
    print(f"[START] task={task} model={model} benchmark={env}", flush=True)


def log_step(step: int, action: str, reward: float, done: bool, error: Optional[str] = None) -> None:
    """Log each step."""
    print(f"[STEP] step={step} action={action} reward={reward:.4f} done={done} error={error}", flush=True)


def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    """Log end of episode."""
    print(f"[END] success={success} steps={steps} score={score:.4f} rewards={rewards}", flush=True)


class LogisticsAgent:
    """LLM-powered logistics agent."""
    
    def __init__(self, client=None):
        self.client = client
    
    def build_prompt(self, state, task_description: str, task_id: str) -> str:
        """Build prompt for LLM agent."""
        
        warehouses_info = []
        for wh in state.warehouses:
            inv = ", ".join([f"{k}: {v}" for k, v in wh.inventory.items()])
            warehouses_info.append(f"  {wh.id} ({wh.position}): [{inv}]")
        
        trucks_info = []
        for truck in state.trucks:
            load = ", ".join([f"{k}: {v}" for k, v in truck.load_contents.items()]) or "empty"
            trucks_info.append(
                f"  {truck.id} @ {truck.location}, Capacity: {truck.capacity}, "
                f"Load: {load}, Steps to dest: {truck.steps_to_destination}"
            )
        
        orders_info = []
        for order in state.orders:
            if order.status == "pending":
                items = ", ".join([f"{k}: {v}" for k, v in order.items.items()])
                orders_info.append(
                    f"  {order.id}: {order.source} -> {order.destination}, "
                    f"Items: [{items}], Deadline: {order.deadline}, Status: {order.status}"
                )
        
        routes_info = []
        for route in state.routes:
            status = "ACTIVE" if route.status.value == "active" else "BLOCKED"
            routes_info.append(f"  {route.from_warehouse} <-> {route.to_warehouse}: {route.distance} ({status})")
        
        prompt = f"""You are an AI logistics manager controlling a delivery fleet.

TASK: {task_description}
Task ID: {task_id}
Current Time: {state.time}

=== WAREHOUSES ===
{chr(10).join(warehouses_info)}

=== TRUCKS ===
{chr(10).join(trucks_info)}

=== ACTIVE ORDERS (pending) ===
{chr(10).join(orders_info) if orders_info else "  No pending orders"}

=== ROUTES ===
{chr(10).join(routes_info)}

=== AVAILABLE ACTIONS ===
1. load: Load items from warehouse to truck
   {{"type": "load", "truck_id": "T1", "target": "W1", "items": {{"itemA": 30}}}}
2. unload: Unload items from truck to warehouse
   {{"type": "unload", "truck_id": "T1", "target": "W1", "items": {{"itemA": 10}}}}
3. move: Move truck towards target warehouse (one step per action)
   {{"type": "move", "truck_id": "T1", "target": "W2"}}
4. deliver: Deliver items to fulfill an order (must be at destination)
   {{"type": "deliver", "truck_id": "T1", "order_id": "O1"}}
5. wait: Skip this step (no action)
   {{"type": "wait", "truck_id": "T1"}}

=== OUTPUT FORMAT ===
Return a JSON object with your action(s):
{{"actions": [...], "reasoning": "brief explanation of your strategy"}}

You can perform multiple actions in one step if they don't conflict.
"""
        return prompt
    
    async def decide_actions(self, state, task_id: str, task_description: str) -> Action:
        """Decide actions based on current state."""
        
        if not self.client:
            return self._rule_based_action(state)
        
        prompt = self.build_prompt(state, task_description, task_id)
        
        try:
            response = self.client.chat.completions.create(
                model=MODEL_NAME,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=500
            )
            
            content = response.choices[0].message.content.strip()
            
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            
            parsed = json.loads(content.strip())
            actions = [SingleAction(**a) for a in parsed.get("actions", [])]
            reasoning = parsed.get("reasoning", "")
            
            return Action(actions=actions, reasoning=reasoning)
            
        except Exception as e:
            print(f"[DEBUG] Model request failed: {e}", flush=True)
            return self._rule_based_action(state)
    
    def _rule_based_action(self, state) -> Action:
        """Simple rule-based fallback agent."""
        actions = []
        
        pending_orders = [o for o in state.orders if o.status == "pending"]
        
        if not pending_orders:
            return Action(actions=[], reasoning="No pending orders")
        
        order = pending_orders[0]
        
        # Find truck to use
        for truck in state.trucks:
            # If at destination and has load -> deliver
            if truck.location == order.destination and truck.current_load > 0:
                actions.append(SingleAction(
                    type=ActionType.DELIVER,
                    truck_id=truck.id,
                    order_id=order.id
                ))
                return Action(actions=actions, reasoning="Rule-based: delivering order")
            
            # If at source and empty -> load
            if truck.location == order.source and truck.current_load == 0:
                items_needed = order.items
                capacity = truck.capacity
                
                actions.append(SingleAction(
                    type=ActionType.LOAD,
                    truck_id=truck.id,
                    target=order.source,
                    items={k: min(v, capacity) for k, v in items_needed.items()}
                ))
                break
            
            # If has load and not at destination -> move
            if truck.location != order.destination and truck.current_load > 0:
                if truck.steps_to_destination == 0:
                    actions.append(SingleAction(
                        type=ActionType.MOVE,
                        truck_id=truck.id,
                        target=order.destination
                    ))
                    break
        
        return Action(actions=actions, reasoning="Rule-based: processing order")


def get_action_string(actions: List[SingleAction]) -> str:
    """Convert actions to string for logging."""
    if not actions:
        return "no_action"
    return "; ".join([f"{a.type.value}({a.truck_id},{a.target or a.order_id})" for a in actions])


async def main() -> None:
    """Main inference function."""
    
    task_name = sys.argv[1] if len(sys.argv) > 1 else "easy_delivery"
    max_steps = int(sys.argv[2]) if len(sys.argv) > 2 else 100
    
    client = None
    if OPENAI_AVAILABLE and OPENAI_API_KEY:
        client = OpenAI(base_url=API_BASE_URL, api_key=OPENAI_API_KEY)
    
    agent = LogisticsAgent(client)
    env = OpenLogisticsEnv()
    
    task_descriptions = {
        "easy_delivery": "Deliver items from W1 to W2 before deadline.",
        "medium_optimization": "Optimize multiple deliveries efficiently.",
        "hard_crisis": "Handle disruptions and prioritize urgent orders."
    }
    
    history: List[str] = []
    rewards: List[float] = []
    steps_taken = 0
    score = 0.0
    success = False
    
    log_start(task=task_name, env="openlogistics", model=MODEL_NAME)
    
    try:
        result = env.reset(task_name)
        state = result
        
        for step in range(1, max_steps + 1):
            if env._done:
                break
            
            actions = await agent.decide_actions(state, task_name, task_descriptions.get(task_name, ""))
            action_str = get_action_string(actions.actions)
            
            result = env.step(actions)
            reward = result.reward or 0.0
            done = result.done
            
            rewards.append(reward)
            steps_taken = step
            state = result.next_state
            
            log_step(step=step, action=action_str, reward=reward, done=done, error=None)
            
            history.append(f"Step {step}: {action_str} -> reward {reward:+.2f}")
            
            if done:
                break
        
        grade_result = env.grade()
        score = grade_result["score"]
        success = score >= 0.7
        
    finally:
        try:
            pass
        except Exception as e:
            print(f"[DEBUG] env.close() error (container cleanup): {e}", flush=True)
        
        log_end(success=success, steps=steps_taken, score=score, rewards=rewards)


if __name__ == "__main__":
    asyncio.run(main())
