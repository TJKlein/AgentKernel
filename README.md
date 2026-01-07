# AgentKernel

A minimal kernel for agentic systems.

**AgentKernel is my attempt to make the runtime structure of agent systems explicit and minimal.**

Created and maintained by **Tassilo J. Klein**

---

[Getting Started](#getting-started) ·
[Configuration](#configuration) ·
[CLI Reference](#cli-reference) ·
[API Documentation](DOCS.md) ·
[Roadmap](#roadmap)

---

## Why I Built This

I kept encountering the same issue across agent frameworks:  
the interesting complexity is not in prompts or tools, but in the *runtime*.

Most systems tightly couple planning, execution, state, and tooling
into framework-specific abstractions. I wanted to understand what
remains invariant if you strip agents down to their computational core.

**AgentKernel** is my attempt to factor agent systems into the smallest
set of stable primitives: execution, state, control, and tool interaction.

AgentKernel reflects how I think about agent systems: **runtimes first, prompts second**.

---

## Design Philosophy

AgentKernel is intentionally minimal.

Instead of adding features, it removes assumptions:
- no opinionated planning strategy  
- no baked-in prompt formats  
- no framework-level orchestration  

The goal is not to be a full agent framework, but a *kernel*:
a small, explicit execution substrate that other systems can build on.

I expect this decomposition to evolve as agent systems mature.

---

## Context and Related Work

This work was directly inspired by recent engineering posts from Anthropic
([*Code Execution with MCP*](https://www.anthropic.com/engineering/code-execution-with-mcp))
and Cloudflare ([*Code Mode*](https://blog.cloudflare.com/code-mode/)),
which describe a shared architectural pattern for agent runtimes:

Instead of exposing all tools directly to a language model, agents
can generate executable code that interacts with tool APIs via
a runtime layer.

I arrived at a similar decomposition independently while exploring
how to make agent execution explicit, inspectable, and durable.

AgentKernel implements this pattern in a minimal, framework-agnostic
form — focusing on the underlying runtime rather than
ecosystem-specific implementations.

---

## What This Is (and Is Not)

**AgentKernel is:**
- a minimal execution loop for agent systems  
- explicit about state, control flow, and tool invocation  
- designed to surface runtime structure rather than hide it  

**AgentKernel is not:**
- a batteries-included agent framework  
- a prompt library  
- a replacement for higher-level orchestration systems  

---

## Who This Is For

AgentKernel is intended for:
- researchers studying agent architectures  
- engineers building custom agent runtimes  
- anyone interested in the foundations of agent execution  

If you are looking for a full-featured framework, this is probably
not what you want.  
If you want to understand *how agents actually run*, this is.

---

## Programmatic Tool Execution

AgentKernel implements the same programmatic tool execution pattern
described by Anthropic as *Programmatic Tool Calling (PTC)*.

Instead of issuing individual structured tool calls, agents generate
and execute code that interacts with tools through a runtime layer.
This allows agents to reason over large datasets locally and return
only distilled results.

This pattern is particularly effective for:
- data-intensive workflows  
- iterative computation  
- scenarios where intermediate results should not enter the model context  

---

## Why Programmatic Tool Execution?

1. **LLMs excel at writing code**  
   They reason naturally in programs, data flows, and control structures.

2. **Token efficiency through local execution**  
   Large intermediate results are processed locally and never enter
   the model context.

3. **Better control and inspectability**  
   Execution becomes explicit, debuggable, and auditable.

---

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

---

## Performance Characteristics

| Dimension | AgentKernel | Cloud Solutions |
|-----------|-------------|-----------------|
| **Startup** | <100ms | 2-5s API latency |
| **Cost** | $0 (self-hosted) | $0.10-0.50/hour |
| **Privacy** | 100% local | Cloud processing |
| **Token Usage** | 50-500 tokens | 5,000-50,000 tokens |
| **Network** | Optional | Required |

---

## Key Features

- **Programmatic Tool Calling** - Execute workflows with generated Python code
- **Async Middleware** - Background task execution with "fire and collect" pattern
- **Sandbox Pooling** - Pre-warmed sandboxes for <100ms startup
- **Volume Mounting** - Persistent workspace across executions
- **Skill Management** - Save and reuse code patterns across sessions
- **MCP Integration** - Compatible with Model Context Protocol
- **Guardrails** - Code validation and safety checks

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

### With Skill Management

```python
from agentkernel import create_agent, SkillManager

agent = create_agent()
skill_manager = SkillManager()

# Agent writes successful code
code = """
def analyze_sentiment(text):
    # Complex sentiment analysis logic
    return score
"""

# Save as reusable skill
skill_manager.save_skill(
    name="sentiment_analyzer",
    code=code,
    description="Analyze sentiment of text",
    tags=["nlp", "sentiment"]
)

# Later sessions: agent imports and reuses
reuse_code = """
from skills import sentiment_analyzer
result = sentiment_analyzer.analyze_sentiment("Great product!")
"""
agent.execute_task(reuse_code)
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
