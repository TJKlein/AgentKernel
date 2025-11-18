"""MCP Server implementation using FastMCP.

This module provides an MCP server that exposes the Code Execution MCP framework
as an MCP server, allowing other MCP clients to use the framework's capabilities.
"""

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional

try:
    from fastmcp import FastMCP
except ImportError:
    FastMCP = None  # type: ignore

from client.agent_helper import AgentHelper
from client.filesystem_helpers import FilesystemHelper
from client.sandbox_executor import SandboxExecutor
from config.loader import load_config
from config.schema import AppConfig

logger = logging.getLogger(__name__)


class MCPServer:
    """MCP Server that exposes Code Execution MCP framework capabilities."""

    def __init__(
        self,
        config: Optional[AppConfig] = None,
        agent: Optional[AgentHelper] = None,
        custom_tools: Optional[List[Callable]] = None,
    ):
        """Initialize MCP server.

        Args:
            config: Optional AppConfig (loads from config.yaml/.env if None)
            agent: Optional AgentHelper instance (creates default if None)
            custom_tools: Optional list of callable functions to register as MCP tools
        """
        if FastMCP is None:
            raise ImportError("fastmcp is not installed. Install it with: pip install fastmcp")

        self.config = config or load_config()
        self.agent = agent or self._create_agent()
        self.mcp = FastMCP("Code Execution MCP")
        self._setup_tools()
        
        # Register custom tools if provided
        if custom_tools:
            self.register_tools(custom_tools)

    def _create_agent(self) -> AgentHelper:
        """Create a default AgentHelper instance."""
        fs_helper = FilesystemHelper(
            workspace_dir=self.config.execution.workspace_dir,
            servers_dir=self.config.execution.servers_dir,
            skills_dir=self.config.execution.skills_dir,
        )

        executor = SandboxExecutor(
            execution_config=self.config.execution,
            guardrail_config=self.config.guardrails,
            optimization_config=self.config.optimizations,
        )

        return AgentHelper(
            fs_helper,
            executor,
            optimization_config=self.config.optimizations,
            llm_config=self.config.llm,
        )

    def _setup_tools(self) -> None:
        """Register MCP tools."""

        @self.mcp.tool()
        def execute_task(
            task_description: str,
            verbose: bool = False,
        ) -> Dict[str, Any]:
            """Execute a task using the Code Execution MCP framework.

            Args:
                task_description: Description of the task to execute
                verbose: Whether to print progress information

            Returns:
                Dictionary with 'result', 'output', and 'error' keys
            """
            try:
                result, output, error = self.agent.execute_task(
                    task_description=task_description,
                    verbose=verbose,
                )
                return {
                    "success": error is None,
                    "result": result,
                    "output": output,
                    "error": error,
                }
            except Exception as e:
                logger.error(f"Error executing task: {e}", exc_info=True)
                return {
                    "success": False,
                    "result": None,
                    "output": "",
                    "error": str(e),
                }

        @self.mcp.tool()
        def list_available_tools() -> Dict[str, List[str]]:
            """List all available tools from the servers directory.

            Returns:
                Dictionary mapping server names to lists of tool names
            """
            try:
                tools = self.agent.discover_tools(verbose=False)
                return tools
            except Exception as e:
                logger.error(f"Error listing tools: {e}", exc_info=True)
                return {}

        @self.mcp.tool()
        def get_state(state_file: str = "state.json") -> Dict[str, Any]:
            """Get the current state from the workspace.

            Args:
                state_file: Name of the state file to read

            Returns:
                Dictionary containing the state data
            """
            try:
                import json
                from pathlib import Path

                state_path = Path(self.config.execution.workspace_dir) / state_file
                if not state_path.exists():
                    return {"exists": False, "data": {}}

                with open(state_path, "r") as f:
                    data = json.load(f)

                return {"exists": True, "data": data}
            except Exception as e:
                logger.error(f"Error reading state: {e}", exc_info=True)
                return {"exists": False, "error": str(e), "data": {}}

        @self.mcp.tool()
        def save_state(
            state_data: Dict[str, Any],
            state_file: str = "state.json",
        ) -> Dict[str, Any]:
            """Save state to the workspace.

            Args:
                state_data: Dictionary containing state data to save
                state_file: Name of the state file to write

            Returns:
                Dictionary with success status
            """
            try:
                import json
                from pathlib import Path

                state_path = Path(self.config.execution.workspace_dir) / state_file
                state_path.parent.mkdir(parents=True, exist_ok=True)

                with open(state_path, "w") as f:
                    json.dump(state_data, f, indent=2)

                return {"success": True, "file": str(state_path)}
            except Exception as e:
                logger.error(f"Error saving state: {e}", exc_info=True)
                return {"success": False, "error": str(e)}

        @self.mcp.tool()
        def list_servers() -> List[str]:
            """List all available server directories.

            Returns:
                List of server names
            """
            try:
                servers = self.agent.fs_helper.list_servers()
                return servers
            except Exception as e:
                logger.error(f"Error listing servers: {e}", exc_info=True)
                return []

        @self.mcp.tool()
        def get_server_tools(server_name: str) -> List[str]:
            """List tools available in a specific server.

            Args:
                server_name: Name of the server

            Returns:
                List of tool names
            """
            try:
                tools = self.agent.fs_helper.list_tools(server_name)
                return tools
            except Exception as e:
                logger.error(f"Error listing tools for server {server_name}: {e}", exc_info=True)
                return []

        @self.mcp.tool()
        def search_tools(
            query: str,
            detail_level: str = "name",
            max_results: int = 10,
        ) -> Dict[str, Any]:
            """Search for relevant tools using semantic search.

            This tool allows agents to find relevant tool definitions without loading
            all tool descriptions upfront, enabling progressive disclosure.

            Args:
                query: Search query describing what tools are needed
                detail_level: Level of detail to return
                    - "name": Tool names only (most efficient)
                    - "description": Tool names and descriptions
                    - "full": Full tool definitions with schemas
                max_results: Maximum number of results to return

            Returns:
                Dictionary with search results based on detail_level
            """
            try:
                # Discover all tools
                discovered_servers = self.agent.discover_tools(verbose=False)
                
                # Get tool descriptions
                tool_descriptions = self.agent._get_tool_descriptions(discovered_servers)
                
                # Use semantic search to find relevant tools
                selected_tools = self.agent.tool_selector.select_tools(
                    query,
                    tool_descriptions,
                    use_gpu=self.config.optimizations.gpu_embeddings if self.config.optimizations.enabled else False,
                )
                
                # Format results based on detail_level
                if detail_level == "name":
                    # Return just tool names grouped by server
                    return selected_tools
                
                elif detail_level == "description":
                    # Return tool names with descriptions
                    result = {}
                    for server_name, tool_names in selected_tools.items():
                        result[server_name] = {}
                        for tool_name in tool_names[:max_results]:
                            key = (server_name, tool_name)
                            if key in tool_descriptions:
                                result[server_name][tool_name] = {
                                    "description": tool_descriptions[key],
                                }
                    return result
                
                elif detail_level == "full":
                    # Return full tool definitions
                    result = {}
                    for server_name, tool_names in selected_tools.items():
                        result[server_name] = {}
                        for tool_name in tool_names[:max_results]:
                            tool_code = self.agent.fs_helper.read_tool_file(server_name, tool_name)
                            if tool_code:
                                result[server_name][tool_name] = {
                                    "code": tool_code,
                                    "description": tool_descriptions.get((server_name, tool_name), ""),
                                }
                    return result
                
                else:
                    return {
                        "error": f"Invalid detail_level: {detail_level}. Must be 'name', 'description', or 'full'"
                    }
                    
            except Exception as e:
                logger.error(f"Error searching tools: {e}", exc_info=True)
                return {"error": str(e)}

    def register_tool(self, tool_func: Callable, name: Optional[str] = None) -> None:
        """Register a custom tool programmatically.

        Args:
            tool_func: Callable function to register as an MCP tool
            name: Optional tool name (defaults to function name)

        Example:
            def my_custom_tool(param: str) -> str:
                \"\"\"My custom tool.\"\"\"
                return f"Result: {param}"

            server.register_tool(my_custom_tool)
        """
        if name:
            # Register with custom name
            tool_func.__name__ = name
        self.mcp.tool()(tool_func)
        logger.info(f"Registered custom tool: {tool_func.__name__}")

    def register_tools(self, tools: List[Callable]) -> None:
        """Register multiple custom tools programmatically.

        Args:
            tools: List of callable functions to register as MCP tools

        Example:
            def tool1(x: int) -> int:
                return x * 2

            def tool2(text: str) -> str:
                return text.upper()

            server.register_tools([tool1, tool2])
        """
        for tool in tools:
            self.register_tool(tool)
        logger.info(f"Registered {len(tools)} custom tools")

    async def run(self, transport: str = "stdio") -> None:
        """Run the MCP server.

        Args:
            transport: Transport type ('stdio', 'sse', or 'http')
        """
        if transport == "stdio":
            await self.mcp.run(transport="stdio")
        elif transport == "sse":
            await self.mcp.run(transport="sse")
        elif transport == "http":
            await self.mcp.run(transport="http")
        else:
            raise ValueError(f"Unsupported transport: {transport}")


def create_server(
    config: Optional[AppConfig] = None,
    agent: Optional[AgentHelper] = None,
    custom_tools: Optional[List[Callable]] = None,
) -> MCPServer:
    """Create an MCP server instance.

    Args:
        config: Optional AppConfig (loads from config.yaml/.env if None)
        agent: Optional AgentHelper instance (creates default if None)
        custom_tools: Optional list of callable functions to register as MCP tools

    Returns:
        MCPServer instance

    Example:
        def my_tool(param: str) -> str:
            return f"Result: {param}"

        server = create_server(custom_tools=[my_tool])
    """
    return MCPServer(config=config, agent=agent, custom_tools=custom_tools)


def run_server(
    transport: str = "stdio",
    config: Optional[AppConfig] = None,
    agent: Optional[AgentHelper] = None,
) -> None:
    """Run the MCP server (blocking).

    Args:
        transport: Transport type ('stdio', 'sse', or 'http')
        config: Optional AppConfig (loads from config.yaml/.env if None)
        agent: Optional AgentHelper instance (creates default if None)
    """
    server = create_server(config=config, agent=agent)
    asyncio.run(server.run(transport=transport))


if __name__ == "__main__":
    # Allow running as a script
    import sys

    transport = sys.argv[1] if len(sys.argv) > 1 else "stdio"
    run_server(transport=transport)

