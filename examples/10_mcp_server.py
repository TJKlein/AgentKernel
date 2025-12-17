#!/usr/bin/env python3
"""Example: Running the framework as an MCP server.

This example demonstrates how to run the Code Execution MCP framework
as an MCP server that can be accessed by other MCP clients.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from agentkernel import create_server, run_server, AppConfig, ExecutionConfig, LLMConfig


def example_basic_server():
    """Example: Start a basic MCP server."""
    print("=" * 60)
    print("Example: Basic MCP Server")
    print("=" * 60)
    print()
    print("Starting MCP server with default configuration...")
    print("The server will expose the following tools:")
    print("  - execute_task: Execute tasks using the framework")
    print("  - list_available_tools: List all available tools")
    print("  - get_state: Get workspace state")
    print("  - save_state: Save workspace state")
    print("  - list_servers: List available server directories")
    print("  - get_server_tools: List tools in a specific server")
    print()
    print("To run the server:")
    print("  python -m code_execution_mcp.server")
    print()
    print("Or programmatically:")
    print("  from agentkernel import run_server")
    print("  run_server(transport='stdio')")
    print()


def example_custom_config_server():
    """Example: Create server with custom configuration."""
    print("=" * 60)
    print("Example: Custom Configuration MCP Server")
    print("=" * 60)
    print()
    print("Creating server with custom configuration...")
    
    config = AppConfig(
        execution=ExecutionConfig(
            workspace_dir="./workspace",
            servers_dir="./servers",
            skills_dir="./skills",
        ),
        llm=LLMConfig(
            enabled=True,
            provider="openai",
            model="gpt-4o-mini",
        ),
    )
    
    server = create_server(config=config)
    print("Server created successfully!")
    print("To run: asyncio.run(server.run(transport='stdio'))")
    print()


def example_server_tools():
    """Example: List available tools when running as server."""
    print("=" * 60)
    print("Example: MCP Server Tools")
    print("=" * 60)
    print()
    print("When running as an MCP server, clients can call:")
    print()
    print("1. execute_task(task_description: str, verbose: bool = False)")
    print("   - Executes a task using the framework")
    print("   - Returns: {success, result, output, error}")
    print()
    print("2. list_available_tools()")
    print("   - Lists all tools from servers/ directory")
    print("   - Returns: {server_name: [tool_names]}")
    print()
    print("3. get_state(state_file: str = 'state.json')")
    print("   - Gets workspace state")
    print("   - Returns: {exists, data}")
    print()
    print("4. save_state(state_data: dict, state_file: str = 'state.json')")
    print("   - Saves workspace state")
    print("   - Returns: {success, file}")
    print()
    print("5. list_servers()")
    print("   - Lists all server directories")
    print("   - Returns: [server_names]")
    print()
    print("6. get_server_tools(server_name: str)")
    print("   - Lists tools in a specific server")
    print("   - Returns: [tool_names]")
    print()


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("MCP Server Examples")
    print("=" * 60)
    print()
    
    example_basic_server()
    example_custom_config_server()
    example_server_tools()
    
    print("\n" + "=" * 60)
    print("Note: To actually start the server, run:")
    print("  python -m code_execution_mcp.server")
    print("=" * 60)

