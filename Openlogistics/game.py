"""
OpenLogistics Console Game Interface
Interactive command-line interface for playing the game.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.environment.core import OpenLogisticsEnv
from app.models.models import Action, SingleAction, ActionType


class ConsoleGame:
    """Interactive console game interface."""
    
    def __init__(self, task_id: str = "easy_delivery"):
        self.env = OpenLogisticsEnv()
        self.task_id = task_id
        self.running = True
    
    def print_header(self):
        """Print game header."""
        print("\n" + "=" * 60)
        print("   🚚  OpenLogistics - AI Supply Chain Game  🚚")
        print("=" * 60)
    
    def print_help(self):
        """Print help message."""
        print("\n📋 COMMANDS:")
        print("  help, ?       - Show this help")
        print("  status, s    - Show current state")
        print("  warehouses   - Show warehouses")
        print("  trucks, t    - Show trucks")
        print("  orders, o    - Show pending orders")
        print("  routes       - Show routes")
        print("  load <truck> <wh> <item> <qty>  - Load items")
        print("  move <truck> <dest>            - Move truck")
        print("  deliver <truck> <order>        - Deliver order")
        print("  wait <truck>                   - Wait (no action)")
        print("  grade, g    - Show current score")
        print("  reset       - Reset environment")
        print("  quit, q     - Quit game")
    
    def print_state(self):
        """Print current state summary."""
        state = self.env.state()
        print(f"\n⏰ Time: {state.time} / {self.env.task_config.max_steps}")
        print(f"📦 Orders: {len([o for o in state.orders if o.status == 'pending'])} pending")
        print(f"🚛 Trucks: {len(state.trucks)} total")
        print(f"💰 Cost: ${state.total_cost:.2f}")
    
    def print_warehouses(self):
        """Print warehouse information."""
        state = self.env.state()
        print("\n🏭 WAREHOUSES:")
        for wh in state.warehouses:
            inv = ", ".join([f"{k}: {v}" for k, v in wh.inventory.items()])
            print(f"  {wh.id} at {wh.position}: [{inv}]")
    
    def print_trucks(self):
        """Print truck information."""
        state = self.env.state()
        print("\n🚛 TRUCKS:")
        for truck in state.trucks:
            load = ", ".join([f"{k}: {v}" for k, v in truck.load_contents.items()]) or "empty"
            status = f"→{truck.target_location}" if truck.target_location else f"@{truck.location}"
            steps = f" ({truck.steps_to_destination} steps)" if truck.steps_to_destination > 0 else ""
            print(f"  {truck.id} {status}{steps}, Load: {load} ({truck.current_load}/{truck.capacity})")
    
    def print_orders(self):
        """Print order information."""
        state = self.env.state()
        print("\n📋 PENDING ORDERS:")
        pending = [o for o in state.orders if o.status == "pending"]
        if not pending:
            print("  No pending orders")
        for order in pending:
            items = ", ".join([f"{k}: {v}" for k, v in order.items.items()])
            print(f"  {order.id}: {order.source} → {order.destination}, [{items}], Deadline: {order.deadline}")
    
    def print_routes(self):
        """Print route information."""
        state = self.env.state()
        print("\n🛤️ ROUTES:")
        for route in state.routes:
            status = "✅" if route.status.value == "active" else "❌"
            print(f"  {route.from_warehouse} ↔ {route.to_warehouse}: {route.distance} {status}")
    
    def print_score(self):
        """Print current grade/score."""
        grade = self.env.grade()
        print("\n📊 CURRENT SCORE:")
        print(f"  Score: {grade['score']:.4f}")
        print(f"  Delivery Rate: {grade['delivery_rate']:.2%}")
        print(f"  Cost Efficiency: {grade['cost_efficiency']:.2%}")
        print(f"  Completed: {grade['completed_orders']}/{grade['total_orders']} orders")
        print(f"  Delivered: {grade['total_delivered']}/{grade['total_items']} items")
    
    def execute_action(self, command: str) -> bool:
        """Execute a game command."""
        parts = command.lower().split()
        if not parts:
            return False
        
        cmd = parts[0]
        
        try:
            if cmd in ("load", "l"):
                truck_id = parts[1].upper() if len(parts) > 1 else None
                warehouse = parts[2].upper() if len(parts) > 2 else None
                item = parts[3] if len(parts) > 3 else "itemA"
                qty = int(parts[4]) if len(parts) > 4 else 1
                
                if not truck_id or not warehouse:
                    print("❌ Usage: load <truck> <warehouse> <item> <qty>")
                    return False
                
                action = Action(actions=[
                    SingleAction(type=ActionType.LOAD, truck_id=truck_id, target=warehouse, items={item: qty})
                ])
                result = self.env.step(action)
                print(f"✅ Loaded {qty} {item} onto {truck_id} from {warehouse}")
                print(f"   Reward: {result.reward:.3f}")
                if result.info.invalid_actions > 0:
                    print(f"   ⚠️ {result.info.invalid_actions} invalid action(s)")
                return True
            
            elif cmd in ("move", "m"):
                truck_id = parts[1].upper() if len(parts) > 1 else None
                dest = parts[2].upper() if len(parts) > 2 else None
                
                if not truck_id or not dest:
                    print("❌ Usage: move <truck> <destination>")
                    return False
                
                action = Action(actions=[
                    SingleAction(type=ActionType.MOVE, truck_id=truck_id, target=dest)
                ])
                result = self.env.step(action)
                print(f"✅ {truck_id} moving to {dest}")
                print(f"   Reward: {result.reward:.3f}, Cost: ${result.info.cost:.2f}")
                if result.info.invalid_actions > 0:
                    print(f"   ⚠️ {result.info.invalid_actions} invalid action(s)")
                return True
            
            elif cmd in ("deliver", "d"):
                truck_id = parts[1].upper() if len(parts) > 1 else None
                order_id = parts[2].upper() if len(parts) > 2 else None
                
                if not truck_id or not order_id:
                    print("❌ Usage: deliver <truck> <order>")
                    return False
                
                action = Action(actions=[
                    SingleAction(type=ActionType.DELIVER, truck_id=truck_id, order_id=order_id)
                ])
                result = self.env.step(action)
                if result.info.delivered > 0:
                    print(f"✅ Delivered {result.info.delivered} items for {order_id}")
                else:
                    print(f"❌ Could not deliver {order_id}")
                print(f"   Reward: {result.reward:.3f}")
                return True
            
            elif cmd in ("wait", "w"):
                truck_id = parts[1].upper() if len(parts) > 1 else "T1"
                
                action = Action(actions=[
                    SingleAction(type=ActionType.WAIT, truck_id=truck_id)
                ])
                result = self.env.step(action)
                print(f"⏰ {truck_id} waiting... Time: {result.next_state.time}")
                return True
            
            elif cmd in ("status", "s"):
                self.print_state()
                return False
            
            elif cmd == "warehouses":
                self.print_warehouses()
                return False
            
            elif cmd in ("trucks", "t"):
                self.print_trucks()
                return False
            
            elif cmd in ("orders", "o"):
                self.print_orders()
                return False
            
            elif cmd == "routes":
                self.print_routes()
                return False
            
            elif cmd in ("grade", "g"):
                self.print_score()
                return False
            
            elif cmd in ("help", "?"):
                self.print_help()
                return False
            
            elif cmd == "reset":
                self.env.reset(self.task_id)
                print("✅ Environment reset!")
                return True
            
            elif cmd in ("quit", "q", "exit"):
                self.running = False
                print("👋 Thanks for playing!")
                return True
            
            else:
                print(f"❌ Unknown command: {cmd}")
                print("   Type 'help' for available commands")
                return False
        
        except (ValueError, IndexError) as e:
            print(f"❌ Error: {e}")
            return False
    
    def run(self):
        """Run the game loop."""
        self.print_header()
        print(f"\n🎮 Starting task: {self.task_id}")
        print("   Type 'help' for commands\n")
        
        self.env.reset(self.task_id)
        self.print_state()
        
        while self.running:
            try:
                command = input("\n> ").strip()
                if command:
                    step_taken = self.execute_action(command)
                    
                    if self.env._done:
                        print("\n" + "=" * 60)
                        print("🎉 EPISODE COMPLETE!")
                        print("=" * 60)
                        self.print_score()
                        print("\nType 'reset' to play again or 'quit' to exit")
                        self.env.reset(self.task_id)
            
            except KeyboardInterrupt:
                print("\n\n👋 Game interrupted. Thanks for playing!")
                break
            except EOFError:
                break


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="OpenLogistics Console Game")
    parser.add_argument("--task", "-t", default="easy_delivery",
                       choices=["easy_delivery", "medium_optimization", "hard_crisis"],
                       help="Task to play")
    
    args = parser.parse_args()
    game = ConsoleGame(task_id=args.task)
    game.run()


if __name__ == "__main__":
    main()
