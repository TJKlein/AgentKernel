"""High-level helper for agent workflows.

This module provides a simple, unified interface for:
- Tool discovery
- Tool selection (semantic search)
- Code generation
- Execution

Minimizes boilerplate code in examples.
"""

import logging
from typing import Any, Dict, List, Optional

from client.filesystem_helpers import FilesystemHelper
from client.sandbox_executor import SandboxExecutor
from client.tool_selector import ToolSelector
from client.code_generator import CodeGenerator

logger = logging.getLogger(__name__)


class AgentHelper:
    """High-level helper that combines tool discovery, selection, generation, and execution."""

    def __init__(
        self,
        fs_helper: FilesystemHelper,
        executor: SandboxExecutor,
        tool_selector: Optional[ToolSelector] = None,
        code_generator: Optional[CodeGenerator] = None,
    ):
        """Initialize agent helper.

        Args:
            fs_helper: FilesystemHelper instance
            executor: SandboxExecutor instance
            tool_selector: Optional ToolSelector (creates default if None)
            code_generator: Optional CodeGenerator (creates default if None)
        """
        self.fs_helper = fs_helper
        self.executor = executor
        self.tool_selector = tool_selector or ToolSelector()
        self.code_generator = code_generator or CodeGenerator()

    def discover_tools(self, verbose: bool = True) -> Dict[str, List[str]]:
        """Discover all available tools from filesystem.

        Args:
            verbose: Whether to print discovery progress

        Returns:
            Dict mapping server names to lists of tool names
        """
        discovered_servers = {}
        servers = self.fs_helper.list_servers()

        if verbose:
            print(f"   Found {len(servers)} servers: {servers}")

        for server_name in servers:
            tools = self.fs_helper.list_tools(server_name)
            discovered_servers[server_name] = tools
            if verbose and tools:
                print(f"   {server_name}: {len(tools)} tools")

        return discovered_servers

    def select_tools_for_task(
        self,
        task_description: str,
        discovered_servers: Optional[Dict[str, List[str]]] = None,
        verbose: bool = True,
    ) -> Dict[str, List[str]]:
        """Select relevant tools for a task using semantic search.

        Args:
            task_description: Description of the task
            discovered_servers: Optional pre-discovered servers (will discover if None)
            verbose: Whether to print selection progress

        Returns:
            Dict mapping server names to lists of selected tool names
        """
        if discovered_servers is None:
            discovered_servers = self.discover_tools(verbose=False)

        if verbose:
            print(f"   Task: {task_description}")

        tool_descriptions = self.tool_selector.get_tool_descriptions(
            self.fs_helper, discovered_servers
        )

        if verbose:
            print(f"   Extracted {len(tool_descriptions)} tool descriptions")

        required_tools = self.tool_selector.select_tools(task_description, tool_descriptions)

        if verbose:
            print(f"   Selected tools: {required_tools}")

        return required_tools

    def execute_task(
        self,
        task_description: str,
        task_specific_calls: Optional[Dict[str, str]] = None,
        required_tools: Optional[Dict[str, List[str]]] = None,
        header_comment: Optional[str] = None,
        verbose: bool = True,
    ) -> tuple[Any, Optional[str], Optional[str]]:
        """Execute a task end-to-end: discover, select, generate, execute.

        Args:
            task_description: Description of the task
            task_specific_calls: Optional dict mapping server names to custom code blocks
            required_tools: Optional pre-selected tools (will select if None)
            header_comment: Optional header comment for generated code
            verbose: Whether to print progress

        Returns:
            Tuple of (result, output, error)
        """
        # Discover and select tools if not provided
        if required_tools is None:
            if verbose:
                print("\n1. Discovering tools...")
            discovered_servers = self.discover_tools(verbose=verbose)
            if verbose:
                print("\n2. Selecting tools for task...")
            required_tools = self.select_tools_for_task(
                task_description, discovered_servers, verbose=verbose
            )
        elif verbose:
            print(f"\n1. Using provided tools: {required_tools}")

        # Generate and execute code
        if verbose:
            print("\n3. Generating code...")
        code = self.code_generator.generate_complete_code(
            required_tools=required_tools,
            task_description=task_description,
            task_specific_calls=task_specific_calls,
            header_comment=header_comment,
        )

        if verbose:
            tool_count = sum(len(tools) for tools in required_tools.values())
            print(
                f"   Generated code with {len(required_tools)} server(s) and {tool_count} tool(s)"
            )
            print("\n   Generated Code:")
            print("   " + "=" * 56)
            # Pretty print the code with line numbers
            for i, line in enumerate(code.split("\n"), 1):
                print(f"   {i:3} | {line}")
            print("   " + "=" * 56)
            print("\n4. Executing code...")

        result, output, error = self.executor.execute(code)

        # Print results
        if verbose:
            if result.value == "success":
                print("   Execution successful!")
            else:
                print(f"   Execution status: {result.value}")

            print("\n   Execution Output:")
            print("   " + "=" * 56)
            # Always show output section - this is critical for seeing results
            if output:
                output_str = str(output) if not isinstance(output, str) else output
                # Remove trailing newlines for cleaner display
                output_str = output_str.rstrip()
                if output_str:
                    # Print all lines, including empty ones for better readability
                    for line in output_str.split("\n"):
                        print(f"   {line}")
                else:
                    print("   (Empty output)")
            else:
                print("   (No output produced)")
                # If execution was successful but no output, that's unusual
                if result.value == "success":
                    print("   Note: Execution succeeded but produced no output.")
                    print("   This may indicate the code ran but didn't print anything.")

            if error:
                print("\n   Execution Error:")
                print("   " + "=" * 56)
                error_str = str(error) if not isinstance(error, str) else error
                for line in error_str.split("\n"):
                    print(f"   {line}")
                if "Cannot connect" in error or "Connect call failed" in error:
                    print("\n   Note: Microsandbox server is not running.")
                    print("   Start it with: msb server start --dev")
                elif "Internal server error" in error or "5002" in error:
                    print("\n   Note: Microsandbox server error.")
                    print("   Check platform compatibility and server logs.")

            print("   " + "=" * 56)

        return result, output, error
