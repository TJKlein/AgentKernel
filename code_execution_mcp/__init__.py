"""Code Execution MCP - A framework for code execution with MCP (Model Context Protocol).

This package provides a simple, high-level API for executing tasks using MCP servers
through Python code generation and sandboxed execution.

Quick Start:
    >>> from code_execution_mcp import create_agent, execute_task
    >>> agent = create_agent()
    >>> result, output, error = execute_task("Calculate 5 + 3")
"""

from typing import Optional, Tuple, Any

# Re-export main components for advanced usage
# Organized by architectural layer for clarity
from client import (
    # Orchestration
    AgentHelper,
    # Execution
    SandboxExecutor,
    SandboxPool,
    CodeExecutor,
    ExecutionResult,
    ValidationResult,
    # Discovery
    FilesystemHelper,
    ToolSelector,
    ToolCache,
    # Generation
    CodeGenerator,
    # Validation
    GuardrailValidatorImpl,
    SecurityValidator,
    PathValidator,
    SchemaValidator,
    # MCP Integration
    MCPClient,
    MockMCPClient,
    # Errors
    CodeExecutionMCPError,
    MCPConnectionError,
    MCPToolCallError,
    ValidationError,
    GuardrailError,
    SandboxExecutionError,
    WorkflowExecutionError,
)
from config import (
    load_config,
    ConfigLoader,
    ExecutionConfig,
    GuardrailConfig,
    LLMConfig,
    StateConfig,
    AppConfig,
)
from server import MCPServer, create_server, run_server

# Import for factory function (use internal imports)
from client.agent_helper import AgentHelper as _AgentHelper
from client.filesystem_helpers import FilesystemHelper as _FilesystemHelper
from client.sandbox_executor import SandboxExecutor as _SandboxExecutor
from config.loader import load_config as _load_config
from config.schema import AppConfig as _AppConfig, OptimizationConfig

__version__ = "0.1.0"

__all__ = [
    # Main API
    "create_agent",
    "execute_task",
    # Components (organized by architectural layer)
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
    # Configuration
    "load_config",
    "ConfigLoader",
    "ExecutionConfig",
    "GuardrailConfig",
    "LLMConfig",
    "StateConfig",
    "AppConfig",
    # MCP Server
    "MCPServer",
    "create_server",
    "run_server",
]


def create_agent(
    workspace_dir: Optional[str] = None,
    servers_dir: Optional[str] = None,
    skills_dir: Optional[str] = None,
    config: Optional[_AppConfig] = None,
    # LLM configuration
    llm_enabled: Optional[bool] = None,
    llm_provider: Optional[str] = None,
    llm_model: Optional[str] = None,
    llm_api_key: Optional[str] = None,
    llm_azure_endpoint: Optional[str] = None,
    llm_azure_deployment: Optional[str] = None,
    llm_temperature: Optional[float] = None,
    llm_max_tokens: Optional[int] = None,
    # State configuration
    state_enabled: Optional[bool] = None,
    state_file: Optional[str] = None,
    state_auto_save: Optional[bool] = None,
    **kwargs: Any,
) -> _AgentHelper:
    """Create an AgentHelper instance with sensible defaults.
    
    This is the recommended way to initialize the framework. It handles all the
    setup boilerplate automatically.
    
    Args:
        workspace_dir: Path to workspace directory (defaults to ./workspace)
        servers_dir: Path to servers directory (defaults to ./servers)
        skills_dir: Path to skills directory (defaults to ./skills)
        config: Optional AppConfig instance (if None, loads from config.yaml/.env)
        
        # LLM Configuration (programmatic)
        llm_enabled: Enable LLM-based code generation
        llm_provider: LLM provider ('openai', 'azure_openai', 'anthropic')
        llm_model: Model name (e.g., 'gpt-4o-mini')
        llm_api_key: API key (or set OPENAI_API_KEY/AZURE_OPENAI_API_KEY env var)
        llm_azure_endpoint: Azure OpenAI endpoint URL
        llm_azure_deployment: Azure deployment name
        llm_temperature: Temperature for code generation (default: 0.3)
        llm_max_tokens: Max tokens for code generation (default: 2000)
        
        # State Configuration (programmatic)
        state_enabled: Enable state persistence (default: True)
        state_file: State file name (default: 'state.json')
        state_auto_save: Auto-save state after execution (default: True)
        
        **kwargs: Additional arguments passed to AgentHelper
        
    Returns:
        AgentHelper instance ready to use
        
    Example:
        >>> # Basic usage
        >>> agent = create_agent()
        >>> result, output, error = agent.execute_task("Your task here")
        
        >>> # With custom directories
        >>> agent = create_agent(
        ...     workspace_dir="./my_workspace",
        ...     servers_dir="./my_servers"
        ... )
        
        >>> # With LLM configuration
        >>> agent = create_agent(
        ...     llm_enabled=True,
        ...     llm_provider="azure_openai",
        ...     llm_azure_endpoint="https://your-resource.openai.azure.com",
        ...     llm_api_key="your_key"
        ... )
        
        >>> # With state configuration
        >>> agent = create_agent(
        ...     state_enabled=True,
        ...     state_file="my_state.json",
        ...     state_auto_save=True
        ... )
    """
    # Load config if not provided
    if config is None:
        config = _load_config()
    
    # Apply LLM configuration overrides
    if llm_enabled is not None:
        config.llm.enabled = llm_enabled
    if llm_provider is not None:
        config.llm.provider = llm_provider
    if llm_model is not None:
        config.llm.model = llm_model
    if llm_api_key is not None:
        config.llm.api_key = llm_api_key
    if llm_azure_endpoint is not None:
        config.llm.azure_endpoint = llm_azure_endpoint
    if llm_azure_deployment is not None:
        config.llm.azure_deployment_name = llm_azure_deployment
    if llm_temperature is not None:
        config.llm.temperature = llm_temperature
    if llm_max_tokens is not None:
        config.llm.max_tokens = llm_max_tokens
    
    # Apply state configuration overrides
    if state_enabled is not None:
        config.execution.state.enabled = state_enabled
    if state_file is not None:
        config.execution.state.state_file = state_file
    if state_auto_save is not None:
        config.execution.state.auto_save = state_auto_save
    
    # Use config values or provided values for directories
    workspace = workspace_dir or config.execution.workspace_dir
    servers = servers_dir or config.execution.servers_dir
    skills = skills_dir or config.execution.skills_dir
    
    # Update workspace in state config if workspace_dir was provided
    if workspace_dir:
        config.execution.state.workspace_dir = workspace
    
    # Initialize filesystem helper
    fs_helper = _FilesystemHelper(
        workspace_dir=workspace,
        servers_dir=servers,
        skills_dir=skills,
    )
    
    # Initialize sandbox executor
    executor = _SandboxExecutor(
        execution_config=config.execution,
        guardrail_config=config.guardrails,
        optimization_config=config.optimizations,
    )
    
    # Initialize agent helper
    agent = _AgentHelper(
        fs_helper,
        executor,
        optimization_config=config.optimizations,
        llm_config=config.llm,
        **kwargs,
    )
    
    return agent


def execute_task(
    task_description: str,
    workspace_dir: Optional[str] = None,
    servers_dir: Optional[str] = None,
    skills_dir: Optional[str] = None,
    verbose: bool = False,
    # LLM configuration
    llm_enabled: Optional[bool] = None,
    llm_provider: Optional[str] = None,
    llm_model: Optional[str] = None,
    llm_api_key: Optional[str] = None,
    llm_azure_endpoint: Optional[str] = None,
    llm_azure_deployment: Optional[str] = None,
    # State configuration
    state_enabled: Optional[bool] = None,
    state_file: Optional[str] = None,
    state_auto_save: Optional[bool] = None,
    **kwargs: Any,
) -> Tuple[Any, str, Optional[str]]:
    """Execute a task using the framework (convenience function).
    
    This is the simplest way to use the framework - it creates an agent,
    executes the task, and returns the result.
    
    Args:
        task_description: Description of the task to execute
        workspace_dir: Path to workspace directory (optional)
        servers_dir: Path to servers directory (optional)
        skills_dir: Path to skills directory (optional)
        verbose: Whether to print progress information
        
        # LLM Configuration (programmatic)
        llm_enabled: Enable LLM-based code generation
        llm_provider: LLM provider ('openai', 'azure_openai', 'anthropic')
        llm_model: Model name (e.g., 'gpt-4o-mini')
        llm_api_key: API key (or set OPENAI_API_KEY/AZURE_OPENAI_API_KEY env var)
        llm_azure_endpoint: Azure OpenAI endpoint URL
        llm_azure_deployment: Azure deployment name
        
        # State Configuration (programmatic)
        state_enabled: Enable state persistence (default: True)
        state_file: State file name (default: 'state.json')
        state_auto_save: Auto-save state after execution (default: True)
        
        **kwargs: Additional arguments passed to create_agent()
        
    Returns:
        Tuple of (result, output, error)
        
    Example:
        >>> # Basic usage
        >>> result, output, error = execute_task("Calculate 5 + 3")
        
        >>> # With LLM configuration
        >>> result, output, error = execute_task(
        ...     "Generate code",
        ...     llm_enabled=True,
        ...     llm_provider="azure_openai",
        ...     llm_azure_endpoint="https://your-resource.openai.azure.com"
        ... )
        
        >>> # With state configuration
        >>> result, output, error = execute_task(
        ...     "Process data",
        ...     state_enabled=True,
        ...     state_file="my_state.json"
        ... )
    """
    agent = create_agent(
        workspace_dir=workspace_dir,
        servers_dir=servers_dir,
        skills_dir=skills_dir,
        llm_enabled=llm_enabled,
        llm_provider=llm_provider,
        llm_model=llm_model,
        llm_api_key=llm_api_key,
        llm_azure_endpoint=llm_azure_endpoint,
        llm_azure_deployment=llm_azure_deployment,
        state_enabled=state_enabled,
        state_file=state_file,
        state_auto_save=state_auto_save,
        **kwargs,
    )
    return agent.execute_task(task_description=task_description, verbose=verbose)

