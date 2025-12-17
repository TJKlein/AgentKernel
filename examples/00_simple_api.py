"""Example 0: Simple API Usage.

Demonstrates the simplest way to use the framework with the new high-level API.

Prerequisites:
    - Microsandbox server running: msb server start --dev
    - Directory structure: servers/, workspace/, skills/
    - Optional: .env file with LLM configuration for code generation

See the Configuration section in README.md for setup instructions.
"""

import sys
from pathlib import Path

# Add parent directory to path for development
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from agentkernel import create_agent, execute_task
except ImportError:
    print("ERROR: Package not installed. Please install with: pip install -e .")
    sys.exit(1)


def main() -> None:
    """Run simple API example."""
    print("=" * 60)
    print("Example 0: Simple API Usage")
    print("=" * 60)

    # Option 1: Simplest usage - one function call
    print("\n--- Option 1: Using execute_task() convenience function ---")
    result, output, error = execute_task(
        "Calculate 5 + 3",
        verbose=True
    )
    
    if error:
        print(f"Error: {error}")
    else:
        print(f"Result: {result}")
        print(f"Output: {output}")

    # Option 2: Create agent and reuse (more efficient for multiple tasks)
    print("\n--- Option 2: Using create_agent() for multiple tasks ---")
    agent = create_agent()
    
    tasks = [
        "Calculate 10 * 5",
        "Get weather for San Francisco",
    ]
    
    for task in tasks:
        print(f"\nExecuting: {task}")
        result, output, error = agent.execute_task(task, verbose=False)
        if error:
            print(f"  Error: {error}")
        else:
            print(f"  Result: {result}")

    # Option 3: Custom directories
    print("\n--- Option 3: Custom directories ---")
    agent = create_agent(
        workspace_dir="./workspace",
        servers_dir="./servers",
        skills_dir="./skills"
    )
    print("Agent created with custom directories")

    print("\n" + "=" * 60)
    print("Example completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()

