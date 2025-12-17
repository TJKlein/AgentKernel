"""Example 9: Programmatic Configuration.

Demonstrates how to configure LLM and statefulness programmatically without .env files.
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
    """Run configuration example."""
    print("=" * 60)
    print("Example 9: Programmatic Configuration")
    print("=" * 60)

    # Example 1: Configure LLM programmatically
    print("\n--- Example 1: LLM Configuration ---")
    print("Configuring Azure OpenAI without .env file...")
    
    agent = create_agent(
        llm_enabled=True,
        llm_provider="azure_openai",
        llm_azure_endpoint="https://your-resource.openai.azure.com",
        llm_api_key="your_api_key_here",  # Or use env var
        llm_azure_deployment="gpt-4o-mini",
        llm_temperature=0.3,
        llm_max_tokens=2000,
    )
    
    print("✅ Agent created with LLM configuration")
    print(f"   LLM Enabled: {agent.code_generator.llm_config.enabled if hasattr(agent.code_generator, 'llm_config') else 'N/A'}")
    print(f"   Provider: {agent.code_generator.llm_config.provider if hasattr(agent.code_generator, 'llm_config') else 'N/A'}")

    # Example 2: Configure statefulness programmatically
    print("\n--- Example 2: State Configuration ---")
    print("Configuring state persistence...")
    
    agent = create_agent(
        state_enabled=True,
        state_file="my_custom_state.json",
        state_auto_save=True,
    )
    
    print("✅ Agent created with state configuration")
    print(f"   State Enabled: {agent.executor.execution_config.state.enabled}")
    print(f"   State File: {agent.executor.execution_config.state.state_file}")
    print(f"   Auto Save: {agent.executor.execution_config.state.auto_save}")

    # Example 3: Disable statefulness
    print("\n--- Example 3: Disable State ---")
    
    agent = create_agent(
        state_enabled=False,
    )
    
    print("✅ Agent created with state disabled")
    print(f"   State Enabled: {agent.executor.execution_config.state.enabled}")

    # Example 4: Combined configuration
    print("\n--- Example 4: Combined Configuration ---")
    
    agent = create_agent(
        workspace_dir="./my_workspace",
        llm_enabled=True,
        llm_provider="openai",
        llm_model="gpt-4o-mini",
        llm_api_key="your_key",  # Or use OPENAI_API_KEY env var
        state_enabled=True,
        state_file="workflow_state.json",
        state_auto_save=True,
    )
    
    print("✅ Agent created with combined configuration")
    print(f"   Workspace: {agent.fs_helper.workspace_dir}")
    print(f"   LLM Enabled: {agent.code_generator.llm_config.enabled if hasattr(agent.code_generator, 'llm_config') else 'N/A'}")
    print(f"   State Enabled: {agent.executor.execution_config.state.enabled}")

    # Example 5: Using execute_task with configuration
    print("\n--- Example 5: execute_task with Configuration ---")
    
    result, output, error = execute_task(
        "Calculate 5 + 3",
        llm_enabled=False,  # Disable LLM for this task
        state_enabled=True,
        state_file="task_state.json",
        verbose=False,
    )
    
    if error:
        print(f"   Error: {error}")
    else:
        print(f"   Result: {result}")

    print("\n" + "=" * 60)
    print("Example completed!")
    print("=" * 60)
    print("\nKey Takeaways:")
    print("  1. LLM can be configured programmatically without .env")
    print("  2. Statefulness can be enabled/disabled and configured")
    print("  3. Configuration can be combined (LLM + State + Directories)")
    print("  4. execute_task() also accepts configuration parameters")


if __name__ == "__main__":
    main()

