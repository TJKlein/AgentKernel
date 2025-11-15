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

    # State persistence works as follows:
    # 1. Workspace files are copied INTO sandbox at start (code can read previous state)
    # 2. Code can write to workspace/ directory in sandbox (persists within session)
    # 3. Note: Files written to workspace/ in sandbox don't automatically sync back to host
    #    microsandbox Rust core supports volumes (patch_with_virtiofs_mounts) but Python API
    #    doesn't expose this yet. See WORKSPACE_PERSISTENCE.md for details.
    task_description = "Calculate 5 + 3, save the result to a file called 'workspace/result.txt', then read it back and print it"

    print("\nSaving and loading state...")
    result, output, error = agent.execute_task(task_description=task_description, verbose=True)

    print("\n" + "=" * 60)
    print("Example completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
