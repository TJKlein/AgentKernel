# Code Execution MCP - Complete Documentation

A comprehensive guide to the Code Execution MCP implementation, following the [Anthropic article on code execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp).

---

## Table of Contents

1. [Overview](#overview)
2. [Installation](#installation)
3. [Architecture & Compliance](#architecture--compliance)
4. [Workspace & Session Management](#workspace--session-management)
5. [Examples](#examples)
6. [Project Structure](#project-structure)
7. [Configuration](#configuration)
8. [Development](#development)

---

## Overview

A generic, extensible code execution pattern for MCP (Model Context Protocol) that allows agents to interact with MCP servers through Python code APIs instead of direct tool calls. This significantly reduces token consumption and improves efficiency by leveraging LLMs' strength at writing code.

### Features

- **Filesystem-based Tool Discovery**: Agents discover tools by exploring the `servers/` directory, loading only what they need
- **State Persistence**: Save and resume work using the `workspace/` directory
- **Skills System**: Reusable code functions stored in `skills/` directory
- **Type Safety**: Full type hints, mypy strict mode, runtime validation
- **Guardrails**: Comprehensive security, privacy, and business logic validation
- **Workflow System**: Configuration-driven workflows with YAML/JSON definitions
- **Form Filling**: Specialized support for form filling workflows
- **Extensible**: Plugin-based architecture for easy extension
- **Secure**: microsandbox integration for hardware-isolated execution

---

## Installation

### Prerequisites

1. **Python 3.10+**
2. **Virtual environment** (recommended)
3. **Microsandbox server** (for code execution)

### Setup Steps

```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install development dependencies (optional)
pip install -r requirements-dev.txt

# Set up pre-commit hooks (optional)
pre-commit install
```

### Microsandbox Server Setup

The code execution requires a Microsandbox server to be running. The `msb` CLI tool needs to be installed separately from the Python package.

**Install the Microsandbox CLI**:
```bash
curl -sSL https://get.microsandbox.dev | sh
```

After installation, verify it's working:
```bash
msb --version
```

**Start the Microsandbox Server**:
```bash
msb server start --dev
```
Keep this running in a separate terminal. The server runs on `localhost:5555` by default.

**Alternative: Configure server URL via environment variable** (if using an existing server):
```bash
export MSB_SERVER_URL=http://localhost:5555
```

**Platform Requirements**:
- **macOS**: Requires Apple Silicon (M1/M2/M3/M4). Intel Macs are not supported.
- **Linux**: Requires KVM virtualization enabled. Check with: `lsmod | grep kvm`
- **Windows**: Support coming soon

**Note**: The server must be running before executing code examples.

### Quick Start

1. **Set up virtual environment** (if not already done):
```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

2. **Install and start the Microsandbox server** (required for code execution):
```bash
# Install the CLI (one-time setup)
curl -sSL https://get.microsandbox.dev | sh

# Start the server (keep this running in a separate terminal)
msb server start --dev
```
The server runs on `localhost:5555` by default.

3. **Generate tool files from MCP servers**:
```bash
python scripts/generate_tool_files.py
```

4. **Run a simple example**:
```bash
python examples/01_basic_tool_call.py
```

---

## Architecture & Compliance

### Anthropic Article Principles

The implementation follows the [Anthropic article on code execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp) with these key principles:

1. **Filesystem-based tool discovery**: Tools are Python modules discovered by exploring filesystem
2. **Progressive disclosure**: Only load tools that are needed for the task
3. **State persistence**: Workspace persists across executions
4. **Tools as filesystem modules**: Tools can be imported directly as Python modules
5. **Code execution pattern**: Agent generates code that imports and uses tools

### Progressive Disclosure: Task-Specific Tool Discovery

The system implements **progressive disclosure** - discovering all available tools but only loading/using the ones needed for a specific task.

#### How It Works

**Step 1: Discovery Phase (Finds ALL Tools)**
- System explores `servers/` directory to find all available tools
- Reads tool files to extract descriptions (lightweight metadata extraction)
- Creates a catalog of all available tools
- **Example**: Discovers 11 tools across 4 servers

**Step 2: Selection Phase (Filters to Task-Specific)**
- Task description is analyzed
- Tool descriptions are compared to task using:
  - **Semantic search** (preferred): Uses sentence-transformers embeddings
  - **Keyword matching** (fallback): Simple keyword matching
- Only relevant tools are selected
- **Example**: Task "Calculate 5 + 3" → selects 3 calculator tools (27% efficiency)

**Step 3: Code Generation (Only Imports Selected Tools)**
- Generated code only imports selected tools
- Only selected tools are used in the execution code
- **Example**: `from servers.calculator import calculate, add, multiply`
- Does NOT import weather, filesystem, or database tools

**Step 4: Execution Phase (Only Selected Tools Loaded)**
- All tool files are written to workspace (filesystem-based requirement)
- But only selected tools are imported in generated code
- Python's import system ensures only imported tools are loaded
- **Key point**: Files being present ≠ tools being loaded

#### Efficiency Example

```
Task: "Calculate 5 + 3"

Discovery:  11 tools found (all available)
Selection:  3 tools selected (calculator tools)
Generated:  Only 3 tools imported
Efficiency: 27% of tools used (73% reduction)
```

#### Benefits

- ✅ **Efficiency**: Only load tools needed for task
- ✅ **Token Savings**: Reduced context size (~73% reduction)
- ✅ **Performance**: Faster execution with fewer imports
- ✅ **Scalability**: Works with hundreds of tools
- ✅ **Flexibility**: Can discover new tools without code changes

This is true progressive disclosure - discover everything, but only load what's needed.

### Customer-Specific Tool Selection

**Important distinction**: Tools are **universal/shared**, but **selection is task-specific** (varies per customer request).

#### How It Works Per Customer

1. **Tools are SHARED** (not customer-specific):
   - All tools come from the same `servers/` directory (shared source)
   - Same tools available to all customers
   - Tools are written to each customer's workspace, but they're identical copies

2. **Tool SELECTION is task-specific** (varies per customer request):
   - Each customer request = different task description
   - Task description determines which tools are selected via semantic/keyword matching
   - Different tasks = different tools selected
   - This is where customer-specificity comes in

#### Example: Different Customers, Different Tool Selection

```python
# Customer A: "Calculate 5 + 3"
# → Selected tools: calculator (3 tools)
# → Generated code: from servers.calculator import calculate, add, multiply

# Customer B: "Get weather for NYC"
# → Selected tools: weather (2 tools)
# → Generated code: from servers.weather import get_weather, get_forecast

# Customer C: "Read file and calculate sum"
# → Selected tools: filesystem + calculator
# → Generated code: from servers.filesystem import read_file
#                   from servers.calculator import calculate
```

#### Workspace Structure

```
workspaces/
  ├── customer_A/
  │   ├── servers/          # Same tools written here (shared source)
  │   │   ├── calculator/   # All tools available
  │   │   ├── weather/
  │   │   ├── filesystem/
  │   │   └── database/
  │   └── state/            # Customer-specific state (unique)
  │
  └── customer_B/
      ├── servers/          # Same tools written here (shared source)
      │   ├── calculator/   # All tools available
      │   ├── weather/
      │   ├── filesystem/
      │   └── database/
      └── state/            # Customer-specific state (unique)
```

#### Key Points

- ✅ **Tools are UNIVERSAL**: All customers have access to the same tools
- ✅ **Selection is TASK-SPECIFIC**: Each customer's request determines which tools are selected
- ✅ **Progressive Disclosure**: Only selected tools are imported in generated code
- ✅ **Customer Isolation**: Each customer has their own workspace and state

#### Why This Design?

1. **Efficiency**: Don't duplicate tool code per customer
2. **Flexibility**: Customers can use any tool based on their needs
3. **Maintainability**: Update tools once, all customers benefit
4. **Scalability**: Works with hundreds of tools and thousands of customers

**In summary**: Tools are shared, but each customer gets a **customized selection** of tools based on their specific use-case/request.

### Compliance Status

#### ✅ Fully Compliant

1. **Filesystem-based Tool Discovery** ✅
   - Tools discovered by exploring `servers/` directory
   - Method: `FilesystemHelper.list_servers()` and `list_tools()` explore filesystem
   - Compliance: Perfect alignment - tools are filesystem-based Python modules

2. **Progressive Disclosure** ✅
   - Tools selected based on task description using semantic/keyword search
   - Method: `ToolSelector.select_tools()` filters tools, only selected tools imported in generated code
   - Compliance: Perfect alignment - only needed tools are loaded and used

3. **State Persistence** ✅
   - Workspace mounted at `/workspace` via virtiofs volume mount
   - Method: Files written to `/workspace` persist to host filesystem
   - Compliance: Perfect alignment - state persists across executions

4. **Tools as Filesystem Modules** ✅
   - Tools written to `/workspace/servers/` as Python modules
   - Method: Can be imported: `from servers.calculator import calculate`
   - Compliance: Perfect alignment - tools are importable Python modules

5. **Code Execution Pattern** ✅
   - Agent generates Python code that imports and uses tools
   - Method: Generated code follows article pattern exactly
   - Compliance: Perfect alignment - code imports tools and executes them

### Implementation Details (Not Violations)

#### 1. Unique Sandbox Names
- **Current**: `code-execution-{uuid}` (unique per execution)
- **Article**: Doesn't specify sandbox naming
- **Impact**: None - workspace still persists (on host filesystem, not in sandbox)
- **Reason**: Technical workaround for microsandbox stale rootfs state bug
- **Verdict**: ✅ Implementation detail, not architectural violation
- **Justification**: Workspace persistence is maintained (on host), which is what matters

#### 2. Pre-writing All Tools to Workspace
- **Current**: All tool files written to workspace before execution
- **Article**: Emphasizes progressive disclosure (only load what's needed)
- **Impact**: None - tools are still filesystem-based, selection still happens
- **Reason**: Ensures tools are available when code executes (filesystem-based requirement)
- **Verdict**: ✅ Optimization, aligns with article
- **Justification**: 
  - Tools are still filesystem-based (article requirement)
  - Selection still happens (only selected tools imported in generated code)
  - Files being present ≠ tools being loaded/used
  - This is actually MORE aligned - tools are truly filesystem-based modules

#### 3. Tool Discovery Outside Sandbox
- **Current**: Discovery happens on host, then files written to workspace
- **Article**: Doesn't specify where discovery happens
- **Impact**: None - tools are still filesystem-based
- **Reason**: Efficient - discover once, write once, use many times
- **Verdict**: ✅ Design choice, doesn't violate architecture

### Summary

**No architectural violations found.** All deviations are:
- Technical optimizations (pre-writing files, unique sandbox names)
- Design choices (discovery location)
- Compatible with article principles (tools are filesystem-based, progressive disclosure maintained)

The core architecture aligns perfectly with the Anthropic article.

---

## Workspace & Session Management

### Current State Persistence Implementation

#### How It Works Now
1. **Workspace Configuration**: Set via `ExecutionConfig.workspace_dir` (default: `./workspace`)
2. **Volume Mount**: Workspace is mounted at `/workspace` in sandbox via virtiofs
3. **File Persistence**: Files written to `/workspace` in sandbox persist to host filesystem
4. **Cross-Session**: Files persist across different executions (workspace is on host)

#### Alignment with Anthropic Article ✅
- ✅ Workspace is mounted and accessible from sandbox
- ✅ Files written to workspace persist across different executions
- ✅ Agents can resume work by reading from workspace
- ✅ State persistence works as described in the article

### Per-Customer Workspace Support

#### Design Pattern

```
workspaces/
  ├── {customer_uid_1}/
  │   ├── client/              # Tools and client code (shared across sessions)
  │   ├── servers/             # Tool modules (shared across sessions)
  │   ├── skills/              # Reusable skills (shared across sessions)
  │   ├── sessions/            # Session logs and state
  │   │   ├── session_001.json
  │   │   ├── session_002.json
  │   │   └── current_session.json
  │   └── state/               # Customer-specific state (shared across sessions)
  │       ├── results.json
  │       └── context.json
  │
  ├── {customer_uid_2}/
  │   ├── client/
  │   ├── servers/
  │   ├── skills/
  │   ├── sessions/
  │   └── state/
  │
  └── ...
```

#### Key Principles

1. **Customer Isolation**: Each customer UID gets their own workspace directory
2. **Session Sharing**: Multiple sessions for the same customer share the same workspace
3. **State Persistence**: Files written by one session are visible to other sessions for the same customer
4. **Tool Sharing**: Tools (client, servers, skills) are written once per customer workspace
5. **Session Continuity**: Session logs enable resuming previous work

### Implementation

#### Creating Per-Customer Executors

```python
from pathlib import Path
from config.schema import ExecutionConfig
from client.sandbox_executor import SandboxExecutor

def create_executor_for_customer(customer_uid: str, base_config: ExecutionConfig) -> SandboxExecutor:
    """Create a SandboxExecutor with customer-specific workspace."""
    # Create customer-specific workspace path
    workspace_base = Path("./workspaces")
    customer_workspace = workspace_base / customer_uid
    
    # Create customer-specific execution config
    customer_exec_config = ExecutionConfig(
        workspace_dir=str(customer_workspace),
        servers_dir=base_config.servers_dir,  # Shared source
        skills_dir=base_config.skills_dir,    # Shared source
        sandbox_type=base_config.sandbox_type,
        sandbox_image=base_config.sandbox_image,
        allow_network_access=base_config.allow_network_access,
    )
    
    return SandboxExecutor(
        execution_config=customer_exec_config,
        guardrail_config=base_config.guardrails,
    )

# Usage:
customer_uid = "user_12345"
executor = create_executor_for_customer(customer_uid, base_config)

# Multiple sessions for same customer share workspace
session_1_executor = create_executor_for_customer(customer_uid, base_config)
session_2_executor = create_executor_for_customer(customer_uid, base_config)
# Both sessions use same workspace: ./workspaces/user_12345/
```

#### Session Logging for Continuity

Session logs enable resuming previous work. Each session writes a log file containing:
- All tasks executed
- Code that was run
- Results and outputs
- Checkpoints for resumption
- State files created

**Session Log Structure**:
```python
{
    "session_id": "session_001",
    "customer_uid": "user_12345",
    "started_at": "2025-11-16T10:00:00Z",
    "ended_at": "2025-11-16T10:30:00Z",
    "tasks": [
        {
            "task_id": "task_001",
            "description": "Calculate 5 + 3",
            "code": "...",
            "result": "8.0",
            "output": "...",
            "timestamp": "2025-11-16T10:00:15Z"
        }
    ],
    "state_files": [
        "/workspace/state/results.json",
        "/workspace/state/context.json"
    ],
    "checkpoint": {
        "step": 3,
        "last_task": "task_003",
        "context": "Working on data analysis",
        "timestamp": "2025-11-16T10:25:00Z"
    }
}
```

**Example: Multi-Session Workflow**:
```python
# Session 1: Initial work
customer_uid = "user_12345"
executor_1 = create_executor_for_customer(customer_uid, config)

# Task 1: Write state
executor_1.execute(
    code="""
import json
import os
os.makedirs('/workspace/state', exist_ok=True)
with open('/workspace/state/results.json', 'w') as f:
    json.dump({'step': 1, 'result': 8}, f)
print("State saved")
""",
    task_description="Save initial state"
)

# Session 2: Same customer reads data (different execution)
executor_2 = create_executor_for_customer(customer_uid, config)  # Same workspace!

executor_2.execute(
    code="""
import json
with open('/workspace/state/results.json', 'r') as f:
    data = json.load(f)
print(f"Resumed from step {data['step']}")
""",
    task_description="Resume from previous session"
)  # ✅ Can read data from session 1!
```

### Benefits

- ✅ **Customer Isolation**: Each customer has their own workspace directory
- ✅ **Session Sharing**: Multiple sessions for the same customer share the same workspace
- ✅ **State Persistence**: Files written by one session are visible to other sessions
- ✅ **Session Continuity**: Session logs enable resuming previous work
- ✅ **Aligns with Anthropic Article**: Workspace persistence across executions

### Security Considerations

1. **Path Validation**: Ensure customer_uid doesn't contain path traversal (`..`, `/`)
2. **Permissions**: Set appropriate filesystem permissions per workspace
3. **Quotas**: Implement disk quota limits per customer
4. **Cleanup**: Implement workspace cleanup for inactive customers

---

## Examples

The `examples/` directory contains comprehensive examples covering all concepts from the Anthropic article:

### Example 1: Basic Tool Call & Filesystem Discovery
- Simple single MCP tool execution
- Filesystem-based tool discovery
- Task-driven tool selection
- Progressive disclosure (only loading needed tools)

**Run:**
```bash
python examples/01_basic_tool_call.py
```

### Example 2: Multi-Tool Chain & Data Flow
- Chaining multiple MCP tools in a single code execution
- Data flow between tools without passing through LLM context
- Intermediate data processing in execution environment

**Run:**
```bash
python examples/02_multi_tool_chain.py
```

### Example 3: Data Filtering & Transformation
- Filtering large datasets in code before returning to LLM
- Aggregations and data processing
- Context-efficient data handling

**Run:**
```bash
python examples/03_data_filtering.py
```

### Example 4: Control Flow & Conditional Logic
- Loops, conditionals, and error handling in code
- Complex control flow patterns
- Decision-making based on tool results

**Run:**
```bash
python examples/04_control_flow.py
```

### Example 5: State Persistence
- Saving and loading state via filesystem
- Resuming work across multiple executions
- Persistent data storage

**Run:**
```bash
python examples/05_state_persistence.py
```

### Example 6: Skills & Reusable Code
- Saving reusable code functions as skills
- Importing and using saved skills
- Building a library of common operations

**Run:**
```bash
python examples/06_skills.py
```

### Example 7: Filesystem Operations
- Reading and writing files
- Directory operations
- File-based data processing

**Run:**
```bash
python examples/07_filesystem_operations.py
```

### Common Patterns

All examples follow the same pattern:

1. **Initialize components:**
   ```python
   config = load_config()
   fs_helper = FilesystemHelper(...)
   executor = SandboxExecutor(...)
   agent = AgentHelper(fs_helper, executor)
   ```

2. **Define task:**
   ```python
   task_description = "Your task description here"
   ```

3. **Execute:**
   ```python
   result, output, error = agent.execute_task(task_description, verbose=True)
   ```

The framework automatically:
- Discovers available tools from `servers/` directory
- Selects relevant tools for the task (semantic/keyword matching)
- Generates Python code using selected tools
- Executes code in sandboxed environment
- Returns results

### Examples Verification

All 7 examples have been verified to:
- ✅ Have valid Python syntax
- ✅ Follow proper structure
- ✅ Cover all key concepts from the Anthropic blog post:
  - Progressive disclosure
  - Context-efficient results
  - Control flow
  - State persistence
  - Skills
  - Filesystem operations
  - Data filtering
  - Multi-tool chaining

---

## Project Structure

```
code-execution-mcp/
├── client/           # Core MCP client and sandbox executor
│   ├── agent_helper.py      # High-level agent workflow helper
│   ├── sandbox_executor.py  # Sandbox execution with volume mounts
│   ├── filesystem_helpers.py # Filesystem operations
│   ├── tool_selector.py     # Tool selection (semantic/keyword)
│   ├── code_generator.py    # Code generation from selected tools
│   └── mcp_client.py        # MCP client implementation
├── workflows/        # Workflow execution engine
├── config/           # Configuration management
│   ├── schema.py     # Pydantic schemas
│   └── loader.py     # Config loading (YAML/env)
├── plugins/          # Plugin system and examples
├── scripts/          # Tool generation scripts
├── servers/          # Generated tool files (filesystem-based discovery)
│   ├── calculator/   # Calculator tools
│   ├── weather/      # Weather tools
│   ├── filesystem/   # Filesystem tools
│   └── database/    # Database tools
├── workspace/        # State persistence directory
│   ├── client/       # Client code (written by executor)
│   ├── servers/      # Tool modules (written by executor)
│   ├── skills/       # Reusable skills
│   └── state/        # Customer-specific state
├── skills/           # Reusable code functions
├── examples/         # Comprehensive showcase examples
├── tests/            # Test suite
└── docs/             # Additional documentation
```

---

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```bash
# Microsandbox server
MSB_SERVER_URL=http://localhost:5555
MSB_API_KEY=your_api_key_here

# Workspace configuration
WORKSPACE_DIR=./workspace
SERVERS_DIR=./servers
SKILLS_DIR=./skills

# Guardrails
GUARDRAILS_ENABLED=true
GUARDRAILS_STRICT_MODE=false

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/code-execution-mcp.log
```

### Configuration File

Alternatively, create a `config.yaml` file:

```yaml
execution:
  workspace_dir: ./workspace
  servers_dir: ./servers
  skills_dir: ./skills
  sandbox_type: microsandbox
  sandbox_image: python
  allow_network_access: false

guardrails:
  enabled: true
  strict_mode: false
  security_checks: true
  max_execution_time: 300
  max_memory_mb: 512

mcp_servers: []
```

### Azure OpenAI Integration

For Azure OpenAI integration, add to `.env`:
```bash
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
AZURE_OPENAI_API_KEY=your_api_key
AZURE_OPENAI_CHAT_DEPLOYMENT_NAME=gpt-4o-mini
AZURE_OPENAI_API_VERSION=2024-08-01-preview
AZURE_OPENAI_EMBEDDER_NAME=text-embedding-ada-002
AZURE_OPENAI_EMBEDDER_VERSION=2023-05-15
```

---

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=client --cov=config

# Run specific test file
pytest tests/test_sandbox_executor.py
```

### Type Checking

```bash
# Type check all files
mypy .

# Type check specific module
mypy client/
```

### Linting

```bash
# Check for linting issues
ruff check .

# Auto-fix linting issues
ruff check . --fix
```

### Formatting

```bash
# Format code
black .

# Check formatting
black . --check
```

### All Checks

```bash
# Run all pre-commit hooks
pre-commit run --all-files
```

---

## Key Implementation Details

### How Tools Are Discovered

1. **Filesystem Exploration**: `FilesystemHelper` explores `servers/` directory
2. **Tool Selection**: `ToolSelector` uses semantic/keyword search to find relevant tools
3. **Code Generation**: `CodeGenerator` creates Python code that imports selected tools
4. **Execution**: `SandboxExecutor` writes tools to workspace and executes code

### How State Persists

1. **Workspace Mount**: Workspace directory is mounted at `/workspace` in sandbox via virtiofs
2. **File Writing**: Files written to `/workspace` in sandbox persist to host filesystem
3. **Cross-Session**: Files persist across different executions (workspace is on host)
4. **Per-Customer**: Each customer UID can have their own workspace directory

### How Session Continuity Works

1. **Session Logs**: Each session writes a log file to `/workspace/sessions/`
2. **Checkpoints**: Sessions can set checkpoints for resumption
3. **State Files**: State files are tracked in session logs
4. **Resumption**: Subsequent sessions can read previous logs and continue work

---

## Troubleshooting

### Common Issues

1. **Microsandbox server not running**
   - Error: "Cannot connect to microsandbox server"
   - Solution: Start server with `msb server start --dev`

2. **Volume mount not working**
   - Error: Files not visible in sandbox
   - Solution: Ensure workspace directory exists and is writable

3. **Import errors in sandbox**
   - Error: "ModuleNotFoundError: No module named 'client.mcp_client'"
   - Solution: Files are written to workspace before sandbox creation - check file writing logs

4. **Sandbox timeout**
   - Error: "Execution timed out"
   - Solution: Increase timeout in `ExecutionConfig` or check server logs

---

## License

MIT

---

## References

- [Anthropic Article: Code execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp)
- [Microsandbox Documentation](https://github.com/zerocore-ai/microsandbox)
- [Model Context Protocol (MCP)](https://modelcontextprotocol.io/)

