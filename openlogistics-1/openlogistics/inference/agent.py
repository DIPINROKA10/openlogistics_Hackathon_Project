"""
OpenLogistics Inference Script
LLM-powered agent for logistics optimization.
"""
import os
import json
import asyncio
from typing import Dict, List, Optional
from dataclasses import dataclass

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

from app.environment.core import OpenLogisticsEnv
from app.models.models import Action, SingleAction, ActionType


@dataclass
class InferenceConfig:
    api_key: Optional[str] = None
    model: str = "gpt-4"
    temperature: float = 0.7
    max_tokens: int = 500


class LogisticsAgent:
    """LLM-powered logistics agent."""
    
    def __init__(self, config: InferenceConfig):
        self.config = config
        self.client = None
        
        if OPENAI_AVAILABLE and config.api_key:
            self.client = OpenAI(api_key=config.api_key)
    
    def build_prompt(self, state: Dict, task_description: str, task_id: str) -> str:
        """Build prompt for LLM agent."""
        
        warehouses_info = []
        for wh in state.get("warehouses", []):
            inv = ", ".join([f"{k}: {v}" for k, v in wh.get("inventory", {}).items()])
            warehouses_info.append(f"  {wh['id']} ({wh['position']}): [{inv}]")
        
        trucks_info = []
        for truck in state.get("trucks", []):
            load = ", ".join([f"{k}: {v}" for k, v in truck.get("load_contents", {}).items()]) or "empty"
            trucks_info.append(
                f"  {truck['id']} @ {truck['location']}, Capacity: {truck['capacity']}, "
                f"Load: {load}, Steps to dest: {truck.get('steps_to_destination', 0)}"
            )
        
        orders_info = []
        for order in state.get("orders", []):
            if order.get("status") == "pending":
                items = ", ".join([f"{k}: {v}" for k, v in order.get("items", {}).items()])
                orders_info.append(
                    f"  {order['id']}: {order['source']} -> {order['destination']}, "
                    f"Items: [{items}], Deadline: {order['deadline']}, Status: {order.get('status', 'pending')}"
                )
        
        routes_info = []
        for route in state.get("routes", []):
            status = "ACTIVE" if route.get("status") == "active" else "BLOCKED"
            routes_info.append(f"  {route['from_warehouse']} <-> {route['to_warehouse']}: {route['distance']} ({status})")
        
        prompt = f"""You are an AI logistics manager controlling a delivery fleet.

TASK: {task_description}
Task ID: {task_id}
Current Time: {state.get('time_step', 0)}

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
    
    async def decide_actions(self, state: Dict, task_id: str, task_description: str) -> Action:
        """Decide actions based on current state."""
        
        if not self.client:
            return self._rule_based_action(state)
        
        prompt = self.build_prompt(state, task_description, task_id)
        
        try:
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens
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
            print(f"LLM error: {e}, falling back to rule-based")
            return self._rule_based_action(state)
    
    def _rule_based_action(self, state: Dict) -> Action:
        """Simple rule-based fallback agent."""
        actions = []
        
        pending_orders = [o for o in state.get("orders", []) if o.get("status") == "pending"]
        
        if not pending_orders:
            return Action(actions=[], reasoning="No pending orders")
        
        order = pending_orders[0]
        
        trucks = state.get("trucks", [])
        for truck in trucks:
            if truck.get("location") == order["source"] and truck.get("current_load", 0) == 0:
                items_needed = order.get("items", {})
                total = sum(items_needed.values())
                capacity = truck.get("capacity", 50)
                
                load_qty = min(total, capacity)
                
                if load_qty > 0:
                    actions.append(SingleAction(
                        type=ActionType.LOAD,
                        truck_id=truck["id"],
                        target=order["source"],
                        items={k: min(v, capacity) for k, v in items_needed.items()}
                    ))
                    break
        
        for truck in trucks:
            if truck.get("location") == order["source"] and truck.get("current_load", 0) > 0:
                if truck.get("steps_to_destination", 0) == 0:
                    actions.append(SingleAction(
                        type=ActionType.MOVE,
                        truck_id=truck["id"],
                        target=order["destination"]
                    ))
                break
        
        return Action(actions=actions, reasoning="Rule-based: moving towards order destination")


async def run_inference(
    task_id: str = "easy_delivery",
    max_steps: Optional[int] = None,
    api_key: Optional[str] = None
):
    """Run inference on a task."""
    
    config = InferenceConfig(api_key=api_key or os.getenv("OPENAI_API_KEY"))
    agent = LogisticsAgent(config)
    env = OpenLogisticsEnv()
    
    task_descriptions = {
        "easy_delivery": "Deliver items from W1 to W2 before deadline.",
        "medium_optimization": "Optimize multiple deliveries efficiently.",
        "hard_crisis": "Handle disruptions and prioritize urgent orders."
    }
    
    print(f"Starting task: {task_id}")
    print("=" * 50)
    
    state = env.reset(task_id)
    print(f"Initial state: Time {state.time_step}")
    
    max_steps = max_steps or env.task_config.max_steps
    
    for step in range(max_steps):
        if env._done:
            print(f"Episode complete at step {step}")
            break
        
        print(f"\nStep {step}:")
        print(f"  Time: {state.time_step}")
        
        actions = await agent.decide_actions(state.model_dump(), task_id, task_descriptions.get(task_id, ""))
        
        if actions.reasoning:
            print(f"  Reasoning: {actions.reasoning}")
        
        if actions.actions:
            for a in actions.actions:
                print(f"  Action: {a.type.value} - Truck: {a.truck_id}, Target: {a.target or a.order_id}")
        else:
            print("  Action: No actions")
        
        result = env.step(actions)
        
        print(f"  Reward: {result.reward:.3f}")
        print(f"  Delivered: {result.info.delivered}")
        
        if result.info.cost > 0:
            print(f"  Cost: {result.info.cost:.2f}")
        
        if result.info.invalid_actions > 0:
            print(f"  Invalid Actions: {result.info.invalid_actions}")
        
        state = result.state
        
        if result.done:
            print("\n" + "=" * 50)
            print("EPISODE COMPLETE")
            print("=" * 50)
            break
    
    final_score = env.grade()
    print("\n" + "=" * 50)
    print("FINAL RESULTS")
    print("=" * 50)
    print(f"Score: {final_score['score']:.4f}")
    print(f"Delivery Rate: {final_score.get('delivery_rate', 0):.2f}")
    print(f"Cost Efficiency: {final_score.get('cost_efficiency', 0):.2f}")
    print(f"Time Efficiency: {final_score.get('time_efficiency', 0):.2f}")
    print(f"SLA Success: {final_score.get('sla_success', 0):.2f}")
    
    return final_score


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="OpenLogistics Inference")
    parser.add_argument("--task", "-t", default="easy_delivery", 
                       choices=["easy_delivery", "medium_optimization", "hard_crisis"],
                       help="Task ID to run")
    parser.add_argument("--max-steps", "-m", type=int, default=None,
                       help="Maximum steps to run")
    parser.add_argument("--api-key", "-k", type=str, default=None,
                       help="OpenAI API key")
    
    args = parser.parse_args()
    
    asyncio.run(run_inference(
        task_id=args.task,
        max_steps=args.max_steps,
        api_key=args.api_key
    ))


if __name__ == "__main__":
    main()
