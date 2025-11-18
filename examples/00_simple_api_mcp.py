#!/usr/bin/env python3
"""Example 0 (MCP Mode): Simple API Usage via MCP Server.

This is the MCP client version of 00_simple_api.py.
It demonstrates the same functionality but connects to the framework
as an MCP server instead of using it directly.

Prerequisites:
    1. MCP server must be running:
       python -m code_execution_mcp.server
       
    2. Or set environment variables:
       export MCP_MODE=true
       export MCP_SERVER_URL=stdio://code-execution-mcp-server

Usage:
    # Terminal 1: Start server
    python -m code_execution_mcp.server
    
    # Terminal 2: Run this example
    python examples/00_simple_api_mcp.py
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from fastmcp import FastMCP
    HAS_FASTMCP = True
except ImportError:
    HAS_FASTMCP = False
    print("ERROR: fastmcp is not installed. Install with: pip install fastmcp")
    sys.exit(1)


def call_mcp_tool(client: FastMCP, tool_name: str, arguments: dict) -> dict:
    """Call an MCP tool (conceptual implementation).
    
    Note: Actual implementation depends on FastMCP client API.
    This is a placeholder showing the pattern.
    """
    print(f"[MCP Call] {tool_name}({arguments})")
    # In real implementation:
    # return client.call_tool(tool_name, arguments)
    
    # For demonstration, return placeholder
    return {
        "success": False,
        "error": "This is a demonstration. Actual MCP client implementation "
                 "requires proper FastMCP client setup. See FastMCP docs.",
    }


def main() -> None:
    """Run simple API example in MCP mode."""
    print("=" * 60)
    print("Example 0 (MCP Mode): Simple API Usage via MCP Server")
    print("=" * 60)
    print()

    # Check if MCP mode is enabled
    mcp_mode = os.environ.get("MCP_MODE", "false").lower() == "true"
    if not mcp_mode:
        print("⚠️  MCP_MODE not set. This example requires MCP mode.")
        print("   Set: export MCP_MODE=true")
        print("   Or start server and set environment variable.")
        print()
        print("   This example demonstrates MCP client usage.")
        print("   For direct framework usage, see: examples/00_simple_api.py")
        print()

    # Create MCP client
    print("Creating MCP client...")
    client = FastMCP("example-client")
    
    # Note: Actual connection would be:
    # client.connect("stdio://code-execution-mcp-server")
    # For this demo, we'll show the pattern
    
    print("✓ MCP client created")
    print()

    # Option 1: Execute a simple task
    print("--- Option 1: Execute task via MCP ---")
    result = call_mcp_tool(
        client,
        "execute_task",
        {
            "task_description": "Calculate 5 + 3",
            "verbose": True,
        },
    )
    
    if result.get("success"):
        print(f"Result: {result.get('result')}")
        print(f"Output: {result.get('output')}")
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")
        print("(This is expected - see note above about implementation)")

    # Option 2: List available tools
    print("\n--- Option 2: List available tools via MCP ---")
    tools_result = call_mcp_tool(client, "list_available_tools", {})
    print(f"Tools: {tools_result}")

    # Option 3: Get state
    print("\n--- Option 3: Get state via MCP ---")
    state_result = call_mcp_tool(client, "get_state", {"state_file": "state.json"})
    print(f"State: {state_result}")

    print("\n" + "=" * 60)
    print("Example completed!")
    print("=" * 60)
    print()
    print("Note: This is a demonstration of MCP client usage.")
    print("For a working implementation, see FastMCP client documentation.")
    print()
    print("To use the framework directly (not via MCP), see:")
    print("  examples/00_simple_api.py")


if __name__ == "__main__":
    main()

