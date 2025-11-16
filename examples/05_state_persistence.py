"""Example 5: State Persistence.

Demonstrates:
- Saving and loading state via filesystem
- Resuming work across multiple executions
- Persistent data storage
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from client.agent_helper import AgentHelper
from client.filesystem_helpers import FilesystemHelper
from client.sandbox_executor import SandboxExecutor
from config.loader import load_config


def main() -> None:
    """Run state persistence example."""
    print("=" * 60)
    print("Example 5: State Persistence")
    print("=" * 60)

    config = load_config()

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
    )

    agent = AgentHelper(fs_helper, executor)

    # State persistence with volume mounts:
    # Workspace directory is mounted at /workspace in sandbox
    # Files written to /workspace are automatically persisted to host
    # Files persist across multiple executions - true session tracking!
    task_description = "Calculate 5 + 3, save the result to a file called '/workspace/result.txt', then read it back and print it. Also check if /workspace exists and is mounted."

    print("\nSaving and loading state...")
    result, output, error = agent.execute_task(task_description=task_description, verbose=True)

    print("\n" + "=" * 60)
    print("Example completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
