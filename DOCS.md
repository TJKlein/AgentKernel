# AgentKernel API Documentation

Complete technical reference for AgentKernel - the high-performance local runtime for autonomous agents.

[Back to README](README.md) | [Configuration](#configuration) | [API Reference](#api-reference) | [Examples](#examples)

---

## Table of Contents

- [Installation](#installation)
- [Configuration](#configuration)
- [Core API](#core-api)
- [Async Middleware](#async-middleware)
- [MCP Tools](#mcp-tools)
- [Examples](#examples)
- [Troubleshooting](#troubleshooting)
- [Performance](#performance)

---

## Installation

### System Requirements

- **Python**: 3.10 or higher
- **Docker**: Latest stable version
- **Rust**: 1.70+ (for building Microsandbox)
- **Memory**: 4GB+ recommended
- **Disk**: 2GB+ for Docker images

### Step-by-Step Installation

#### 1. Install Rust (if not already installed)

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source $HOME/.cargo/env
```

#### 2. Clone and Build Microsandbox

```bash
git clone https://github.com/TJKlein/microsandbox.git
cd microsandbox
cargo build --release
```

**Important**: The standard `msb` installation does NOT support volume mounting. You must build from source.

#### 3. Install AgentKernel

```bash
git clone https://github.com/your-org/agentkernel.git
cd agentkernel
pip install -e .
```

#### 4. Verify Installation

```bash
# Check Microsandbox binary
ls -lh /path/to/microsandbox/target/release/msbserver

# Check AgentKernel installation
python -c "from code_execution_mcp import create_agent; print('✓ AgentKernel installed')"
```

### Why Build Microsandbox from Source?

**Critical Requirement**: AgentKernel requires microsandbox with **volume mounting support**, which is NOT included in the standard installation.

#### The Problem

The standard microsandbox installation (`curl -sSL https://get.microsandbox.dev | sh`) uses an older version that:
- Does NOT support volume mounting
- Cannot share files between host and sandbox
- Will fail with error: `"Invalid params for sandbox.start: invalid type: map, expected a string"`

#### What Volume Mounting Enables

Volume mounting allows AgentKernel to:

1. **Persistent Workspace**: Share files between your host system and the sandbox
2. **Tool Libraries**: Mount MCP tools and Python modules directly into the sandbox
3. **State Management**: Persist data across multiple executions
4. **File-based Communication**: Enable the Programmatic Tool Calling (PTC) pattern

#### The Required Patches

The microsandbox repository at `https://github.com/TJKlein/microsandbox` includes volume mounting support (commit `9170b93`), which adds:

**Python SDK Changes** (`base_sandbox.py`):
- Accept `volumes` parameter in `create()` and `start()` methods
- Format volumes as `[{"host": "/path", "mount": "/path"}]` in JSON-RPC requests

**Rust Server Changes**:
- `payload.rs`: New `VolumeMount` struct to deserialize volume configurations
- `handler.rs`: Convert volume configurations to YAML format for sandbox creation

#### Verification

After building from source, verify volume support works:

```bash
# Start server
cd /path/to/microsandbox
./target/release/msbserver --dev

# In another terminal, run test
python test_async_middleware.py

# Look for this in server logs:
# ✓ Starting sandboxes (no "Invalid params" errors)
```

If you see `"Invalid params for sandbox.start"`, you're using the wrong binary. Make sure to use the rebuilt `./target/release/msbserver` and NOT the global `msb` command.

### Automatic Setup Verification

To prevent setup mistakes, AgentKernel includes an automatic verification script:

```bash
python verify_setup.py
```

This script will:

1. **Check Docker** - Verify Docker is installed and running
2. **Detect Wrong Binary** - Warn if global `msb` is installed
3. **Verify Server** - Check if correct msbserver is running
4. **Validate Sandboxfile** - Ensure code-execution sandbox is configured
5. **Test Volume Mounting** - Actually test that volumes work!

**Sample Output:**

```
============================================================
AgentKernel Setup Verification
============================================================

[1/5] Checking Docker...
✓ Docker is running

[2/5] Checking for global msb installation...

[3/5] Checking Microsandbox server...
✓ Microsandbox server is running (from source build)

[4/5] Checking Sandboxfile configuration...
✓ Sandboxfile configured

[5/5] Testing volume mounting support...
✓ Volume mounting works!

============================================================
✅ ALL CHECKS PASSED!
AgentKernel is ready to use.
============================================================
```

**If volume mounting fails**, you'll see:

```
[5/5] Testing volume mounting support...
✗ Volume mounting NOT supported
  ERROR: Your microsandbox doesn't support volume mounting!
  You MUST rebuild microsandbox from source:
    cd /path/to/microsandbox
    cargo build --release
    ./target/release/msbserver --dev
```

**Run this script before first use** to catch setup issues early!

---

## Configuration

### Sandboxfile Configuration

Location: `~/.microsandbox/namespaces/default/Sandboxfile`

#### Basic Configuration

```yaml
sandboxes:
  code-execution:
    image: microsandbox/python
    memory: 512
    cpus: 1
    volumes:
    - /absolute/path/to/workspace:/workspace
    ports:
    - 64943:4444
```

#### Production Configuration

```yaml
sandboxes:
  code-execution:
    image: microsandbox/python
    memory: 2048      # Increased memory
    cpus: 4.0         # More CPU cores
    volumes:
    - /data/workspace:/workspace
    - /data/tools:/tools:ro  # Read-only tool libraries
    env:
      PYTHONUNBUFFERED: "1"
      TZ: "UTC"
    ports:
    - 64943:4444
```

### Environment Variables

```bash
# Workspace directory (optional)
export AGENTKERNEL_WORKSPACE=/path/to/workspace

# Log level (optional)
export AGENTKERNEL_LOG_LEVEL=DEBUG  # DEBUG, INFO, WARNING, ERROR

# Microsandbox server URL (optional, defaults to localhost:5555)
export MICROSANDBOX_URL=http://localhost:5555

# Disable sandbox pooling (optional, for debugging)
export AGENTKERNEL_DISABLE_POOLING=true
```

### Starting the Server

#### Development Mode

```bash
cd /path/to/microsandbox
./target/release/msbserver --dev
```

The `--dev` flag:
- Disables authentication
- Allows local connections
- Enables verbose logging
- **Use only for development**

#### Production Mode

```bash
# Set API key
export MSB_API_KEY="your-secret-key"

# Start server
./target/release/msbserver --key $MSB_API_KEY --host 0.0.0.0 --port 5555
```

---

## Core API

### Creating an Agent

```python
from code_execution_mcp import create_agent

# Basic usage
agent = create_agent()

# With custom configuration
from config.schema import ExecutionConfig

config = ExecutionConfig(
    workspace_dir="./custom_workspace",
    timeout=120.0,
    max_retries=3
)
agent = create_agent(config=config)
```

### Executing Tasks

```python
# Simple execution
result, output, error = agent.execute_task("print('Hello, World!')")

if error:
    print(f"Error: {error}")
else:
    print(f"Output: {output}")

# With tool discovery
result, output, error = agent.execute_task(
    "Analyze stock data for NVDA",
    required_tools={"finance": ["get_stock_data", "calculate_metrics"]}
)
```

### Convenience Function

```python
from code_execution_mcp import execute_task

# One-liner for simple tasks
result, output, error = execute_task("Calculate fibonacci(30)")
```

---

## Async Middleware

### TaskManager

The `TaskManager` enables background task execution with a "fire and collect" pattern.

#### Basic Usage

```python
from code_execution_mcp import create_agent, TaskManager

agent = create_agent()
manager = TaskManager(agent, max_workers=5)

# Dispatch tasks
task1 = manager.dispatch_task("Process dataset A")
task2 = manager.dispatch_task("Process dataset B")
task3 = manager.dispatch_task("Process dataset C")

# Do other work...

# Collect results
result1 = manager.wait_for_task(task1, timeout=60)
result2 = manager.wait_for_task(task2, timeout=60)
result3 = manager.wait_for_task(task3, timeout=60)
```

#### Advanced Features

```python
# Check status without blocking
status = manager.get_task_status(task1)
print(f"Status: {status['status']}")  # running, completed, failed, timeout

# List all tasks
all_tasks = manager.list_tasks()
for task_id, info in all_tasks.items():
    print(f"{task_id}: {info['status']}")

# Cancel a running task
success = manager.cancel_task(task1)

# Shutdown (cleanup)
manager.shutdown(wait=True)
```

#### Configuration

```python
manager = TaskManager(
    agent=agent,
    max_workers=10,          # Number of worker threads
    default_timeout=300.0    # Default timeout in seconds
)
```

---

## MCP Tools

AgentKernel provides 5 MCP tools for async task management:

### 1. dispatch_background_task

Dispatch a task to run in the background.

```python
{
    "name": "dispatch_background_task",
    "description": "Dispatch a task to run asynchronously in the background",
    "parameters": {
        "task_description": "string - Task to execute",
        "verbose": "boolean - Enable verbose output (default: false)"
    },
    "returns": {
        "task_id": "string - Unique task identifier",
        "status": "string - Initial status (always 'running')"
    }
}
```

**Example:**
```json
{
    "task_description": "Analyze 1M rows of financial data",
    "verbose": true
}
```

### 2. get_background_task_status

Check the status of a background task.

```python
{
    "name": "get_background_task_status",
    "description": "Get the current status of a background task",
    "parameters": {
        "task_id": "string - Task identifier from dispatch_background_task"
    },
    "returns": {
        "task_id": "string",
        "status": "string - running, completed, failed, timeout, cancelled",
        "output": "string - Task output (if completed)",
        "error": "string - Error message (if failed)"
    }
}
```

### 3. wait_for_background_task

Block until a task completes or times out.

```python
{
    "name": "wait_for_background_task",
    "description": "Wait for a background task to complete",
    "parameters": {
        "task_id": "string - Task identifier",
        "timeout": "number - Maximum wait time in seconds (default: 60)"
    },
    "returns": {
        "task_id": "string",
        "status": "string",
        "output": "string",
        "error": "string"
    }
}
```

### 4. list_background_tasks

List all tracked tasks.

```python
{
    "name": "list_background_tasks",
    "description": "List all background tasks",
    "parameters": {},
    "returns": {
        "tasks": "object - Map of task_id to task info"
    }
}
```

### 5. cancel_background_task

Cancel a running task.

```python
{
    "name": "cancel_background_task",
    "description": "Cancel a running background task",
    "parameters": {
        "task_id": "string - Task identifier"
    },
    "returns": {
        "success": "boolean",
        "message": "string"
    }
}
```

---

## Examples

### Example 1: Data Processing Pipeline

```python
from code_execution_mcp import create_agent, TaskManager

agent = create_agent()
manager = TaskManager(agent)

# Stage 1: Data loading
task1 = manager.dispatch_task("""
import pandas as pd
df = pd.read_csv('data/large_dataset.csv')
df.to_pickle('data/loaded.pkl')
print(f'Loaded {len(df)} rows')
""")

# Wait for loading
result1 = manager.wait_for_task(task1)

# Stage 2: Parallel processing
tasks = []
for i in range(5):
    task = manager.dispatch_task(f"""
import pandas as pd
df = pd.read_pickle('data/loaded.pkl')
chunk = df[{i*200000}:{(i+1)*200000}]
result = chunk.groupby('category').sum()
result.to_pickle(f'data/chunk_{i}.pkl')
print(f'Processed chunk {i}')
""")
    tasks.append(task)

# Wait for all chunks
for task in tasks:
    manager.wait_for_task(task)

# Stage 3: Aggregation
task3 = manager.dispatch_task("""
import pandas as pd
results = []
for i in range(5):
    results.append(pd.read_pickle(f'data/chunk_{i}.pkl'))
final = pd.concat(results).groupby(level=0).sum()
print(final.head())
""")

result3 = manager.wait_for_task(task3)
print(result3['output'])
```

### Example 2: Concurrent API Calls

```python
from code_execution_mcp import create_agent, TaskManager

agent = create_agent()
manager = TaskManager(agent, max_workers=10)

# Dispatch multiple API calls
tickers = ['AAPL', 'GOOGL', 'MSFT', 'AMZN', 'TSLA']
tasks = {}

for ticker in tickers:
    task_id = manager.dispatch_task(f"""
import requests
response = requests.get(f'https://api.example.com/stock/{ticker}')
print(response.json())
""")
    tasks[ticker] = task_id

# Collect results
results = {}
for ticker, task_id in tasks.items():
    result = manager.wait_for_task(task_id, timeout=30)
    if result['status'] == 'completed':
        results[ticker] = result['output']

print(results)
```

### Example 3: Error Handling

```python
from code_execution_mcp import create_agent, TaskManager

agent = create_agent()
manager = TaskManager(agent)

task_id = manager.dispatch_task("""
# This will fail
division_by_zero = 1 / 0
""")

result = manager.wait_for_task(task_id)

if result['status'] == 'failed':
    print(f"Task failed: {result['error']}")
elif result['status'] == 'timeout':
    print("Task timed out")
    manager.cancel_task(task_id)
else:
    print(f"Task completed: {result['output']}")
```

---

## Troubleshooting

### Common Issues

#### 1. "Invalid params for sandbox.start: invalid type: map, expected a string"

**Cause**: Microsandbox server doesn't support volume mounting (old version).

**Solution**:
```bash
cd /path/to/microsandbox
cargo build --release
killall msbserver  # or: pkill -f msbserver
./target/release/msbserver --dev
```

**Verify**: Look for "✓ Starting sandboxes" in server logs without errors.

#### 2. "cannot find sandbox: 'code-execution' in Sandboxfile"

**Cause**: Sandboxfile missing or misconfigured.

**Solution**:
```bash
# Verify file exists
cat ~/.microsandbox/namespaces/default/Sandboxfile

# Should contain:
# sandboxes:
#   code-execution:
#     volumes:
#     - /path/to/workspace:/workspace

# Restart server after updating
killall msbserver
./target/release/msbserver --dev
```

#### 3. Tests timeout after 30 seconds

**Cause**: First-time Docker image pull or slow VM initialization.

**Solution**:
```bash
# Pre-pull images
docker pull microsandbox/python

# Check if images are cached
docker images | grep microsandbox
```

**Note**: First sandbox startup is always slower. Subsequent runs will be faster (< 100ms with pooling).

#### 4. "Address already in use (os error 48)"

**Cause**: Another microsandbox instance running on port 5555.

**Solution**:
```bash
# Find process
ps aux | grep msbserver

# Kill it
kill <PID>

# Or use pkill
pkill -f msbserver
```

#### 5. Import errors in sandbox (e.g., "ModuleNotFoundError")

**Cause**: Tool files not mounted correctly in workspace.

**Solution**:
```bash
# Verify workspace path is absolute
echo /absolute/path/to/workspace

# Check volume in Sandboxfile
cat ~/.microsandbox/namespaces/default/Sandboxfile

# Restart server
killall msbserver
./target/release/msbserver --dev
```

---

## Performance

### Benchmarks

| Operation | AgentKernel | Cloud API |
|-----------|-------------|-----------|
| Sandbox startup (cold) | ~3s | ~5s |
| Sandbox startup (pooled) | <100ms | 2-5s |
| Simple calculation | 200ms | 3s |
| 1M row processing | 5s | 15s |
| Token usage (typical) | 50-500 | 5,000-50,000 |

### Optimization Tips

#### 1. Enable Sandbox Pooling (Default)

```python
# Pooling is enabled by default
agent = create_agent()

# To disable (for debugging only)
import os
os.environ['AGENTKERNEL_DISABLE_POOLING'] = 'true'
agent = create_agent()
```

#### 2. Pre-pull Docker Images

```bash
# Before production deployment
docker pull microsandbox/python

# Verify
docker images | grep microsandbox
```

#### 3. Use Async Middleware for Parallel Tasks

```python
# Bad: Sequential execution
for task in tasks:
    result, output, error = agent.execute_task(task)

# Good: Parallel execution
manager = TaskManager(agent, max_workers=10)
task_ids = [manager.dispatch_task(task) for task in tasks]
results = [manager.wait_for_task(tid) for tid in task_ids]
```

#### 4. Increase Sandbox Resources

```yaml
# Sandboxfile
sandboxes:
  code-execution:
    memory: 2048  # Increase for data-intensive tasks
    cpus: 4.0     # More cores for parallel processing
```

#### 5. Cache Tool Discovery Results

Tool discovery is automatically cached. To clear cache:
```python
agent.clear_tool_cache()
```

---

## Documentation Automation

### Daily Documentation Updater

The `daily-doc-updater` workflow (`.github/workflows/daily-doc-updater.md`) runs every morning at 06:00 UTC. It scans merged pull requests and commits from the previous 24 hours, decides which parts of the code base need documentation, and uses the safe-outputs `create-pull-request` helper to publish `[docs]` updates. Before invoking the Codex engine it creates `/opt/gh-aw/safeoutputs/outputs.jsonl` (so an `agent-output` artifact exists even if the automation emits no PR) and chmods `/tmp/gh-aw` plus the host-mounted log directory so the gh-aw agent can write log files without hitting EACCES.

The workflow runs with the `codex` engine configured for `gpt-5.1-codex-mini` but proxies every request through Azure OpenAI. It writes a user-scoped `~/.codex/config.toml` that trusts the workspace, and the workflow frontmatter sets `OPENAI_BASE_URL`, `OPENAI_QUERY_PARAMS`, and `OPENAI_API_TYPE` so Codex can reach the preview endpoint. `safe-outputs.create-pull-request` keeps the branch alive for 24 hours, labels it with `documentation` and `automation`, and prefixes every title with `[docs]`.

### Developer Documentation Consolidator

The developer documentation consolidator (`.github/workflows/developer-docs-consolidator.md`) runs daily at 03:17 UTC. It reads the markdown drafts stored in `scratchpad/`, standardizes tone and formatting using the Serena MCP static-analysis tool, and merges the cleaned content into `.github/agents/developer.instructions.agent.md`. Recent updates ensure the workflow scans `scratchpad/` instead of `specs/`, which keeps it aligned with the latest drafts, and it mirrors the same Azure Codex configuration steps as the updater so both automations share provider settings.

The consolidator stores run metadata inside `/tmp/gh-aw/cache-memory/`, emits a discussion report via `safe-outputs.create-discussion`, and then opens a `[docs]` pull request that stays open for up to two days. To reach Azure OpenAI it relaxes the firewall (`strict: false`) and explicitly allows GitHub defaults plus `tk-mas28nfr-swedencentral.cognitiveservices.azure.com`.

### Azure Codex Configuration (Shared by Both Workflows)

The workflows both depend on the same Azure OpenAI settings, so the `daily-doc-updater` writes this trusted `~/.codex/config.toml` before any agent runs:

```toml
model = "gpt-5.1-codex-mini"
model_provider = "azure"

[model_providers.azure]
name = "Azure OpenAI"
base_url = "https://tk-mas28nfr-swedencentral.cognitiveservices.azure.com/openai"
env_key = "AZURE_OPENAI_API_KEY"
wire_api = "responses"
query_params = { api-version = "2025-04-01-preview" }

[projects."$GITHUB_WORKSPACE"]
trust_level = "trusted"
```

Both workflows also export `OPENAI_BASE_URL=https://tk-mas28nfr-swedencentral.cognitiveservices.azure.com/openai/v1`, `OPENAI_QUERY_PARAMS=api-version=2025-04-01-preview`, and `OPENAI_API_TYPE=responses` so calls are routed through the preview API. The repository must set `AZURE_OPENAI_API_KEY` as a secret, and the workflows depend on the safe-outputs helpers (including the `noop` requirement when there are no doc changes) to keep `/opt/gh-aw/safeoutputs/outputs.jsonl` and the `agent-output` artifact in place for auditing.

## API Reference

### `create_agent(config=None)`

Create an AgentHelper instance.

**Parameters:**
- `config` (ExecutionConfig, optional): Custom configuration

**Returns:**
- `AgentHelper`: Configured agent instance

**Example:**
```python
from code_execution_mcp import create_agent
from config.schema import ExecutionConfig

config = ExecutionConfig(timeout=120.0)
agent = create_agent(config)
```

### `execute_task(task_description, config=None)`

Convenience function for one-off task execution.

**Parameters:**
- `task_description` (str): Task to execute
- `config` (ExecutionConfig, optional): Custom configuration

**Returns:**
- `tuple`: (ExecutionResult, output: Any, error: Optional[str])

**Example:**
```python
from code_execution_mcp import execute_task

result, output, error = execute_task("print('Hello')")
```

### `class TaskManager`

Async task manager for background execution.

#### `__init__(agent, max_workers=5, default_timeout=300.0)`

Initialize task manager.

**Parameters:**
- `agent` (AgentHelper): Agent instance
- `max_workers` (int): Number of worker threads
- `default_timeout` (float): Default timeout in seconds

#### `dispatch_task(task_description, required_tools=None, verbose=False)`

Dispatch task to background worker.

**Parameters:**
- `task_description` (str): Task to execute
- `required_tools` (dict, optional): Required tools
- `verbose` (bool): Enable verbose output

**Returns:**
- `str`: Task ID

#### `get_task_status(task_id)`

Get task status.

**Parameters:**
- `task_id` (str): Task identifier

**Returns:**
- `dict`: Status information

#### `wait_for_task(task_id, timeout=None)`

Wait for task completion.

**Parameters:**
- `task_id` (str): Task identifier
- `timeout` (float, optional): Maximum wait time

**Returns:**
- `dict`: Task result

#### `list_tasks()`

List all tracked tasks.

**Returns:**
- `dict`: Map of task_id to task info

#### `cancel_task(task_id)`

Cancel running task.

**Parameters:**
- `task_id` (str): Task identifier

**Returns:**
- `bool`: Success status

#### `shutdown(wait=True)`

Shutdown task manager.

**Parameters:**
- `wait` (bool): Wait for tasks to complete

---

For more information, see the [README](README.md) or visit the [GitHub repository](https://github.com/your-org/agentkernel).
