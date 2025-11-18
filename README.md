# Code Execution MCP Framework

A generic, extensible code execution pattern for MCP (Model Context Protocol) that allows agents to interact with MCP servers through Python code APIs instead of direct tool calls. This significantly reduces token consumption and improves efficiency by leveraging LLMs' strength at writing code.

## Table of Contents

- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
  - [Running as an MCP Server](#running-as-an-mcp-server)
- [Compliance with Anthropic's Code Execution with MCP](#compliance-with-anthropics-code-execution-with-mcp)
- [Examples](#examples)
- [Architecture](#architecture)
- [Features](#features)
- [Performance](#performance)
- [Development](#development)
  - [Testing MCP Tools](#testing-mcp-tools)
  - [Running Examples](#running-examples)
- [Troubleshooting](#troubleshooting)
- [License](#license)

## Installation

### Install from PyPI (when published)

```bash
pip install code-execution-mcp
```

### Install from Source

```bash
# Clone the repository
git clone https://github.com/your-org/code-execution-mcp.git
cd code-execution-mcp

# Install in development mode
pip install -e .

# Or install in regular mode
pip install .
```

### Install with Development Dependencies

```bash
pip install -e ".[dev]"
```

### Verify Installation

After installation, verify that the package can be imported:

```python
from code_execution_mcp import create_agent, execute_task
print("✓ Package installed successfully!")
```

## Configuration

**⚠️ Important:** The framework requires configuration before use.

### Quick Setup Checklist

Before using the framework, ensure:

- [ ] **Microsandbox server is running** (required)
- [ ] **Directory structure exists** (`servers/`, `workspace/`, `skills/`)
- [ ] **Environment variables set** (optional, for LLM code generation)
- [ ] **Configuration file created** (optional, for advanced settings)

### Required Configuration

#### 1. Microsandbox Server

The framework requires a running Microsandbox server for code execution.

**Install and start:**
```bash
# Install microsandbox
curl -sSL https://get.microsandbox.dev | sh

# Start server (keep running in a separate terminal)
msb server start --dev
```

**Verify it's running:**
```bash
curl http://localhost:5555/health
```

#### 2. Directory Structure

Create the required directories:

```bash
mkdir -p servers workspace skills
```

- **`servers/`**: Contains MCP tool files (Python modules)
- **`workspace/`**: Persistent storage for execution state
- **`skills/`**: Reusable code functions

**Example structure:**
```
your-project/
├── servers/          # Tool files
│   ├── calculator/
│   │   ├── __init__.py
│   │   └── add.py
│   └── weather/
│       ├── __init__.py
│       └── get_weather.py
├── workspace/       # Execution state (auto-created)
└── skills/          # Reusable code
    └── double_number.py
```

### Optional Configuration

#### Environment Variables (.env file)

Create a `.env` file in your project root:

```bash
# Microsandbox server URL (default: http://localhost:5555)
MSB_SERVER_URL=http://localhost:5555

# Directory paths (defaults shown)
WORKSPACE_DIR=./workspace
SERVERS_DIR=./servers
SKILLS_DIR=./skills

# Sandbox pooling (recommended for performance)
OPTIMIZATION_SANDBOX_POOLING=true

# LLM-based code generation (optional)
# Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
AZURE_OPENAI_API_KEY=your_api_key
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o-mini
AZURE_OPENAI_API_VERSION=2024-08-01-preview

# Or OpenAI
OPENAI_API_KEY=your_openai_key
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
LLM_TEMPERATURE=0.3
LLM_MAX_TOKENS=2000

# State Configuration (optional)
STATE_ENABLED=true
STATE_FILE=state.json
STATE_AUTO_SAVE=true
STATE_FORMAT=json

# Guardrails
GUARDRAILS_ENABLED=true
GUARDRAILS_STRICT_MODE=false
MAX_EXECUTION_TIME=300
MAX_MEMORY_MB=512

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/code-execution-mcp.log
```

#### Configuration File (config.yaml)

For advanced configuration, create `config.yaml` (see `config.example.yaml` for a template):

```yaml
execution:
  workspace_dir: ./workspace
  servers_dir: ./servers
  skills_dir: ./skills
  sandbox_type: microsandbox
  sandbox_image: python
  allow_network_access: false
  state:
    enabled: true
    workspace_dir: ./workspace
    state_file: state.json
    auto_save: true
    state_format: json

llm:
  enabled: true
  provider: azure_openai  # or "openai"
  model: gpt-4o-mini
  azure_endpoint: https://your-resource.openai.azure.com
  azure_deployment_name: gpt-4o-mini
  azure_api_version: 2024-08-01-preview
  temperature: 0.3
  max_tokens: 2000

optimizations:
  enabled: true
  sandbox_pooling: true  # Critical for performance
  sandbox_pool_size: 3
  tool_cache: true
  parallel_discovery: true

guardrails:
  enabled: true
  strict_mode: false
  security_checks: true
  max_execution_time: 300
  max_memory_mb: 512

logging:
  level: INFO
  file: logs/code-execution-mcp.log
```

### Configuration Priority

Configuration is loaded in this order (later overrides earlier):

1. **Default values** (from schema)
2. **config.yaml** (if exists)
3. **Environment variables** (from `.env` or system env)
4. **Runtime arguments** (passed to `create_agent()`)

### Programmatic Configuration

**No .env file needed!** Configure LLM and statefulness directly in code:

#### LLM Configuration

```python
from code_execution_mcp import create_agent

# Configure Azure OpenAI programmatically
agent = create_agent(
    llm_enabled=True,
    llm_provider="azure_openai",
    llm_azure_endpoint="https://your-resource.openai.azure.com",
    llm_api_key="your_api_key",
    llm_azure_deployment="gpt-4o-mini",
    llm_temperature=0.3,
    llm_max_tokens=2000
)

# Or configure OpenAI
agent = create_agent(
    llm_enabled=True,
    llm_provider="openai",
    llm_model="gpt-4o-mini",
    llm_api_key="your_openai_key"  # Or use OPENAI_API_KEY env var
)
```

#### State Configuration

```python
from code_execution_mcp import create_agent

# Enable statefulness with custom settings
agent = create_agent(
    state_enabled=True,
    state_file="my_state.json",
    state_auto_save=True
)

# Disable statefulness
agent = create_agent(
    state_enabled=False
)
```

#### Combined Configuration

```python
from code_execution_mcp import create_agent, execute_task

# Configure everything programmatically
agent = create_agent(
    workspace_dir="./my_workspace",
    llm_enabled=True,
    llm_provider="azure_openai",
    llm_azure_endpoint="https://your-resource.openai.azure.com",
    llm_api_key="your_key",
    state_enabled=True,
    state_file="workflow_state.json",
    state_auto_save=True
)

# Or use execute_task with configuration
result, output, error = execute_task(
    "Your task",
    llm_enabled=True,
    llm_provider="openai",
    state_enabled=True,
    state_file="task_state.json"
)
```

### Verify Configuration

Run the setup verification script:

```bash
python check_setup.py
```

This checks:
- ✅ Required packages installed
- ✅ Project modules importable
- ✅ Directory structure exists
- ✅ Configuration loads correctly

## Usage

### Using as a Framework (Client Mode)

The framework can be used directly in Python code to execute tasks:

### Simple API (Recommended)

The framework provides a simple, high-level API that handles all the setup automatically:

```python
from code_execution_mcp import create_agent, execute_task

# Option 1: Use the convenience function (simplest)
result, output, error = execute_task("Calculate 5 + 3 and get weather for San Francisco")
if error:
    print(f"Error: {error}")
else:
    print(f"Result: {result}")

# Option 2: Create an agent and reuse it (more efficient for multiple tasks)
agent = create_agent()
result, output, error = agent.execute_task("Your task here", verbose=True)

# Option 3: Configure LLM programmatically (no .env needed)
agent = create_agent(
    llm_enabled=True,
    llm_provider="azure_openai",
    llm_azure_endpoint="https://your-resource.openai.azure.com",
    llm_api_key="your_key",
    llm_azure_deployment="gpt-4o-mini"
)

# Option 4: Configure statefulness programmatically
agent = create_agent(
    state_enabled=True,
    state_file="my_state.json",
    state_auto_save=True
)

# Option 5: Combined configuration
agent = create_agent(
    workspace_dir="./my_workspace",
    llm_enabled=True,
    llm_provider="openai",
    llm_model="gpt-4o-mini",
    state_enabled=True,
    state_file="workflow_state.json"
)
```

### Advanced API

For more control, you can use the lower-level components:

```python
from code_execution_mcp import AgentHelper, FilesystemHelper, SandboxExecutor
from code_execution_mcp import load_config

# Load configuration
config = load_config()

# Initialize components manually
fs_helper = FilesystemHelper(
    workspace_dir=config.execution.workspace_dir,
    servers_dir=config.execution.servers_dir,
    skills_dir=config.execution.skills_dir,
)

executor = SandboxExecutor(
    execution_config=config.execution,
    guardrail_config=config.guardrails,
    optimization_config=config.optimizations,
)

agent = AgentHelper(
    fs_helper, 
    executor, 
    optimization_config=config.optimizations,
    llm_config=config.llm
)

# Execute a task
result, output, error = agent.execute_task(
    task_description="Your task here",
    verbose=True
)
```

### Running as an MCP Server

The framework can run as an MCP (Model Context Protocol) server, exposing its capabilities to other MCP clients.

#### How It Works

The framework uses **FastMCP** to create an MCP server that exposes framework functionality as MCP tools.

**Architecture:**
```
┌─────────────────────────────────────────┐
│         MCP Client                      │
│  (e.g., Claude Desktop, custom client) │
└─────────────────────────────────────────┘
                    ↓
            MCP Protocol
        (stdio/sse/http transport)
                    ↓
┌─────────────────────────────────────────┐
│      MCPServer (FastMCP)               │
│  - Exposes 7 tools                     │
│  - Handles MCP protocol                │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│      AgentHelper                        │
│  - Task execution                       │
│  - Tool discovery                       │
│  - State management                     │
└─────────────────────────────────────────┘
```

**Implementation:**
- Server is implemented in `server/mcp_server.py`
- Creates FastMCP instance: `FastMCP("Code Execution MCP")`
- Registers tools using `@mcp.tool()` decorator
- Each tool calls the underlying `AgentHelper` methods
- Runs server using `mcp.run(transport=...)`

#### Quick Start

**1. Start the MCP server:**

```bash
# Using the command-line entry point (after installation)
code-execution-mcp-server

# Or using Python module
python -m code_execution_mcp.server

# Or with a specific transport (stdio, sse, or http)
python -m code_execution_mcp.server stdio
```

**2. Programmatic usage:**

```python
from code_execution_mcp import create_server, run_server

# Create and run server with default config
run_server(transport="stdio")

# Or create server with custom configuration
from code_execution_mcp import AppConfig, ExecutionConfig, LLMConfig, create_server

config = AppConfig(
    execution=ExecutionConfig(workspace_dir="./workspace"),
    llm=LLMConfig(enabled=True, provider="openai"),
)

server = create_server(config=config)
# Then run: asyncio.run(server.run(transport="stdio"))
```

#### Available MCP Tools

The server exposes 7 MCP tools:

**1. `execute_task`**
Execute a task using the framework.

**Parameters:**
- `task_description` (str): Description of the task to execute
- `verbose` (bool, optional): Whether to print progress information

**Returns:**
```json
{
  "success": true,
  "result": <task result>,
  "output": "<execution output>",
  "error": null
}
```

**2. `list_available_tools`**
List all available tools from the servers directory.

**Parameters:** None

**Returns:**
```json
{
  "calculator": ["add", "multiply", "calculate"],
  "weather": ["get_weather", "get_forecast"],
  "filesystem": ["read_file", "write_file", "list_directory"]
}
```

**3. `get_state`**
Get the current state from the workspace. Enables statefulness by retrieving persisted data.

**Parameters:**
- `state_file` (str, optional): Name of the state file (default: "state.json")

**Returns:**
```json
{
  "exists": true,
  "data": {
    "key1": "value1",
    "key2": "value2"
  }
}
```

**State Access:**
- Reads from `workspace_dir/{state_file}`
- Returns `{"exists": false, "data": {}}` if file doesn't exist
- State persists across server restarts and client sessions

**4. `save_state`**
Save state to the workspace. Enables statefulness by persisting data across tool calls and sessions.

**Parameters:**
- `state_data` (dict): State data to save
- `state_file` (str, optional): Name of the state file (default: "state.json")

**Returns:**
```json
{
  "success": true,
  "file": "/path/to/workspace/state.json"
}
```

**State Persistence:**
- State is stored in `workspace_dir` (default: `./workspace`)
- Persists across server restarts
- Shared across all clients
- Can be accessed by code execution via `/workspace/state.json`

**5. `list_servers`**
List all available server directories.

**Parameters:** None

**Returns:**
```json
["calculator", "weather", "filesystem", "database"]
```

**6. `get_server_tools`**
List tools available in a specific server.

**Parameters:**
- `server_name` (str): Name of the server

**Returns:**
```json
["add", "multiply", "calculate"]
```

**7. `search_tools`**
Search for relevant tools using semantic search. Enables progressive disclosure by allowing agents to find relevant tool definitions without loading all tool descriptions upfront.

**Parameters:**
- `query` (str): Search query describing what tools are needed
- `detail_level` (str, optional): Level of detail to return
  - `"name"`: Tool names only (most efficient)
  - `"description"`: Tool names and descriptions
  - `"full"`: Full tool definitions with code
- `max_results` (int, optional): Maximum number of results (default: 10)

**Returns:**
Based on `detail_level`:
- `"name"`: `{"calculator": ["add", "multiply"]}`
- `"description"`: `{"calculator": {"add": {"description": "..."}}}`
- `"full"`: `{"calculator": {"add": {"code": "...", "description": "..."}}}`

This tool implements the **progressive disclosure** pattern, allowing agents to load only the tool definitions they need.

#### Transport Types

The server supports three transport types:

- **`stdio`** (default): Standard input/output
  - Best for: Local development, CLI tools
  - Connection: Process-to-process communication

- **`sse`**: Server-Sent Events
  - Best for: Web-based clients
  - Connection: HTTP with SSE protocol

- **`http`**: HTTP REST API
  - Best for: REST API clients
  - Connection: Standard HTTP requests

#### Client Usage Examples

**Using FastMCP Client:**
```python
from fastmcp import FastMCP

# Create client
client = FastMCP("my-client")

# Connect to server (stdio transport)
client.connect("stdio://code-execution-mcp-server")

# Execute a task
result = client.call_tool("execute_task", {
    "task_description": "Calculate 2 + 2",
    "verbose": False
})
print(result)  # {"success": True, "result": 4, ...}

# List available tools
tools = client.call_tool("list_available_tools", {})
print(tools)  # {"calculator": ["add", ...], ...}
```

**Using Claude Desktop:**
Add to your MCP configuration:
```json
{
  "mcpServers": {
    "code-execution-mcp": {
      "command": "python",
      "args": ["-m", "code_execution_mcp.server", "stdio"]
    }
  }
}
```

#### MCP Server Configuration

**Configuration Flow:**
When the MCP server starts, configuration flows through these layers:

1. **Default values** (from schema)
2. **config.yaml** (if exists)
3. **Environment variables** (from `.env` or system env)
4. **Programmatic config** (passed to `create_server()`)
5. **Pre-configured agent** (if provided, overrides everything)

**Tool Discovery Configuration:**
- Tools are discovered from `execution.servers_dir` (default: `./servers`)
- Each subdirectory = one MCP server
- Each `.py` file = one tool
- Discovered dynamically at runtime

**Agent Configuration:**
The agent (`AgentHelper`) is configured with:
- `FilesystemHelper`: Manages directories (workspace, servers, skills)
- `SandboxExecutor`: Manages code execution and guardrails
- `ToolSelector`: Semantic search for tool selection
- `CodeGenerator`: LLM-based code generation

**Example Configuration:**
```python
from code_execution_mcp import create_server, AppConfig, ExecutionConfig, LLMConfig

config = AppConfig(
    execution=ExecutionConfig(
        workspace_dir="./workspace",
        servers_dir="./servers",      # Tool discovery directory
        skills_dir="./skills",
    ),
    llm=LLMConfig(
        enabled=True,
        provider="openai",
        model="gpt-4o-mini",
    ),
)

server = create_server(config=config)
```

**See [MCP Server Configuration Details](#mcp-server-configuration-details) below for complete configuration guide.**

#### Adding Custom Tools Programmatically

You can add custom tools to the MCP server programmatically:

**Register single tool:**
```python
from code_execution_mcp import create_server

def my_custom_tool(param: str) -> str:
    """My custom tool."""
    return f"Result: {param}"

server = create_server()
server.register_tool(my_custom_tool)
```

**Register multiple tools:**
```python
def tool1(x: int) -> int:
    return x * 2

def tool2(text: str) -> str:
    return text.upper()

server.register_tools([tool1, tool2])

# Or register at creation
server = create_server(custom_tools=[tool1, tool2])
```

**Tool with server access:**
```python
def get_server_info() -> dict:
    """Get server information."""
    # Access server internals
    tools = server.agent.discover_tools()
    return {
        "tools": tools,
        "workspace": str(server.config.execution.workspace_dir),
    }

server.register_tool(get_server_info)
```

**See `examples/13_programmatic_tools.py` for complete examples.**

#### MCP Server Statefulness

The MCP server fully supports statefulness, enabling agents to maintain state across multiple tool calls and sessions.

**State Management:**
- **State Tools**: `get_state` and `save_state` MCP tools
- **Persistent Storage**: Filesystem-based state storage in `workspace_dir`
- **Cross-Session**: State persists across server restarts and client connections
- **Configurable**: State settings via `StateConfig`
- **Multiple Formats**: JSON, YAML, or Pickle
- **Code Access**: Agents can read/write state files directly in code
- **Tool Access**: Clients can manage state via MCP tools

**State Storage:**
- Default location: `{workspace_dir}/state.json`
- Custom location: `{workspace_dir}/{state_file}`
- The `workspace_dir` is mounted in the sandbox at `/workspace`
- Persisted on the host filesystem
- Shared across all executions

**State Access Patterns:**

**Pattern 1: Explicit State Management**
```python
# Save state explicitly
client.call_tool("save_state", {"state_data": {...}})

# Read state explicitly
state = client.call_tool("get_state", {})
```

**Pattern 2: Code-Based State Management**
```python
# Agent writes code that manages state
client.call_tool("execute_task", {
    "task_description": "Save current progress to state.json and continue"
})
```

**Pattern 3: Hybrid Approach**
```python
# Read state via tool
state = client.call_tool("get_state", {})

# Use state in task execution
client.call_tool("execute_task", {
    "task_description": f"Continue from step {state['data']['step']}"
})
```

**See `examples/14_mcp_statefulness.py` for complete statefulness examples.**

#### MCP Server Configuration Details

**Tool Discovery:**
Tools are discovered from the `servers_dir` directory:

1. **Server Discovery**: Scans `servers_dir/` for subdirectories
   - Each subdirectory = one MCP server
   - Example: `servers/calculator/` = "calculator" server

2. **Tool Discovery**: For each server, scans for `.py` files
   - Each `.py` file = one tool
   - Example: `servers/calculator/add.py` = "add" tool

**Example tool file structure:**
```
servers/
├── calculator/
│   ├── __init__.py          # Exports all tools
│   ├── add.py               # Tool: add(a, b)
│   ├── multiply.py          # Tool: multiply(a, b)
│   └── calculate.py         # Tool: calculate(expression)
├── weather/
│   ├── __init__.py
│   ├── get_weather.py       # Tool: get_weather(location)
│   └── get_forecast.py      # Tool: get_forecast(location, days)
└── filesystem/
    ├── __init__.py
    ├── read_file.py         # Tool: read_file(path)
    └── write_file.py        # Tool: write_file(path, content)
```

**Configuring Tool Directories:**

**Via config.yaml:**
```yaml
execution:
  servers_dir: "./servers"      # Change tool discovery directory
  skills_dir: "./skills"        # Reusable code functions
  workspace_dir: "./workspace"  # Execution workspace
```

**Via programmatic config:**
```python
config = AppConfig(
    execution=ExecutionConfig(
        servers_dir="/custom/path/to/tools",  # Custom tool directory
        skills_dir="/custom/path/to/skills",
        workspace_dir="/custom/path/to/workspace",
    )
)
```

**Via environment variables:**
```bash
EXECUTION_SERVERS_DIR=/custom/path/to/tools
EXECUTION_SKILLS_DIR=/custom/path/to/skills
EXECUTION_WORKSPACE_DIR=/custom/path/to/workspace
```

**Complete Configuration Example:**
```python
from code_execution_mcp import (
    create_server,
    AppConfig,
    ExecutionConfig,
    LLMConfig,
    GuardrailConfig,
    OptimizationConfig,
)

# Full configuration
config = AppConfig(
    execution=ExecutionConfig(
        workspace_dir="./workspace",
        servers_dir="./servers",           # Tool discovery directory
        skills_dir="./skills",
        sandbox_type="microsandbox",
        allow_network_access=False,
        mount_directories=["./data"],       # Mount data directory
    ),
    llm=LLMConfig(
        enabled=True,
        provider="azure_openai",
        azure_endpoint="https://your-resource.openai.azure.com",
        api_key="your_key",
        azure_deployment="gpt-4o-mini",
        temperature=0.3,
        max_tokens=2000,
    ),
    guardrails=GuardrailConfig(
        enabled=True,
        strict_mode=False,
        security_checks=True,
        max_execution_time=300,
        max_memory_mb=512,
    ),
    optimizations=OptimizationConfig(
        enabled=True,
        parallel_discovery=True,           # Faster tool discovery
        tool_cache=True,                   # Cache tool descriptions
        sandbox_pooling=False,             # Disable pooling (experimental)
    ),
)

# Create server with configuration
server = create_server(config=config)
```

**Adding New Tools:**

**Method 1: Filesystem-Based (Framework Tools)**
Add tools by creating files in the `servers/` directory:
1. Create tool file in `servers/{server_name}/{tool_name}.py`
2. Create/update `__init__.py` in server directory
3. Restart server (or tools will be discovered on next call)

**Method 2: Programmatic Registration (Custom Tools)**
Add tools programmatically without creating files:
```python
server = create_server()
server.register_tool(my_function)
server.register_tools([tool1, tool2])
# Or at creation
server = create_server(custom_tools=[tool1, tool2])
```

#### MCP Server Troubleshooting

**Server won't start:**
- Ensure `fastmcp` is installed: `pip install fastmcp`
- Check that required directories exist: `servers/`, `workspace/`, `skills/`
- Verify microsandbox server is running (if using code execution)

**Client can't connect:**
- Verify server is running
- Check transport type matches between server and client
- For stdio: ensure proper process communication setup
- For sse/http: check network connectivity and ports

**Tools not working:**
- Verify `servers/` directory contains tool files
- Check workspace directory is writable
- Review server logs for errors
- Check `servers_dir` configuration: `print(server.agent.fs_helper.servers_dir)`

## Compliance with Anthropic's Code Execution with MCP

This framework implements the concepts described in [Anthropic's blog post on code execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp).

### ✅ Fully Implemented Concepts

**1. Code Execution with MCP**
- Tools are presented as Python modules in `servers/` directory
- Agents write Python code to call tools instead of direct MCP tool calls
- Code execution via microsandbox for secure execution

**2. File Tree Structure**
- Generating a file tree of all available tools from connected MCP servers
- Each server = subdirectory, each tool = `.py` file

**3. Progressive Disclosure**
- Filesystem-based tool discovery via `FilesystemHelper`
- Agents explore `servers/` directory to find available tools
- Semantic search via `ToolSelector` to find relevant tools
- Only loads tool definitions when needed (not all upfront)
- `search_tools` MCP tool with detail level parameter (`name`, `description`, `full`)

**4. Context Efficient Tool Results**
- Code execution allows filtering, aggregation, transformation
- Results processed in sandbox before returning to model
- Example: Filter 10,000 rows to show only 5

**5. More Powerful Control Flow**
- Full Python control flow support (loops, conditionals, try/except)
- Code execution environment handles control flow
- Reduces latency vs. model evaluating conditionals

**6. Privacy-Preserving Operations**
- PII detection and tokenization via `PIIDetector`
- Tokenization of emails, phones, SSNs, credit cards
- Untokenization when data flows to MCP tools
- Intermediate results stay in sandbox by default

**7. State Persistence**
- `workspace/` directory for state persistence
- Save/load state via `get_state()` and `save_state()` tools
- Cross-session persistence
- File-based state storage

**8. Search Tools**
- Semantic search via `ToolSelector` class
- Tool description extraction and embedding-based search
- `search_tools` MCP tool exposed in server
- Detail level parameter with three options: `name`, `description`, `full`

### ⚠️ Partially Implemented Concepts

**Skills System**
- ✅ `skills/` directory for reusable code functions
- ✅ Save skills via `fs_helper.save_skill()` (creates `.py` and `.md` files)
- ⚠️ Uses `.md` files but not specifically `SKILL.md` format
- ✅ Skills can be imported and reused in code

**Gap**: Could add explicit `SKILL.md` format support for structured skill definitions.

### Summary

| Concept | Status | Notes |
|---------|--------|-------|
| Code execution with MCP | ✅ | Fully implemented |
| File tree structure | ✅ | Fully implemented |
| Progressive disclosure | ✅ | Fully implemented |
| Context efficient results | ✅ | Fully implemented |
| Control flow in code | ✅ | Fully implemented |
| Privacy-preserving (tokenization) | ✅ | Fully implemented |
| State persistence | ✅ | Fully implemented |
| Skills system | ⚠️ | Implemented but could add SKILL.md format |
| Search tools | ✅ | Fully implemented as MCP tool |
| Detail level parameter | ✅ | Implemented (name/description/full) |

**References:**
- [Anthropic Blog Post: Code execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp)
- Our implementation follows the core patterns described in the post

## Examples

**📚 Comprehensive examples are available in the `examples/` directory.**

### Quick Start Example

Try the simplest example first:

```bash
python examples/00_simple_api.py
```

This demonstrates the easiest way to use the framework:

```python
from code_execution_mcp import create_agent, execute_task

# One-line execution
result, output, error = execute_task("Calculate 5 + 3")

# Or create a reusable agent
agent = create_agent()
result, output, error = agent.execute_task("Your task here")
```

### All Available Examples

| Example | Description | Use Case |
|---------|-------------|----------|
| **00_simple_api.py** ⭐ | Simple API usage | **Start here!** Learn the basics |
| 01_basic_tool_call.py | Basic tool execution | Single tool calls |
| 02_multi_tool_chain.py | Multi-tool chaining | Complex workflows |
| 03_data_filtering.py | Data filtering | Processing large datasets |
| 04_control_flow.py | Control flow | Conditional logic & loops |
| 05_state_persistence.py | State persistence | Cross-session state |
| 06_skills.py | Reusable skills | Building code libraries |
| 07_filesystem_operations.py | File operations | Reading/writing files |
| 08_cross_session_persistence.py | Multi-session workflows | Long-running tasks |
| 09_configuration.py | Programmatic configuration | Configuring LLM & state |
| 10_mcp_server.py | Running as MCP server | Exposing framework as MCP server |
| 11_mcp_server_client.py | MCP server client usage | Using the server from clients |
| 12_mcp_client_example.py | Running examples in MCP mode | Examples via MCP server |
| 00_simple_api_mcp.py | Simple API via MCP | MCP client version of example 0 |
| 13_programmatic_tools.py | Programmatic tool registration | Adding custom tools to MCP server |
| 14_mcp_statefulness.py | Statefulness with MCP server | State management via MCP tools |

**📖 See [examples/README.md](examples/README.md) for detailed documentation.**

**Run any example:**
```bash
# Direct mode (default)
python examples/00_simple_api.py

# With sandbox pooling (recommended for performance)
OPTIMIZATION_SANDBOX_POOLING=true python examples/00_simple_api.py

# MCP client mode (connect to framework as MCP server)
# Terminal 1: Start server
python -m code_execution_mcp.server

# Terminal 2: Run example
export MCP_MODE=true
python examples/00_simple_api.py
```

**Running Examples in MCP Mode:**

Examples can run in two modes:

1. **Direct Mode** (default): Use framework directly
   ```python
   from code_execution_mcp import execute_task
   result, output, error = execute_task("task")
   ```

2. **MCP Client Mode**: Connect to framework as MCP server
   ```bash
   # Start server
   python -m code_execution_mcp.server
   
   # Run example with MCP mode
   export MCP_MODE=true
   python examples/00_simple_api.py
   ```

See `examples/12_mcp_client_example.py` and `examples/mcp_client_helper.py` for details.

## Architecture

The framework follows a **layered architecture** with clear separation of concerns:

```
┌─────────────────────────────────────────┐
│     Public API Layer                    │
│  (code_execution_mcp/__init__.py)      │
│  - create_agent()                       │
│  - execute_task()                       │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│     Orchestration Layer                 │
│  (client/agent_helper.py)              │
│  - Coordinates discovery, selection,  │
│    generation, execution               │
└─────────────────────────────────────────┘
    ↓         ↓         ↓         ↓
┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
│Discovery│ │Selection│ │Generation│ │Execution│
│ Layer   │ │ Layer   │ │ Layer    │ │ Layer   │
└────────┘ └────────┘ └────────┘ └────────┘
```

### Architecture Layers

#### 1. Public API Layer (`code_execution_mcp/`)
- **Purpose**: Provides a simple, high-level API for users
- **Components**:
  - `create_agent()`: Factory function for creating agents
  - `execute_task()`: Convenience function for one-shot execution
  - Re-exports of core components for advanced usage

#### 2. Orchestration Layer (`client/agent_helper.py`)
- **Purpose**: Coordinates tool discovery, selection, generation, and execution
- **Responsibilities**:
  - Tool discovery and caching
  - Tool selection (semantic/keyword matching)
  - Code generation coordination
  - Execution coordination

#### 3. Execution Layer
- **Purpose**: Manages code execution in sandboxed environments
- **Components**:
  - `SandboxExecutor`: Executes code in microsandbox
  - `SandboxPool`: Manages sandbox pooling for performance
  - `CodeExecutor`: Base interface for executors

#### 4. Discovery Layer
- **Purpose**: Discovers and selects tools from filesystem
- **Components**:
  - `FilesystemHelper`: Filesystem operations and tool discovery
  - `ToolSelector`: Semantic/keyword-based tool selection
  - `ToolCache`: Caches tool descriptions for performance

#### 5. Generation Layer
- **Purpose**: Generates Python code from task descriptions
- **Components**:
  - `CodeGenerator`: LLM-based and rule-based code generation

#### 6. Validation Layer
- **Purpose**: Validates code and execution safety
- **Components**:
  - `GuardrailValidator`: Security and safety checks
  - `Validators`: Input validation utilities

#### 7. MCP Integration Layer
- **Purpose**: Integrates with MCP servers
- **Components**:
  - `MCPClient`: MCP protocol client
  - `MockMCPClient`: Mock client for testing

#### 8. Configuration Layer (`config/`)
- **Purpose**: Manages framework configuration
- **Components**:
  - `schema.py`: Pydantic configuration schemas
  - `loader.py`: Configuration loading from YAML/env

### Data Flow

```
User Request
    ↓
create_agent() / execute_task()
    ↓
AgentHelper
    ↓
┌─────────────────────────────────────┐
│ 1. Discovery                        │
│    FilesystemHelper → ToolSelector  │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ 2. Selection                        │
│    ToolSelector (semantic/keyword)  │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ 3. Generation                       │
│    CodeGenerator (LLM/rule-based)   │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ 4. Validation                       │
│    GuardrailValidator               │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ 5. Execution                        │
│    SandboxExecutor → SandboxPool    │
└─────────────────────────────────────┘
    ↓
Result
```

### Design Principles

1. **Separation of Concerns**: Each layer has a single, well-defined responsibility
2. **Dependency Inversion**: High-level modules depend on abstractions (interfaces)
3. **Single Responsibility**: Each class/module has one reason to change
4. **Open/Closed Principle**: Open for extension, closed for modification
5. **Configuration Over Code**: Behavior configurable through config files/env vars

### Project Structure

```
code-execution-mcp/
├── code_execution_mcp/   # Main package (public API)
│   └── __init__.py       # High-level API exports
├── client/               # Core framework components
│   ├── __init__.py       # Client module exports
│   ├── agent_helper.py   # Orchestration layer
│   ├── base.py           # Base interfaces
│   ├── errors.py         # Error classes
│   │
│   ├── Execution Layer:
│   ├── sandbox_executor.py  # Sandbox execution
│   └── sandbox_pool.py      # Sandbox pooling
│   │
│   ├── Discovery Layer:
│   ├── filesystem_helpers.py # Filesystem operations
│   ├── tool_selector.py      # Tool selection
│   └── tool_cache.py         # Tool caching
│   │
│   ├── Generation Layer:
│   └── code_generator.py     # Code generation
│   │
│   ├── Validation Layer:
│   ├── guardrails.py         # Guardrail validation
│   └── validators.py         # Input validators
│   │
│   └── MCP Integration:
│       ├── mcp_client.py     # MCP client
│       └── mock_mcp_client.py # Mock client
│
├── config/               # Configuration management
│   ├── __init__.py       # Config exports
│   ├── schema.py         # Pydantic schemas
│   └── loader.py         # Config loading
│
├── servers/              # Tool files (filesystem-based discovery)
│   ├── calculator/       # Calculator tools
│   ├── weather/          # Weather tools
│   ├── filesystem/       # Filesystem tools
│   └── database/         # Database tools
│
├── workspace/            # State persistence directory
│   ├── client/          # Client code (written by executor)
│   ├── servers/         # Tool modules (written by executor)
│   ├── skills/          # Reusable skills
│   └── state.json       # State file
│
├── skills/              # Reusable code functions
├── examples/            # Comprehensive examples
└── .env                 # Environment variables (create this)
```

## Features

- **Filesystem-based Tool Discovery**: Agents discover tools by exploring the `servers/` directory
- **Progressive Disclosure**: Only load tools needed for the task (semantic/keyword selection)
- **State Persistence**: Save and resume work using the `workspace/` directory (cross-session)
- **Skills System**: Reusable code functions stored in `skills/` directory
- **LLM-based Code Generation**: Uses Azure OpenAI or OpenAI to generate Python code (with rule-based fallback)
- **Smart Sandbox Pooling**: Reuses sandboxes for 100-700x faster execution
- **Secure Execution**: microsandbox integration for hardware-isolated execution
- **Programmatic Configuration**: Configure LLM and statefulness without .env files

This implementation follows the [Anthropic article on code execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp):
- ✅ Filesystem-based tool discovery
- ✅ Progressive disclosure (discover all, load only needed)
- ✅ State persistence via volume mounts
- ✅ Tools as filesystem modules
- ✅ Code execution pattern
- ✅ Privacy-preserving operations (PII tokenization)
- ✅ Skills system for reusable code
- ✅ Search tools with detail level parameter

**📖 See [Compliance with Anthropic's Code Execution with MCP](#compliance-with-anthropics-code-execution-with-mcp) section above for detailed compliance analysis.**

## Performance

### Sandbox Pooling

**Critical for performance**: Sandbox pooling reuses pre-created sandboxes, achieving **100-700x speedup** after the first execution.

#### How It Works

The standard `PythonSandbox.create()` context manager stops sandboxes automatically, preventing reuse. Our implementation manually manages the sandbox lifecycle:

- **Pre-creates 3 sandboxes** on initialization
- **Keeps sandboxes running** between executions (not stopped)
- **Recreates HTTP sessions** when event loops are closed (handles `asyncio.run()`)
- **Health checks** verify sandboxes are still active before reuse
- **Shared pool** works across all examples

#### Performance Metrics

- **First execution**: ~100-140s (pool initialization + first run)
- **Subsequent executions**: ~0.5-1.5s (**141-700x faster**)
- **Works across different examples** (same pool shared)

#### Enable Pooling

Set environment variable:
```bash
export OPTIMIZATION_SANDBOX_POOLING=true
```

Or add to `.env`:
```bash
OPTIMIZATION_SANDBOX_POOLING=true
```

#### Benchmarking

Use `benchmark_pooling.py` to measure pooling performance:

```bash
# Run a sequence of different examples (tests pooling across examples)
OPTIMIZATION_SANDBOX_POOLING=true python3 benchmark_pooling.py --sequence 01,03,01,07,03,05,08

# Run same example multiple times (tests pooling reuse)
OPTIMIZATION_SANDBOX_POOLING=true python3 benchmark_pooling.py --example 01 -n 5

# Run all examples once
OPTIMIZATION_SANDBOX_POOLING=true python3 benchmark_pooling.py --all
```

**Expected Results**:
- First run: ~100-140s (pool initialization)
- Subsequent runs: ~0.5-1.5s (141-700x faster)

### Other Optimizations

- **File Content Caching**: Only writes changed files to workspace
- **Shared Model Cache**: Sentence-transformers model loaded once and reused
- **Parallel Tool Discovery**: Concurrent server discovery
- **Tool Caching**: Caches tool descriptions for performance

## Development

### Testing MCP Tools

The framework includes a comprehensive test script for verifying all MCP tools work correctly:

```bash
# Test all MCP tools (direct framework mode, no server needed)
python test_mcp_tools.py

# Test specific tools only
python test_mcp_tools.py --tool execute_task --tool get_state

# Test with verbose output
python test_mcp_tools.py --verbose
```

**What it tests:**
- ✅ `execute_task` - Task execution via code generation
- ✅ `list_available_tools` - Tool discovery from filesystem
- ✅ `get_state` - Reading state from workspace
- ✅ `save_state` - Writing state to workspace
- ✅ `list_servers` - Server directory listing
- ✅ `get_server_tools` - Tool listing for specific server
- ✅ `search_tools` - Semantic tool search

**Expected output:**
```
======================================================================
MCP Tool Usage Test
======================================================================

✓ Using direct framework mode

======================================================================
TEST: execute_task
======================================================================
✅ Task executed successfully
...

======================================================================
TEST SUMMARY
======================================================================

✅ PASS: execute_task
✅ PASS: list_available_tools
✅ PASS: get_state
✅ PASS: save_state
✅ PASS: list_servers
✅ PASS: get_server_tools
✅ PASS: search_tools

Total: 7/7 tests passed
✅ All tests passed!
```

**Troubleshooting:**
- If tests fail, check that `servers/` directory exists with tool files
- Ensure `workspace/` directory is writable
- For LLM-based tests, ensure LLM is configured (optional, falls back to rule-based)

### Running Examples

```bash
# Run all examples
python run_all_examples.py

# Run specific example with pooling
OPTIMIZATION_SANDBOX_POOLING=true python examples/01_basic_tool_call.py

# Run specific example without pooling (for debugging)
python examples/01_basic_tool_call.py
```

### Type Checking

```bash
mypy .
```

### Linting

```bash
ruff check .
```

### Building Distribution Packages

```bash
# Install build tools
pip install build

# Build distributions
python -m build

# This creates:
# - dist/code-execution-mcp-0.1.0.tar.gz (source distribution)
# - dist/code-execution-mcp-0.1.0-py3-none-any.whl (wheel)
```

## Troubleshooting

### Common Issues

1. **"Event loop is closed" error**
   - **Cause**: `asyncio.run()` closes event loop, making pooled sandbox sessions unusable
   - **Solution**: Already handled in `sandbox_pool.py` - sessions are recreated automatically
   - **Location**: `client/sandbox_pool.py:130-149`

2. **Sandbox pooling not working**
   - **Check**: `OPTIMIZATION_SANDBOX_POOLING=true` is set
   - **Check**: First execution should be slow (~100-140s), subsequent should be fast (~0.5-1.5s)
   - **Debug**: Check logs for "Sandbox pool ready" message

3. **LLM code generation falling back to rule-based**
   - **Check**: Azure OpenAI credentials in `.env`
   - **Check**: Model supports `max_tokens` (some require `max_completion_tokens`)
   - **Debug**: Check logs for "LLM code generation failed" messages

4. **Microsandbox server not running**
   - **Error**: "Cannot connect to microsandbox server"
   - **Solution**: Start server with `msb server start --dev`

5. **Volume mount not working**
   - **Error**: Files not visible in sandbox
   - **Solution**: Ensure workspace directory exists and is writable

6. **"Cannot connect to microsandbox server"**
   - **Solution**: Start the microsandbox server:
     ```bash
     msb server start --dev
     ```

7. **"Directory not found" errors**
   - **Solution**: Create required directories:
     ```bash
     mkdir -p servers workspace skills
     ```

8. **LLM code generation not working**
   - **Check**:
     1. LLM credentials in `.env` or environment variables
     2. `config.llm.enabled = True`
     3. API endpoint is accessible
     4. Check logs for error messages

9. **Import Errors**
   - **Solution**:
     1. Verify the package is installed: `pip show code-execution-mcp`
     2. Check Python path: `python -c "import sys; print(sys.path)"`
     3. Reinstall: `pip uninstall code-execution-mcp && pip install .`

### Known Issues & Limitations

1. **Azure OpenAI `max_tokens` parameter**: Some models (e.g., `gpt-5.1-codex-mini`) require `max_completion_tokens` instead of `max_tokens`. This causes LLM generation to fall back to rule-based. Fix pending.

2. **Sandbox pooling requires manual lifecycle management**: The standard `PythonSandbox.create()` context manager stops sandboxes automatically, so we had to implement custom pooling with manual session management.

3. **Event loop handling**: Pooled sandboxes need session recreation when event loops are closed (handled automatically but adds complexity).

## License

MIT

## References

- [Anthropic Article: Code execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp)
- [Microsandbox Documentation](https://github.com/zerocore-ai/microsandbox)
- [Model Context Protocol (MCP)](https://modelcontextprotocol.io/)
