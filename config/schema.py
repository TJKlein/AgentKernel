"""Configuration schemas using Pydantic."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class MCPServerConfig(BaseModel):
    """Configuration for an MCP server."""

    name: str = Field(..., description="Server name")
    url: str = Field(..., description="Connection URL (SSE, stdio, or HTTP)")
    connection_type: str = Field(default="sse", description="Connection type: sse, stdio, or http")
    enabled: bool = Field(default=True, description="Whether the server is enabled")
    timeout: int = Field(default=30, description="Connection timeout in seconds")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    @field_validator("connection_type")
    @classmethod
    def validate_connection_type(cls, v: str) -> str:
        """Validate connection type."""
        if v not in ["sse", "stdio", "http"]:
            raise ValueError(f"Invalid connection type: {v}. Must be sse, stdio, or http")
        return v


class GuardrailConfig(BaseModel):
    """Configuration for guardrails."""

    enabled: bool = Field(default=True, description="Whether guardrails are enabled")
    strict_mode: bool = Field(default=False, description="Strict validation mode")
    content_filtering: bool = Field(default=True, description="Enable content filtering")
    security_checks: bool = Field(default=True, description="Enable security checks")
    privacy_protection: bool = Field(default=True, description="Enable privacy protection")
    pii_detection: bool = Field(default=True, description="Enable PII detection")
    tokenization: bool = Field(default=True, description="Enable data tokenization")
    rate_limiting: bool = Field(default=True, description="Enable rate limiting")
    max_execution_time: int = Field(default=300, description="Max execution time in seconds")
    max_memory_mb: int = Field(default=512, description="Max memory in MB")
    allowed_networks: List[str] = Field(
        default_factory=list, description="Allowed network endpoints"
    )
    blocked_patterns: List[str] = Field(default_factory=list, description="Blocked code patterns")


class OptimizationConfig(BaseModel):
    """Configuration for performance optimizations."""

    enabled: bool = Field(default=True, description="Enable all optimizations")
    sandbox_pooling: bool = Field(default=False, description="Enable sandbox pooling (experimental - disabled by default)")
    sandbox_pool_size: int = Field(default=3, description="Number of sandboxes in pool")
    tool_cache: bool = Field(default=True, description="Enable tool description caching")
    tool_cache_file: str = Field(default=".tool_cache.json", description="Tool cache file path")
    gpu_embeddings: bool = Field(default=True, description="Use GPU for embeddings if available")
    parallel_discovery: bool = Field(default=True, description="Enable parallel tool discovery")
    file_content_cache: bool = Field(default=True, description="Enable file content caching")


class ExecutionConfig(BaseModel):
    """Configuration for code execution."""

    sandbox_type: str = Field(default="microsandbox", description="Sandbox type")
    sandbox_image: str = Field(default="python", description="Sandbox image")
    workspace_dir: str = Field(default="./workspace", description="Workspace directory")
    servers_dir: str = Field(default="./servers", description="Servers directory")
    skills_dir: str = Field(default="./skills", description="Skills directory")
    allow_network_access: bool = Field(
        default=False, description="Allow network access from sandbox"
    )
    mount_directories: List[str] = Field(
        default_factory=list, description="Directories to mount in sandbox"
    )


class ToolMappingConfig(BaseModel):
    """Configuration for tool mappings."""

    server_name: str = Field(..., description="Server name")
    tool_name: str = Field(..., description="Tool name")
    python_function_name: str = Field(..., description="Python function name")
    input_schema: Dict[str, Any] = Field(..., description="Input schema")
    output_schema: Dict[str, Any] = Field(..., description="Output schema")


class WorkflowStepConfig(BaseModel):
    """Configuration for a workflow step."""

    name: str = Field(..., description="Step name")
    type: str = Field(..., description="Step type: tool_call, code_execution, condition, loop")
    config: Dict[str, Any] = Field(..., description="Step configuration")
    guardrails: Optional[GuardrailConfig] = Field(
        default=None, description="Step-specific guardrails"
    )
    on_error: Optional[str] = Field(default=None, description="Error handling strategy")
    retry: Optional[Dict[str, Any]] = Field(default=None, description="Retry configuration")


class WorkflowConfig(BaseModel):
    """Configuration for a workflow."""

    name: str = Field(..., description="Workflow name")
    description: Optional[str] = Field(default=None, description="Workflow description")
    version: str = Field(default="1.0", description="Workflow version")
    steps: List[WorkflowStepConfig] = Field(..., description="Workflow steps")
    variables: Dict[str, Any] = Field(default_factory=dict, description="Workflow variables")
    guardrails: Optional[GuardrailConfig] = Field(
        default=None, description="Workflow-level guardrails"
    )


class AppConfig(BaseModel):
    """Main application configuration."""

    mcp_servers: List[MCPServerConfig] = Field(
        default_factory=list, description="MCP server configurations"
    )
    guardrails: GuardrailConfig = Field(
        default_factory=GuardrailConfig, description="Global guardrail configuration"
    )
    execution: ExecutionConfig = Field(
        default_factory=ExecutionConfig, description="Execution configuration"
    )
    optimizations: OptimizationConfig = Field(
        default_factory=OptimizationConfig, description="Performance optimization configuration"
    )
    tool_mappings: List[ToolMappingConfig] = Field(
        default_factory=list, description="Tool mappings"
    )
    workflows: List[WorkflowConfig] = Field(
        default_factory=list, description="Workflow configurations"
    )
    logging: Dict[str, Any] = Field(
        default_factory=lambda: {"level": "INFO", "file": "logs/code-execution-mcp.log"},
        description="Logging configuration",
    )
