"""Example 15: Recursive Agent (RLM).

Demonstrates using RecursiveAgent to handle infinite context by treating it as a variable
in the Monty environment and recursively querying the LLM.

Prerequisites:
    - pydantic-monty installed: pip install pydantic-monty
    - LLM configuration in .env or environment variables
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from agentkernel import RecursiveAgent, create_agent
    from client.monty_executor import Monty
except ImportError as e:
    print(f"ERROR: Package not installed properly. {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

def main():
    print("=" * 60)
    print("Example 15: Recursive Agent (RLM)")
    print("=" * 60)
    
    if Monty is None:
        print("ERROR: pydantic-monty is not installed.")
        print("Please install it with: pip install pydantic-monty")
        return

    # Check for API key
    if not os.environ.get("OPENAI_API_KEY") and not os.environ.get("AZURE_OPENAI_API_KEY"):
        print("WARNING: No API key found. RLM requires an LLM to function.")
        print("Set OPENAI_API_KEY or AZURE_OPENAI_API_KEY environment variable.")
        # We continue anyway to show initialization, but execution will fail gracefully
    
    # Initialize RecursiveAgent
    # We can use create_agent but we need to instantiate RecursiveAgent specifically
    # Currently create_agent returns proper agent based on config, but doesn't expose class selection easily yet
    # mixed with subtypes. 
    # So we instantiate directly, reusing helper from create_agent if we wanted, 
    # but easier to just use the factory we modified or direct init.
    
    # Let's instantiate directly to be sure
    # Load config first to get defaults
    from config import load_config
    config = load_config()
    
    # Force Monty executor
    config.execution.sandbox_type = "monty"
    
    # Create agent using our factory params but direct class
    # We can actually use create_agent if we registered it? 
    # No, create_agent is hardcoded to return AgentHelper.
    # We'll just instantiate RecursiveAgent manually reusing the logic from create_agent (roughly)
    
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
    
    print("\nInitialized RecursiveAgent with Monty backend.")
    
    # Path to "large" context
    context_file = Path(__file__).parent / "15_infinite_context.txt"
    if not context_file.exists():
        print(f"Creating dummy context file at {context_file}...")
        context_file.write_text("""
[INFO] Start
...
[ERROR] Something went wrong. Code: ER-12345
...
[INFO] End
""")

    print(f"\nContext file: {context_file}")
    
    task = "Find the error code in the CONTEXT_DATA variable."
    
    print(f"\nTask: {task}")
    print("-" * 60)
    
    # Execute
    result, output, error = agent.execute_recursive_task(
        task_description=task,
        context_data=context_file,
        verbose=True
    )
    
    if error:
        print(f"\nError: {error}")
    else:
        print(f"\nResult: {result}")
        print(f"Output:\n{output}")
        
    print("=" * 60)

if __name__ == "__main__":
    main()
