"""Example 6: Skills & Reusable Code.

Demonstrates:
- Saving reusable code functions as skills
- Importing and using saved skills
- Building a library of common operations
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from client.agent_helper import AgentHelper
from client.filesystem_helpers import FilesystemHelper
from client.sandbox_executor import SandboxExecutor
from config.loader import load_config


def main() -> None:
    """Run skills example."""
    print("=" * 60)
    print("Example 6: Skills & Reusable Code")
    print("=" * 60)

    config = load_config()

    fs_helper = FilesystemHelper(
        workspace_dir=config.execution.workspace_dir,
        servers_dir=config.execution.servers_dir,
        skills_dir=config.execution.skills_dir,
    )

    # Save a skill first
    skill_code = """
def double_number(x: float) -> float:
    \"\"\"Double a number.\"\"\"
    return x * 2
"""
    fs_helper.save_skill("double_number", skill_code, description="Doubles a number")

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

    # Use the saved skill
    task_description = "Import the double_number skill and use it to double 15"

    print("\nUsing saved skills...")
    result, output, error = agent.execute_task(task_description=task_description, verbose=True)

    print("\n" + "=" * 60)
    print("Example completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
