"""High-level helper for agent workflows.

This module provides a simple, unified interface for:
- Tool discovery
- Tool selection (semantic search)
- Code generation
- Execution

Minimizes boilerplate code in examples.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path

from client.filesystem_helpers import FilesystemHelper
from client.base import CodeExecutor
from client.tool_selector import ToolSelector
from client.code_generator import CodeGenerator
from config.schema import OptimizationConfig

logger = logging.getLogger(__name__)


class AgentHelper:
    """High-level helper that combines tool discovery, selection, generation, and execution."""

    def __init__(
        self,
        fs_helper: FilesystemHelper,
        executor: CodeExecutor,
        tool_selector: Optional[ToolSelector] = None,
        code_generator: Optional[CodeGenerator] = None,
        optimization_config: Optional[OptimizationConfig] = None,
        llm_config: Optional[Any] = None,  # LLMConfig from config.schema
        skill_manager: Optional[Any] = None,  # SkillManager type
        auto_save_skills: bool = True,
        session_id: Optional[str] = None,
        replay_logging_enabled: bool = True,
    ):
        """Initialize agent helper.

        Args:
            fs_helper: FilesystemHelper instance
            executor: CodeExecutor instance
            tool_selector: Optional ToolSelector (creates default if None)
            code_generator: Optional CodeGenerator (creates default if None)
            optimization_config: Optional OptimizationConfig (defaults to enabled)
            llm_config: Optional LLMConfig for LLM-based code generation
            skill_manager: Optional SkillManager for saving/reusing skills
            auto_save_skills: Whether to automatically save successful code as skills
            session_id: Optional session identifier for replays (auto-generated if None)
            replay_logging_enabled: Whether to log executions for time-travel debugging
        """
        self.fs_helper = fs_helper
        self.executor = executor
        self.tool_selector = tool_selector or ToolSelector()
        self.optimization_config = optimization_config or OptimizationConfig()
        self.llm_config = llm_config
        self.skill_manager = skill_manager
        self.auto_save_skills = auto_save_skills
        self._tool_cache = None
        
        import uuid
        self.session_id = session_id or str(uuid.uuid4())
        self.replay_logging_enabled = replay_logging_enabled
        
        # Initialize code generator with LLM config if not provided
        if code_generator is None:
            # Get tool descriptions if LLM is enabled (will be populated during discovery)
            self.code_generator = CodeGenerator(llm_config=llm_config, tool_descriptions={})
        else:
            self.code_generator = code_generator

    def discover_tools(self, verbose: bool = True) -> Dict[str, List[str]]:
        """Discover all available tools from filesystem.
        
        Optimized to be under 100ms using fast directory operations and caching.

        Args:
            verbose: Whether to print discovery progress

        Returns:
            Dict mapping server names to lists of tool names
        """
        import time
        start_time = time.time()
        
        # Use parallel discovery if enabled (optimization)
        if (self.optimization_config.enabled and 
            self.optimization_config.parallel_discovery):
            result = self._discover_tools_parallel(verbose)
        else:
            result = self._discover_tools_sequential(verbose)
        
        elapsed = (time.time() - start_time) * 1000  # Convert to ms
        if verbose and elapsed > 100:
            logger.warning(f"Tool discovery took {elapsed:.1f}ms (target: <100ms)")
        elif verbose:
            logger.debug(f"Tool discovery took {elapsed:.1f}ms")
        
        return result
    
    def _discover_tools_sequential(self, verbose: bool = True) -> Dict[str, List[str]]:
        """Discover tools sequentially (original slow path)."""
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
    
    def _discover_tools_parallel(self, verbose: bool = True) -> Dict[str, List[str]]:
        """Discover tools in parallel (optimization)."""
        import asyncio
        
        servers = self.fs_helper.list_servers()
        
        async def read_tools_async(server):
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            tools = await loop.run_in_executor(
                None, self.fs_helper.list_tools, server
            )
            return (server, tools)
        
        async def gather_all():
            tasks = [read_tools_async(server) for server in servers]
            results = await asyncio.gather(*tasks)
            return {server: tools for server, tools in results}
        
        discovered = asyncio.run(gather_all())
        
        if verbose:
            print(f"   Found {len(servers)} servers: {servers} (parallel discovery)")
            for server_name, tools in discovered.items():
                if tools:
                    print(f"   {server_name}: {len(tools)} tools")
        
        return discovered

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

        # Get tool descriptions (with caching if enabled)
        tool_descriptions = self._get_tool_descriptions(discovered_servers)

        if verbose:
            print(f"   Extracted {len(tool_descriptions)} tool descriptions")

        # Pass GPU flag to tool selector
        use_gpu = (self.optimization_config.enabled and 
                   self.optimization_config.gpu_embeddings)
        
        required_tools = self.tool_selector.select_tools(
            task_description, tool_descriptions, use_gpu=use_gpu
        )

        if verbose:
            print(f"   Selected tools: {required_tools}")

        return required_tools
    
    def _get_tool_descriptions(
        self, discovered_servers: Dict[str, List[str]]
    ) -> Dict[Tuple[str, str], str]:
        """Get tool descriptions with caching if enabled.
        
        Args:
            discovered_servers: Dict mapping server names to lists of tool names
            
        Returns:
            Dict mapping (server_name, tool_name) tuples to descriptions
        """
        # Check if tool cache is enabled
        if (self.optimization_config.enabled and 
            self.optimization_config.tool_cache):
            if self._tool_cache is None:
                from client.tool_cache import get_tool_cache
                self._tool_cache = get_tool_cache(
                    cache_file=self.optimization_config.tool_cache_file
                )
            
            return self._get_tool_descriptions_cached(discovered_servers)
        else:
            # Slow path: no caching
            return self.tool_selector.get_tool_descriptions(
                self.fs_helper, discovered_servers
            )
    
    def _get_tool_descriptions_cached(
        self, discovered_servers: Dict[str, List[str]]
    ) -> Dict[tuple, str]:
        """Get tool descriptions using cache (optimization).
        
        Args:
            discovered_servers: Dict mapping server names to lists of tool names
            
        Returns:
            Dict mapping (server_name, tool_name) tuples to descriptions
        """
        from pathlib import Path
        from client.tool_selector import extract_tool_description
        
        tool_descriptions = {}
        
        for server_name, tools in discovered_servers.items():
            for tool_name in tools:
                source_file = Path(self.fs_helper.servers_dir) / server_name / f"{tool_name}.py"
                
                # Try cache first
                cached_desc = self._tool_cache.get_tool_description(
                    server_name, tool_name, source_file
                )
                
                if cached_desc:
                    tool_descriptions[(server_name, tool_name)] = cached_desc
                else:
                    # Cache miss, read and cache
                    tool_code = self.fs_helper.read_tool_file(server_name, tool_name)
                    if tool_code:
                        description = extract_tool_description(tool_code)
                        full_description = f"{server_name} {tool_name}: {description}"
                        tool_descriptions[(server_name, tool_name)] = full_description
                        
                        # Cache for next time
                        self._tool_cache.set_tool_description(
                            server_name, tool_name, full_description, source_file
                        )
        
        # Save cache at end
        self._tool_cache.save()
        return tool_descriptions

    def execute_task(
        self,
        task_description: str,
        task_specific_calls: Optional[Dict[str, str]] = None,
        required_tools: Optional[Dict[str, List[str]]] = None,
        header_comment: Optional[str] = None,
        verbose: bool = True,
        context: Optional[Dict[str, Any]] = None,
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

        # Update code generator with tool descriptions if LLM is enabled
        if self.llm_config and self.llm_config.enabled:
            discovered_servers = required_tools if required_tools else self.discover_tools(verbose=False)
            tool_descriptions = self._get_tool_descriptions_cached(discovered_servers)
            self.code_generator.tool_descriptions = tool_descriptions

        # Get available skills from skill manager if present
        skill_listing = None
        if self.skill_manager:
            skill_listing = self.skill_manager.get_skill_listing()

        # Generate and execute code
        if verbose:
            print("\n3. Generating code...")
        code = self.code_generator.generate_complete_code(
            required_tools=required_tools,
            task_description=task_description,
            task_specific_calls=task_specific_calls,
            header_comment=header_comment,
            skill_listing=skill_listing,
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

        result, output, error = self.executor.execute(code, context=context)

        # Save successful skills
        if result.value == "success" and self.auto_save_skills and self.skill_manager:
            self._maybe_save_skill(task_description, code, output, verbose)

        # Log execution for replay / time-travel debugging
        if self.replay_logging_enabled:
            from mcpruntime.replay_log import log_execution
            
            # Use the workspace-relative .replay directory
            log_dir = Path(self.fs_helper.workspace_dir) / ".replay"
            
            # Safely get sandbox_type from config if available
            sandbox_type = "unknown"
            if hasattr(self.executor, "execution_config") and hasattr(self.executor.execution_config, "sandbox_type"):
                sandbox_type = self.executor.execution_config.sandbox_type

            log_execution(self.session_id, {
                "task": task_description,
                "code": code,
                "output": str(output) if output else "",
                "success": result.value == "success",
                "sandbox_type": sandbox_type
            }, log_dir=log_dir)

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

    def _maybe_save_skill(self, task_description: str, code: str, output: Any, verbose: bool = False):
        """Evaluate if the executed code is worth saving as a skill, and if so, save it."""
        if not self.skill_manager.is_worth_saving(code, output):
            return

        import re
        import time

        # Generate a safe skill name from the task description
        # e.g. "Fetch weather for Tokyo" -> "fetch_weather_for_tokyo"
        # We take just the first few words to keep it reasonable
        clean_desc = re.sub(r'[^a-zA-Z0-9\s]', '', task_description).strip()
        words = clean_desc.lower().split()
        if not words:
            return
            
        base_name = "_".join(words[:4])
        # Make sure it's a valid python identifier
        if not base_name.isidentifier() or base_name.startswith('_'):
            base_name = "skill_" + str(int(time.time()))
            
        skill_name = base_name

        wrapped_code = self.skill_manager.extract_skill_from_code(code, skill_name, task_description)
        try:
            self.skill_manager.update_skill(skill_name, wrapped_code, task_description)
            if verbose:
                print(f"\n   [Skill Evolution] Automatically saved successful code as skill: '{skill_name}'")
        except Exception as e:
            if verbose:
                logger.warning(f"Failed to auto-save skill {skill_name}: {e}")

    def resume_from(self, session_id: str, step: int) -> None:
        """Load a previous session and fast-forward the sandbox to a specific step.
        
        This enables Time-Travel Debugging by replaying prior code states into the sandbox.
        """
        from mcpruntime.replay_log import load_session
        
        log_dir = Path(self.fs_helper.workspace_dir) / ".replay"
        entries = load_session(session_id, log_dir=log_dir)[:step]
        print(f"\n🔄 Fast-forwarding session '{session_id}' to step {step} ({len(entries)} steps)...")
        
        # We process each step, explicitly bypassing new LLM generations, and just running the old code
        for i, entry in enumerate(entries):
            task_preview = entry['task'][:50] + "..." if len(entry['task']) > 50 else entry['task']
            print(f"  [{i+1}/{len(entries)}] Replaying: {task_preview}")
            self.executor.execute(entry["code"])
            
        self.session_id = session_id
        print("✅ Sandbox state restored. Ready for new commands.\n")

