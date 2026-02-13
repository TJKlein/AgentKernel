"""Example 16: Recursive Agent with Tools.

Demonstrates combining RLM (infinite context) with standard Tool usage.
The agent finds a number in a large file and then uses the Calculator tool to process it.
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from agentkernel import RecursiveAgent
    from client.monty_executor import Monty
except ImportError as e:
    print(f"ERROR: {e}")
    sys.exit(1)

def main():
    print("=" * 60)
    print("Example 16: Recursive Agent + Tools")
    print("=" * 60)
    
    # Check proper setup
    if Monty is None:
        print("ERROR: pydantic-monty not installed.")
        return

    # Load config
    from config import load_config
    config = load_config()
    config.execution.sandbox_type = "monty"
    
    # Initialize Agent
    from client.filesystem_helpers import FilesystemHelper
    from client.monty_executor import MontyExecutor
    
    fs_helper = FilesystemHelper(
        workspace_dir="./workspace",
        servers_dir="./servers",
        skills_dir="./skills",
    )
    
    executor = MontyExecutor(
        execution_config=config.execution,
        guardrail_config=config.guardrails,
        optimization_config=config.optimizations,
    )
    
    agent = RecursiveAgent(
        fs_helper=fs_helper,
        executor=executor,
        optimization_config=config.optimizations,
        llm_config=config.llm,
    )

    # 1. Create a dummy context file with a "secret number"
    context_file = Path(__file__).parent / "16_context_with_number.txt"
    context_file.write_text("""
[Page 1] Irrelevant data...
[Page 2] ...
[Page 50] The secret number is 42.
[Page 99] ...
""")
    print(f"Context file created at {context_file}")

    # 2. Define Task: Find number and use calculator
    # We explicitly ask for the calculator tool
    task = "Find the secret number in CONTEXT_DATA and use the 'calculator' tool to multiply it by 10."
    
    print(f"\nTask: {task}")
    print("-" * 60)

    # 3. Execute
    # agent.execute_recursive_task defaults logic, but we want to ensure tool is selected.
    # execute_recursive_task calls execute_task which does discovery.
    # If we want to guarantee calculator is available, we can rely on semantic selection 
    # OR explicit requirement.
    # The 'calculator' tool should be picked up if 'multiply' or 'calculator' is mentioned.
    
    # Force use of calculator tool
    required_tools = {"calculator": ["multiply"]}
    
    result, output, error = agent.execute_recursive_task(
        task_description=task,
        context_data=context_file,
        verbose=True,
        required_tools=required_tools
    )
    
    if error:
        print(f"\nError: {error}")
    else:
        print(f"\nResult: {result}")
        print(f"Output:\n{output}")
        
    print("=" * 60)

if __name__ == "__main__":
    main()
