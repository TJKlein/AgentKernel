# Code Execution MCP Examples

This directory contains examples demonstrating different use cases of the code execution MCP framework.

## Examples

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
**State Persistence**
- Saving and loading state via filesystem
- Resuming work across multiple executions
- Persistent data storage

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

## Prerequisites

All examples require:
- Virtual environment activated (`.venv`)
- Microsandbox server running (`msb server start --dev`)
- Dependencies installed (`pip install -r requirements.txt`)

## Common Patterns

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

