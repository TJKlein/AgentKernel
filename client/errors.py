"""Error handling and custom exceptions."""

from typing import Any, Dict, List, Optional


class CodeExecutionMCPError(Exception):
    """Base exception for code execution MCP."""

    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        """Initialize error."""
        super().__init__(message)
        self.message = message
        self.context = context or {}


class MCPConnectionError(CodeExecutionMCPError):
    """Error connecting to MCP server."""

    pass


class MCPToolCallError(CodeExecutionMCPError):
    """Error calling MCP tool."""

    def __init__(
        self,
        message: str,
        server_name: str,
        tool_name: str,
        parameters: Optional[Dict[str, Any]] = None,
    ):
        """Initialize tool call error."""
        super().__init__(
            message,
            {
                "server_name": server_name,
                "tool_name": tool_name,
                "parameters": parameters,
            },
        )
        self.server_name = server_name
        self.tool_name = tool_name
        self.parameters = parameters


class ValidationError(CodeExecutionMCPError):
    """Validation error."""

    def __init__(
        self, message: str, errors: Optional[List[str]] = None, warnings: Optional[List[str]] = None
    ):
        """Initialize validation error."""
        super().__init__(message, {"errors": errors or [], "warnings": warnings or []})
        self.errors = errors or []
        self.warnings = warnings or []


class GuardrailError(CodeExecutionMCPError):
    """Guardrail validation error."""

    def __init__(
        self,
        message: str,
        guardrail_type: str,
        blocked_reason: Optional[str] = None,
    ):
        """Initialize guardrail error."""
        super().__init__(
            message,
            {
                "guardrail_type": guardrail_type,
                "blocked_reason": blocked_reason,
            },
        )
        self.guardrail_type = guardrail_type
        self.blocked_reason = blocked_reason


class SandboxExecutionError(CodeExecutionMCPError):
    """Sandbox execution error."""

    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        output: Optional[str] = None,
        error: Optional[str] = None,
    ):
        """Initialize sandbox execution error."""
        super().__init__(
            message,
            {
                "code": code,
                "output": output,
                "error": error,
            },
        )
        self.code = code
        self.output = output
        self.error = error


class WorkflowExecutionError(CodeExecutionMCPError):
    """Workflow execution error."""

    def __init__(
        self,
        message: str,
        workflow_name: str,
        step_name: Optional[str] = None,
        step_result: Optional[Any] = None,
    ):
        """Initialize workflow execution error."""
        super().__init__(
            message,
            {
                "workflow_name": workflow_name,
                "step_name": step_name,
                "step_result": step_result,
            },
        )
        self.workflow_name = workflow_name
        self.step_name = step_name
        self.step_result = step_result

