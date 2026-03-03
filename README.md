# AgentKernel

![AgentKernel Banner](assets/agentkernel_banner.png)

[![License](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://github.com/TJKlein/agentkernel/workflows/Tests/badge.svg)](https://github.com/TJKlein/agentkernel/actions)
[![Version](https://img.shields.io/badge/version-0.1.1-blue.svg)](pyproject.toml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](Dockerfile)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

**A minimal computational substrate for Model Context Protocol (MCP) agents — with a self-growing tool library.**

AgentKernel decouples the **execution runtime** from the agent's reasoning loop. It provides a stable, high-performance primitive for building durable agent systems that can read, write, and execute code safely.

By treating tools as importable libraries within a sandboxed environment (the **[Programmatic Tool Calling](https://www.anthropic.com/engineering/code-execution-with-mcp)** pattern), AgentKernel enables agents to reason over large datasets and perform complex multi-step tasks without the latency and context bloat of chat-based tool use.

What sets AgentKernel apart is its implementation of **[Code Actions as Tools](https://gradion-ai.github.io/agents-nanny/2025/12/16/code-actions-as-tools-evolving-tool-libraries-for-agents/)**: instead of treating agent-generated code as ephemeral — generated, executed, then discarded — AgentKernel recognizes that a working code action represents a *tested solution*. When saved in a discoverable format with a callable API, it becomes a tool that future code actions can import and compose. **The agent thus serves two roles: a domain-specific agent performing the task at hand, and a toolsmith evolving its own capabilities.**

---

## ⚡️ Quick Start (Docker)

The fastest way to run AgentKernel is with Docker. This spins up a fully patched `microsandbox` environment and the AgentKernel runtime in a single command.

```bash
git clone https://github.com/TJKlein/agentkernel.git
cd agentkernel

# Set your API key (or use a .env file; do not commit credentials)
export OPENAI_API_KEY=your-key-here

# Start the environment
docker-compose up --build
```

You are now ready to run agents inside the container!

```bash
# In a new terminal
docker-compose exec agentkernel python examples/00_simple_api.py
```

**Running locally:** Clone the repository, then run `make env` (copy `.env.example` to `.env` and set your API key), `make install-dev`, and `make test`. See [CONTRIBUTING.md](CONTRIBUTING.md) for the full setup guide and microsandbox configuration.

---

## 1. Architecture

AgentKernel standardizes the interaction between the semantic agent (LLM) and the execution environment (Kernel).

```mermaid
graph TD
    %% Define the distinct vertical layers explicitly
    subgraph Layer1 ["Agent (Semantic Layer)"]
        direction TB
        A["LLM Reasoner"]
        B["Planner"]
    end

    subgraph Layer2 ["AgentKernel (Runtime Layer)"]
        direction TB
        K["Kernel Controller"]
        M["Middleware / Task Manager"]
        S["State Manager"]
        SK["Skill Registry (Self-Growing Tool Library)"]
    end

    subgraph Layer3 ["Execution Environment (Sandboxed)"]
        direction TB
        VM["Runtime Environment (e.g. Microsandbox)"]
        T["MCP Tools"]
        D["Data Context"]
    end

    %% Semantic -> Kernel
    A -->|Generates Program| K
    B -.-> A
    
    %% Kernel Operations
    K -->|Delegates async tasks| M
    K -->|Manages workspace state| S
    K -->|Save Successful Code Action| SK
    
    %% Kernel -> Env
    K -->|Dispatches execution| VM
    
    %% Env Internal
    VM -->|Imports| T
    VM -->|Imports| SK
    T -->|Reduces| D
    
    %% Upward Returns
    VM -.->|Returns Artifacts| K
    K -.->|Observations| A
```

## 2. Philosophy: Code Actions as Tools

Contemporary agent frameworks often conflate planning, execution, and state management. AgentKernel posits that the **execution runtime** is the invariant component of agent systems.

> **Thesis**: The interesting complexity in agent systems lies not in the prompt engineering, but in the runtime ability to safely execute generated programs — and to **learn from them** by evolving a persistent tool library.

AgentKernel implements the **Programmatic Tool Calling (PTC)** pattern described by [Anthropic](https://www.anthropic.com/engineering/code-execution-with-mcp) and [Cloudflare](https://blog.cloudflare.com/code-mode/), treating tools as importable libraries within a sandboxed environment rather than HTTP endpoints.

Building on this, AgentKernel introduces the **[Code Actions as Tools](https://gradion-ai.github.io/agents-nanny/2025/12/16/code-actions-as-tools-evolving-tool-libraries-for-agents/)** pattern: code actions that successfully complete a task are automatically extracted, typed, and saved into a persistent skill registry. In future sessions, the agent discovers and reuses these evolved tools — composing them with other tools to solve increasingly complex tasks without re-implementing logic from scratch.

The key difference from static JSON tool calling is **mutability**: an agent's tool library can evolve at runtime — tools can be added, modified, or composed based on what the agent learns while working.

## 3. Performance & Capabilities

AgentKernel is designed for high-throughput, low-latency execution of agent-generated code.

| Capability | Specification | Comparison |
|------------|---------------|------------|
| **Cold Start** | **< 100ms** | vs 2-5s (AWS Lambda / Containers) |
| **Context** | **Infinite (RLM)** | vs 128k - 2M Tokens (LLM Limit) |
| **Isolation** | Configurable (MicroVM / Wasm / Process) | vs Container (Docker) |
| **State** | Volume-mounted persistence | vs Ephemeral / Stateless |
| **Cost** | Self-hosted ($0) | vs Cloud metering |

### Key Features
*   **Model Context Protocol (MCP)**: Native support for MCP tools and patterns.
*   **Programmatic Tool Calling**: Tools are Python modules, not JSON schemas. Agents write code to use them.
*   **Code Actions as Tools / Skill Evolution**: Successfully executed code is automatically saved as a typed, callable tool. The agent builds a *Self-Growing Tool Library* that persists across sessions. ([Read the concept →](https://gradion-ai.github.io/agents-nanny/2025/12/16/code-actions-as-tools-evolving-tool-libraries-for-agents/))
*   **Async Middleware**: "Fire-and-forget" background task execution for long-running jobs.
*   **Sandbox Pooling**: Pre-warmed pools ensure immediate availability for interactive agents.
*   **Volume Mounting**: Persistent workspaces allow multi-turn reasoning with state preservation.
*   **Recursive Language Models (RLM)**: Process infinite context by treating data as variables and recursively querying the LLM.

### Execution Backends

AgentKernel supports pluggable execution runtimes to match workload requirements. The **Docker** image comes pre-configured with `microsandbox` built from source.

*   **Microsandbox (Default)**: Full Linux MicroVMs.
    *   *Advantage*: Supports complex system dependencies (compilers, databases, apt packages) and full OS isolation.
*   **Monty (Experimental)**: [High-performance Python interpreter](https://github.com/pydantic/monty).
    *   *Advantage*: Enables **sub-millisecond cold starts** and **in-process execution bridging**, ideal for pure-logic reasoning loops.

## 4. Manual Installation (Advanced)

If you prefer to install locally without Docker, you must compile the patched `microsandbox` binary manually, as the version on PyPI does not support volume mounting.

### 1. Install Rust & Build Microsandbox
```bash
git clone https://github.com/TJKlein/microsandbox.git
cd microsandbox
cargo build --release
```

### 2. Install AgentKernel
```bash
pip install agentkernel
```

### 3. Verify Setup
```bash
python verify_setup.py
```

## 5. Usage Example

```python
from agentkernel import create_agent

# Initialize the kernel
agent = create_agent()

# Execute a complex, multi-step task in a single turn
result = agent.execute_task("""
    import pandas as pd
    from tools.data_analysis import load_dataset
    
    # Load and process data locally in the sandbox
    df = load_dataset("large_file.csv")
    summary = df.describe()
    
    print(summary)
""")

print(result.output)
```

## 6. Skill Evolution (Self-Growing Tool Library)

AgentKernel implements the **[Code Actions as Tools](https://gradion-ai.github.io/agents-nanny/2025/12/16/code-actions-as-tools-evolving-tool-libraries-for-agents/)** pattern, enabling a **Self-Growing Tool Library** where the agent acts as both a problem solver and a toolsmith.

### How it works

1.  **Execute**: The agent generates code to solve a novel task and executes it in the sandbox.
2.  **Evaluate**: On success, a heuristic evaluates whether the code action is worth preserving (compilability, function structure, output quality).
3.  **Extract & Save**: The code is wrapped into a canonical skill module with a typed `run()` entry-point, docstring metadata, and source attribution — then saved to `skills/`.
4.  **Discover & Reuse**: In future sessions, the agent's prompt is automatically injected with a listing of available skills (including typed signatures). The LLM can then `from skills.my_tool import run` instead of rewriting the logic.

```
Turn 1 (novel task):
  Agent → generates code → executes → success ✓ → auto-saved as skills/fetch_weather.py

Turn 2 (related task):
  Agent prompt includes: "# Available skills: fetch_weather(city: str) -> dict"
  Agent → imports fetch_weather → composes with new logic → done in fewer tokens
```

This closed-loop creates an **accumulating advantage**: the more tasks the agent solves, the richer its tool library becomes, and the faster and cheaper future tasks execute.

**Backend Compatibility:** Skill Evolution is seamlessly integrated across all AgentKernel runtimes natively. Whether executing standard scripts in `microsandbox`, running high-performance AST evaluations via `MontyExecutor`, or processing infinite-context chunks through the `RecursiveAgent`, evolved skills are automatically saved, discovered, and shared between all backends.

> See [`examples/17_skill_evolution.py`](examples/17_skill_evolution.py) for an end-to-end demo.

## 7. Recursive Language Models (RLM)

AgentKernel supports **Recursive Language Models**, a powerful pattern for processing infinite context by treating it as a programmable variable.

*   **Recursive Querying**: The agent writes code to inspect, slice, and chunk this data, and recursively calls the LLM via `ask_llm()` to process each chunk.
*   **No Context Window Limits**: Process gigabytes of text by delegating the "reading" to a loop, only pulling relevant info into the agent's context.

See `examples/15_recursive_agent.py` for a complete example.

## 8. Development and Testing

See **[CONTRIBUTING.md](CONTRIBUTING.md)** for setup and contribution guidelines.

```bash
make install-dev    # Install with dev deps
make env            # Copy .env.example → .env (add your API keys)
make test           # Unit + integration (no API key needed)
make test-e2e       # E2E with real LLM (requires .env)
make test-all       # Full suite
```

Without Make: `pytest tests/ -v -m "not live"` for unit+integration; `pytest tests/e2e/ -v` for live E2E (requires `.env`).

## 9. References & Inspiration

AgentKernel stands on the shoulders of giants.

*   **[Code Actions as Tools: Evolving Tool Libraries for Agents](https://gradion-ai.github.io/agents-nanny/2025/12/16/code-actions-as-tools-evolving-tool-libraries-for-agents/)** — The conceptual foundation for the Skill Evolution / Self-Growing Tool Library feature. Introduces the idea that working code actions should be saved as typed, discoverable tools rather than discarded after execution.
*   **[Anthropic: Code Execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp)** — The Programmatic Tool Calling pattern: tools as importable code, not JSON schemas.
*   **[Cloudflare: Code Mode](https://blog.cloudflare.com/code-mode/)** — Production-scale implementation of code-based tool calling.
*   **[Recursive Language Models](https://arxiv.org/abs/2512.24601)** — Research into infinite context processing via recursive querying.
*   **[Microsandbox](https://github.com/TJKlein/microsandbox)** — The robust MicroVM runtime for secure code execution.
*   **[Monty](https://github.com/pydantic/monty)** — High-performance, sandboxed Python interpreter.

## Supporting the Project

If you find AgentKernel useful, consider starring the repository on GitHub. Stars help others discover the project and signal interest to the maintainers.

## License

MIT &copy; 2026 AgentKernel Team.
