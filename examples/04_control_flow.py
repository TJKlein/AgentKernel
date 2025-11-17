"""Example 4: Control Flow & Conditional Logic.

Demonstrates:
- Loops, conditionals, and error handling in code
- Complex control flow patterns
- Decision-making based on tool results
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from client.agent_helper import AgentHelper
from client.filesystem_helpers import FilesystemHelper
from client.sandbox_executor import SandboxExecutor
from config.loader import load_config


def main() -> None:
    """Run control flow example."""
    print("=" * 60)
    print("Example 4: Control Flow & Conditional Logic")
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

    agent = AgentHelper(
        fs_helper, 
        executor, 
        optimization_config=config.optimizations,
        llm_config=config.llm  # Pass LLM config for LLM-based code generation
    )

    # Use control flow: check weather, then decide what to do
    task_description = "Get weather for San Francisco, and if temperature is above 20, calculate how many days until summer"

    print("\nUsing control flow with tool results...")
    result, output, error = agent.execute_task(task_description=task_description, verbose=True)

    print("\n" + "=" * 60)
    print("Example completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()

