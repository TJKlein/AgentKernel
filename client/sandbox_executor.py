"""Sandbox executor using microsandbox."""

import asyncio
import logging
from typing import Any, Dict, List, Optional
from pathlib import Path

try:
    from microsandbox import PythonSandbox
except ImportError:
    PythonSandbox = None  # type: ignore

from client.base import CodeExecutor, ExecutionResult, ValidationResult
from client.guardrails import GuardrailValidatorImpl
from config.schema import ExecutionConfig, GuardrailConfig, OptimizationConfig

logger = logging.getLogger(__name__)


class SandboxExecutor(CodeExecutor):
    """Sandbox executor using microsandbox."""

    def __init__(
        self,
        execution_config: ExecutionConfig,
        guardrail_config: Optional[GuardrailConfig] = None,
        optimization_config: Optional[OptimizationConfig] = None,
    ):
        """Initialize sandbox executor.
        
        Args:
            execution_config: Execution configuration
            guardrail_config: Guardrail configuration
            optimization_config: Optimization configuration (defaults to enabled)
        """
        self.execution_config = execution_config
        self.guardrail_config = guardrail_config or GuardrailConfig()
        self.optimization_config = optimization_config or OptimizationConfig()
        self.guardrail_validator = GuardrailValidatorImpl(self.guardrail_config)
        self._sandbox_pool = None

    def validate_code(self, code: str) -> ValidationResult:
        """Validate code before execution."""
        guardrail_result = self.guardrail_validator.validate_code(code, {})
        return ValidationResult(
            valid=len(guardrail_result.errors) == 0,
            errors=guardrail_result.errors,
            warnings=guardrail_result.warnings,
        )

    def execute(self, code: str) -> tuple[ExecutionResult, Any, Optional[str]]:
        """Execute code in a sandboxed environment."""
        if PythonSandbox is None:
            raise ImportError(
                "microsandbox is not installed. Install it with: pip install microsandbox"
            )

        # Pre-execution validation
        validation_result = self.validate_code(code)
        if not validation_result.valid:
            error_msg = "; ".join(validation_result.errors)
            logger.error(f"Code validation failed: {error_msg}")
            return ExecutionResult.FAILURE, None, error_msg

        try:
            # Execute in sandbox
            result = asyncio.run(self._execute_async(code))
            output, error = result

            if error:
                logger.error(f"Code execution error: {error}")
                return ExecutionResult.FAILURE, None, error

            # Post-execution validation
            if output is not None:
                output_result = self.guardrail_validator.validate_output(output, {})
                if not output_result.valid and self.guardrail_config.strict_mode:
                    error_msg = "; ".join(output_result.errors)
                    logger.error(f"Output validation failed: {error_msg}")
                    return ExecutionResult.BLOCKED, None, error_msg

            return ExecutionResult.SUCCESS, output, None

        except asyncio.TimeoutError:
            logger.error("Code execution timed out")
            return ExecutionResult.TIMEOUT, None, "Execution timeout"
        except Exception as e:
            logger.error(f"Code execution failed: {e}")
            return ExecutionResult.FAILURE, None, str(e)

    def _find_project_root(self) -> Path:
        """Find project root by looking for marker files (pyproject.toml, requirements.txt, etc.)."""
        current = Path.cwd().resolve()
        
        # Check current directory and parents
        for path in [current] + list(current.parents):
            # Look for project markers
            markers = ["pyproject.toml", "requirements.txt", ".git", "setup.py"]
            if any((path / marker).exists() for marker in markers):
                # Also verify client directory exists (confirms it's the right root)
                if (path / "client").exists():
                    return path
        
        # Fallback: assume current directory is project root if client exists
        if (current / "client").exists():
            return current
        
        # Last resort: use current directory
        logger.warning(f"Could not find project root, using current directory: {current}")
        return current

    async def _execute_async(self, code: str) -> tuple[Any, Optional[str]]:
        """Execute code asynchronously in sandbox."""
        if PythonSandbox is None:
            raise ImportError("microsandbox is not installed")

        try:
            # Find project root first (works regardless of current working directory)
            project_root = self._find_project_root()
            logger.debug(f"Project root: {project_root}")
            
            # Resolve all paths relative to project root
            workspace_path = (project_root / self.execution_config.workspace_dir.lstrip("./")).resolve()
            servers_path = (project_root / self.execution_config.servers_dir.lstrip("./")).resolve()
            skills_path = (project_root / self.execution_config.skills_dir.lstrip("./")).resolve()
            client_path = (project_root / "client").resolve()
            
            workspace_path.mkdir(parents=True, exist_ok=True)
            
            # Ensure client, servers, and skills directories are clean
            # This prevents stale empty directories from interfering with volume mounts
            for subdir in ["client", "servers", "skills"]:
                subdir_path = workspace_path / subdir
                if subdir_path.exists() and not any(subdir_path.iterdir()):
                    # Remove empty directories to ensure fresh state
                    subdir_path.rmdir()
                    logger.debug(f"Removed empty {subdir_path}")

            # Per Anthropic article: tools are filesystem-based Python modules
            # Write files directly to host workspace BEFORE sandbox creation
            # With volume mounts, files written to host workspace are immediately
            # available in the sandbox at /workspace
            self._write_files_to_workspace(
                workspace_path=workspace_path,
                servers_path=servers_path,
                client_path=client_path,
                skills_path=skills_path,
            )
            
            # Note: os.sync() removed for performance - modern filesystems don't need it
            # Files are written synchronously and will be available via virtiofs
            
            # Verify files exist on host before creating sandbox
            client_file = workspace_path / "client" / "mcp_client.py"
            if not client_file.exists():
                logger.warning(f"Files not written correctly: {client_file} does not exist")
            
            # Mount workspace directory for true persistence across executions
            workspace_path_abs = workspace_path.resolve()
            
            # Use sandbox pooling if enabled (optimization)
            if (self.optimization_config.enabled and 
                self.optimization_config.sandbox_pooling):
                return await self._execute_with_pool(workspace_path_abs, code)
            else:
                # Original slow path for debugging
                # Use fixed sandbox name to match Sandboxfile configuration
                sandbox_name = "code-execution"
                
                async with PythonSandbox.create(
                    name=sandbox_name,
                    volumes=[(str(workspace_path_abs), "/workspace")]
                ) as sandbox:
                    return await self._execute_in_sandbox(sandbox, code)

        except Exception as e:
            logger.error(f"Sandbox execution error: {e}", exc_info=True)
            return None, str(e)
    
    async def _execute_with_pool(
        self, workspace_path_abs: Path, code: str
    ) -> tuple[Any, Optional[str]]:
        """Execute code using sandbox pool (optimization).
        
        Args:
            workspace_path_abs: Absolute workspace path
            code: Code to execute
            
        Returns:
            Tuple of (output, error)
        """
        # Initialize pool if needed
        if self._sandbox_pool is None:
            from client.sandbox_pool import get_sandbox_pool
            self._sandbox_pool = await get_sandbox_pool(
                pool_size=self.optimization_config.sandbox_pool_size,
                workspace_dir=str(workspace_path_abs)
            )
        
        # Acquire sandbox from pool
        sandbox = await self._sandbox_pool.acquire()
        try:
            return await self._execute_in_sandbox(sandbox, code)
        finally:
            # Return sandbox to pool
            await self._sandbox_pool.release(sandbox)

    async def _execute_in_sandbox(
        self,
        sandbox: Any,
        code: str,
    ) -> tuple[Any, Optional[str]]:
        """Execute code in sandbox with workspace mounted at /workspace.
        
        Args:
            sandbox: PythonSandbox instance (with workspace mounted)
            code: Code to execute
        """
        import asyncio

        workspace_path = Path(self.execution_config.workspace_dir)
        servers_path = Path(self.execution_config.servers_dir).resolve()
        skills_path = Path(self.execution_config.skills_dir).resolve()
        project_root = workspace_path.parent.resolve()
        client_path = project_root / "client"

        try:
            # Files are already written to host workspace (done before sandbox creation)
            # Generate minimal setup code to verify files exist and add /workspace to sys.path
            setup_code = self._generate_verification_code()
            
            # Write code to a file and execute it to avoid REPL mode breaking on errors
            # This ensures the code executes as a complete script, not line-by-line
            script_path = "/workspace/_execute_task.py"
            combined_code = setup_code + "\n\n# Execute task code\n" + code
            
            # Write code to file and execute it using exec() to avoid REPL mode issues
            execute_code = f"""
import os
import sys

# Setup code
{setup_code}

# Write task code to file
task_code = {repr(code)}
with open('{script_path}', 'w', encoding='utf-8') as f:
    f.write(task_code)

# Execute the script file using compile() and exec() to avoid REPL mode breaking
try:
    with open('{script_path}', 'r', encoding='utf-8') as f:
        script_content = f.read()
    compiled = compile(script_content, '{script_path}', 'exec')
    exec(compiled, {{'__name__': '__main__', '__file__': '{script_path}'}})
except Exception as e:
    print(f"Script execution error: {{type(e).__name__}}: {{e}}", flush=True)
    import traceback
    traceback.print_exc()
"""
            
            logger.debug(f"Execution code length: {len(execute_code)} chars")
            logger.debug("Executing code via script file to avoid REPL mode issues...")
            
            exec_result = await asyncio.wait_for(sandbox.run(execute_code), timeout=45.0)
            output = await exec_result.output()
            error = None
            
            logger.debug(f"Execution completed. Output length: {len(output) if output else 0} chars")
            if output:
                logger.debug(f"Output first 1000 chars:\n{output[:1000]}")
            
            # Also check stderr for any errors that might not be in stdout
            try:
                stderr_output = await exec_result.error()
                if stderr_output:
                    logger.debug(f"Stderr output: {stderr_output[:500]}")
                    # Append stderr to output for visibility
                    if output:
                        output = output + "\n[STDERR]\n" + stderr_output
                    else:
                        output = "[STDERR]\n" + stderr_output
            except Exception as e:
                logger.debug(f"Could not get stderr: {e}")

            # Check for errors in output - be more specific
            # Import failures should be shown in output, not moved to error
            # Only treat as error if it's a fatal traceback or setup failure
            if output:
                # Check for actual fatal error indicators
                if (
                    "Traceback (most recent call last)" in output
                    and "FAILED Import error:" not in output
                ):
                    # Only treat as error if it's not an import error (import errors are shown in output)
                    # This allows us to see import errors in the output
                    if "Setup error:" in output:
                        error = output
                # Import failures are shown in output, not moved to error
                # This way users can see what went wrong with imports
                # Don't treat "Error calling" as a fatal error - it's just in a print statement

            return output, error
        except asyncio.TimeoutError:
            logger.error("Sandbox execution timed out after 30 seconds")
            return None, "Execution timed out after 30 seconds"

    def _generate_copy_code(self, servers_path: Path, client_path: Path, skills_path: Path) -> str:
        """Generate code to write files into mounted workspace.

        Reads files directly from source directories and embeds them in setup code.
        Files are written to /workspace (mounted volume) so they persist and are importable.
        Per Anthropic article: tools are filesystem-based Python modules.
        """
        import base64

        setup_lines = [
            "import os",
            "import sys",
            "import base64",
            "",
            "print('=== SETUP START ===', flush=True)",
            "print(f'Python version: {sys.version}', flush=True)",
            "print(f'Current working directory: {os.getcwd()}', flush=True)",
            "print(f'sys.path: {sys.path}', flush=True)",
            "",
            "# Verify /workspace is mounted (volume mount check)",
            "print('=== VOLUME MOUNT VERIFICATION ===', flush=True)",
            "workspace_exists = os.path.exists('/workspace')",
            "workspace_isdir = os.path.isdir('/workspace') if workspace_exists else False",
            "print(f'/workspace exists: {workspace_exists}', flush=True)",
            "print(f'/workspace is directory: {workspace_isdir}', flush=True)",
            "if workspace_exists:",
            "    try:",
            "        # Try to list contents to verify mount is accessible",
            "        contents = os.listdir('/workspace')",
            "        print(f'/workspace contents: {contents}', flush=True)",
            "        # Try to write a test file to verify mount is writable",
            "        test_file = '/workspace/.mount_test'",
            "        with open(test_file, 'w') as f:",
            "            f.write('mount_test')",
            "        if os.path.exists(test_file):",
            "            os.remove(test_file)",
            "            print('✅ /workspace is mounted and writable', flush=True)",
            "        else:",
            "            print('⚠️ /workspace exists but test file write failed', flush=True)",
            "    except Exception as e:",
            "        print(f'❌ Error accessing /workspace: {type(e).__name__}: {e}', flush=True)",
            "        import traceback",
            "        traceback.print_exc(file=sys.stdout)",
            "",
            "# Add /workspace to Python path for imports",
            "if '/workspace' not in sys.path:",
            "    sys.path.insert(0, '/workspace')",
            "    print('Added /workspace to sys.path', flush=True)",
            "else:",
            "    print('/workspace already in sys.path', flush=True)",
            "",
            "# Create directory structure in mounted workspace",
            "print('=== Creating directories ===', flush=True)",
            "print('About to create /workspace/servers...', flush=True)",
            "try:",
            "    os.makedirs('/workspace/servers', exist_ok=True)",
            "    servers_exists = os.path.exists('/workspace/servers')",
            "    servers_isdir = os.path.isdir('/workspace/servers') if servers_exists else False",
            "    print(f'✅ Created /workspace/servers (exists: {servers_exists}, is_dir: {servers_isdir})', flush=True)",
            "except Exception as e:",
            "    print(f'❌ Failed to create /workspace/servers: {type(e).__name__}: {e}', flush=True)",
            "    import traceback",
            "    traceback.print_exc(file=sys.stdout)",
            "print('About to create /workspace/client...', flush=True)",
            "try:",
            "    os.makedirs('/workspace/client', exist_ok=True)",
            "    client_exists = os.path.exists('/workspace/client')",
            "    client_isdir = os.path.isdir('/workspace/client') if client_exists else False",
            "    print(f'✅ Created /workspace/client (exists: {client_exists}, is_dir: {client_isdir})', flush=True)",
            "except Exception as e:",
            "    print(f'❌ Failed to create /workspace/client: {type(e).__name__}: {e}', flush=True)",
            "    import traceback",
            "    traceback.print_exc(file=sys.stdout)",
            "print('About to create /workspace/skills...', flush=True)",
            "try:",
            "    os.makedirs('/workspace/skills', exist_ok=True)",
            "    skills_exists = os.path.exists('/workspace/skills')",
            "    skills_isdir = os.path.isdir('/workspace/skills') if skills_exists else False",
            "    print(f'✅ Created /workspace/skills (exists: {skills_exists}, is_dir: {skills_isdir})', flush=True)",
            "except Exception as e:",
            "    print(f'❌ Failed to create /workspace/skills: {type(e).__name__}: {e}', flush=True)",
            "    import traceback",
            "    traceback.print_exc(file=sys.stdout)",
            "",
            "# Verify all directories were created",
            "print('=== Directory Creation Summary ===', flush=True)",
            "try:",
            "    all_dirs = ['/workspace/servers', '/workspace/client', '/workspace/skills']",
            "    for dir_path in all_dirs:",
            "        exists = os.path.exists(dir_path)",
            "        is_dir = os.path.isdir(dir_path) if exists else False",
            "        print(f'{dir_path}: exists={exists}, is_dir={is_dir}', flush=True)",
            "    print('=== End Directory Creation Summary ===', flush=True)",
            "except Exception as e:",
            "    print(f'❌ Error in directory summary: {e}', flush=True)",
            "    import traceback",
            "    traceback.print_exc(file=sys.stdout)",
            "",
            "# Checkpoint: All directories should be created by now",
            "print('=== CHECKPOINT: Starting file writing phase ===', flush=True)",
            "print(f'All directories exist check:', flush=True)",
            "for d in ['/workspace/servers', '/workspace/client', '/workspace/skills']:",
            "    print(f'  {d}: {os.path.exists(d)}', flush=True)",
            "",
        ]

        # Write client directory FIRST (servers depend on it)
        # Per Anthropic article: tools are filesystem-based Python modules
        client_dir = client_path
        if client_dir.exists():
            # Ensure client directory exists before writing files
            setup_lines.append("print('=== SETUP: Setting up client directory in /workspace ===', flush=True)")
            setup_lines.append("print(f'Current working directory: {os.getcwd()}', flush=True)")
            setup_lines.append("print(f'/workspace exists: {os.path.exists(\"/workspace\")}', flush=True)")
            setup_lines.append("print(f'/workspace is dir: {os.path.isdir(\"/workspace\")}', flush=True)")
            setup_lines.append("# Ensure /workspace/client directory exists (should already exist from above)")
            setup_lines.append("if not os.path.exists('/workspace/client'):")
            setup_lines.append("    try:")
            setup_lines.append("        os.makedirs('/workspace/client', exist_ok=True)")
            setup_lines.append("        print('✅ Ensured /workspace/client directory exists', flush=True)")
            setup_lines.append("    except Exception as e:")
            setup_lines.append("        print(f'❌ Failed to create /workspace/client: {e}', flush=True)")
            setup_lines.append("        import traceback")
            setup_lines.append("        traceback.print_exc(file=sys.stdout)")
            setup_lines.append("        raise RuntimeError('Cannot continue without /workspace/client directory')")
            setup_lines.append("else:")
            setup_lines.append("    print('✅ /workspace/client directory already exists', flush=True)")
            setup_lines.append("client_dir_exists = os.path.exists('/workspace/client')")
            setup_lines.append("print(f'Directory /workspace/client exists: {client_dir_exists}', flush=True)")
            setup_lines.append("try:")
            setup_lines.append("    print('=== About to write __init__.py ===', flush=True)")
            setup_lines.append("    init_content = 'Client module for sandbox execution.\\n'")
            setup_lines.append("    print(f'Content to write: {repr(init_content)}', flush=True)")
            setup_lines.append("    with open('/workspace/client/__init__.py', 'w', encoding='utf-8') as f:")
            setup_lines.append("        f.write(init_content)")
            setup_lines.append("        print('File handle opened and written', flush=True)")
            setup_lines.append("    print('✅ Written /workspace/client/__init__.py', flush=True)")
            setup_lines.append("    file_exists = os.path.exists('/workspace/client/__init__.py')")
            setup_lines.append("    print(f'File exists after write: {file_exists}', flush=True)")
            setup_lines.append("    if file_exists:")
            setup_lines.append("        with open('/workspace/client/__init__.py', 'r') as f:")
            setup_lines.append("            read_back = f.read()")
            setup_lines.append("        print(f'Read back content: {repr(read_back)}', flush=True)")
            setup_lines.append("except Exception as e:")
            setup_lines.append("    print(f'❌ ERROR writing client/__init__.py: {type(e).__name__}: {e}', flush=True)")
            setup_lines.append("    import traceback")
            setup_lines.append("    traceback.print_exc(file=sys.stdout)")
            setup_lines.append("    print('=== End of error traceback ===', flush=True)")
            # Don't raise - continue to try writing mcp_client.py

            # Write mcp_client.py (use mock for examples, real for production)
            # Prefer mock_mcp_client.py for examples (no real MCP server needed)
            mock_client_file = client_dir / "mock_mcp_client.py"
            real_client_file = client_dir / "mcp_client.py"
            
            if mock_client_file.exists():
                # Use mock client for examples
                # Per Anthropic article: tools are filesystem-based Python modules
                content = mock_client_file.read_text(encoding="utf-8")
                content_b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")
                # Write base64 in chunks to avoid string literal limits
                chunk_size = 1000
                chunks = [content_b64[i:i+chunk_size] for i in range(0, len(content_b64), chunk_size)]
                setup_lines.append("try:")
                setup_lines.append("    print('Writing /workspace/client/mcp_client.py...', flush=True)")
                setup_lines.append("    content_b64_parts = [")
                for chunk in chunks:
                    # Use repr() to safely escape the chunk
                    setup_lines.append(f"        {repr(chunk)},")
                setup_lines.append("    ]")
                setup_lines.append("    content_b64 = ''.join(content_b64_parts)")
                setup_lines.append("    decoded_content = base64.b64decode(content_b64).decode('utf-8')")
                setup_lines.append("    with open('/workspace/client/mcp_client.py', 'w', encoding='utf-8') as f:")
                setup_lines.append("        f.write(decoded_content)")
                setup_lines.append("    print('✅ Written /workspace/client/mcp_client.py', flush=True)")
                setup_lines.append("except Exception as e:")
                setup_lines.append("    print(f'❌ Error writing mcp_client.py: {e}', flush=True)")
                setup_lines.append("    import traceback")
                setup_lines.append("    traceback.print_exc()")
                setup_lines.append("    raise")
            elif real_client_file.exists():
                # Use real client if mock doesn't exist
                content = real_client_file.read_text(encoding="utf-8")
                content_b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")
                chunk_size = 1000
                chunks = [content_b64[i:i+chunk_size] for i in range(0, len(content_b64), chunk_size)]
                setup_lines.append("try:")
                setup_lines.append("    print('Writing /workspace/client/mcp_client.py...', flush=True)")
                setup_lines.append("    content_b64_parts = [")
                for chunk in chunks:
                    setup_lines.append(f"        {repr(chunk)},")
                setup_lines.append("    ]")
                setup_lines.append("    content_b64 = ''.join(content_b64_parts)")
                setup_lines.append("    decoded_content = base64.b64decode(content_b64).decode('utf-8')")
                setup_lines.append("    with open('/workspace/client/mcp_client.py', 'w', encoding='utf-8') as f:")
                setup_lines.append("        f.write(decoded_content)")
                setup_lines.append("    print('✅ Written /workspace/client/mcp_client.py', flush=True)")
                setup_lines.append("except Exception as e:")
                setup_lines.append("    print(f'❌ Error writing mcp_client.py: {e}', flush=True)")
                setup_lines.append("    import traceback")
                setup_lines.append("    traceback.print_exc()")
                setup_lines.append("    raise")

        # Write servers directory (after client is available)
        servers_dir = servers_path
        if servers_dir.exists():
            for server_dir in sorted(servers_dir.iterdir()):
                if server_dir.is_dir():
                    server_name = server_dir.name
                    setup_lines.append(f"os.makedirs('/workspace/servers/{server_name}', exist_ok=True)")
                    # Write tool files first (before __init__.py which imports them)
                    for tool_file in sorted(server_dir.glob("*.py")):
                        if tool_file.name != "__init__.py":
                            content = tool_file.read_text(encoding="utf-8")
                            content_b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")
                            chunk_size = 1000
                            chunks = [content_b64[i:i+chunk_size] for i in range(0, len(content_b64), chunk_size)]
                            setup_lines.append("try:")
                            setup_lines.append(f"    print('Writing /workspace/servers/{server_name}/{tool_file.name}...', flush=True)")
                            setup_lines.append("    content_b64_parts = [")
                            for chunk in chunks:
                                setup_lines.append(f"        {repr(chunk)},")
                            setup_lines.append("    ]")
                            setup_lines.append("    content_b64 = ''.join(content_b64_parts)")
                            setup_lines.append("    decoded_content = base64.b64decode(content_b64).decode('utf-8')")
                            setup_lines.append(f"    with open('/workspace/servers/{server_name}/{tool_file.name}', 'w', encoding='utf-8') as f:")
                            setup_lines.append("        f.write(decoded_content)")
                            setup_lines.append(f"    print(f'✅ Written /workspace/servers/{server_name}/{tool_file.name}', flush=True)")
                            setup_lines.append("except Exception as e:")
                            setup_lines.append(f"    print(f'❌ Error writing {tool_file.name}: {{e}}', flush=True)")
                            setup_lines.append("    import traceback")
                            setup_lines.append("    traceback.print_exc()")
                            setup_lines.append("    raise")
                    # Write __init__.py last (it imports from tool files)
                    init_file = server_dir / "__init__.py"
                    if init_file.exists():
                        content = init_file.read_text(encoding="utf-8")
                        content_b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")
                        chunk_size = 1000
                        chunks = [content_b64[i:i+chunk_size] for i in range(0, len(content_b64), chunk_size)]
                        setup_lines.append("try:")
                        setup_lines.append(f"    print('Writing /workspace/servers/{server_name}/__init__.py...', flush=True)")
                        setup_lines.append("    content_b64_parts = [")
                        for chunk in chunks:
                            setup_lines.append(f"        {repr(chunk)},")
                        setup_lines.append("    ]")
                        setup_lines.append("    content_b64 = ''.join(content_b64_parts)")
                        setup_lines.append("    decoded_content = base64.b64decode(content_b64).decode('utf-8')")
                        setup_lines.append(f"    with open('/workspace/servers/{server_name}/__init__.py', 'w', encoding='utf-8') as f:")
                        setup_lines.append("        f.write(decoded_content)")
                        setup_lines.append(f"    print(f'✅ Written /workspace/servers/{server_name}/__init__.py', flush=True)")
                        setup_lines.append("except Exception as e:")
                        setup_lines.append("    print(f'❌ Error writing __init__.py: {e}', flush=True)")
                        setup_lines.append("    import traceback")
                        setup_lines.append("    traceback.print_exc()")
                        setup_lines.append("    raise")

        # Clear any cached modules to force fresh imports
        setup_lines.append("# Clear any cached modules to force fresh imports")
        setup_lines.append(
            "modules_to_clear = [m for m in list(sys.modules.keys()) if m.startswith('servers.') or m.startswith('client.')]"
        )
        setup_lines.append("for mod in modules_to_clear:")
        setup_lines.append("    del sys.modules[mod]")
        setup_lines.append("")
        setup_lines.append("# Verify client.mcp_client is importable (per Anthropic article pattern)")
        setup_lines.append("try:")
        setup_lines.append("    from client.mcp_client import call_mcp_tool")
        setup_lines.append("    print('✅ client.mcp_client imported successfully', flush=True)")
        setup_lines.append("except Exception as e:")
        setup_lines.append("    print(f'❌ client.mcp_client import failed: {e}', flush=True)")
        setup_lines.append("    import traceback")
        setup_lines.append("    traceback.print_exc(limit=3)")
        setup_lines.append("")
        setup_lines.append("print('=== SETUP COMPLETE ===', flush=True)")

        return "\n".join(setup_lines)
    
    def _write_files_to_workspace(
        self,
        workspace_path: Path,
        servers_path: Path,
        client_path: Path,
        skills_path: Path,
    ) -> None:
        """Write files directly to host workspace before sandbox execution.
        
        With volume mounts, files written to host workspace are immediately
        available in the sandbox at /workspace. This avoids the large script
        execution issue in Python's interactive mode.
        
        Per Anthropic article: tools are filesystem-based Python modules.
        
        Performance optimization: Only writes files if they don't exist or content changed.
        Can be disabled via optimization_config.file_content_cache = False
        """
        # Check if file caching is enabled
        use_cache = (self.optimization_config.enabled and 
                     self.optimization_config.file_content_cache)
        
        if not use_cache:
            # Slow path: always write files (for debugging)
            self._write_files_always(workspace_path, servers_path, client_path, skills_path)
            return
        
        # Fast path: only write changed files
        import hashlib
        
        workspace_path = workspace_path.resolve()
        logger.debug(f"Writing files to workspace: {workspace_path}")
        
        def _file_needs_update(source: Path, target: Path) -> bool:
            """Check if file needs to be updated (doesn't exist or content changed)."""
            if not target.exists():
                return True
            if not source.exists():
                return False
            # Compare file contents using hash for speed
            try:
                source_hash = hashlib.md5(source.read_bytes()).hexdigest()
                target_hash = hashlib.md5(target.read_bytes()).hexdigest()
                return source_hash != target_hash
            except Exception:
                # If we can't compare, assume it needs updating
                return True
        
        def _write_if_needed(source: Path, target: Path, description: str = "") -> None:
            """Write file only if it doesn't exist or content changed."""
            if _file_needs_update(source, target):
                content = source.read_text(encoding="utf-8")
                target.write_text(content, encoding="utf-8")
                logger.debug(f"Wrote {target} ({len(content)} chars){' - ' + description if description else ''}")
            else:
                logger.debug(f"Skipped {target} (unchanged)")
        
        # Create directory structure
        (workspace_path / "client").mkdir(parents=True, exist_ok=True)
        (workspace_path / "servers").mkdir(parents=True, exist_ok=True)
        (workspace_path / "skills").mkdir(parents=True, exist_ok=True)
        
        # Write client files
        if client_path.exists():
            # Write __init__.py (always write, it's tiny)
            client_init_path = workspace_path / "client" / "__init__.py"
            init_content = '"""Client module for sandbox execution."""\n'
            if not client_init_path.exists() or client_init_path.read_text(encoding="utf-8") != init_content:
                client_init_path.write_text(init_content, encoding="utf-8")
                logger.debug(f"Wrote {client_init_path}")
            
            # Write mcp_client.py (prefer mock, fallback to real)
            mock_client_file = client_path / "mock_mcp_client.py"
            real_client_file = client_path / "mcp_client.py"
            mcp_client_path = workspace_path / "client" / "mcp_client.py"
            
            if mock_client_file.exists():
                _write_if_needed(mock_client_file, mcp_client_path, "mock client")
            elif real_client_file.exists():
                _write_if_needed(real_client_file, mcp_client_path, "real client")
            else:
                logger.warning(f"Neither mock_mcp_client.py nor mcp_client.py found in {client_path}")
        else:
            logger.warning(f"Client path does not exist: {client_path}")
        
        # Write server files
        if servers_path.exists():
            for server_dir in sorted(servers_path.iterdir()):
                if server_dir.is_dir():
                    server_name = server_dir.name
                    target_server_dir = workspace_path / "servers" / server_name
                    target_server_dir.mkdir(parents=True, exist_ok=True)
                    
                    # Copy tool files first (before __init__.py which imports them)
                    for tool_file in sorted(server_dir.glob("*.py")):
                        if tool_file.name != "__init__.py":
                            target_file = target_server_dir / tool_file.name
                            _write_if_needed(tool_file, target_file)
                    
                    # Copy __init__.py last (it imports from tool files)
                    init_file = server_dir / "__init__.py"
                    if init_file.exists():
                        target_init = target_server_dir / "__init__.py"
                        _write_if_needed(init_file, target_init)
        
        # Write skill files
        if skills_path.exists():
            for skill_file in sorted(skills_path.glob("*.py")):
                target_skill = workspace_path / "skills" / skill_file.name
                _write_if_needed(skill_file, target_skill)
    
    def _write_files_always(
        self,
        workspace_path: Path,
        servers_path: Path,
        client_path: Path,
        skills_path: Path,
    ) -> None:
        """Write all files always (slow path for debugging).
        
        This is the original implementation without caching.
        Used when file_content_cache is disabled.
        """
        workspace_path = workspace_path.resolve()
        logger.debug(f"Writing all files to workspace (no cache): {workspace_path}")
        
        # Create directory structure
        (workspace_path / "client").mkdir(parents=True, exist_ok=True)
        (workspace_path / "servers").mkdir(parents=True, exist_ok=True)
        (workspace_path / "skills").mkdir(parents=True, exist_ok=True)
        
        # Write client files
        if client_path.exists():
            client_init_path = workspace_path / "client" / "__init__.py"
            client_init_path.write_text(
                '"""Client module for sandbox execution."""\n', encoding="utf-8"
            )
            
            mock_client_file = client_path / "mock_mcp_client.py"
            real_client_file = client_path / "mcp_client.py"
            mcp_client_path = workspace_path / "client" / "mcp_client.py"
            
            if mock_client_file.exists():
                content = mock_client_file.read_text(encoding="utf-8")
                mcp_client_path.write_text(content, encoding="utf-8")
            elif real_client_file.exists():
                content = real_client_file.read_text(encoding="utf-8")
                mcp_client_path.write_text(content, encoding="utf-8")
        
        # Write server files
        if servers_path.exists():
            for server_dir in sorted(servers_path.iterdir()):
                if server_dir.is_dir():
                    server_name = server_dir.name
                    target_server_dir = workspace_path / "servers" / server_name
                    target_server_dir.mkdir(parents=True, exist_ok=True)
                    
                    for tool_file in sorted(server_dir.glob("*.py")):
                        if tool_file.name != "__init__.py":
                            content = tool_file.read_text(encoding="utf-8")
                            (target_server_dir / tool_file.name).write_text(content, encoding="utf-8")
                    
                    init_file = server_dir / "__init__.py"
                    if init_file.exists():
                        content = init_file.read_text(encoding="utf-8")
                        (target_server_dir / "__init__.py").write_text(content, encoding="utf-8")
        
        # Write skill files
        if skills_path.exists():
            for skill_file in sorted(skills_path.glob("*.py")):
                content = skill_file.read_text(encoding="utf-8")
                (workspace_path / "skills" / skill_file.name).write_text(content, encoding="utf-8")
    
    def _generate_verification_code(self) -> str:
        """Generate minimal code to verify files exist and set up Python path.
        
        Since files are written directly to host workspace, we just need to:
        1. Verify /workspace is mounted
        2. Add /workspace to sys.path
        3. Verify files exist and can be imported
        """
        return "\n".join([
            "import os",
            "import sys",
            "",
            "# Add /workspace to Python path for imports",
            "if '/workspace' not in sys.path:",
            "    sys.path.insert(0, '/workspace')",
            "",
            "# Verify /workspace is mounted and files exist",
            "if os.path.exists('/workspace'):",
            "    print('✅ /workspace is mounted', flush=True)",
            "    try:",
            "        contents = os.listdir('/workspace')",
            "        print(f'/workspace contents: {contents}', flush=True)",
            "    except Exception as e:",
            "        print(f'⚠️ Error listing /workspace: {e}', flush=True)",
            "    ",
            "    client_dir_exists = os.path.exists('/workspace/client')",
            "    print(f'/workspace/client exists: {client_dir_exists}', flush=True)",
            "    if client_dir_exists:",
            "        try:",
            "            client_contents = os.listdir('/workspace/client')",
            "            print(f'/workspace/client contents: {client_contents}', flush=True)",
            "        except Exception as e:",
            "            print(f'⚠️ Error listing /workspace/client: {e}', flush=True)",
            "    ",
            "    mcp_client_exists = os.path.exists('/workspace/client/mcp_client.py')",
            "    print(f'/workspace/client/mcp_client.py exists: {mcp_client_exists}', flush=True)",
            "    if mcp_client_exists:",
            "        print('✅ client/mcp_client.py exists', flush=True)",
            "        # Try to import to verify it works",
            "        try:",
            "            from client.mcp_client import call_mcp_tool",
            "            print('✅ client.mcp_client imported successfully', flush=True)",
            "        except Exception as e:",
            "            print(f'⚠️ client.mcp_client import failed: {e}', flush=True)",
            "            import traceback",
            "            traceback.print_exc(file=sys.stdout)",
            "    else:",
            "        print('⚠️ client/mcp_client.py not found', flush=True)",
            "else:",
            "    print('❌ /workspace not mounted', flush=True)",
            "",
        ])

