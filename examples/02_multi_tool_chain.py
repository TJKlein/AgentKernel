"""Example 2: Multi-Tool Chain & Data Flow.

Demonstrates:
- Chaining multiple MCP tools in a single code execution
- Data flow between tools without passing through LLM context
- Intermediate data processing in execution environment
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from client.agent_helper import AgentHelper
from client.filesystem_helpers import FilesystemHelper
from client.sandbox_executor import SandboxExecutor
from config.loader import load_config


def main() -> None:
    """Run multi-tool chain example."""
    print("=" * 60)
    print("Example 2: Multi-Tool Chain & Data Flow")
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
        optimization_config=config.optimizations,
    )

    agent = AgentHelper(fs_helper, executor, optimization_config=config.optimizations)

    # Chain multiple tools: calculate, then use result in weather query
    task_description = "Calculate 10 * 5, then get weather for that many cities starting with San Francisco"

    print("\nChaining multiple tool calls in a single execution...")
    result, output, error = agent.execute_task(task_description=task_description, verbose=True)

    print("\n" + "=" * 60)
    print("Example completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()

