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
from config.schema import ExecutionConfig, GuardrailConfig

logger = logging.getLogger(__name__)


class SandboxExecutor(CodeExecutor):
    """Sandbox executor using microsandbox."""

    def __init__(
        self,
        execution_config: ExecutionConfig,
        guardrail_config: Optional[GuardrailConfig] = None,
    ):
        """Initialize sandbox executor."""
        self.execution_config = execution_config
        self.guardrail_config = guardrail_config or GuardrailConfig()
        self.guardrail_validator = GuardrailValidatorImpl(self.guardrail_config)

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

    async def _execute_async(self, code: str) -> tuple[Any, Optional[str]]:
        """Execute code asynchronously in sandbox."""
        if PythonSandbox is None:
            raise ImportError("microsandbox is not installed")

        try:
            # Prepare workspace with required directories before sandbox creation
            workspace_path = Path(self.execution_config.workspace_dir)
            workspace_path.mkdir(parents=True, exist_ok=True)

            # Get absolute paths for source directories
            # Read directly from source - no need to copy to workspace first
            servers_path = Path(self.execution_config.servers_dir).resolve()
            skills_path = Path(self.execution_config.skills_dir).resolve()

            # Find client directory (typically at project root)
            project_root = workspace_path.parent.resolve()
            client_path = project_root / "client"

            # Read files directly from source directories and embed in setup code
            # Files are written into sandbox for execution (sandbox is isolated)
            # State files created by code should be written to workspace (persistent)
            # Note: microsandbox Rust core supports volumes via patch_with_virtiofs_mounts,
            # but Python API doesn't expose this yet. For now, we copy workspace files in.
            # TODO: Extend PythonSandbox.create() to support volumes parameter
            async with PythonSandbox.create(name="code-execution") as sandbox:
                import asyncio

                try:
                    # First run: Write files into sandbox
                    # Read directly from source directories (servers, client, skills)
                    # Embed in setup code and write into sandbox so they're importable
                    setup_code = self._generate_copy_code(
                        servers_path=servers_path,
                        client_path=client_path,
                        skills_path=skills_path,
                    )
                    setup_result = await asyncio.wait_for(sandbox.run(setup_code), timeout=15.0)
                    setup_output = await setup_result.output()

                    # Check for setup errors
                    if setup_output and "Setup error:" in setup_output:
                        return setup_output, setup_output

                    # Copy workspace files into sandbox (for state persistence)
                    # This allows code to read previous state
                    workspace_files_code = self._generate_workspace_copy_in_code(workspace_path)
                    if workspace_files_code:
                        workspace_setup_result = await asyncio.wait_for(
                            sandbox.run(workspace_files_code), timeout=10.0
                        )
                        workspace_setup_output = await workspace_setup_result.output()
                        if workspace_setup_output and "Setup error:" in workspace_setup_output:
                            return workspace_setup_output, workspace_setup_output

                    # Second run: Execute the task code
                    # Files copied in first run are now available in sandbox
                    exec_result = await asyncio.wait_for(sandbox.run(code), timeout=30.0)
                    # Get output
                    output = await exec_result.output()
                    error = None

                    # Copy workspace files back from sandbox (for state persistence)
                    # This saves state created during execution
                    workspace_sync_code = self._generate_workspace_sync_code(workspace_path)
                    if workspace_sync_code:
                        try:
                            sync_result = await asyncio.wait_for(
                                sandbox.run(workspace_sync_code), timeout=10.0
                            )
                            sync_output = await sync_result.output()
                            # Sync output is informational, not critical
                        except Exception as e:
                            logger.warning(f"Workspace sync failed (non-critical): {e}")

                    # Combine setup and execution output (only if setup had important output)
                    if setup_output and setup_output.strip() and "Setup error:" in setup_output:
                        output = setup_output + "\n" + (output or "")

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

        except Exception as e:
            logger.error(f"Sandbox execution error: {e}", exc_info=True)
            return None, str(e)

    def _generate_copy_code(self, servers_path: Path, client_path: Path, skills_path: Path) -> str:
        """Generate code to write files into sandbox.

        Reads files directly from source directories and embeds them in setup code.
        Files are written into sandbox so they're importable.
        State files created by code should be written to workspace (persistent).
        """
        import base64

        setup_lines = [
            "import os",
            "import base64",
            "",
            "# Create directory structure in sandbox",
            "os.makedirs('servers', exist_ok=True)",
            "os.makedirs('client', exist_ok=True)",
            "os.makedirs('skills', exist_ok=True)",
            "",
        ]

        # Write client directory FIRST (servers depend on it)
        client_dir = client_path
        if client_dir.exists():
            # Write minimal __init__.py
            setup_lines.append(
                "try:\n"
                "    with open('client/__init__.py', 'w', encoding='utf-8') as f:\n"
                '        f.write(\'"""Client module for sandbox execution."""\\n\')\n'
                "except Exception as e:\n"
                "    print(f'Error writing client/__init__.py: {e}', flush=True)\n"
                "    raise"
            )

            # Write mock mcp_client.py (for examples)
            mock_client_file = client_dir / "mock_mcp_client.py"
            if mock_client_file.exists():
                content = mock_client_file.read_text(encoding="utf-8")
                content_b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")
                setup_lines.append(
                    f"try:\n"
                    f"    decoded_content = base64.b64decode('{content_b64}').decode('utf-8')\n"
                    f"    with open('client/mcp_client.py', 'w', encoding='utf-8') as f:\n"
                    f"        f.write(decoded_content)\n"
                    f"except Exception as e:\n"
                    f"    print(f'Error writing mcp_client.py: {{e}}', flush=True)\n"
                    f"    raise"
                )
            else:
                # Fallback: try to use real mcp_client.py if mock doesn't exist
                real_client_file = client_dir / "mcp_client.py"
                if real_client_file.exists():
                    content = real_client_file.read_text(encoding="utf-8")
                    content_b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")
                    setup_lines.append(
                        f"try:\n"
                        f"    decoded_content = base64.b64decode('{content_b64}').decode('utf-8')\n"
                        f"    with open('client/mcp_client.py', 'w', encoding='utf-8') as f:\n"
                        f"        f.write(decoded_content)\n"
                        f"except Exception as e:\n"
                        f"    print(f'Error writing mcp_client.py: {{e}}', flush=True)\n"
                        f"    raise"
                    )

        # Write servers directory (after client is available)
        servers_dir = servers_path
        if servers_dir.exists():
            for server_dir in sorted(servers_dir.iterdir()):
                if server_dir.is_dir():
                    server_name = server_dir.name
                    setup_lines.append(f"os.makedirs('servers/{server_name}', exist_ok=True)")
                    # Write tool files first (before __init__.py which imports them)
                    for tool_file in sorted(server_dir.glob("*.py")):
                        if tool_file.name != "__init__.py":
                            content = tool_file.read_text(encoding="utf-8")
                            content_b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")
                            setup_lines.append(
                                f"try:\n"
                                f"    decoded_content = base64.b64decode('{content_b64}').decode('utf-8')\n"
                                f"    with open('servers/{server_name}/{tool_file.name}', 'w', encoding='utf-8') as f:\n"
                                f"        f.write(decoded_content)\n"
                                f"except Exception as e:\n"
                                f"    print(f'Error writing {tool_file.name}: {{e}}', flush=True)\n"
                                f"    raise"
                            )
                    # Write __init__.py last (it imports from tool files)
                    init_file = server_dir / "__init__.py"
                    if init_file.exists():
                        content = init_file.read_text(encoding="utf-8")
                        content_b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")
                        setup_lines.append(
                            f"try:\n"
                            f"    decoded_content = base64.b64decode('{content_b64}').decode('utf-8')\n"
                            f"    with open('servers/{server_name}/__init__.py', 'w', encoding='utf-8') as f:\n"
                            f"        f.write(decoded_content)\n"
                            f"except Exception as e:\n"
                            f"    print(f'Error writing __init__.py: {{e}}', flush=True)\n"
                            f"    raise"
                        )

        # Add current directory to sys.path and clear import cache
        setup_lines.append("import sys")
        setup_lines.append("if '.' not in sys.path:")
        setup_lines.append("    sys.path.insert(0, '.')")
        setup_lines.append("")
        setup_lines.append("# Clear any cached modules to force fresh imports")
        setup_lines.append(
            "modules_to_clear = [m for m in list(sys.modules.keys()) if m.startswith('servers.') or m.startswith('client.')]"
        )
        setup_lines.append("for mod in modules_to_clear:")
        setup_lines.append("    del sys.modules[mod]")

        return "\n".join(setup_lines)

    def _generate_workspace_copy_in_code(self, workspace_path: Path) -> str:
        """Generate code to copy workspace files into sandbox.

        This allows code to read previous state from workspace.
        Since microsandbox doesn't support mounting, we copy files in.
        """
        if not workspace_path.exists():
            return ""

        import base64

        lines = [
            "import os",
            "import base64",
            "",
            "# Create workspace directory in sandbox",
            "os.makedirs('workspace', exist_ok=True)",
            "",
        ]

        # Copy all files from workspace into sandbox
        file_count = 0
        for file_path in workspace_path.rglob("*"):
            if file_path.is_file():
                rel_path = file_path.relative_to(workspace_path)
                # Skip hidden files and __pycache__
                if rel_path.parts[0].startswith(".") or "__pycache__" in rel_path.parts:
                    continue

                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                    content_b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")

                    # Create directory structure
                    if rel_path.parent != Path("."):
                        dir_path = "workspace/" + str(rel_path.parent).replace("\\", "/")
                        lines.append(f"os.makedirs('{dir_path}', exist_ok=True)")

                    # Write file
                    file_name = rel_path.name
                    rel_path_str = str(rel_path).replace("\\", "/")
                    lines.append(
                        f"try:\n"
                        f"    decoded_content = base64.b64decode('{content_b64}').decode('utf-8')\n"
                        f"    with open('workspace/{rel_path_str}', 'w', encoding='utf-8') as f:\n"
                        f"        f.write(decoded_content)\n"
                        f"except Exception as e:\n"
                        f"    print(f'Error copying workspace file {rel_path_str}: {{e}}', flush=True)"
                    )
                    file_count += 1
                except Exception as e:
                    logger.warning(f"Failed to read workspace file {file_path}: {e}")

        if file_count > 0:
            lines.append(
                f"print(f'Copied {file_count} workspace file(s) into sandbox', flush=True)"
            )
            return "\n".join(lines)
        return ""

    def _generate_workspace_sync_code(self, workspace_path: Path) -> str:
        """Generate code to identify workspace files for sync.

        Note: microsandbox doesn't provide direct file extraction.
        Files written to workspace/ in sandbox persist within the session
        but need to be extracted separately for cross-session persistence.
        This is a limitation of the current microsandbox API.
        """
        # For now, just log what files are in workspace
        # In a full implementation, you'd extract these files from sandbox
        lines = [
            "import os",
            "",
            "# List files in workspace directory (for debugging)",
            "workspace_files = []",
            "if os.path.exists('workspace'):",
            "    for root, dirs, files in os.walk('workspace'):",
            "        for file in files:",
            "            file_path = os.path.join(root, file)",
            "            if os.path.isfile(file_path):",
            "                rel_path = os.path.relpath(file_path, 'workspace')",
            "                workspace_files.append(rel_path)",
            "",
            "if workspace_files:",
            "    print(f'Workspace files created: {workspace_files}', flush=True)",
        ]
        return "\n".join(lines)
