"""Helper for running examples in MCP client mode.

This module provides a wrapper that allows examples to work in two modes:
1. Direct mode: Uses framework directly (default)
2. MCP client mode: Connects to MCP server and calls tools via MCP protocol

Usage:
    # Direct mode (default)
    from examples.mcp_client_helper import MCPExampleHelper
    helper = MCPExampleHelper()
    result, output, error = helper.execute_task("Calculate 5 + 3")
    
    # MCP client mode
    helper = MCPExampleHelper(mcp_mode=True, server_url="stdio://code-execution-mcp-server")
    result, output, error = helper.execute_task("Calculate 5 + 3")
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from fastmcp import FastMCP
    HAS_FASTMCP = True
except ImportError:
    HAS_FASTMCP = False
    FastMCP = None  # type: ignore

try:
    from agentkernel import create_agent, execute_task
    HAS_FRAMEWORK = True
except ImportError:
    HAS_FRAMEWORK = False


class MCPExampleHelper:
    """Helper class that allows examples to work in both direct and MCP client modes."""

    def __init__(
        self,
        mcp_mode: bool = False,
        server_url: Optional[str] = None,
        transport: str = "stdio",
    ):
        """Initialize helper.

        Args:
            mcp_mode: If True, use MCP client mode. If False, use direct framework mode.
            server_url: MCP server URL (e.g., "stdio://code-execution-mcp-server")
            transport: Transport type ("stdio", "sse", or "http")
        """
        self.mcp_mode = mcp_mode
        self.server_url = server_url
        self.transport = transport
        
        if mcp_mode:
            if not HAS_FASTMCP:
                raise ImportError(
                    "fastmcp is required for MCP client mode. "
                    "Install with: pip install fastmcp"
                )
            self._init_mcp_client()
        else:
            if not HAS_FRAMEWORK:
                raise ImportError(
                    "Framework is required for direct mode. "
                    "Install with: pip install -e ."
                )
            self._init_direct_mode()

    def _init_mcp_client(self) -> None:
        """Initialize MCP client."""
        self.client = FastMCP("example-client")
        # Note: Actual connection would happen when calling tools
        # For stdio, we'd need subprocess management
        self._connected = False

    def _init_direct_mode(self) -> None:
        """Initialize direct framework mode."""
        self.agent = None  # Lazy initialization

    def _ensure_agent(self) -> None:
        """Ensure agent is initialized in direct mode."""
        if self.agent is None:
            self.agent = create_agent()

    def execute_task(
        self,
        task_description: str,
        verbose: bool = False,
    ) -> Tuple[Any, str, Optional[str]]:
        """Execute a task.

        Args:
            task_description: Description of the task
            verbose: Whether to print progress

        Returns:
            Tuple of (result, output, error)
        """
        if self.mcp_mode:
            return self._execute_task_mcp(task_description, verbose)
        else:
            return self._execute_task_direct(task_description, verbose)

    def _execute_task_direct(
        self,
        task_description: str,
        verbose: bool = False,
    ) -> Tuple[Any, str, Optional[str]]:
        """Execute task using direct framework."""
        self._ensure_agent()
        return self.agent.execute_task(task_description, verbose=verbose)

    def _execute_task_mcp(
        self,
        task_description: str,
        verbose: bool = False,
    ) -> Tuple[Any, str, Optional[str]]:
        """Execute task via MCP server."""
        # For stdio transport, we'd need to manage subprocess
        # For now, this is a placeholder showing the pattern
        # In practice, you'd use FastMCP client properly
        
        # This is a conceptual implementation
        # Actual implementation would depend on FastMCP client API
        try:
            # Connect if not connected
            if not self._connected:
                # In real implementation, connect to server
                # For stdio: subprocess.Popen(["python", "-m", "code_execution_mcp.server"])
                # For sse/http: client.connect(server_url)
                self._connected = True

            # Call execute_task tool via MCP
            # result = self.client.call_tool("execute_task", {
            #     "task_description": task_description,
            #     "verbose": verbose,
            # })
            
            # For now, return a placeholder
            # In real implementation, parse MCP response
            raise NotImplementedError(
                "MCP client mode requires proper FastMCP client implementation. "
                "See examples/12_mcp_client_example.py for a working example."
            )
        except Exception as e:
            return None, "", str(e)

    def discover_tools(self, verbose: bool = False) -> Dict[str, List[str]]:
        """Discover available tools.

        Args:
            verbose: Whether to print progress

        Returns:
            Dictionary mapping server names to tool names
        """
        if self.mcp_mode:
            return self._discover_tools_mcp(verbose)
        else:
            return self._discover_tools_direct(verbose)

    def _discover_tools_direct(self, verbose: bool = False) -> Dict[str, List[str]]:
        """Discover tools using direct framework."""
        self._ensure_agent()
        return self.agent.discover_tools(verbose=verbose)

    def _discover_tools_mcp(self, verbose: bool = False) -> Dict[str, List[str]]:
        """Discover tools via MCP server."""
        # Call list_available_tools via MCP
        # result = self.client.call_tool("list_available_tools", {})
        # return result
        raise NotImplementedError(
            "MCP client mode requires proper FastMCP client implementation."
        )


def get_helper(mcp_mode: Optional[bool] = None) -> MCPExampleHelper:
    """Get helper instance, auto-detecting mode from environment.

    Args:
        mcp_mode: Force MCP mode if True, direct mode if False, auto-detect if None

    Returns:
        MCPExampleHelper instance
    """
    if mcp_mode is None:
        # Auto-detect from environment
        mcp_mode = os.environ.get("MCP_MODE", "false").lower() == "true"
        server_url = os.environ.get("MCP_SERVER_URL")
    else:
        server_url = None

    return MCPExampleHelper(mcp_mode=mcp_mode, server_url=server_url)

