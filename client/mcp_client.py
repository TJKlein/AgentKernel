"""MCP client implementation using FastMCP."""

import logging
from typing import Any, Dict, List, Optional

try:
    from fastmcp import FastMCP
except ImportError:
    FastMCP = None  # type: ignore

from client.base import MCPAdapter, ToolCall, ExecutionResult
from client.guardrails import GuardrailValidatorImpl
from config.schema import MCPServerConfig, GuardrailConfig

logger = logging.getLogger(__name__)


class MCPClient:
    """MCP client for connecting to MCP servers."""

    def __init__(
        self,
        server_config: MCPServerConfig,
        guardrail_config: Optional[GuardrailConfig] = None,
    ):
        """Initialize MCP client."""
        self.server_config = server_config
        self.guardrail_config = guardrail_config or GuardrailConfig()
        self.guardrail_validator = GuardrailValidatorImpl(self.guardrail_config)
        self._client: Optional[Any] = None
        self._connected = False

    def connect(self) -> None:
        """Connect to the MCP server."""
        if self._connected:
            return

        if FastMCP is None:
            raise ImportError("fastmcp is not installed. Install it with: pip install fastmcp")

        try:
            # Initialize FastMCP client based on connection type
            if self.server_config.connection_type == "sse":
                self._client = FastMCP(self.server_config.name)
                # SSE connection setup would go here
            elif self.server_config.connection_type == "stdio":
                self._client = FastMCP(self.server_config.name)
                # stdio connection setup would go here
            elif self.server_config.connection_type == "http":
                self._client = FastMCP(self.server_config.name)
                # HTTP connection setup would go here
            else:
                raise ValueError(
                    f"Unsupported connection type: {self.server_config.connection_type}"
                )

            self._connected = True
            logger.info(f"Connected to MCP server: {self.server_config.name}")

        except Exception as e:
            logger.error(f"Failed to connect to MCP server {self.server_config.name}: {e}")
            raise

    def disconnect(self) -> None:
        """Disconnect from the MCP server."""
        if self._client and self._connected:
            self._connected = False
            logger.info(f"Disconnected from MCP server: {self.server_config.name}")

    def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools from the server."""
        if not self._connected:
            self.connect()

        try:
            # FastMCP tool listing would go here
            # For now, return empty list as placeholder
            return []
        except Exception as e:
            logger.error(f"Failed to list tools from {self.server_config.name}: {e}")
            raise

    def call_tool(self, tool_name: str, parameters: Dict[str, Any], validate: bool = True) -> Any:
        """Call a tool on the MCP server."""
        if not self._connected:
            self.connect()

        tool_call = ToolCall(
            server_name=self.server_config.name, tool_name=tool_name, parameters=parameters
        )

        try:
            # Validate input with guardrails
            if validate:
                input_result = self.guardrail_validator.validate_input(
                    parameters, {"tool_name": tool_name}
                )
                if not input_result.valid:
                    raise ValueError(f"Input validation failed: {input_result.errors}")

                # Tokenize sensitive data
                parameters = self.guardrail_validator.tokenize_sensitive_data(parameters)

            # Call the tool via FastMCP
            # This is a placeholder - actual FastMCP integration would go here
            result = None  # Placeholder

            tool_call.result = result

            # Validate output with guardrails
            if validate:
                output_result = self.guardrail_validator.validate_output(
                    result, {"tool_name": tool_name}
                )
                if not output_result.valid:
                    logger.warning(f"Output validation warnings: {output_result.warnings}")

                # Untokenize sensitive data
                result = self.guardrail_validator.untokenize_sensitive_data(result)

            return result

        except Exception as e:
            tool_call.error = str(e)
            logger.error(f"Tool call failed: {tool_name} on {self.server_config.name}: {e}")
            raise


def call_mcp_tool(
    server_name: str,
    tool_name: str,
    parameters: Dict[str, Any],
    server_configs: Optional[List[MCPServerConfig]] = None,
) -> Any:
    """Convenience function to call an MCP tool."""
    if server_configs is None:
        server_configs = []

    # Find the server config
    server_config = next((s for s in server_configs if s.name == server_name), None)
    if not server_config:
        raise ValueError(f"MCP server '{server_name}' not found in configuration")

    client = MCPClient(server_config)
    client.connect()
    try:
        return client.call_tool(tool_name, parameters)
    finally:
        client.disconnect()


class MCPAdapterImpl:
    """Implementation of MCPAdapter protocol."""

    def __init__(self, client: MCPClient):
        """Initialize adapter with MCP client."""
        self.client = client

    def connect(self, connection_string: str) -> None:
        """Connect to an MCP server."""
        # Update server config with connection string
        self.client.server_config.url = connection_string
        self.client.connect()

    def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools from the server."""
        return self.client.list_tools()

    def call_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        """Call a tool on the server."""
        return self.client.call_tool(tool_name, parameters)

    def disconnect(self) -> None:
        """Disconnect from the server."""
        self.client.disconnect()
