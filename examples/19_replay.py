"""Example 19: Execution Replay and Time-Travel Debugging

Demonstrates how MCPRuntime logs execution state and allows for
"Time-Travel Debugging" - rewinding an agent session to a specific point
and taking a different path.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from mcpruntime import create_agent

def main():
    print("=" * 60)
    print("Example 19: Time-Travel Debugging")
    print("=" * 60)
    
    # 1. Create agent and run initial session
    agent = create_agent(replay_logging_enabled=True)
    print(f"Started new session: {agent.session_id}\n")
    
    print("--- Step 1: Create a variable ---")
    agent.execute_task("Create a variable `x = 10` and print it.", verbose=False)
    
    print("--- Step 2: Multiply it ---")
    agent.execute_task("Multiply `x` by 5 and print it.", verbose=False)
    
    print("--- Step 3: Add to it ---")
    agent.execute_task("Add 7 to `x` and print it.", verbose=False)
    
    original_session = agent.session_id
    
    # 2. Time-Travel!
    print("\n" + "=" * 60)
    print("TIME TRAVEL: Resuming from Step 2")
    print("=" * 60)
    
    # Create a fresh agent to prove state gets fully restored
    new_agent = create_agent(replay_logging_enabled=True)
    
    # Resume the original session up to step 2
    # This automatically executes the code from Step 1 and Step 2
    new_agent.resume_from(session_id=original_session, step=2)
    
    print("\n--- Step 3 (Alternate Timeline) ---")
    # In the original timeline we added 7. 
    # Here we take a different path: divide by 2!
    result, output, error = new_agent.execute_task(
        "Divide `x` by 2 and print it. (x should be 50 from step 2)", 
        verbose=False
    )
    
    print(f"Alternate Timeline Output: {str(output).strip() if output else ''}")

if __name__ == "__main__":
    main()
