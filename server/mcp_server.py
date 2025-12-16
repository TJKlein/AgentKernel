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
from client.task_manager import TaskManager
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
        self.task_manager = TaskManager(self.agent)  # Initialize async middleware
        self.mcp = FastMCP("AgentKernel")  # Updated branding
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
            """Search for relevant tools using progressive disclosure.

            This tool enables progressive disclosure by only loading what's needed:
            - "name": Fast keyword search on tool names only (no file loading)
            - "description": Semantic search on metadata only (no full code loading)
            - "full": Loads only matching tool definitions (lazy loading)

            Args:
                query: Search query describing what tools are needed
                detail_level: Level of detail to return
                    - "name": Tool names only (most efficient, no file loading)
                    - "description": Tool names and descriptions (metadata only)
                    - "full": Full tool definitions with schemas (loads only matches)
                max_results: Maximum number of results to return

            Returns:
                Dictionary with search results based on detail_level
            """
            try:
                from code_execution_mcp.client.tool_metadata import ToolMetadataIndex

                metadata_index = ToolMetadataIndex(self.agent.fs_helper.servers_dir)

                if detail_level == "name":
                    # PROGRESSIVE DISCLOSURE: Fast keyword search, no file loading
                    # Only searches tool names, doesn't load any files
                    return metadata_index.search_tool_names(query, max_results=max_results)

                elif detail_level == "description":
                    # PROGRESSIVE DISCLOSURE: Semantic search on metadata only
                    # Extracts descriptions from files but doesn't load full code
                    # First, get all metadata (still efficient - only reads docstrings)
                    all_metadata = metadata_index.get_all_tool_metadata()

                    # Convert to format expected by tool_selector
                    tool_descriptions = {
                        key: f"{meta['server']} {meta['name']}: {meta['description']}"
                        for key, meta in all_metadata.items()
                    }

                    # Use semantic search to find relevant tools
                    selected_tools = self.agent.tool_selector.select_tools(
                        query,
                        tool_descriptions,
                        use_gpu=(
                            self.config.optimizations.gpu_embeddings
                            if self.config.optimizations.enabled
                            else False
                        ),
                    )

                    # Return tool names with descriptions (from metadata, not full code)
                    result = {}
                    for server_name, tool_names in selected_tools.items():
                        result[server_name] = {}
                        for tool_name in tool_names[:max_results]:
                            metadata = metadata_index.get_tool_metadata(server_name, tool_name)
                            if metadata:
                                result[server_name][tool_name] = {
                                    "description": metadata.get("description", ""),
                                }
                    return result

                elif detail_level == "full":
                    # PROGRESSIVE DISCLOSURE: Load only matching tools
                    # First, do semantic search on metadata (doesn't load full code)
                    all_metadata = metadata_index.get_all_tool_metadata()

                    tool_descriptions = {
                        key: f"{meta['server']} {meta['name']}: {meta['description']}"
                        for key, meta in all_metadata.items()
                    }

                    # Use semantic search to find relevant tools
                    selected_tools = self.agent.tool_selector.select_tools(
                        query,
                        tool_descriptions,
                        use_gpu=(
                            self.config.optimizations.gpu_embeddings
                            if self.config.optimizations.enabled
                            else False
                        ),
                    )

                    # NOW load only the matching tool files (lazy loading)
                    result = {}
                    for server_name, tool_names in selected_tools.items():
                        result[server_name] = {}
                        for tool_name in tool_names[:max_results]:
                            tool_code = self.agent.fs_helper.read_tool_file(server_name, tool_name)
                            if tool_code:
                                metadata = metadata_index.get_tool_metadata(server_name, tool_name)
                                result[server_name][tool_name] = {
                                    "code": tool_code,
                                    "description": (
                                        metadata.get("description", "") if metadata else ""
                                    ),
                                }
                    return result

                else:
                    return {
                        "error": f"Invalid detail_level: {detail_level}. Must be 'name', 'description', or 'full'"
                    }

            except Exception as e:
                logger.error(f"Error searching tools: {e}", exc_info=True)
                return {"error": str(e)}

        # ===== ASYNC MIDDLEWARE TOOLS =====
        
        @self.mcp.tool()
        def dispatch_background_task(
            task_description: str,
            verbose: bool = False,
        ) -> Dict[str, str]:
            """Dispatch a task to run in the background (async execution).
            
            This tool enables "fire-and-forget" async execution. The task runs
            in a background thread while the main agent continues working.
            
            Args:
                task_description: Description of the task to execute
                verbose: Whether to print execution progress
                
            Returns:
                Dictionary with task_id for tracking
            """
            try:
                task_id = self.task_manager.dispatch_task(
                    task_description=task_description,
                    verbose=verbose,
                )
                return {
                    "task_id": task_id,
                    "status": "dispatched",
                    "description": task_description,
                }
            except Exception as e:
                logger.error(f"Error dispatching task: {e}", exc_info=True)
                return {
                    "error": str(e),
                    "status": "failed",
                }
        
        @self.mcp.tool()
        def get_background_task_status(task_id: str) -> Dict[str, Any]:
            """Get the current status of a background task.
            
            Args:
                task_id: Unique task identifier from dispatch_background_task
                
            Returns:
                Dictionary containing task status, result, output, and errors
            """
            try:
                return self.task_manager.get_task_status(task_id)
            except Exception as e:
                logger.error(f"Error getting task status: {e}", exc_info=True)
                return {"error": str(e), "status": "unknown"}
        
        @self.mcp.tool()
        def wait_for_background_task(
            task_id: str,
            timeout: float = 300.0,
        ) -> Dict[str, Any]:
            """Wait for a background task to complete and return results.
            
            This blocks until the task completes or timeout is reached.
            
            Args:
                task_id: Unique task identifier from dispatch_background_task
                timeout: Maximum time to wait in seconds (default: 300)
                
            Returns:
                Dictionary containing task status, result, output, and errors
            """
            try:
                return self.task_manager.wait_for_task(task_id, timeout=timeout)
            except Exception as e:
                logger.error(f"Error waiting for task: {e}", exc_info=True)
                return {"error": str(e), "status": "unknown"}
        
        @self.mcp.tool()
        def list_background_tasks() -> Dict[str, Dict[str, Any]]:
            """List all background tasks and their current status.
            
            Returns:
                Dictionary mapping task_ids to their status information
            """
            try:
                return self.task_manager.list_tasks()
            except Exception as e:
                logger.error(f"Error listing tasks: {e}", exc_info=True)
                return {"error": str(e)}
        
        @self.mcp.tool()
        def cancel_background_task(task_id: str) -> Dict[str, Any]:
            """Attempt to cancel a running background task.
            
            Args:
                task_id: Unique task identifier from dispatch_background_task
                
            Returns:
                Dictionary with cancellation result
            """
            try:
                cancelled = self.task_manager.cancel_task(task_id)
                return {
                    "task_id": task_id,
                    "cancelled": cancelled,
                    "status": "cancelled" if cancelled else "could_not_cancel",
                }
            except Exception as e:
                logger.error(f"Error cancelling task: {e}", exc_info=True)
                return {"error": str(e), "cancelled": False}

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

    def http_app(self, path: str = "/"):
        """Get FastAPI app for HTTP transport (for mounting in FastAPI applications).

        Args:
            path: Path prefix for the MCP server

        Returns:
            FastAPI application instance

        Example:
            from fastapi import FastAPI
            from code_execution_mcp import create_server

            app = FastAPI()
            mcp_server = create_server()
            mcp_app = mcp_server.http_app(path="/mcp")
            app.mount("/mcp", mcp_app)
        """
        return self.mcp.http_app(path=path)

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
