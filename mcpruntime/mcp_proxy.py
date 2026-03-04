"""MCP Proxy Tools - Proxy tools from other MCP servers.

This module provides utilities to connect to other MCP servers and proxy
their tools through the code-execution-mcp framework.
"""

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional

try:
    from fastmcp import Client
    from fastmcp.client.transports import StreamableHttpTransport
except ImportError:
    Client = None
    StreamableHttpTransport = None

logger = logging.getLogger(__name__)


class MCPProxy:
    """Proxy for connecting to external MCP servers and exposing their tools."""

    def __init__(
        self,
        server_url: str,
        server_name: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ):
        """Initialize MCP proxy.

        Args:
            server_url: URL of the external MCP server (e.g., "http://localhost:8000/mcp/")
            server_name: Optional name for the server (defaults to URL-based name)
            headers: Optional headers to include in requests (e.g., Authorization)
        """
        if Client is None or StreamableHttpTransport is None:
            raise ImportError(
                "fastmcp is required for MCP proxy. Install with: pip install fastmcp"
            )

        self.server_url = server_url.rstrip("/") + "/"  # Ensure trailing slash
        self.server_name = server_name or f"proxy_{server_url.split('/')[-2]}"
        self.headers = headers or {}
        self._client: Optional[Client] = None
        self._transport: Optional[StreamableHttpTransport] = None
        self._tools_cache: Optional[List[Dict[str, Any]]] = None

    async def _ensure_connected(self):
        """Ensure connection to external MCP server."""
        if self._client is None:
            self._transport = StreamableHttpTransport(
                url=self.server_url, headers=self.headers
            )
            self._client = Client(self._transport)
            await self._client.__aenter__()

    async def list_tools(self) -> List[Dict[str, Any]]:
        """List all tools available from the external MCP server.

        Returns:
            List of tool definitions
        """
        await self._ensure_connected()
        if self._tools_cache is None:
            tools = await self._client.list_tools()
            self._tools_cache = tools
        return self._tools_cache

    async def call_tool(self, tool_name: str, **kwargs) -> Any:
        """Call a tool on the external MCP server.

        Args:
            tool_name: Name of the tool to call
            **kwargs: Tool parameters

        Returns:
            Tool result
        """
        await self._ensure_connected()
        result = await self._client.call_tool_mcp(tool_name, kwargs)
        # Extract text content from result
        if hasattr(result, "content") and result.content:
            import json
            return json.loads(result.content[0].text)
        return result

    def create_proxy_tools(self) -> List[Callable]:
        """Create proxy tool functions for all tools from the external server.

        Returns:
            List of async tool functions that can be registered with MCPServer
        """
        tools = []

        async def _create_proxy_tool(tool_name: str, tool_info: Dict[str, Any]):
            """Create a proxy tool function for a specific tool."""

            async def proxy_tool(**kwargs):
                """Proxy tool that forwards calls to external MCP server."""
                try:
                    return await self.call_tool(tool_name, **kwargs)
                except Exception as e:
                    logger.error(f"Error calling proxy tool {tool_name}: {e}")
                    raise

            # Set function metadata
            proxy_tool.__name__ = f"{self.server_name}_{tool_name}"
            proxy_tool.__doc__ = tool_info.get("description", f"Proxy for {tool_name}")

            return proxy_tool

        # Note: This requires async initialization, so we'll use a different approach
        return tools


async def create_proxy_tools_from_server(
    server_url: str,
    server_name: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
) -> List[Callable]:
    """Create proxy tools from an external MCP server.

    This function connects to an external MCP server, discovers its tools,
    and creates proxy functions that can be registered with MCPServer.

    Args:
        server_url: URL of the external MCP server
        server_name: Optional name prefix for tools (defaults to URL-based)
        headers: Optional headers (e.g., {"Authorization": "Bearer token"})

    Returns:
        List of tool functions ready to register

    Example:
        # Create proxy tools from external server
        proxy_tools = await create_proxy_tools_from_server(
            "http://localhost:8000/mcp/",
            server_name="external",
            headers={"Authorization": "Bearer token"}
        )

        # Register with server
        server = create_server()
        for tool in proxy_tools:
            server.register_tool(tool)
    """
    proxy = MCPProxy(server_url, server_name, headers)

    # Connect and discover tools
    await proxy._ensure_connected()
    tools_info = await proxy.list_tools()

    proxy_tools = []

    for tool_info in tools_info:
        tool_name = tool_info.get("name", "")
        tool_description = tool_info.get("description", f"Proxy for {tool_name} from {server_url}")

        # Create proxy function with proper closure
        def make_proxy_func(name: str, desc: str):
            """Factory function to create proxy with proper closure."""
            async def proxy_func(**kwargs):
                """Proxy tool function."""
                try:
                    return await proxy.call_tool(name, **kwargs)
                except Exception as e:
                    logger.error(f"Error calling proxy tool {name}: {e}")
                    raise
            
            proxy_func.__name__ = f"{server_name}_{name}" if server_name else name
            proxy_func.__doc__ = desc
            return proxy_func

        proxy_tool = make_proxy_func(tool_name, tool_description)
        proxy_tools.append(proxy_tool)

    return proxy_tools


def create_simple_proxy_tool(
    server_url: str,
    tool_name: str,
    proxy_name: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
) -> Callable:
    """Create a simple proxy tool for a specific tool from an external server.

    This is a synchronous wrapper that creates an async proxy tool.

    Args:
        server_url: URL of the external MCP server
        tool_name: Name of the tool to proxy
        proxy_name: Optional name for the proxy tool (defaults to tool_name)
        headers: Optional headers

    Returns:
        Async tool function ready to register

    Example:
        # Create proxy for specific tool
        weather_tool = create_simple_proxy_tool(
            "http://localhost:8000/mcp/",
            "get_weather",
            proxy_name="external_weather"
        )

        server.register_tool(weather_tool)
    """
    proxy = MCPProxy(server_url, headers=headers)

    async def proxy_tool(**kwargs):
        """Proxy tool function."""
        await proxy._ensure_connected()
        return await proxy.call_tool(tool_name, **kwargs)

    proxy_tool.__name__ = proxy_name or tool_name
    proxy_tool.__doc__ = f"Proxy for {tool_name} from {server_url}"

    return proxy_tool

