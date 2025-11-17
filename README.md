# Code Execution MCP Implementation

A generic, extensible code execution pattern for MCP (Model Context Protocol) that allows agents to interact with MCP servers through Python code APIs instead of direct tool calls. This significantly reduces token consumption and improves efficiency by leveraging LLMs' strength at writing code.

## Quick Start

```bash
# Setup
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Install and start Microsandbox server
curl -sSL https://get.microsandbox.dev | sh
msb server start --dev  # Keep running in separate terminal

# Configure Azure OpenAI (optional, for LLM-based code generation)
# Create .env file with:
# AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
# AZURE_OPENAI_API_KEY=your_api_key
# AZURE_OPENAI_DEPLOYMENT_NAME=gpt-5.1-codex-mini
# AZURE_OPENAI_API_VERSION=2024-08-01-preview

# Run an example
OPTIMIZATION_SANDBOX_POOLING=true python examples/01_basic_tool_call.py
```

## Features

- **Filesystem-based Tool Discovery**: Agents discover tools by exploring the `servers/` directory
- **Progressive Disclosure**: Only load tools needed for the task (semantic/keyword selection)
- **State Persistence**: Save and resume work using the `workspace/` directory (cross-session)
- **Skills System**: Reusable code functions stored in `skills/` directory
- **LLM-based Code Generation**: Uses Azure OpenAI or OpenAI to generate Python code (with rule-based fallback)
- **Smart Sandbox Pooling**: Reuses sandboxes for 100-700x faster execution
- **Secure Execution**: microsandbox integration for hardware-isolated execution

## Architecture

This implementation follows the [Anthropic article on code execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp):

- ✅ Filesystem-based tool discovery
- ✅ Progressive disclosure (discover all, load only needed)
- ✅ State persistence via volume mounts
- ✅ Tools as filesystem modules
- ✅ Code execution pattern

## Sandbox Pooling

**Critical for performance**: Sandbox pooling reuses pre-created sandboxes, achieving **100-700x speedup** after the first execution.

### How It Works

The standard `PythonSandbox.create()` context manager stops sandboxes automatically, preventing reuse. Our implementation manually manages the sandbox lifecycle:

- **Pre-creates 3 sandboxes** on initialization
- **Keeps sandboxes running** between executions (not stopped)
- **Recreates HTTP sessions** when event loops are closed (handles `asyncio.run()`)
- **Health checks** verify sandboxes are still active before reuse
- **Shared pool** works across all examples

### Performance

- **First execution**: ~100-140s (pool initialization + first run)
- **Subsequent executions**: ~0.5-1.5s (**141-700x faster**)
- **Works across different examples** (same pool shared)

### Enable Pooling

Set environment variable:
```bash
export OPTIMIZATION_SANDBOX_POOLING=true
```

Or add to `.env`:
```bash
OPTIMIZATION_SANDBOX_POOLING=true
```

### Benchmarking Pooling

Use `benchmark_pooling.py` to measure pooling performance:

```bash
# Run a sequence of different examples (tests pooling across examples)
OPTIMIZATION_SANDBOX_POOLING=true python3 benchmark_pooling.py --sequence 01,03,01,07,03,05,08

# Run same example multiple times (tests pooling reuse)
OPTIMIZATION_SANDBOX_POOLING=true python3 benchmark_pooling.py --example 01 -n 5

# Run all examples once
OPTIMIZATION_SANDBOX_POOLING=true python3 benchmark_pooling.py --all

# Run with verbose output
OPTIMIZATION_SANDBOX_POOLING=true python3 benchmark_pooling.py --sequence 01,03,05 -v
```

**Expected Results**:
- First run: ~100-140s (pool initialization)
- Subsequent runs: ~0.5-1.5s (141-700x faster)

**Location**: `client/sandbox_pool.py`

## LLM-based Code Generation

Integrated Azure OpenAI and OpenAI for code generation with automatic fallback to rule-based generation.

**Configuration**: Auto-detected from `.env` or `config.yaml`. If Azure OpenAI env vars are present, LLM generation is automatically enabled.

**Flow**: Attempts LLM generation first, falls back to rule-based on error or if disabled.

**Note**: Some Azure OpenAI models require `max_completion_tokens` instead of `max_tokens` (fix pending).

**Location**: `client/code_generator.py`

## Progressive Disclosure

1. **Discovery**: Explores `servers/` directory to find ALL available tools
2. **Selection**: Uses semantic search or keyword matching to select only relevant tools
3. **Code Generation**: Generated code only imports selected tools
4. **Execution**: Only selected tools are loaded (Python import system)

**Efficiency**: Typically uses 20-30% of available tools per task (70-80% reduction in context size).

**Location**: `client/tool_selector.py`

## State Persistence

Workspace directory mounted at `/workspace` in sandbox via virtiofs. Files written to `/workspace` persist to host filesystem and work across separate executions (true cross-session persistence).

**Examples**: 
- `examples/05_state_persistence.py`: 2-session persistence
- `examples/08_cross_session_persistence.py`: 3-session workflow

## Benchmarking

Use `benchmark_pooling.py` to measure performance and verify pooling works correctly.

### Basic Usage

```bash
# Run a sequence of different examples (tests pooling across examples)
OPTIMIZATION_SANDBOX_POOLING=true python3 benchmark_pooling.py --sequence 01,03,01,07,03,05,08

# Run same example multiple times (tests pooling reuse)
OPTIMIZATION_SANDBOX_POOLING=true python3 benchmark_pooling.py --example 01 -n 5

# Run all examples once
OPTIMIZATION_SANDBOX_POOLING=true python3 benchmark_pooling.py --all

# Run with verbose output
OPTIMIZATION_SANDBOX_POOLING=true python3 benchmark_pooling.py --sequence 01,03,05 -v
```

### Available Examples

- `01`: Basic Tool Call
- `03`: Data Filtering
- `05`: State Persistence
- `07`: Filesystem Operations
- `08`: Cross-Session Persistence

### Expected Results

**With Pooling Enabled**:
- First execution: ~100-140s (pool initialization)
- Subsequent executions: ~0.5-1.5s (**141-700x faster**)

**Without Pooling**:
- Average execution: ~35-40s per task

### Other Optimizations

- **File Content Caching**: Only writes changed files to workspace
- **Shared Model Cache**: Sentence-transformers model loaded once and reused
- **Parallel Tool Discovery**: Concurrent server discovery

## Configuration

### Environment Variables

Create a `.env` file:

```bash
# Microsandbox server
MSB_SERVER_URL=http://localhost:5555

# Workspace configuration
WORKSPACE_DIR=./workspace
SERVERS_DIR=./servers
SKILLS_DIR=./skills

# Sandbox pooling (critical for performance)
OPTIMIZATION_SANDBOX_POOLING=true

# LLM-based code generation (optional)
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
AZURE_OPENAI_API_KEY=your_api_key
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-5.1-codex-mini
AZURE_OPENAI_API_VERSION=2024-08-01-preview

# Or OpenAI
OPENAI_API_KEY=your_openai_key
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
```

### Configuration File

Alternatively, create `config.yaml`:

```yaml
execution:
  workspace_dir: ./workspace
  servers_dir: ./servers
  skills_dir: ./skills
  sandbox_type: microsandbox
  sandbox_image: python
  allow_network_access: false

llm:
  enabled: true
  provider: azure_openai
  model: gpt-4o-mini
  azure_endpoint: https://your-resource.openai.azure.com
  azure_deployment_name: gpt-5.1-codex-mini
  azure_api_version: 2024-08-01-preview
  temperature: 0.3
  max_tokens: 2000

guardrails:
  enabled: true
  strict_mode: false
  security_checks: true
  max_execution_time: 300
  max_memory_mb: 512
```

## Examples

The `examples/` directory contains comprehensive examples:

- **01_basic_tool_call.py**: Basic tool call & filesystem discovery
- **02_multi_tool_chain.py**: Multi-tool chaining & data flow
- **03_data_filtering.py**: Data filtering & transformation
- **04_control_flow.py**: Control flow & conditional logic
- **05_state_persistence.py**: Cross-session state persistence (2 sessions)
- **06_skills.py**: Skills & reusable code
- **07_filesystem_operations.py**: Filesystem operations
- **08_cross_session_persistence.py**: Multi-session workflow (3 sessions)

**Run examples**:
```bash
# With pooling (recommended)
OPTIMIZATION_SANDBOX_POOLING=true python examples/01_basic_tool_call.py

# Without pooling (for debugging)
python examples/01_basic_tool_call.py
```

## Project Structure

```
code-execution-mcp/
├── client/              # Core framework components
│   ├── agent_helper.py         # High-level agent workflow
│   ├── sandbox_executor.py      # Sandbox execution with volume mounts
│   ├── sandbox_pool.py          # Smart sandbox pooling (critical optimization)
│   ├── filesystem_helpers.py   # Filesystem operations
│   ├── tool_selector.py         # Tool selection (semantic/keyword)
│   ├── code_generator.py        # Code generation (LLM + rule-based)
│   └── mcp_client.py            # MCP client implementation
├── config/              # Configuration management
│   ├── schema.py        # Pydantic schemas (including LLMConfig)
│   └── loader.py        # Config loading (YAML/env, auto-loads .env)
├── servers/              # Generated tool files (filesystem-based discovery)
│   ├── calculator/      # Calculator tools
│   ├── weather/         # Weather tools
│   ├── filesystem/      # Filesystem tools
│   └── database/        # Database tools
├── workspace/            # State persistence directory
│   ├── client/          # Client code (written by executor)
│   ├── servers/         # Tool modules (written by executor)
│   ├── skills/          # Reusable skills
│   └── state/           # Customer-specific state
├── skills/               # Reusable code functions
├── examples/             # Comprehensive showcase examples
├── benchmark_pooling.py  # Performance benchmarking script
└── .env                  # Environment variables (create this)
```

## Development

### Running Examples

```bash
# Run all examples
python run_all_examples.py

# Run specific example with pooling
OPTIMIZATION_SANDBOX_POOLING=true python examples/01_basic_tool_call.py

# Run specific example without pooling (for debugging)
python examples/01_basic_tool_call.py
```

### Benchmarking

See [Benchmarking](#benchmarking) section above for detailed benchmark commands.

### Type Checking

```bash
mypy .
```

### Linting

```bash
ruff check .
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

## Known Issues & Limitations

1. **Azure OpenAI `max_tokens` parameter**: Some models (e.g., `gpt-5.1-codex-mini`) require `max_completion_tokens` instead of `max_tokens`. This causes LLM generation to fall back to rule-based. Fix pending.

2. **Sandbox pooling requires manual lifecycle management**: The standard `PythonSandbox.create()` context manager stops sandboxes automatically, so we had to implement custom pooling with manual session management.

3. **Event loop handling**: Pooled sandboxes need session recreation when event loops are closed (handled automatically but adds complexity).


## License

MIT

## References

- [Anthropic Article: Code execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp)
- [Microsandbox Documentation](https://github.com/zerocore-ai/microsandbox)
- [Model Context Protocol (MCP)](https://modelcontextprotocol.io/)
