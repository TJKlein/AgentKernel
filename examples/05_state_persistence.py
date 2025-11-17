"""Example 5: State Persistence.

Demonstrates:
- Saving and loading state via filesystem
- Resuming work across multiple executions (true cross-session persistence)
- Persistent data storage with volume mounts

This example demonstrates TRUE cross-session persistence:
1. Session 1: Write state to /workspace (sandbox is destroyed after)
2. Session 2: Read state from /workspace (new sandbox, same workspace)

This verifies that state persists across separate execution sessions,
as described in the Anthropic article on code execution with MCP.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from client.agent_helper import AgentHelper
from client.filesystem_helpers import FilesystemHelper
from client.sandbox_executor import SandboxExecutor
from config.loader import load_config


def session_1_write_state(config) -> tuple[bool, str]:
    """Session 1: Write state to workspace."""
    print("\n" + "=" * 60)
    print("SESSION 1: Writing state to workspace")
    print("=" * 60)
    print("(This execution will create a sandbox, write state, then destroy the sandbox)")

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

    agent = AgentHelper(
        fs_helper, 
        executor, 
        optimization_config=config.optimizations,
        llm_config=config.llm  # Pass LLM config for LLM-based code generation
    )

    # Write state to workspace
    task_description = """
    Calculate 5 + 3, then save the result and metadata to /workspace/state.json.
    The JSON file should contain:
    - calculation: "5 + 3"
    - result: 8
    - step: 1
    - message: "State saved in session 1"
    
    Also verify that /workspace exists and is mounted.
    Print a confirmation message when state is saved.
    """

    print("\nExecuting Session 1...")
    result, output, error = agent.execute_task(task_description=task_description, verbose=True)

    if result.value != "success":
        return False, f"Session 1 failed: {error or 'Unknown error'}"

    # Verify file was created on host
    workspace_path = Path(config.execution.workspace_dir).resolve()
    state_file = workspace_path / "state.json"

    if not state_file.exists():
        # Check if any JSON files exist in workspace
        json_files = list(workspace_path.glob("*.json"))
        if json_files:
            return False, f"State file not found at {state_file}, but found: {[f.name for f in json_files]}"
        return False, f"State file not found at {state_file}. Workspace contents: {list(workspace_path.iterdir())}"

    print(f"\n✅ Session 1 completed. State file exists on host: {state_file}")
    print("   (Sandbox has been destroyed, but state persists on host filesystem)")
    return True, "Session 1 completed successfully"


def session_2_read_state(config) -> tuple[bool, str]:
    """Session 2: Read state from workspace (different execution)."""
    print("\n" + "=" * 60)
    print("SESSION 2: Reading state from workspace")
    print("=" * 60)
    print("(This is a NEW execution - different sandbox instance)")
    print("(State from Session 1 should be accessible)")

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

    agent = AgentHelper(
        fs_helper, 
        executor, 
        optimization_config=config.optimizations,
        llm_config=config.llm  # Pass LLM config for LLM-based code generation
    )

    # Read state from workspace
    task_description = """
    Read the state from /workspace/state.json that was saved in a previous session.
    Print the contents of the file.
    Verify that /workspace exists and is mounted.
    Confirm that you can read the state file from the previous session.
    Update the step field to 2 and save it back to /workspace/state.json.
    """

    print("\nExecuting Session 2...")
    result, output, error = agent.execute_task(task_description=task_description, verbose=True)

    if result.value != "success":
        return False, f"Session 2 failed: {error or 'Unknown error'}"

    # Verify file still exists on host and was updated
    workspace_path = Path(config.execution.workspace_dir).resolve()
    state_file = workspace_path / "state.json"

    if not state_file.exists():
        return False, f"State file not found on host at {state_file}"

    # Try to read the file content
    try:
        state_data = json.loads(state_file.read_text())
        print(f"\n✅ Session 2 completed. State file contents: {state_data}")

        # Verify expected fields
        if "step" not in state_data or "result" not in state_data:
            return False, "State file missing expected fields"

        if state_data.get("step") != 2:
            return False, f"Expected step=2, got step={state_data.get('step')}"

        return True, f"Session 2 completed successfully. Read step={state_data.get('step')}, result={state_data.get('result')}"
    except Exception as e:
        return False, f"Failed to read state file: {e}"


def main() -> None:
    """Run state persistence example with cross-session testing."""
    print("=" * 60)
    print("Example 5: State Persistence (Cross-Session)")
    print("=" * 60)
    print("\nThis example demonstrates TRUE cross-session persistence:")
    print("  - Session 1: Write state to /workspace (sandbox destroyed)")
    print("  - Session 2: Read state from /workspace (new sandbox)")
    print("\nThis verifies state persists across separate execution sessions,")
    print("as described in the Anthropic article on code execution with MCP.\n")

    config = load_config()

    # Session 1: Write state
    success1, msg1 = session_1_write_state(config)
    if not success1:
        print(f"\n❌ Example failed: {msg1}")
        sys.exit(1)

    print("\n" + "-" * 60)
    print("SESSION 1 COMPLETE - Sandbox destroyed")
    print("(State should persist on host filesystem)")
    print("-" * 60)

    # Session 2: Read state (NEW execution)
    success2, msg2 = session_2_read_state(config)
    if not success2:
        print(f"\n❌ Example failed: {msg2}")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("✅ Example 5 completed successfully!")
    print("=" * 60)
    print("\nState successfully persisted across two separate execution sessions!")
    print("This confirms that:")
    print("  1. Workspace is properly mounted via virtiofs")
    print("  2. Files written in one session persist to host filesystem")
    print("  3. Files are accessible in subsequent sessions")
    print("  4. State persistence works as described in the Anthropic article")


if __name__ == "__main__":
    main()
