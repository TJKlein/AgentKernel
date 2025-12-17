#!/usr/bin/env python3
"""Example: Using the framework as an MCP server with a client.

This example demonstrates:
1. How to start the framework as an MCP server
2. How to connect to it from an MCP client
3. How to call the exposed tools

Note: This is a demonstration. In practice, the server would run
in a separate process and clients would connect via stdio/sse/http.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from agentkernel import create_server, AppConfig, ExecutionConfig


async def example_server_setup():
    """Example: Setting up the MCP server."""
    print("=" * 70)
    print("Example: Setting Up MCP Server")
    print("=" * 70)
    print()
    
    print("1. Create server with default configuration:")
    print("   (Loads from config.yaml / .env / defaults)")
    print("   from agentkernel import create_server")
    print("   server = create_server()")
    print()
    
    print("2. Create server with custom configuration:")
    print("   from agentkernel import AppConfig, ExecutionConfig, create_server")
    print("   config = AppConfig(")
    print("       execution=ExecutionConfig(")
    print("           workspace_dir='./workspace',")
    print("           servers_dir='./servers',      # Tool discovery directory")
    print("           skills_dir='./skills',")
    print("       )")
    print("   )")
    print("   server = create_server(config=config)")
    print()
    
    print("3. Run the server:")
    print("   import asyncio")
    print("   asyncio.run(server.run(transport='stdio'))")
    print()
    
    # Actually create a server instance to show it works
    try:
        config = AppConfig(
            execution=ExecutionConfig(
                workspace_dir="./workspace",
                servers_dir="./servers",      # Tools discovered from here
                skills_dir="./skills",
            )
        )
        server = create_server(config=config)
        print("✓ Server created successfully!")
        print(f"  Server name: {server.mcp.name}")
        print(f"  Tool discovery directory: {server.agent.fs_helper.servers_dir}")
        print(f"  Workspace directory: {server.agent.fs_helper.workspace_dir}")
        print(f"  Skills directory: {server.agent.fs_helper.skills_dir}")
        
        # Try to discover tools
        try:
            tools = server.agent.discover_tools(verbose=False)
            print(f"  Discovered {sum(len(t) for t in tools.values())} tools from {len(tools)} servers")
        except Exception:
            pass
        print()
    except Exception as e:
        print(f"⚠ Could not create server (this is OK if dependencies are missing): {e}")
        print()


def example_exposed_tools():
    """Example: Show what tools are exposed."""
    print("=" * 70)
    print("Example: Exposed MCP Tools")
    print("=" * 70)
    print()
    
    tools_info = [
        {
            "name": "execute_task",
            "description": "Execute a task using the Code Execution MCP framework",
            "parameters": {
                "task_description": "str - Description of the task to execute",
                "verbose": "bool (optional, default=False) - Print progress info"
            },
            "returns": "Dict with keys: success, result, output, error"
        },
        {
            "name": "list_available_tools",
            "description": "List all available tools from the servers directory",
            "parameters": {},
            "returns": "Dict mapping server names to lists of tool names"
        },
        {
            "name": "get_state",
            "description": "Get the current state from the workspace",
            "parameters": {
                "state_file": "str (optional, default='state.json') - State file name"
            },
            "returns": "Dict with keys: exists, data"
        },
        {
            "name": "save_state",
            "description": "Save state to the workspace",
            "parameters": {
                "state_data": "dict - State data to save",
                "state_file": "str (optional, default='state.json') - State file name"
            },
            "returns": "Dict with keys: success, file"
        },
        {
            "name": "list_servers",
            "description": "List all available server directories",
            "parameters": {},
            "returns": "List of server names"
        },
        {
            "name": "get_server_tools",
            "description": "List tools available in a specific server",
            "parameters": {
                "server_name": "str - Name of the server"
            },
            "returns": "List of tool names"
        },
    ]
    
    for i, tool in enumerate(tools_info, 1):
        print(f"{i}. {tool['name']}")
        print(f"   {tool['description']}")
        if tool['parameters']:
            print("   Parameters:")
            for param, desc in tool['parameters'].items():
                print(f"     - {param}: {desc}")
        print(f"   Returns: {tool['returns']}")
        print()


def example_client_usage():
    """Example: How a client would use the server."""
    print("=" * 70)
    print("Example: Client Usage (Conceptual)")
    print("=" * 70)
    print()
    
    print("When the server is running, clients can connect and call tools:")
    print()
    print("```python")
    print("# Client code (using FastMCP or another MCP client)")
    print("from fastmcp import FastMCP")
    print()
    print("# Connect to the server")
    print("client = FastMCP('my-client')")
    print("client.connect('stdio://code-execution-mcp-server')")
    print()
    print("# Call execute_task tool")
    print("result = client.call_tool('execute_task', {")
    print("    'task_description': 'Calculate 5 + 3',")
    print("    'verbose': False")
    print("})")
    print("# Returns: {'success': True, 'result': 8, 'output': '...', 'error': None}")
    print()
    print("# List available tools")
    print("tools = client.call_tool('list_available_tools', {})")
    print("# Returns: {'calculator': ['add', 'multiply', 'calculate'], ...}")
    print()
    print("# Get workspace state")
    print("state = client.call_tool('get_state', {'state_file': 'state.json'})")
    print("# Returns: {'exists': True, 'data': {...}}")
    print("```")
    print()


def example_running_server():
    """Example: How to actually run the server."""
    print("=" * 70)
    print("Example: Running the Server")
    print("=" * 70)
    print()
    
    print("Method 1: Command-line entry point (after installation)")
    print("  code-execution-mcp-server")
    print()
    
    print("Method 2: Python module")
    print("  python -m code_execution_mcp.server")
    print()
    
    print("Method 3: With specific transport")
    print("  python -m code_execution_mcp.server stdio")
    print("  python -m code_execution_mcp.server sse")
    print("  python -m code_execution_mcp.server http")
    print()
    
    print("Method 4: Programmatically")
    print("  from agentkernel import run_server")
    print("  run_server(transport='stdio')")
    print()
    
    print("Method 5: With custom configuration")
    print("  from agentkernel import create_server, AppConfig")
    print("  import asyncio")
    print("  ")
    print("  config = AppConfig(...)")
    print("  server = create_server(config=config)")
    print("  asyncio.run(server.run(transport='stdio'))")
    print()


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("MCP Server Client Examples")
    print("=" * 70)
    print()
    
    example_server_setup()
    example_exposed_tools()
    example_client_usage()
    example_running_server()
    
    print("\n" + "=" * 70)
    print("How It Works")
    print("=" * 70)
    print()
    print("The framework exposes itself as an MCP server using FastMCP:")
    print()
    print("1. Configuration:")
    print("   - Loads config from config.yaml / .env / defaults")
    print("   - Or uses programmatic AppConfig")
    print("   - Creates AgentHelper with FilesystemHelper, SandboxExecutor, etc.")
    print()
    print("2. Tool Discovery:")
    print("   - Scans servers_dir/ directory (default: ./servers)")
    print("   - Each subdirectory = one MCP server")
    print("   - Each .py file = one tool")
    print("   - Tools are discovered by FilesystemHelper")
    print()
    print("3. MCP Server Setup:")
    print("   - Creates FastMCP instance with name 'Code Execution MCP'")
    print("   - Registers 6 tools using @mcp.tool() decorator:")
    print("     - execute_task: Main task execution")
    print("     - list_available_tools: Tool discovery")
    print("     - get_state/save_state: State management")
    print("     - list_servers/get_server_tools: Server introspection")
    print()
    print("4. Server Execution:")
    print("   - Runs with specified transport (stdio/sse/http)")
    print("   - Clients connect and call tools via MCP protocol")
    print("   - Each tool call uses the configured AgentHelper")
    print()
    print("The server wraps the framework's AgentHelper, so all framework")
    print("capabilities are available through the MCP interface.")
    print()
    print("📖 See README.md (MCP Server Configuration section) for detailed configuration guide.")
    print("=" * 70)

