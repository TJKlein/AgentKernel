"""Example 8: Cross-Session State Persistence (Comprehensive).

Demonstrates:
- True cross-session state persistence across multiple separate executions
- Resuming work from previous sessions
- Building on previous session's state
- Multiple sequential sessions working with shared state

This is a comprehensive example showing how agents can maintain state
across multiple execution sessions, enabling long-running workflows
and resumable tasks.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from client.agent_helper import AgentHelper
from client.filesystem_helpers import FilesystemHelper
from client.sandbox_executor import SandboxExecutor
from config.loader import load_config


def create_agent(config) -> AgentHelper:
    """Create an agent helper with the given config."""
    fs_helper = FilesystemHelper(
        workspace_dir=config.execution.workspace_dir,
        servers_dir=config.execution.servers_dir,
        skills_dir=config.execution.skills_dir,
    )

    relaxed_guardrails = config.guardrails.model_copy()
    relaxed_guardrails.security_checks = False
    executor = SandboxExecutor(
        execution_config=config.execution,
        guardrail_config=relaxed_guardrails,
        optimization_config=config.optimizations,
    )

    return AgentHelper(fs_helper, executor, optimization_config=config.optimizations,
        llm_config=config.llm)


def session_1_initialize(config) -> tuple[bool, str]:
    """Session 1: Initialize state and perform first calculation."""
    print("\n" + "=" * 60)
    print("SESSION 1: Initialize State")
    print("=" * 60)

    agent = create_agent(config)

    task_description = """
    Initialize a calculation workflow:
    1. Create /workspace/workflow_state.json with:
       - workflow_id: "calc_001"
       - current_step: 1
       - total_steps: 3
       - results: []
       - status: "in_progress"
    2. Calculate 10 * 5 and add the result to the results array
    3. Update current_step to 2
    4. Verify /workspace exists and is mounted
    5. Print confirmation that workflow state was initialized
    """

    print("\nExecuting Session 1...")
    result, output, error = agent.execute_task(task_description=task_description, verbose=True)

    if result.value != "success":
        return False, f"Session 1 failed: {error or 'Unknown error'}"

    # Verify state file exists
    workspace_path = Path(config.execution.workspace_dir).resolve()
    state_file = workspace_path / "workflow_state.json"

    if not state_file.exists():
        # Check if any JSON files exist in workspace
        json_files = list(workspace_path.glob("*.json"))
        if json_files:
            return False, f"State file not found at {state_file}, but found: {[f.name for f in json_files]}"
        return False, f"State file not found at {state_file}. Workspace contents: {list(workspace_path.iterdir())}"

    try:
        state = json.loads(state_file.read_text())
        if state.get("current_step") != 2:
            return False, f"Expected current_step=2, got {state.get('current_step')}"
    except Exception as e:
        return False, f"Failed to verify state: {e}"

    print(f"\n✅ Session 1 completed. State file: {state_file}")
    return True, "Session 1 completed successfully"


def session_2_continue(config) -> tuple[bool, str]:
    """Session 2: Continue workflow from previous session."""
    print("\n" + "=" * 60)
    print("SESSION 2: Continue Workflow")
    print("=" * 60)
    print("(Reading state from Session 1)")

    agent = create_agent(config)

    task_description = """
    Continue the workflow from the previous session:
    1. Read /workspace/workflow_state.json
    2. Print the current state (workflow_id, current_step, results)
    3. Calculate 20 * 3 and add the result to the results array
    4. Update current_step to 3
    5. Verify you can read the state from the previous session
    6. Print confirmation that workflow continued
    """

    print("\nExecuting Session 2...")
    result, output, error = agent.execute_task(task_description=task_description, verbose=True)

    if result.value != "success":
        return False, f"Session 2 failed: {error or 'Unknown error'}"

    # Verify state was updated
    workspace_path = Path(config.execution.workspace_dir).resolve()
    state_file = workspace_path / "workflow_state.json"

    if not state_file.exists():
        # Check if any JSON files exist in workspace
        json_files = list(workspace_path.glob("*.json"))
        if json_files:
            return False, f"State file not found at {state_file}, but found: {[f.name for f in json_files]}"
        return False, f"State file not found at {state_file}. Workspace contents: {list(workspace_path.iterdir())}"

    try:
        state = json.loads(state_file.read_text())
        if state.get("current_step") != 3:
            return False, f"Expected current_step=3, got {state.get('current_step')}"
        if len(state.get("results", [])) != 2:
            return False, f"Expected 2 results, got {len(state.get('results', []))}"
    except Exception as e:
        return False, f"Failed to verify state: {e}"

    print(f"\n✅ Session 2 completed. State file: {state_file}")
    return True, "Session 2 completed successfully"


def session_3_complete(config) -> tuple[bool, str]:
    """Session 3: Complete workflow and finalize state."""
    print("\n" + "=" * 60)
    print("SESSION 3: Complete Workflow")
    print("=" * 60)
    print("(Reading state from Sessions 1 & 2)")

    agent = create_agent(config)

    task_description = """
    Complete the workflow:
    1. Read /workspace/workflow_state.json
    2. Print the current state (workflow_id, current_step, all results)
    3. Calculate 15 * 4 and add the result to the results array
    4. Calculate the sum of all results in the results array
    5. Update current_step to 4 (completed)
    6. Update status to "completed"
    7. Add a "total" field with the sum of all results
    8. Print a summary of the completed workflow
    """

    print("\nExecuting Session 3...")
    result, output, error = agent.execute_task(task_description=task_description, verbose=True)

    if result.value != "success":
        return False, f"Session 3 failed: {error or 'Unknown error'}"

    # Verify workflow is completed
    workspace_path = Path(config.execution.workspace_dir).resolve()
    state_file = workspace_path / "workflow_state.json"

    if not state_file.exists():
        # Check if any JSON files exist in workspace
        json_files = list(workspace_path.glob("*.json"))
        if json_files:
            return False, f"State file not found at {state_file}, but found: {[f.name for f in json_files]}"
        return False, f"State file not found at {state_file}. Workspace contents: {list(workspace_path.iterdir())}"

    try:
        state = json.loads(state_file.read_text())
        if state.get("status") != "completed":
            return False, f"Expected status='completed', got {state.get('status')}"
        if state.get("current_step") != 4:
            return False, f"Expected current_step=4, got {state.get('current_step')}"
        if len(state.get("results", [])) != 3:
            return False, f"Expected 3 results, got {len(state.get('results', []))}"
        if "total" not in state:
            return False, "Expected 'total' field in completed state"
    except Exception as e:
        return False, f"Failed to verify state: {e}"

    print(f"\n✅ Session 3 completed. Final state file: {state_file}")
    
    # Print final summary
    print("\n" + "-" * 60)
    print("WORKFLOW SUMMARY")
    print("-" * 60)
    print(f"Workflow ID: {state.get('workflow_id')}")
    print(f"Status: {state.get('status')}")
    print(f"Steps completed: {state.get('current_step')} / {state.get('total_steps')}")
    print(f"Results: {state.get('results')}")
    print(f"Total: {state.get('total')}")
    print("-" * 60)
    
    return True, "Session 3 completed successfully"


def main() -> None:
    """Run comprehensive cross-session persistence example."""
    print("=" * 60)
    print("Example 8: Cross-Session State Persistence (Comprehensive)")
    print("=" * 60)
    print("\nThis example demonstrates a multi-session workflow:")
    print("  - Session 1: Initialize workflow state")
    print("  - Session 2: Continue workflow (reads Session 1 state)")
    print("  - Session 3: Complete workflow (reads Sessions 1 & 2 state)")
    print("\nEach session runs in a separate sandbox execution, but shares")
    print("the same workspace, demonstrating true cross-session persistence.\n")

    config = load_config()

    # Session 1: Initialize
    success1, msg1 = session_1_initialize(config)
    if not success1:
        print(f"\n❌ Example failed: {msg1}")
        sys.exit(1)

    print("\n" + "-" * 60)
    print("SESSION 1 COMPLETE - Sandbox destroyed")
    print("(State persists on host filesystem)")
    print("-" * 60)

    # Session 2: Continue
    success2, msg2 = session_2_continue(config)
    if not success2:
        print(f"\n❌ Example failed: {msg2}")
        sys.exit(1)

    print("\n" + "-" * 60)
    print("SESSION 2 COMPLETE - Sandbox destroyed")
    print("(State persists on host filesystem)")
    print("-" * 60)

    # Session 3: Complete
    success3, msg3 = session_3_complete(config)
    if not success3:
        print(f"\n❌ Example failed: {msg3}")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("✅ Example 8 completed successfully!")
    print("=" * 60)
    print("\nMulti-session workflow completed successfully!")
    print("This demonstrates:")
    print("  1. State initialization in Session 1")
    print("  2. State reading and continuation in Session 2")
    print("  3. State reading and completion in Session 3")
    print("  4. True cross-session persistence across 3 separate executions")
    print("  5. Workflow resumability as described in the Anthropic article")


if __name__ == "__main__":
    main()

