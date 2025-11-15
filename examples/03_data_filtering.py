"""Example 3: Data Filtering & Transformation.

Demonstrates:
- Filtering large datasets in code before returning to LLM
- Aggregations and data processing
- Context-efficient data handling
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from client.agent_helper import AgentHelper
from client.filesystem_helpers import FilesystemHelper
from client.sandbox_executor import SandboxExecutor
from config.loader import load_config


def main() -> None:
    """Run data filtering example."""
    print("=" * 60)
    print("Example 3: Data Filtering & Transformation")
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

    # Filter and process data in code
    task_description = "Query database for users, filter for active users, and calculate statistics"

    print("\nFiltering and processing data in code...")
    result, output, error = agent.execute_task(task_description=task_description, verbose=True)

    print("\n" + "=" * 60)
    print("Example completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()

