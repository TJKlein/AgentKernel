"""
Zero-dependency Minimal Monty Example

This script demonstrates AgentKernel functioning entirely in-process
using the fast 'Monty' AST evaluation backend. It requires no Docker,
no Rust binaries, and no extra installations beyond 'pydantic-monty'.
"""
import os
from agentkernel import create_agent

def main():
    # Only run if OPENAI_API_KEY is available
    if "OPENAI_API_KEY" not in os.environ:
        print("Please set your OPENAI_API_KEY environment variable.")
        print("Example: export OPENAI_API_KEY='sk-...'")
        return

    # Create an agent strictly using the Monty backend (no external dependencies)
    agent = create_agent(
        # We programmatically override the sandbox type here for the demo
        config_overrides={"execution": {"sandbox_type": "monty"}}
    )
    
    # We'll use a fast model if default isn't set
    agent.llm_config.model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    print("\n🚀 Starting Zero-Dependency Monty Agent")
    print("-" * 50)
    
    prompt = """
    Write a function that calculates the first 10 numbers of the Fibonacci sequence,
    prints the sequence, and returns the sum.
    """
    print(f"Task: {prompt.strip()}")
    print("-" * 50)

    # Execute the reasoning loop and the generated code seamlessly
    result, output, error = agent.execute_task(prompt, verbose=True)
    
    print("-" * 50)
    if result.is_success():
        print("✅ Execution Successful!")
        print(f"Output:\n{output}")
    else:
        print(f"❌ Execution Failed: {error}")

if __name__ == "__main__":
    main()
