#!/usr/bin/env python3
"""Example 13: Adding Tools Programmatically to MCP Server.

This example demonstrates how to add custom tools to the MCP server
programmatically, without needing to create files in the servers/ directory.

Prerequisites:
    - Framework installed
    - Optional: MCP server running (for testing)
"""

import sys
from pathlib import Path
from typing import Any, Dict

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agentkernel import create_server


def example_register_single_tool():
    """Example: Register a single custom tool."""
    print("=" * 70)
    print("Example: Register Single Custom Tool")
    print("=" * 70)
    print()

    # Define a custom tool function
    def greet(name: str) -> str:
        """Greet someone by name.
        
        Args:
            name: Name of the person to greet
            
        Returns:
            Greeting message
        """
        return f"Hello, {name}! Welcome to the MCP server."

    # Create server and register the tool
    print("Creating server...")
    server = create_server()
    
    print("Registering custom tool...")
    server.register_tool(greet)
    
    print("✓ Tool 'greet' registered successfully!")
    print()
    print("The tool can now be called via MCP protocol:")
    print("  client.call_tool('greet', {'name': 'Alice'})")
    print()


def example_register_multiple_tools():
    """Example: Register multiple custom tools."""
    print("=" * 70)
    print("Example: Register Multiple Custom Tools")
    print("=" * 70)
    print()

    # Define multiple custom tools
    def calculate_square(x: float) -> float:
        """Calculate the square of a number.
        
        Args:
            x: Number to square
            
        Returns:
            Square of x
        """
        return x * x

    def reverse_string(text: str) -> str:
        """Reverse a string.
        
        Args:
            text: String to reverse
            
        Returns:
            Reversed string
        """
        return text[::-1]

    def get_info() -> Dict[str, Any]:
        """Get server information.
        
        Returns:
            Dictionary with server info
        """
        return {
            "name": "Code Execution MCP",
            "version": "0.1.0",
            "tools": ["calculate_square", "reverse_string", "get_info"],
        }

    # Create server and register all tools at once
    print("Creating server...")
    server = create_server()
    
    print("Registering multiple tools...")
    server.register_tools([calculate_square, reverse_string, get_info])
    
    print("✓ Registered 3 custom tools:")
    print("  - calculate_square")
    print("  - reverse_string")
    print("  - get_info")
    print()


def example_register_at_creation():
    """Example: Register tools when creating the server."""
    print("=" * 70)
    print("Example: Register Tools at Server Creation")
    print("=" * 70)
    print()

    # Define tools
    def multiply(a: float, b: float) -> float:
        """Multiply two numbers."""
        return a * b

    def divide(a: float, b: float) -> float:
        """Divide two numbers."""
        if b == 0:
            raise ValueError("Division by zero")
        return a / b

    # Register tools when creating server
    print("Creating server with custom tools...")
    server = create_server(custom_tools=[multiply, divide])
    
    print("✓ Server created with 2 custom tools:")
    print("  - multiply")
    print("  - divide")
    print()


def example_dynamic_tool_registration():
    """Example: Register tools dynamically after server creation."""
    print("=" * 70)
    print("Example: Dynamic Tool Registration")
    print("=" * 70)
    print()

    # Create server
    server = create_server()
    
    # Register tools dynamically based on conditions
    if True:  # Some condition
        def conditional_tool(value: int) -> int:
            """A conditionally registered tool."""
            return value * 2
        
        server.register_tool(conditional_tool)
        print("✓ Conditionally registered tool: conditional_tool")
    
    # Register tools from a list
    tool_functions = []
    
    def tool_a(x: str) -> str:
        return f"A: {x}"
    
    def tool_b(x: str) -> str:
        return f"B: {x}"
    
    tool_functions.extend([tool_a, tool_b])
    
    if tool_functions:
        server.register_tools(tool_functions)
        print(f"✓ Registered {len(tool_functions)} tools from list")
    print()


def example_tool_with_server_access():
    """Example: Tool that accesses server internals."""
    print("=" * 70)
    print("Example: Tool with Server Access")
    print("=" * 70)
    print()

    # Create server first
    server = create_server()
    
    # Define a tool that uses server's agent
    def get_server_stats() -> Dict[str, Any]:
        """Get statistics about the server.
        
        Returns:
            Dictionary with server statistics
        """
        # Access server's agent to get tool information
        tools = server.agent.discover_tools(verbose=False)
        total_tools = sum(len(t) for t in tools.values())
        
        return {
            "framework_tools": total_tools,
            "servers": list(tools.keys()),
            "workspace_dir": str(server.config.execution.workspace_dir),
        }
    
    # Register the tool (using closure to access server)
    server.register_tool(get_server_stats)
    
    print("✓ Registered tool 'get_server_stats' that accesses server internals")
    print("  This tool can access:")
    print("  - server.agent (AgentHelper)")
    print("  - server.config (AppConfig)")
    print("  - server.mcp (FastMCP instance)")
    print()


def example_tool_naming():
    """Example: Register tool with custom name."""
    print("=" * 70)
    print("Example: Custom Tool Names")
    print("=" * 70)
    print()

    server = create_server()
    
    def my_function(x: int) -> int:
        """A function with a generic name."""
        return x + 1
    
    # Register with default name (function name)
    server.register_tool(my_function)
    print("✓ Registered as 'my_function' (default name)")
    
    # Register with custom name
    def another_function(x: int) -> int:
        """Another function."""
        return x * 2
    
    server.register_tool(another_function, name="custom_multiply")
    print("✓ Registered as 'custom_multiply' (custom name)")
    print()


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("Example 13: Adding Tools Programmatically to MCP Server")
    print("=" * 70)
    print()

    example_register_single_tool()
    example_register_multiple_tools()
    example_register_at_creation()
    example_dynamic_tool_registration()
    example_tool_with_server_access()
    example_tool_naming()

    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)
    print()
    print("Ways to add tools programmatically:")
    print()
    print("1. Register single tool after creation:")
    print("   server.register_tool(my_function)")
    print()
    print("2. Register multiple tools after creation:")
    print("   server.register_tools([tool1, tool2, tool3])")
    print()
    print("3. Register tools at server creation:")
    print("   server = create_server(custom_tools=[tool1, tool2])")
    print()
    print("4. Register with custom name:")
    print("   server.register_tool(my_function, name='custom_name')")
    print()
    print("Tools can:")
    print("  - Access server internals (server.agent, server.config)")
    print("  - Be registered dynamically based on conditions")
    print("  - Have custom names")
    print("  - Use type hints for automatic schema generation")
    print()
    print("=" * 70)

