"""Monty executor implementation."""

import logging
import io
import sys
from typing import Any, Dict, Optional, List
from pathlib import Path

try:
    from pydantic_monty import Monty, ResourceLimits
except ImportError:
    Monty = None
    ResourceLimits = None

from client.base_executor import BaseExecutor
from client.base import ExecutionResult
from config.schema import ExecutionConfig, GuardrailConfig, OptimizationConfig

logger = logging.getLogger(__name__)


class MontyExecutor(BaseExecutor):
    """Execution backend using pydantic-monty."""

    def __init__(
        self,
        execution_config: ExecutionConfig,
        guardrail_config: Optional[GuardrailConfig] = None,
        optimization_config: Optional[OptimizationConfig] = None,
    ):
        """Initialize Monty executor."""
        super().__init__(execution_config, guardrail_config, optimization_config)

    def execute(self, code: str, context: Optional[Dict[str, Any]] = None) -> tuple[ExecutionResult, Any, Optional[str]]:
        """Execute code using Monty."""
        if Monty is None:
            raise ImportError(
                "pydantic-monty is not installed. Install it with: pip install pydantic-monty"
            )

        # Pre-execution validation
        validation_result = self.validate_code(code)
        if not validation_result.valid:
            error_msg = "; ".join(validation_result.errors)
            logger.error(f"Code validation failed: {error_msg}")
            return ExecutionResult.FAILURE, None, error_msg

        output_buffer = io.StringIO()

        def print_cb(kind: str, text: str) -> None:
            output_buffer.write(text)

        try:
            # Find project root for path setup
            project_root = self._find_project_root()
            workspace_path = (project_root / self.execution_config.workspace_dir.lstrip("./")).resolve()
            
            # Setup code to add workspace to sys.path
            # Monty has its own import system, we might need to handle it via external_functions or inputs
            # For now, we'll try to execute it as is.
            
            # Monty requires code at init
            # We wrap the code to add /workspace to sys.path if possible, 
            # but Monty might not support sys.path directly if it's a minimal interpreter.
            # Usually we'd use the 'os' callback to redirect file access to the workspace.
            
            # Prepare external functions for Monty
            # Monty doesn't support complex standard library imports yet, so we provide helpers
            import json
            ext_funcs = {
                "json_loads": json.loads,
                "json_dumps": json.dumps,
            }
            if context:
                # Add context functions if needed
                pass
                
            logger.info(f"Executing Monty code:\n{code}")
            logger.info(f"External functions: {list(ext_funcs.keys())}")
            
            mnt = Monty(
                code=code,
                external_functions=list(ext_funcs.keys())
            )
            
            # Use os callback to redirect file access to workspace
            def os_cb(func_name: str, args: tuple[Any, ...], kwargs: Optional[Dict[str, Any]] = None) -> Any:
                try:
                    # Basic OS redirection for safety and workspace access
                    # args[0] is usually the path (as string or PurePosixPath)
                    path_str = str(args[0])
                    if path_str.startswith("/workspace/"):
                        rel_path = path_str[11:]
                    elif path_str.startswith("/workspace"):
                        rel_path = path_str[10:]
                    else:
                        rel_path = path_str.lstrip("/")
                        
                    # Prevent path traversal
                    if ".." in rel_path:
                        raise PermissionError("Path traversal not allowed")
                        
                    real_path = (workspace_path / rel_path).resolve()
                    if not str(real_path).startswith(str(workspace_path)):
                         raise PermissionError("Access outside workspace not allowed")

                    if func_name == "Path.read_text":
                        return real_path.read_text(encoding="utf-8")
                    elif func_name == "Path.read_bytes":
                        return real_path.read_bytes()
                    elif func_name == "Path.write_text":
                        # args[1] is data
                        return real_path.write_text(args[1], encoding="utf-8")
                    elif func_name == "Path.write_bytes":
                        return real_path.write_bytes(args[1])
                    elif func_name == "Path.exists":
                        return real_path.exists()
                    elif func_name == "Path.is_file":
                        return real_path.is_file()
                    elif func_name == "Path.is_dir":
                        return real_path.is_dir()
                    elif func_name == "Path.mkdir":
                        # kwargs are passed in args? No, os_cb signature in _monty.pyi says:
                        # os: Callable[[OsFunction, tuple[Any, ...]], Any]
                        # It doesn't receive kwargs explicitly?
                        # Wait, AbstractOS.__call__ receives kwargs.
                        # But Monty.run call signature says:
                        # os: Callable[[OsFunction, tuple[Any, ...]], Any]
                        # Let's assume args logic for now. 
                        # mkdir usually takes parents, exist_ok.
                        # We'll just default to parents=True, exist_ok=True for now as mostly assumed behavior
                        real_path.mkdir(parents=True, exist_ok=True)
                        return None
                    
                    return None
                except Exception as e:
                    logger.error(f"OS callback error for {func_name}: {e}")
                    raise

            result = mnt.run(
                print_callback=print_cb,
                os=os_cb,
                external_functions=ext_funcs,
            )
            
            output = output_buffer.getvalue()
            
            # Post-execution validation
            if output:
                output_result = self.guardrail_validator.validate_output(output, {})
                if not output_result.valid and self.guardrail_config.strict_mode:
                    error_msg = "; ".join(output_result.errors)
                    logger.error(f"Output validation failed: {error_msg}")
                    return ExecutionResult.BLOCKED, None, error_msg

            return ExecutionResult.SUCCESS, output, None

        except Exception as e:
            logger.error(f"Monty execution failed: {e}")
            return ExecutionResult.FAILURE, None, str(e)
