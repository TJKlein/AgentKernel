#!/usr/bin/env python3
"""Example 12: Running Examples in MCP Client Mode.

This example demonstrates how to run framework examples by connecting
to the framework as an MCP server, rather than using it directly.

Prerequisites:
    1. Start the MCP server in a separate terminal:
       python -m code_execution_mcp.server
       
    2. Or set environment variables:
       export MCP_MODE=true
       export MCP_SERVER_URL=stdio://code-execution-mcp-server

This example shows:
    - How to connect to the MCP server
    - How to call tools via MCP protocol
    - How examples can work in both direct and MCP modes
"""

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from fastmcp import FastMCP
    HAS_FASTMCP = True
except ImportError:
    HAS_FASTMCP = False
    print("ERROR: fastmcp is not installed. Install with: pip install fastmcp")
    sys.exit(1)


class MCPFrameworkClient:
    """Client for connecting to Code Execution MCP framework as MCP server."""

    def __init__(self, server_command: Optional[list] = None):
        """Initialize MCP client.

        Args:
            server_command: Command to start server (for stdio transport)
                           Default: ["python", "-m", "code_execution_mcp.server", "stdio"]
        """
        self.server_command = server_command or [
            "python",
            "-m",
            "code_execution_mcp.server",
            "stdio",
        ]
        self.server_process: Optional[subprocess.Popen] = None
        self.client: Optional[FastMCP] = None

    def start_server(self) -> None:
        """Start the MCP server as a subprocess (for stdio transport)."""
        if self.server_process is None:
            print(f"Starting MCP server: {' '.join(self.server_command)}")
            self.server_process = subprocess.Popen(
                self.server_command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
            # Give server time to start
            time.sleep(1)
            print("✓ MCP server started")

    def stop_server(self) -> None:
        """Stop the MCP server."""
        if self.server_process:
            self.server_process.terminate()
            self.server_process.wait()
            self.server_process = None
            print("✓ MCP server stopped")

    def execute_task(
        self, task_description: str, verbose: bool = False
    ) -> Dict[str, Any]:
        """Execute a task via MCP server.

        Args:
            task_description: Task description
            verbose: Whether to print progress

        Returns:
            Dictionary with success, result, output, error keys
        """
        # Note: This is a conceptual implementation
        # Actual FastMCP client API may differ
        # For stdio transport, you'd send JSON-RPC messages
        
        # Example JSON-RPC request:
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "execute_task",
                "arguments": {
                    "task_description": task_description,
                    "verbose": verbose,
                },
            },
        }

        # In real implementation, send request via stdio and parse response
        # For now, this demonstrates the pattern
        print(f"\n[Would call MCP tool: execute_task]")
        print(f"  Task: {task_description}")
        print(f"  Verbose: {verbose}")
        
        # Placeholder response
        return {
            "success": False,
            "result": None,
            "output": "",
            "error": "MCP client implementation requires proper FastMCP client setup. "
                     "See FastMCP documentation for stdio transport details.",
        }

    def list_available_tools(self) -> Dict[str, list]:
        """List available tools via MCP server."""
        print("\n[Would call MCP tool: list_available_tools]")
        return {}

    def get_state(self, state_file: str = "state.json") -> Dict[str, Any]:
        """Get state via MCP server."""
        print(f"\n[Would call MCP tool: get_state]")
        print(f"  State file: {state_file}")
        return {"exists": False, "data": {}}


def example_direct_vs_mcp():
    """Compare direct mode vs MCP client mode."""
    print("=" * 70)
    print("Example: Direct Mode vs MCP Client Mode")
    print("=" * 70)
    print()

    print("DIRECT MODE (Current Examples):")
    print("  - Examples use framework directly")
    print("  - Import: from agentkernel import execute_task")
    print("  - Call: result, output, error = execute_task('task')")
    print("  - Pros: Simple, fast, no server needed")
    print("  - Cons: Framework must be installed locally")
    print()

    print("MCP CLIENT MODE (This Example):")
    print("  - Examples connect to framework as MCP server")
    print("  - Server runs separately: python -m code_execution_mcp.server")
    print("  - Client calls tools via MCP protocol")
    print("  - Pros: Server can run remotely, multiple clients, standardized protocol")
    print("  - Cons: More complex setup, requires server running")
    print()


def example_mcp_client_usage():
    """Show how to use MCP client."""
    print("=" * 70)
    print("Example: MCP Client Usage")
    print("=" * 70)
    print()

    print("Step 1: Start the MCP server (in separate terminal):")
    print("  python -m code_execution_mcp.server")
    print()

    print("Step 2: Connect from client:")
    print("  from fastmcp import FastMCP")
    print("  client = FastMCP('my-client')")
    print("  client.connect('stdio://code-execution-mcp-server')")
    print()

    print("Step 3: Call tools:")
    print("  result = client.call_tool('execute_task', {")
    print("      'task_description': 'Calculate 5 + 3',")
    print("      'verbose': False")
    print("  })")
    print()

    # Demonstrate conceptual usage
    try:
        client = MCPFrameworkClient()
        print("Step 4: Example client calls:")
        client.execute_task("Calculate 5 + 3", verbose=False)
        client.list_available_tools()
        client.get_state()
    except Exception as e:
        print(f"Note: Full implementation requires proper FastMCP client setup: {e}")
    print()


def example_environment_switching():
    """Show how to switch between modes using environment variables."""
    print("=" * 70)
    print("Example: Environment-Based Mode Switching")
    print("=" * 70)
    print()

    print("Run examples in direct mode (default):")
    print("  python examples/00_simple_api.py")
    print()

    print("Run examples in MCP client mode:")
    print("  # Terminal 1: Start server")
    print("  python -m code_execution_mcp.server")
    print()
    print("  # Terminal 2: Run example with MCP mode")
    print("  export MCP_MODE=true")
    print("  export MCP_SERVER_URL=stdio://code-execution-mcp-server")
    print("  python examples/00_simple_api.py")
    print()

    print("Or use the helper:")
    print("  from examples.mcp_client_helper import get_helper")
    print("  helper = get_helper()  # Auto-detects from MCP_MODE env var")
    print("  result, output, error = helper.execute_task('task')")
    print()


def example_hybrid_example():
    """Show how an example can work in both modes."""
    print("=" * 70)
    print("Example: Hybrid Example (Works in Both Modes)")
    print("=" * 70)
    print()

    print("Example code that works in both modes:")
    print()
    print("```python")
    print("import os")
    print("from examples.mcp_client_helper import get_helper")
    print()
    print("# Auto-detect mode from environment")
    print("helper = get_helper()")
    print()
    print("# Same API works in both modes")
    print("result, output, error = helper.execute_task('Calculate 5 + 3')")
    print("tools = helper.discover_tools()")
    print("```")
    print()

    print("To run in direct mode:")
    print("  python example.py")
    print()

    print("To run in MCP client mode:")
    print("  # Start server first")
    print("  python -m code_execution_mcp.server &")
    print("  # Then run example")
    print("  MCP_MODE=true python example.py")
    print()


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("Example 12: Running Examples in MCP Client Mode")
    print("=" * 70)
    print()

    example_direct_vs_mcp()
    example_mcp_client_usage()
    example_environment_switching()
    example_hybrid_example()

    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)
    print()
    print("Examples can run in two modes:")
    print()
    print("1. DIRECT MODE (default):")
    print("   - Use framework directly")
    print("   - Import: from agentkernel import execute_task")
    print("   - No server needed")
    print()
    print("2. MCP CLIENT MODE:")
    print("   - Connect to framework as MCP server")
    print("   - Server runs separately")
    print("   - Use MCP protocol to call tools")
    print("   - Set MCP_MODE=true environment variable")
    print()
    print("To enable MCP mode for examples:")
    print("  1. Start server: python -m code_execution_mcp.server")
    print("  2. Set env var: export MCP_MODE=true")
    print("  3. Run example: python examples/00_simple_api.py")
    print()
    print("See examples/mcp_client_helper.py for helper utilities.")
    print("=" * 70)

