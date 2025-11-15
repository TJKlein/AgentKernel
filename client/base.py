"""Base classes and interfaces for extensibility."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable
from dataclasses import dataclass
from enum import Enum


class ExecutionResult(Enum):
    """Execution result status."""

    SUCCESS = "success"
    FAILURE = "failure"
    BLOCKED = "blocked"
    TIMEOUT = "timeout"


@dataclass
class ToolCall:
    """Represents a tool call."""

    server_name: str
    tool_name: str
    parameters: Dict[str, Any]
    result: Optional[Any] = None
    error: Optional[str] = None


@dataclass
class ValidationResult:
    """Result of a validation operation."""

    valid: bool
    errors: List[str]
    warnings: List[str]


@runtime_checkable
class MCPAdapter(Protocol):
    """Protocol for MCP server adapters."""

    def connect(self, connection_string: str) -> None:
        """Connect to an MCP server."""
        ...

    def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools from the server."""
        ...

    def call_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        """Call a tool on the server."""
        ...

    def disconnect(self) -> None:
        """Disconnect from the server."""
        ...


class WorkflowExecutor(ABC):
    """Abstract base class for workflow executors."""

    @abstractmethod
    def execute(self, workflow_config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a workflow."""
        ...

    @abstractmethod
    def validate(self, workflow_config: Dict[str, Any]) -> ValidationResult:
        """Validate a workflow configuration."""
        ...


class ToolGenerator(ABC):
    """Abstract base class for tool generators."""

    @abstractmethod
    def generate_tool_file(
        self, server_name: str, tool_definition: Dict[str, Any], output_dir: str
    ) -> str:
        """Generate a tool file from a tool definition."""
        ...

    @abstractmethod
    def generate_index_file(self, server_name: str, tools: List[str], output_dir: str) -> str:
        """Generate an index file for a server."""
        ...


class CodeExecutor(ABC):
    """Abstract base class for code executors."""

    @abstractmethod
    def execute(
        self, code: str, context: Optional[Dict[str, Any]] = None
    ) -> tuple[ExecutionResult, Any, Optional[str]]:
        """Execute code in a sandboxed environment."""
        ...

    @abstractmethod
    def validate_code(self, code: str) -> ValidationResult:
        """Validate code before execution."""
        ...


class GuardrailValidator(ABC):
    """Abstract base class for guardrail validators."""

    @abstractmethod
    def validate_input(self, data: Any, context: Dict[str, Any]) -> ValidationResult:
        """Validate input data."""
        ...

    @abstractmethod
    def validate_output(self, data: Any, context: Dict[str, Any]) -> ValidationResult:
        """Validate output data."""
        ...

    @abstractmethod
    def validate_code(self, code: str, context: Dict[str, Any]) -> ValidationResult:
        """Validate code before execution."""
        ...


class TypeChecker(ABC):
    """Abstract base class for type checkers."""

    @abstractmethod
    def check_type(self, value: Any, expected_type: type) -> bool:
        """Check if a value matches an expected type."""
        ...

    @abstractmethod
    def validate_schema(self, data: Dict[str, Any], schema: Dict[str, Any]) -> ValidationResult:
        """Validate data against a schema."""
        ...


class Hook(ABC):
    """Abstract base class for hooks."""

    @abstractmethod
    def before_tool_call(self, tool_call: ToolCall) -> Optional[ToolCall]:
        """Called before a tool call."""
        ...

    @abstractmethod
    def after_tool_call(self, tool_call: ToolCall) -> None:
        """Called after a tool call."""
        ...

    @abstractmethod
    def before_code_execution(self, code: str, context: Dict[str, Any]) -> Optional[str]:
        """Called before code execution."""
        ...

    @abstractmethod
    def after_code_execution(
        self, result: ExecutionResult, output: Any, error: Optional[str]
    ) -> None:
        """Called after code execution."""
        ...


class Middleware(ABC):
    """Abstract base class for middleware."""

    @abstractmethod
    def process(self, request: Any, next_handler: Any) -> Any:
        """Process a request through the middleware chain."""
        ...
