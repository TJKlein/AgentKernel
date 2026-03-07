# PTC-Bench: The Programmatic Tool Calling Benchmark

**PTC-Bench** is the first systematic benchmark comparing **Programmatic Tool Calling (PTC)** — where agents generate code that imports and calls tools — vs traditional **Function Calling (FC)** — where agents emit JSON tool calls.

> **Research Question:** When should AI agents use Programmatic Tool Calling (code-first) vs traditional Function Calling (JSON-first)? We provide empirical answers.

## Prerequisites

- **Docker** (for OpenSandbox backend)
- **Python 3.10+** with project dependencies
- **LLM API key** (e.g. `OPENAI_API_KEY` or Azure) for agent (LLM) mode; required for Function Calling comparison

## Quick Run

### 1. PTC mode (Programmatic Tool Calling)

LLM generates code that imports/calls tools → runs in sandbox:

```bash
python -m benchmarks run --backend opensandbox --llm-provider openai --approach ptc
```

### 2. FC mode (Function Calling - JSON tool calls)

LLM emits JSON tool calls → framework executes → results fed back → repeat:

```bash
python -m benchmarks run --backend opensandbox --llm-provider openai --approach function_calling
```

### 3. Both approaches (for direct comparison)

Run the same tasks with both PTC and FC, then compare:

```bash
python -m benchmarks run --backend opensandbox --llm-provider openai --approach both
```

This generates a comparison report showing:
- Success rates (PTC vs FC)
- Latency (execution time)
- Cost (estimated from token usage)
- LLM calls and tool calls
- Retries needed

### 4. Baseline mode (infrastructure verification)

Runs hand-written reference code (no LLM):

```bash
python -m benchmarks run --backend opensandbox --llm-provider none
```

## Options

| Option | Description |
|--------|-------------|
| `--backend` | `opensandbox` (recommended) or `subprocess` |
| `--approach` | `ptc`, `function_calling`, or `both` (default: `ptc`) |
| `--llm-provider` | `openai`, `anthropic`, `google`, `azure_openai`, or `none` |
| `--llm-model` | Model name (default: `gpt-4o`); for Azure, use deployment name |
| `--runs` | Number of runs per task (for statistical variance, default: 1) |
| `--categories` | Comma-separated, e.g. `compute,ptc,io` |
| `--output` | Write report to file (e.g. `report.md`) |

## Task layout

- `tasks/` — Task definitions by category: `ptc`, `compute`, `import_heavy`, `io`, `memory`, `concurrency`, `enterprise`
- `runner.py` — Execution harness with dual approach support
- `function_calling_runner.py` — FC baseline (JSON tool calling loop)
- `metrics.py` / `reports.py` — Aggregation and PTC vs FC comparison reporting

## How the comparison works

When you run with `--approach both`, each task is executed twice:

1. **PTC run**: LLM generates Python code → code runs in sandbox → output validated
2. **FC run**: LLM sees task + tool schemas → emits JSON tool calls → framework executes → results fed back → repeat until done → output validated

The harness then computes and reports:
- Per-approach success rates
- Average execution time
- Cost (from token usage estimates)
- Number of LLM calls (FC makes more for multi-step tasks)
- Number of tool calls
- Retries needed

## Full methodology

For detailed taxonomy, metrics, and NeurIPS-compliant reporting, see **[PTC-Bench Guide](../docs/benchmark_guide.md)**.

For expected results and interpretations, see **[RESULTS.md](RESULTS.md)**.
