# Code Execution MCP Examples

This directory contains examples demonstrating different use cases of the code execution MCP framework.

## Examples

### 00_simple_api.py (Start Here!)
**Simple API Usage - Recommended for New Users**
- Demonstrates the new simplified framework API
- Shows three ways to use the framework:
  1. One-shot execution with `execute_task()`
  2. Reusable agent with `create_agent()`
  3. Custom configuration
- **Best starting point** for learning the framework

**Run:**
```bash
python examples/00_simple_api.py
```

**Code:**
```python
from code_execution_mcp import create_agent, execute_task

# Simplest usage
result, output, error = execute_task("Calculate 5 + 3")

# Or create reusable agent
agent = create_agent()
result, output, error = agent.execute_task("Your task here")
```

### 01_basic_tool_call.py
**Basic Tool Call & Filesystem Discovery**
- Simple single MCP tool execution
- Filesystem-based tool discovery
- Task-driven tool selection
- Progressive disclosure (only loading needed tools)

**Run:**
```bash
python examples/01_basic_tool_call.py
```

### 02_multi_tool_chain.py
**Multi-Tool Chain & Data Flow**
- Chaining multiple MCP tools in a single code execution
- Data flow between tools without passing through LLM context
- Intermediate data processing in execution environment

**Run:**
```bash
python examples/02_multi_tool_chain.py
```

### 03_data_filtering.py
**Data Filtering & Transformation**
- Filtering large datasets in code before returning to LLM
- Aggregations and data processing
- Context-efficient data handling

**Run:**
```bash
python examples/03_data_filtering.py
```

### 04_control_flow.py
**Control Flow & Conditional Logic**
- Loops, conditionals, and error handling in code
- Complex control flow patterns
- Decision-making based on tool results

**Run:**
```bash
python examples/04_control_flow.py
```

### 05_state_persistence.py
**State Persistence (Cross-Session)**
- Saving and loading state via filesystem
- TRUE cross-session persistence across separate executions
- Resuming work from previous sessions
- Persistent data storage with volume mounts

This example demonstrates true cross-session persistence:
- Session 1: Write state to /workspace (sandbox destroyed after)
- Session 2: Read state from /workspace (new sandbox, same workspace)

**Run:**
```bash
python examples/05_state_persistence.py
```

### 06_skills.py
**Skills & Reusable Code**
- Saving reusable code functions as skills
- Importing and using saved skills
- Building a library of common operations

**Run:**
```bash
python examples/06_skills.py
```

### 07_filesystem_operations.py
**Filesystem Operations**
- Reading and writing files
- Directory operations
- File-based data processing

**Run:**
```bash
python examples/07_filesystem_operations.py
```

### 08_cross_session_persistence.py
**Cross-Session State Persistence (Comprehensive)**
- Multi-session workflow demonstration
- True cross-session state persistence across 3+ separate executions
- Resuming and building on previous session's state
- Long-running workflow resumability

This comprehensive example shows a complete multi-session workflow:
- Session 1: Initialize workflow state
- Session 2: Continue workflow (reads Session 1 state)
- Session 3: Complete workflow (reads Sessions 1 & 2 state)

Each session runs in a separate sandbox execution but shares the same workspace.

**Run:**
```bash
python examples/08_cross_session_persistence.py
```

### 09_configuration.py

**Programmatic Configuration**

Demonstrates how to configure the framework programmatically without using `.env` files.

**Key Features:**
- Configure LLM settings (provider, model, API keys)
- Configure statefulness (enabled/disabled, auto-save)
- Combine multiple configuration options

**Run:**
```bash
python examples/09_configuration.py
```

### 10_mcp_server.py

**Running as MCP Server**

Demonstrates how to run the framework as an MCP server, exposing its capabilities to other MCP clients.

**Key Features:**
- Start MCP server with default or custom configuration
- Expose framework tools as MCP tools
- Support for multiple transport types (stdio, sse, http)

**Run:**
```bash
python examples/10_mcp_server.py
```

**Note:** To actually start the server, run:
```bash
python -m code_execution_mcp.server
```

### 11_mcp_server_client.py

**MCP Server Client Usage**

Demonstrates how to use the framework as an MCP server and connect to it from clients.

**Key Features:**
- Server setup and configuration
- Exposed MCP tools documentation
- Client connection examples
- Transport types (stdio, sse, http)

**Run:**
```bash
python examples/11_mcp_server_client.py
```

**See also:** [README.md](../README.md#running-as-an-mcp-server) for detailed documentation.

### 14_mcp_statefulness.py

**Statefulness with MCP Server**

Demonstrates how to leverage statefulness when using the framework as an MCP server.

**Key Features:**
- Using `get_state` and `save_state` MCP tools
- Multi-session workflows via MCP server
- State persistence across server restarts
- Combining state tools with `execute_task`
- Cross-client state sharing
- Multiple state file management

**Run:**
```bash
# Terminal 1: Start server
python -m code_execution_mcp.server

# Terminal 2: Run example
python examples/14_mcp_statefulness.py
```

**See also:**
- `examples/05_state_persistence.py` - Direct framework state usage
- `examples/08_cross_session_persistence.py` - Multi-session workflows
- `README.md` (MCP Server Statefulness section) - Complete state management guide

### 12_mcp_client_example.py

**Running Examples in MCP Client Mode**

Demonstrates how to run framework examples by connecting to the framework as an MCP server.

**Key Features:**
- Compare direct mode vs MCP client mode
- Connect to MCP server from examples
- Environment-based mode switching
- Hybrid examples that work in both modes

**Run:**
```bash
python examples/12_mcp_client_example.py
```

**To run examples in MCP mode:**
```bash
# Terminal 1: Start server
python -m code_execution_mcp.server

# Terminal 2: Run example
export MCP_MODE=true
python examples/00_simple_api.py
```

### 00_simple_api_mcp.py

**Simple API Usage via MCP Server**

MCP client version of `00_simple_api.py`. Demonstrates the same functionality but connects to the framework as an MCP server.

**Key Features:**
- Same API as direct mode
- Connects via MCP protocol
- Shows MCP client usage pattern

**Run:**
```bash
# Terminal 1: Start server
python -m code_execution_mcp.server

# Terminal 2: Run example
python examples/00_simple_api_mcp.py
```

## Running Examples in MCP Mode

All examples can run in two modes:

### Direct Mode (Default)

Examples use the framework directly:
```python
from code_execution_mcp import execute_task
result, output, error = execute_task("task")
```

### MCP Client Mode

Examples connect to the framework as an MCP server:

**1. Start the MCP server:**
```bash
python -m code_execution_mcp.server
```

**2. Run example with MCP mode:**
```bash
export MCP_MODE=true
export MCP_SERVER_URL=stdio://code-execution-mcp-server
python examples/00_simple_api.py
```

**3. Or use the helper:**
```python
from examples.mcp_client_helper import get_helper

helper = get_helper()  # Auto-detects from MCP_MODE env var
result, output, error = helper.execute_task("task")
```

See `examples/mcp_client_helper.py` for helper utilities and `examples/12_mcp_client_example.py` for detailed examples.

## Prerequisites

**⚠️ Configuration Required:** All examples require proper setup before running.

### Required Setup

1. **Microsandbox server running**:
   ```bash
   curl -sSL https://get.microsandbox.dev | sh
   msb server start --dev  # Keep running in separate terminal
   ```

2. **Directory structure**:
   ```bash
   mkdir -p servers workspace skills
   ```

3. **Dependencies installed**:
   ```bash
   pip install -r requirements.txt
   # or
   pip install -e .
   ```

### Optional Configuration

- **LLM code generation**: Create `.env` file with Azure OpenAI or OpenAI credentials
- **Sandbox pooling**: Add `OPTIMIZATION_SANDBOX_POOLING=true` to `.env` for better performance

**📖 See the [Configuration](../README.md#configuration) section in the main README for detailed setup instructions.**

### Setup Verification

Before running examples, verify your setup:

```bash
# Activate virtual environment
source .venv/bin/activate

# Check if all packages are installed
python check_setup.py
```

If any packages are missing, install them:

```bash
pip install -r requirements.txt
```

### Common Issues

**Missing packages error:**
- Ensure virtual environment is activated: `source .venv/bin/activate`
- Verify packages are installed: `pip list | grep -E "(fastmcp|microsandbox|pydantic|sentence-transformers)"`
- Reinstall if needed: `pip install -r requirements.txt`

**Module not found errors:**
- Run examples from project root: `python examples/01_basic_tool_call.py`
- Ensure `servers/` directory exists with tool files
- Check that `workspace/` directory is writable

## Common Patterns

### Simple API (Recommended)

For most use cases, use the simplified API:

```python
from code_execution_mcp import create_agent, execute_task

# Option 1: One-shot execution
result, output, error = execute_task("Your task here")

# Option 2: Reusable agent (more efficient for multiple tasks)
agent = create_agent()
result, output, error = agent.execute_task("Your task here", verbose=True)
```

### Advanced API

For more control, use the lower-level components:

```python
from code_execution_mcp import AgentHelper, FilesystemHelper, SandboxExecutor
from code_execution_mcp import load_config

# Initialize components
config = load_config()
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
agent = AgentHelper(fs_helper, executor, ...)

# Execute task
result, output, error = agent.execute_task("Your task here", verbose=True)
```

The framework automatically:
- Discovers available tools from `servers/` directory
- Selects relevant tools for the task (semantic/keyword matching)
- Generates Python code using selected tools
- Executes code in sandboxed environment
- Returns results

