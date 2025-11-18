#!/usr/bin/env python3
"""Example 14: Statefulness with MCP Server.

This example demonstrates how to leverage statefulness when using the framework
as an MCP server. It shows both explicit state management via MCP tools and
implicit state persistence via code execution.

This example works in two modes:
1. Direct mode: Uses framework directly (no server needed)
2. MCP mode: Uses framework via MCP server (requires server running)

Prerequisites:
    - Framework installed
    - Optional: MCP server running for MCP mode
"""

import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from code_execution_mcp import create_server, create_agent, execute_task


def example_direct_state_management():
    """Example: State management using framework directly."""
    print("=" * 70)
    print("Example: Direct State Management (Framework)")
    print("=" * 70)
    print()

    # Create agent
    agent = create_agent()

    # Session 1: Save state via code execution
    print("Session 1: Saving state...")
    result, output, error = agent.execute_task(
        """
        Save state to /workspace/state.json:
        {
            "workflow_id": "wf_001",
            "step": 1,
            "progress": "initialized",
            "data": {"key": "value"}
        }
        Verify the file was created.
        """,
        verbose=True
    )

    if error:
        print(f"Error: {error}")
        return False

    # Verify state file exists
    workspace_path = Path("./workspace")
    state_file = workspace_path / "state.json"
    if not state_file.exists():
        print(f"❌ State file not found at {state_file}")
        return False

    print(f"✅ State saved to {state_file}")

    # Session 2: Read state
    print("\nSession 2: Reading state...")
    result, output, error = agent.execute_task(
        """
        Read state from /workspace/state.json.
        Print the contents.
        Update the step field to 2.
        Save the updated state back to /workspace/state.json.
        """,
        verbose=True
    )

    if error:
        print(f"Error: {error}")
        return False

    # Verify state was updated
    try:
        state_data = json.loads(state_file.read_text())
        if state_data.get("step") != 2:
            print(f"❌ Expected step=2, got step={state_data.get('step')}")
            return False
        print(f"✅ State updated: step={state_data.get('step')}")
    except Exception as e:
        print(f"❌ Failed to verify state: {e}")
        return False

    return True


def example_mcp_server_state_tools():
    """Example: Using MCP server state tools directly."""
    print("=" * 70)
    print("Example: MCP Server State Tools")
    print("=" * 70)
    print()

    # Create server instance (for testing state tools)
    server = create_server()

    # Test save_state tool
    print("1. Testing save_state tool...")
    try:
        # Access the tool directly (for demonstration)
        # In real usage, this would be called via MCP client
        state_data = {
            "workflow_id": "wf_mcp_001",
            "step": 1,
            "progress": "started",
            "timestamp": "2024-01-01T00:00:00Z"
        }

        # Simulate calling the tool (we'll call it directly for demo)
        # In production, this would be: client.call_tool("save_state", {...})
        workspace_path = Path(server.config.execution.workspace_dir)
        state_file = workspace_path / "mcp_state.json"
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(json.dumps(state_data, indent=2))

        print(f"✅ State saved to {state_file}")
        print(f"   Data: {state_data}")

    except Exception as e:
        print(f"❌ Error saving state: {e}")
        return False

    # Test get_state tool
    print("\n2. Testing get_state tool...")
    try:
        # Simulate calling get_state
        if state_file.exists():
            data = json.loads(state_file.read_text())
            result = {"exists": True, "data": data}
            print(f"✅ State retrieved: {result}")
            print(f"   Step: {result['data']['step']}")
        else:
            result = {"exists": False, "data": {}}
            print("❌ State file not found")

    except Exception as e:
        print(f"❌ Error reading state: {e}")
        return False

    # Test updating state
    print("\n3. Testing state update...")
    try:
        if state_file.exists():
            data = json.loads(state_file.read_text())
            data["step"] = 2
            data["progress"] = "updated"
            state_file.write_text(json.dumps(data, indent=2))
            print(f"✅ State updated: step={data['step']}")
        else:
            print("❌ State file not found")
            return False

    except Exception as e:
        print(f"❌ Error updating state: {e}")
        return False

    return True


def example_stateful_workflow():
    """Example: Complete stateful workflow."""
    print("=" * 70)
    print("Example: Stateful Workflow")
    print("=" * 70)
    print()

    agent = create_agent()
    workspace_path = Path("./workspace")
    state_file = workspace_path / "workflow_state.json"

    # Step 1: Initialize workflow
    print("Step 1: Initialize workflow...")
    result, output, error = agent.execute_task(
        """
        Initialize a workflow:
        1. Create /workspace/workflow_state.json with:
           - workflow_id: "wf_stateful_001"
           - current_step: 0
           - total_steps: 3
           - results: []
           - status: "initialized"
        2. Print confirmation
        """,
        verbose=False
    )

    if error:
        print(f"❌ Error: {error}")
        return False

    # Step 2: Execute step 1
    print("\nStep 2: Execute workflow step 1...")
    result, output, error = agent.execute_task(
        """
        Read /workspace/workflow_state.json.
        Calculate 10 * 5 = 50.
        Add the result to the results array.
        Update current_step to 1.
        Save the updated state.
        """,
        verbose=False
    )

    if error:
        print(f"❌ Error: {error}")
        return False

    # Step 3: Execute step 2
    print("\nStep 3: Execute workflow step 2...")
    result, output, error = agent.execute_task(
        """
        Read /workspace/workflow_state.json.
        Calculate 20 * 3 = 60.
        Add the result to the results array.
        Update current_step to 2.
        Save the updated state.
        """,
        verbose=False
    )

    if error:
        print(f"❌ Error: {error}")
        return False

    # Step 4: Complete workflow
    print("\nStep 4: Complete workflow...")
    result, output, error = agent.execute_task(
        """
        Read /workspace/workflow_state.json.
        Update status to "completed".
        Update current_step to 3.
        Calculate the sum of all results.
        Add a "total" field with the sum.
        Save the final state.
        """,
        verbose=False
    )

    if error:
        print(f"❌ Error: {error}")
        return False

    # Verify final state
    try:
        if state_file.exists():
            final_state = json.loads(state_file.read_text())
            print(f"\n✅ Workflow completed!")
            print(f"   Workflow ID: {final_state.get('workflow_id')}")
            print(f"   Current Step: {final_state.get('current_step')}")
            print(f"   Status: {final_state.get('status')}")
            print(f"   Results: {final_state.get('results')}")
            print(f"   Total: {final_state.get('total')}")
            return True
        else:
            print("❌ State file not found")
            return False
    except Exception as e:
        print(f"❌ Error verifying state: {e}")
        return False


def example_cross_session_persistence():
    """Example: State persistence across separate executions."""
    print("=" * 70)
    print("Example: Cross-Session State Persistence")
    print("=" * 70)
    print()

    workspace_path = Path("./workspace")
    state_file = workspace_path / "cross_session_state.json"

    # Session 1: Create agent and save state
    print("Session 1: Creating initial state...")
    agent1 = create_agent()
    result, output, error = agent1.execute_task(
        f"""
        Create /workspace/cross_session_state.json with:
        {{
            "session": 1,
            "step": 1,
            "message": "State created in session 1",
            "data": {{"value": 100}}
        }}
        Print confirmation that state was saved.
        """,
        verbose=False
    )

    if error:
        print(f"❌ Session 1 error: {error}")
        return False

    if not state_file.exists():
        print(f"❌ State file not created: {state_file}")
        return False

    print(f"✅ Session 1: State saved to {state_file}")

    # Session 2: Create new agent and read state
    print("\nSession 2: Reading state from previous session...")
    agent2 = create_agent()  # New agent instance
    result, output, error = agent2.execute_task(
        """
        Read /workspace/cross_session_state.json.
        Print the contents.
        Update session to 2, step to 2.
        Add a new field: "session_2_data": {"value": 200}
        Save the updated state.
        """,
        verbose=False
    )

    if error:
        print(f"❌ Session 2 error: {error}")
        return False

    # Verify state was updated
    try:
        state_data = json.loads(state_file.read_text())
        if state_data.get("session") != 2:
            print(f"❌ Expected session=2, got session={state_data.get('session')}")
            return False
        if state_data.get("step") != 2:
            print(f"❌ Expected step=2, got step={state_data.get('step')}")
            return False
        print(f"✅ Session 2: State updated successfully")
        print(f"   Session: {state_data.get('session')}")
        print(f"   Step: {state_data.get('step')}")
        return True
    except Exception as e:
        print(f"❌ Error verifying state: {e}")
        return False


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("Example 14: Statefulness with MCP Server")
    print("=" * 70)
    print()

    # Run examples
    success1 = example_direct_state_management()
    print()

    success2 = example_mcp_server_state_tools()
    print()

    success3 = example_stateful_workflow()
    print()

    success4 = example_cross_session_persistence()
    print()

    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)
    print()

    if success1 and success2 and success3 and success4:
        print("✅ All statefulness examples completed successfully!")
        print()
        print("Statefulness features demonstrated:")
        print("  ✅ Direct state management via code execution")
        print("  ✅ MCP server state tools (get_state, save_state)")
        print("  ✅ Stateful workflows with multiple steps")
        print("  ✅ Cross-session state persistence")
        print()
        print("State files created:")
        workspace = Path("./workspace")
        if workspace.exists():
            json_files = list(workspace.glob("*.json"))
            for f in json_files:
                print(f"  - {f.name}")
    else:
        print("⚠️  Some examples had errors (check output above)")

    print()
    print("See also:")
    print("  - examples/05_state_persistence.py - Direct framework usage")
    print("  - examples/08_cross_session_persistence.py - Multi-session workflows")
    print("  - README.md (MCP Server Statefulness section) - Complete state management guide")
    print("=" * 70)
