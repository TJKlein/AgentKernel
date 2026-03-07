"""
Minimal agent example (default OpenSandbox backend).

Uses create_agent() with default configuration. Requires Docker and
opensandbox-server start. For LLM-based code generation, set OPENAI_API_KEY
or Azure env vars.
"""
import os
from mcpruntime import create_agent

def main():
    # Only run if OPENAI_API_KEY is available (for LLM code generation)
    if "OPENAI_API_KEY" not in os.environ and "AZURE_OPENAI_API_KEY" not in os.environ:
        print("Optional: set OPENAI_API_KEY or AZURE_OPENAI_API_KEY for LLM code generation.")
        print("Without it, only pre-written tasks will run. Continuing with default agent...")

    # Default backend is OpenSandbox (Docker). Ensure opensandbox-server start is running.
    agent = create_agent()
    if agent.llm_config and agent.llm_config.enabled:
        agent.llm_config.model = os.environ.get("LLM_MODEL", agent.llm_config.model or "gpt-4o-mini")

    print("\n🚀 Starting agent (OpenSandbox backend)")
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
    if not error and (result is None or getattr(result, "is_success", lambda: True)()):
        print("✅ Execution Successful!")
        print(f"Output:\n{output}")
    else:
        print(f"❌ Execution Failed: {error}")

if __name__ == "__main__":
    main()
