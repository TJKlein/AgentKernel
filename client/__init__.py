"""Code Execution MCP - Core client components.

This package provides the main framework for code execution with MCP (Model Context Protocol).

Architecture:
    - Orchestration: AgentHelper (high-level coordination)
    - Execution: SandboxExecutor, SandboxPool (code execution)
    - Discovery: FilesystemHelper, ToolSelector (tool discovery/selection)
    - Generation: CodeGenerator (code generation)
    - Validation: GuardrailValidator (safety checks)
    - MCP Integration: MCPClient (MCP protocol)
"""

# Orchestration Layer
from client.agent_helper import AgentHelper

# Execution Layer
from client.sandbox_executor import SandboxExecutor
from client.sandbox_pool import SandboxPool
from client.base import CodeExecutor, ExecutionResult, ValidationResult

# Discovery Layer
from client.filesystem_helpers import FilesystemHelper
from client.tool_selector import ToolSelector
from client.tool_cache import ToolCache

# Generation Layer
from client.code_generator import CodeGenerator

# Validation Layer
from client.guardrails import GuardrailValidatorImpl
from client.validators import SecurityValidator, PathValidator, SchemaValidator

# MCP Integration Layer
from client.mcp_client import MCPClient
from client.mock_mcp_client import MockMCPClient

# Error Handling
from client.errors import (
    CodeExecutionMCPError,
    MCPConnectionError,
    MCPToolCallError,
    ValidationError,
    GuardrailError,
    SandboxExecutionError,
    WorkflowExecutionError,
)

__all__ = [
    # Orchestration
    "AgentHelper",
    # Execution
    "SandboxExecutor",
    "SandboxPool",
    "CodeExecutor",
    "ExecutionResult",
    "ValidationResult",
    # Discovery
    "FilesystemHelper",
    "ToolSelector",
    "ToolCache",
    # Generation
    "CodeGenerator",
    # Validation
    "GuardrailValidatorImpl",
    "SecurityValidator",
    "PathValidator",
    "SchemaValidator",
    # MCP Integration
    "MCPClient",
    "MockMCPClient",
    # Errors
    "CodeExecutionMCPError",
    "MCPConnectionError",
    "MCPToolCallError",
    "ValidationError",
    "GuardrailError",
    "SandboxExecutionError",
    "WorkflowExecutionError",
]
