# AgentKernel

**The High-Performance Local Runtime for Autonomous Agents**

Build production-grade AI agents with 100x faster execution, zero cloud costs, and enterprise-grade isolation. AgentKernel implements [Anthropic's Programmatic Tool Calling (PTC)](https://www.anthropic.com/engineering/code-execution-with-mcp) pattern with MCP integration, enabling agents to execute tasks through generated Python code instead of individual tool calls.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

---

## �� Why AgentKernel?

| Feature | AgentKernel (Local) | Cloud Solutions (Daytona, RunPod) |
|---------|---------------------|-----------------------------------|
| **Speed** | <100ms sandbox pool | 2-5s API round-trip |
| **Cost** | $0 (self-hosted) | $0.10-0.50 per hour |
| **Privacy** | 100% local | Cloud processing |
| **Network** | Optional | Required |
| **Customization** | Full control | Limited |

**Key Benefits:**
- 🚀 **10-100x Faster**: Local sandbox pooling eliminates cloud latency
- 💰 **Zero Cost**: Self-hosted with no API fees
- 🔒 **Enterprise Security**: Process-level isolation, no data leaves your infrastructure
- 🎯 **Token Efficiency**: 85-98% reduction by processing data locally
- ⚡ **Async Middleware**: Background task execution with "fire-and-forget" pattern
- 🔧 **Production-Ready**: Guardrails, state management, extensive optimization

---

## ✨ What's New: Async Middleware

AgentKernel now includes async middleware for background task execution, matching the capabilities of tools like `open-ptc-agent`:

```python
from code_execution_mcp import create_agent, TaskManager

agent = create_agent()
manager = TaskManager(agent)

# Dispatch tasks to background workers
task1 = manager.dispatch_task("Analyze 1M row CSV")
task2 = manager.dispatch_task("Scrape 50 websites")
task3 = manager.dispatch_task("Calculate fibonacci(40)")

# Continue working while tasks run...

# Collect results when ready
results = [manager.wait_for_task(tid) for tid in [task1, task2, task3]]
```

**5 New MCP Tools** for async execution:
- `dispatch_background_task()` - Start async execution
- `get_background_task_status()` - Check progress
- `wait_for_background_task()` - Block until complete
- `list_background_tasks()` - View all tasks
- `cancel_background_task()` - Cancel running task

---

## 🚀 Quick Start

### 1. Install Microsandbox (Required)

**⚠️ Important**: AgentKernel requires microsandbox with **volume mounting support**. The standard installation doesn't include this feature.

#### Option A: Build from Source (Recommended)

```bash
# Clone microsandbox repository (ensure it has volume support)
git clone https://github.com/TJKlein/microsandbox.git
cd microsandbox

# Build the server
cargo build --release

# Start server (keep running in a separate terminal)
./target/release/msbserver --dev
```

#### Option B: Standard Installation (Limited)

```bash
# Standard installation (does NOT support volumes)
curl -sSL https://get.microsandbox.dev | sh

# ⚠️ This will NOT work with AgentKernel!
# You must build from source instead.
```

### 2. Install AgentKernel

```bash
pip install code-execution-mcp  # (When published)
# Or from source:
git clone https://github.com/your-org/code-execution-mcp.git
cd code-execution-mcp
pip install -e .
```

### 3. Create Your First Agent

```python
from code_execution_mcp import create_agent, execute_task

# Simple one-liner
result, output, error = execute_task("Calculate fibonacci(30)")

# Or create reusable agent
agent = create_agent()
result, output, error = agent.execute_task("Get weather for Paris")
```

### 4. Configure Microsandbox (Important!)

AgentKernel requires proper microsandbox configuration to work correctly. Follow these steps:

#### A. Create Sandboxfile

Create `/Users/YOUR_USERNAME/.microsandbox/namespaces/default/Sandboxfile`:

```yaml
sandboxes:
  code-execution:
    image: microsandbox/python
    memory: 512
    cpus: 1
    volumes:
    - /path/to/code-execution-mcp/workspace:/workspace
    ports:
    - 64943:4444
```

**Important**: Replace `/path/to/code-execution-mcp/workspace` with your actual workspace path!

#### B. Pre-pull Docker Image

```bash
docker pull microsandbox/python
```

#### C. Start Microsandbox Server

**⚠️ IMPORTANT**: You must use the **rebuilt binary** from your local microsandbox repository, not the globally installed `msb` command!

The global `msb` (installed via `curl -sSL https://get.microsandbox.dev | sh`) does **NOT** include volume mounting support and will cause errors like:
```
"Invalid params for sandbox.start: invalid type: map, expected a string"
```

**Correct way** (use the rebuilt binary):
```bash
cd /path/to/microsandbox
./target/release/msbserver --dev
```

**Wrong way** (will fail):
```bash
msb server start --dev  # ❌ This uses the old global binary without volume support
```

**Why?** The global installation doesn't include the volume mounting patches. You need to:
1. Clone the microsandbox repo with volume support
2. Build it locally: `cargo build --release`
3. Use the binary from `target/release/msbserver`

**About the `--dev` flag:**
- `--dev`: Development mode - disables authentication, allows local connections
- Without `--dev`: Production mode - requires API key authentication
- **For local development**: Always use `--dev`
- **For production**: Omit `--dev` and set up proper authentication

### 5. Run Tests

```bash
cd code-execution-mcp
python test_async_middleware.py
```

Expected output:
```
✅ All critical tests passed!
Async middleware is working correctly!
```

---

## 🔧 Troubleshooting

### Issue: "Invalid params for sandbox.start: invalid type: map, expected a string"

**Cause**: Microsandbox server doesn't support volume mounting (old version).

**Solution**:
1. Ensure you have the latest microsandbox with volume support
2. Rebuild the server: `cd microsandbox && cargo build --release`
3. Restart with the rebuilt binary: `./target/release/msbserver --dev`

### Issue: "cannot find sandbox: 'code-execution-xxx' in Sandboxfile"

**Cause**: Sandboxfile missing or incorrect configuration.

**Solution**:
1. Verify Sandboxfile exists at `~/.microsandbox/namespaces/default/Sandboxfile`
2. Ensure it has a `code-execution` sandbox defined with volumes
3. Restart microsandbox server after updating Sandboxfile

### Issue: Tests timeout after 30 seconds

**Cause**: First-time Docker image pull or slow VM initialization.

**Solution**:
1. Pre-pull the image: `docker pull microsandbox/python`
2. Wait for first sandbox to warm up (subsequent runs will be faster)
3. This is normal microsandbox behavior, not an AgentKernel issue

### Issue: "Address already in use (os error 48)"

**Cause**: Microsandbox server already running on port 5555.

**Solution**:
```bash
# Find and kill existing server
ps aux | grep msbserver
kill <PID>

# Or use pkill
pkill -f msbserver
```

---

## 📖 Core Concepts

### Programmatic Tool Calling (PTC)

Traditional agents make individual JSON tool calls. AgentKernel generates **Python code** that orchestrates multiple tools:

**Traditional Approach:**
```json
{"tool": "get_stock", "args": {"ticker": "AAPL"}}
→ Returns 2,500 OHLCV data points (10,000+ tokens)
{"tool": "calculate_mean", "args": {"data": [...]}}
```

**AgentKernel (PTC) Approach:**
```python
from tools.finance import get_stock_history
import pandas as pd

data = get_stock_history("AAPL", period="1y")  # Stays in sandbox
df = pd.DataFrame(data)
summary = {"mean": df["close"].mean(), "std": df["close"].std()}
print(summary)  # Only summary returns to LLM (50 tokens)
```

**Result**: 85-98% token reduction, faster execution, lower costs.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────┐
│   AgentHelper (Orchestration)      │
│   - Task execution                  │
│   - Tool discovery                  │
│   - Async middleware (NEW)          │
└─────────────────────────────────────┘
              ↓
┌─────────────────────────────────────┐
│   Progressive Tool Discovery        │
│   - Semantic search                 │
│   - Lazy loading                    │
│   - Caching                         │
└─────────────────────────────────────┘
              ↓
┌─────────────────────────────────────┐
│   Code Generation                   │
│   - Template-based (default)        │
│   - LLM-based (optional)            │
└─────────────────────────────────────┘
              ↓
┌─────────────────────────────────────┐
│   Microsandbox Execution            │
│   - Sandbox pooling                 │
│   - Volume mounting                 │
│   - Process isolation               │
└─────────────────────────────────────┘
```

---

## 🔧 Advanced Features

### LLM-Based Code Generation

```python
agent = create_agent(
    llm_enabled=True,
    llm_provider="azure_openai",  # or "openai"
    llm_azure_endpoint="https://your-resource.openai.azure.com",
    llm_api_key="your_key"
)
```

### State Persistence

```python
agent = create_agent(
    state_enabled=True,
    state_file="workflow_state.json",
    state_auto_save=True
)
```

### Run as MCP Server

```bash
# Start MCP server
python -m code_execution_mcp.server stdio

# Or programmatically
from code_execution_mcp import run_server
run_server(transport="stdio")
```

**12 MCP Tools Exposed:**
- `execute_task` - Execute tasks
- `list_available_tools` - Discover tools
- `search_tools` - Progressive disclosure
- `get_state` / `save_state` - State management  
- `dispatch_background_task` - Async execution (NEW)
- `wait_for_background_task` - Collect results (NEW)
- And more...

---

## 📊 Performance Optimizations

AgentKernel includes production-grade optimizations:

- **Sandbox Pooling**: Pre-warmed sandboxes for <100ms execution
- **Tool Caching**: Avoid redundant file reads
- **Parallel Discovery**: Concurrent tool discovery
- **GPU Embeddings**: Hardware-accelerated semantic search

```python
agent = create_agent()
# Sandbox pooling enabled by default
# First call: ~500ms (cold start)
# Subsequent calls: <100ms (pooled)
```

---

## 🎯 Use Cases

### Data Processing Agents
Process large datasets locally without sending data to cloud LLMs:
```python
task = "Analyze sales_data.csv (10M rows) and generate monthly revenue report"
result = execute_task(task)
```

### Multi-Tool Workflows
Chain multiple tools efficiently:
```python
task = "Get weather for top 10 US cities, compare temperatures, generate chart"
result = execute_task(task)
```

### Parallel Execution
Run multiple tasks concurrently:
```python
manager = TaskManager(agent)
tasks = [manager.dispatch_task(f"Process file_{i}.csv") for i in range(100)]
results = [manager.wait_for_task(t) for t in tasks]
```

---

## 📚 Documentation

- **[Integration Guide](INTEGRATION_AND_PROGRESSIVE_DISCLOSURE_GUIDE.md)** - JWT-aware state, progressive disclosure
- **[Examples](examples/)** - 14+ working examples
- **[API Reference](DOCUMENTATION.md)** - Complete API documentation

---

## 🤝 Comparison with Alternatives

| Framework | Sandbox | Code Gen | Async | Cost | Speed |
|-----------|---------|----------|-------|------|-------|
| **AgentKernel** | Microsandbox (local) | Template + LLM (optional) | ✅ Built-in | Free | 🚀 <100ms |
| open-ptc-agent | Daytona (cloud) | LLM-based | ✅ Built-in | $$$ | ⏱️ 2-5s |
| langchain-code-exec | Various | LLM-based | ❌ | Varies | Varies |

---

## 🛣️ Roadmap

- [x] Async middleware (TaskManager)
- [x] Progressive tool discovery
- [x] Sandbox pooling optimization
- [ ] Docker sandbox backend option
- [ ] Multi-language support (Node.js, Go)
- [ ] Visual debugging / monitoring dashboard
- [ ] Cloud deployment templates (K8s, Docker Compose)

---

## 📄 License

MIT License - see [LICENSE](LICENSE) for details

---

## 🙏 Acknowledgements

Built on:
- [Microsandbox](https://microsandbox.dev) - Secure code execution
- [FastMCP](https://github.com/jlowin/fastmcp) - MCP server framework
- Anthropic's [Programmatic Tool Calling](https://www.anthropic.com/engineering/code-execution-with-mcp) pattern

---

## 🌟 Star History

If you find AgentKernel useful, please consider starring the repository!

---

**Ready to build blazing-fast agents?** [Get Started](#-quick-start) | [View Examples](examples/) | [Join Discussions](https://github.com/your-org/code-execution-mcp/discussions)
