"""Example 15: Recursive Agent (RLM).

Demonstrates using RecursiveAgent to handle infinite context: CONTEXT_DATA and
ask_llm are injected by the OpenSandbox executor; the agent recursively queries
the LLM over chunks.

Prerequisites:
    - OpenSandbox: opensandbox-server start (Docker)
    - LLM: OPENAI_API_KEY or AZURE_OPENAI_* in .env
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from mcpruntime import RecursiveAgent
    from client.filesystem_helpers import FilesystemHelper
    from client.opensandbox_executor import OpenSandboxExecutor
    from config import load_config
except ImportError as e:
    print(f"ERROR: Package not installed properly. {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

def main():
    print("=" * 60)
    print("Example 15: Recursive Agent (RLM)")
    print("=" * 60)

    if not os.environ.get("OPENAI_API_KEY") and not os.environ.get("AZURE_OPENAI_API_KEY"):
        print("WARNING: No API key found. RLM requires an LLM to function.")
        print("Set OPENAI_API_KEY or AZURE_OPENAI_API_KEY environment variable.")
        # We continue anyway to show initialization, but execution will fail gracefully

    config = load_config()
    fs_helper = FilesystemHelper(
        workspace_dir=config.execution.workspace_dir,
        servers_dir=config.execution.servers_dir,
        skills_dir=config.execution.skills_dir,
    )
    executor = OpenSandboxExecutor(
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
    print("\nInitialized RecursiveAgent with OpenSandbox backend.")
    
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
