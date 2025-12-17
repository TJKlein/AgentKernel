# AgentKernel

[Getting Started](#getting-started) | [Configuration](#configuration) | [CLI Reference](#cli-reference) | [API Documentation](DOCS.md) | [Roadmap](#roadmap)

**The High-Performance Local Runtime for Autonomous Agents**

Demo: Processing 1M+ rows of financial data with 100x faster execution and zero cloud costs

---

## What is Programmatic Tool Calling?

AgentKernel is an open source implementation of Anthropic's [Programmatic Tool Calling (PTC)](https://www.anthropic.com/engineering/code-execution-with-mcp), which enables agents to invoke tools with code execution rather than making individual JSON tool calls. This paradigm is featured in their engineering blog [Code execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp).

## Why PTC?

1. **LLMs excel at writing code!** They understand context, reason about data flows, and generate precise logic. PTC lets them orchestrate entire workflows rather than reasoning through one tool call at a time.

2. **Token efficiency through local processing.** Traditional tool calling returns full results to the model's context. Fetching 1 year of stock prices for 10 tickers means 2,500+ OHLCV data points - tens of thousands of tokens. With PTC, code runs in a sandbox, processes data locally, and only the final output returns. Result: **85-98% token reduction**.

3. **Optimized for data-intensive tasks.** PTC shines when working with large volumes of structured data, time series analysis, and scenarios requiring filtering, aggregating, or transforming results before returning them to the model.

## How It Works

```
User Task
    |
    v
+-------------------+
|   AgentKernel     |
| Tool discovery -> Writes Python code
+-------------------+
    |              ^
    v              |
+-------------------+
| Microsandbox      |
| Executes code     |
|  +-----------+    |
|  | MCP Tools |    |
|  | tool() -> process/filter/aggregate -> output
|  | (Python)  |    |
|  +-----------+    |
+-------------------+
    |
    v
+-------------------+
|Final deliverables |
| Results returned  |
| to agent          |
+-------------------+
```

Built on **Microsandbox** for secure local execution with enterprise-grade isolation.

## What's New

- **Async Middleware** - Background task execution with "fire and collect" pattern
- **Task Monitoring** - `wait_for_task()` and `get_task_status()` tools for async workflows
- **Sandbox Pooling** - <100ms startup with pre-warmed sandbox pool
- **Volume Mounting** - Persistent workspace for tool libraries and state
- **Zero Cloud Costs** - 100% local execution, no API fees

## Why AgentKernel?

| Feature | AgentKernel | Cloud Solutions |
|---------|-------------|-----------------|
| **Speed** | <100ms startup | 2-5s API latency |
| **Cost** | $0 (self-hosted) | $0.10-0.50/hour |
| **Privacy** | 100% local | Cloud processing |
| **Token Usage** | 50-500 tokens | 5,000-50,000 tokens |
| **Network** | Optional | Required |

---

## Getting Started

### Prerequisites

- Python 3.10+
- Docker
- Rust (for building Microsandbox)

### Installation

```bash
# Clone Microsandbox with volume support
git clone https://github.com/TJKlein/microsandbox.git
cd microsandbox
cargo build --release

# Clone AgentKernel
cd ..
git clone https://github.com/your-org/agentkernel.git
cd agentkernel
pip install -e .
```

> **Why build from source?** AgentKernel requires microsandbox with volume mounting support, which is NOT included in the standard  installation. See [Why Build Microsandbox from Source?](DOCS.md#why-build-microsandbox-from-source) for details.

### Minimal Configuration

Create a Sandboxfile at `~/.microsandbox/namespaces/default/Sandboxfile`:

```yaml
sandboxes:
  code-execution:
    image: microsandbox/python
    memory: 512
    cpus: 1
    volumes:
    - /absolute/path/to/agentkernel/workspace:/workspace
    ports:
    - 64943:4444
```

Pre-pull Docker image:

```bash
docker pull microsandbox/python
```

### Verify Setup

**Important**: Run this verification script to ensure everything is configured correctly:

```bash
python verify_setup.py
```

This will check:
- ✓ Docker is running
- ✓ No global `msb` interfering (wrong binary)
- ✓ Microsandbox server running with correct binary
- ✓ Sandboxfile configured
- ✓ **Volume mounting actually works**

If all checks pass, you're ready to use AgentKernel!

---

Start Microsandbox server:

```bash
cd /path/to/microsandbox
./target/release/msbserver --dev
```

Use AgentKernel:

```python
from code_execution_mcp import create_agent

agent = create_agent()
result, output, error = agent.execute_task("Calculate fibonacci(30)")
print(output)
```

### With Async Middleware

```python
from code_execution_mcp import create_agent, TaskManager

agent = create_agent()
manager = TaskManager(agent, max_workers=5)

# Dispatch background tasks
task1 = manager.dispatch_task("Process large dataset")
task2 = manager.dispatch_task("Analyze time series")

# Continue working while tasks run...

# Collect results when ready
result1 = manager.wait_for_task(task1)
result2 = manager.wait_for_task(task2)
```

See the [API Documentation](DOCS.md) for complete usage examples.

---

## Configuration

### Sandboxfile Settings

Customize sandbox resources:

```yaml
sandboxes:
  code-execution:
    image: microsandbox/python
    memory: 1024  # MB
    cpus: 2.0     # cores
    volumes:
    - /path/to/workspace:/workspace
```

### Environment Variables

```bash
# Optional: Custom workspace
export AGENTKERNEL_WORKSPACE=/path/to/workspace

# Optional: Debug logging
export AGENTKERNEL_LOG_LEVEL=DEBUG
```

See [Configuration Guide](DOCS.md#configuration) for all options.

---

## CLI Reference

### Basic Commands

```bash
# Run tests
python test_async_middleware.py

# Check sandbox status
docker ps | grep microsandbox

# View logs
tail -f ~/.microsandbox/logs/server.log
```

### Troubleshooting

**Issue: "Invalid params for sandbox.start"**

```bash
# Solution: Rebuild microsandbox
cd microsandbox && cargo build --release
./target/release/msbserver --dev
```

**Issue: "cannot find sandbox in Sandboxfile"**

```bash
# Solution: Verify Sandboxfile exists and is configured
cat ~/.microsandbox/namespaces/default/Sandboxfile
```

See [Troubleshooting Guide](DOCS.md#troubleshooting) for complete solutions.

---

## Features

### Core Features

- **Programmatic Tool Calling** - Execute workflows with generated Python code
- **Async Middleware** - Background task execution and monitoring
- **Sandbox Pooling** - Pre-warmed sandboxes for <100ms startup
- **Volume Mounting** - Persistent workspace across executions
- **MCP Integration** - Compatible with Model Context Protocol
- **Guardrails** - Code validation and safety checks

### Native Tools

Core tools available in the sandbox:

- **File Operations** - Read, write, and manipulate files
- **Data Processing** - Pandas, NumPy for data analysis
- **HTTP Requests** - Network calls and API integration
- **State Management** - Persistent state across executions

### Middleware

Async task management:

- `dispatch_background_task()` - Fire and forget pattern
- `get_background_task_status()` - Check task progress
- `wait_for_background_task()` - Block until completion
- `list_background_tasks()` - View all running tasks
- `cancel_background_task()` - Cancel execution

---

## Project Structure

```
agentkernel/
├── client/           # Core agent implementation
│   ├── agent.py      # AgentHelper class
│   ├── task_manager.py  # Async middleware
│   └── sandbox_executor.py  # Sandbox integration
├── server/           # MCP server
│   └── mcp_server.py # FastMCP server with tools
├── config/           # Configuration
├── examples/         # Usage examples
├── tests/            # Test suite
└── workspace/        # Default workspace
```

---

## Roadmap

- [ ] Multi-language support (JavaScript, TypeScript)
- [ ] Custom tool registry
- [ ] Advanced monitoring and metrics
- [ ] Cloud deployment templates
- [ ] VSCode extension
- [ ] Web UI for task management

---

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new features
4. Submit a pull request

---

## Acknowledgements

- Built on [Microsandbox](https://microsandbox.dev) for secure local execution
- Inspired by Anthropic's [Programmatic Tool Calling](https://www.anthropic.com/engineering/code-execution-with-mcp)
- Thanks to the LangChain and FastMCP communities

---

## Star History

⭐ Star this repo if you find it useful!

---

## License

MIT License - See LICENSE file for details

---

## About

**AgentKernel** - High-performance local runtime for autonomous agents

**Topics**: ai-agents, mcp, programmatic-tool-calling, sandbox, async-execution, python

**Resources**: [Documentation](DOCS.md) | [Examples](examples/) | [Issues](https://github.com/your-org/agentkernel/issues)
