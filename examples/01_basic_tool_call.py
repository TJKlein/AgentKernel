"""Example 1: Basic Tool Call & Filesystem Discovery.

Demonstrates:
- Simple single MCP tool execution via code using FastMCP
- Filesystem-based tool discovery (listing servers/, reading tool files)
- Task-driven tool selection (agent determines which tools are needed)
- Progressive disclosure (only loading needed tools)
"""

import sys
from pathlib import Path

# Check if running in virtual environment or if microsandbox is available
try:
    import microsandbox
except ImportError:
    print("ERROR: microsandbox is not installed or virtual environment is not activated.")
    print("Please run:")
    print("  source .venv/bin/activate")
    print("  python examples/01_basic_tool_call.py")
    print("\nOr use the venv Python directly:")
    print("  .venv/bin/python examples/01_basic_tool_call.py")
    sys.exit(1)

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from client.agent_helper import AgentHelper
from client.filesystem_helpers import FilesystemHelper
from client.sandbox_executor import SandboxExecutor
from config.loader import load_config


def main() -> None:
    """Run basic tool call example."""
    print("=" * 60)
    print("Example 1: Basic Tool Call & Filesystem Discovery")
    print("=" * 60)

    # Load configuration
    config = load_config()

    # Initialize filesystem helper
    fs_helper = FilesystemHelper(
        workspace_dir=config.execution.workspace_dir,
        servers_dir=config.execution.servers_dir,
        skills_dir=config.execution.skills_dir,
    )

    # Initialize sandbox executor with relaxed guardrails for mock client
    relaxed_guardrails = config.guardrails.model_copy()
    relaxed_guardrails.security_checks = False
    executor = SandboxExecutor(
        execution_config=config.execution,
        guardrail_config=relaxed_guardrails,
        optimization_config=config.optimizations,  # Pass optimization config
    )

    # Initialize agent helper (combines discovery, selection, generation, execution)
    agent = AgentHelper(fs_helper, executor, optimization_config=config.optimizations)

    # Define task - framework will auto-generate appropriate code
    task_description = "Calculate 5 + 3 and get weather for San Francisco"

    # Execute task end-to-end (discovery, selection, generation, execution all in one)
    print("\nUsing framework components for tool selection and code generation...")
    result, output, error = agent.execute_task(task_description=task_description, verbose=True)

    print("\n" + "=" * 60)
    print("Example completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
