# PTC-Bench: The Programmatic Tool Calling Benchmark

**PTC-Bench** is the first systematic benchmark comparing **Programmatic Tool Calling (PTC)** — where agents generate code that imports and calls tools — vs traditional **Function Calling (FC)** — where agents emit JSON tool calls.

> **Research Question:** When should AI agents use Programmatic Tool Calling (code-first) vs traditional Function Calling (JSON-first)? We provide empirical answers.

## What PTC-Bench Evaluates

Unlike traditional benchmarks that test pre-written reference code, PTC-Bench tests the **complete agent loop** for both paradigms:

**PTC Mode:**
```
Natural Language Task → LLM Generates Code → Runtime Executes (Sandbox) → Validator Checks
         ↑                                    ↓              ↓
    (Agent reasoning)              (Execution speed)    (Correctness)
```

**FC Mode:**
```
Natural Language Task → LLM Emits JSON Tool Call → Framework Executes Tool → Result → (repeat) → Validator Checks
         ↑                                                              ↓
    (Agent reasoning per step)                                   (Multiple LLM rounds)
```

This provides actionable insights for:
- **Agent developers**: Which paradigm should I use for my workload?
- **Tool authors**: How should I expose my tools (code libraries vs JSON APIs)?
- **Researchers**: When is code-first better than JSON-first? What are the tradeoffs?

## Why PTC-Bench is Different

| Benchmark Type | Measures | Example |
|----------------|----------|---------|
| **Code Execution** (e.g., E2B) | Speed of running given code | "How fast does this function run?" |
| **Agent Capability** (e.g., SWE-bench) | LLM reasoning quality | "Can the LLM fix this bug?" |
| **ToolBench** | Tool selection | "Can the agent pick the right tool?" |
| **PTC-Bench** (this suite) | **PTC vs FC paradigm comparison** | "Which approach is faster/cheaper/more reliable for this task type?" |

PTC-Bench is unique because it:
1. Tests the **same tasks** with both paradigms for direct comparison
2. Measures **cost and reliability** (retries, LLM calls) not just speed
3. Answers the practical question: "Which approach should I use?"

## Task Taxonomy

Tasks are organized by the runtime characteristics they stress. **All tasks are executable with and without recursion** (with or without `--recursive`). Some tasks **favor RLM**: they have optional context (`context_data_source`); when present, `CONTEXT_DATA` is injected in both modes, and with `--recursive`, `ask_llm` is also available for chunked reasoning.

### 1. **Programmatic Tool Calling (PTC)** (8 tasks)
True PTC tasks where the agent must import and call tools rather than write standalone code:
- Calculator: `call_mcp_tool('calculator', 'add', {...})`
- Weather: `call_mcp_tool('weather', 'get_weather', {...})`
- Filesystem: `call_mcp_tool('filesystem', 'read_file', {...})`
- Database: `call_mcp_tool('database', 'query', {...})`
- Multi-tool: Combining multiple tool calls in one task
- *Agent challenge*: Understanding tool APIs, correct argument passing, composing multiple tools
- *This is true PTC*: Agent writes code that **calls external tools as importable libraries**

### 2. **Compute** (19 tasks)
Standalone algorithmic tasks: FizzBuzz, Fibonacci, sorting, dynamic programming, TSP, FFT, knapsack.
- *Agent challenge*: Generating correct algorithms from natural language descriptions
- *Note*: These test code generation but are **not PTC** - they don't import/call external tools

### 3. **Import-Heavy** (12 tasks)  
Package loading and data processing: pandas, numpy, JSON parsing.
- *Agent challenge*: Using correct library APIs and handling data correctly

### 4. **File I/O** (14 tasks)
Filesystem operations: read, write, directory traversal, temp files. Includes tasks that **favor RLM** (e.g. find ERROR in log, find secret in document) via optional `CONTEXT_DATA`; run with or without `--recursive`.
- *Agent challenge*: Proper file handling, path management, cleanup

### 5. **Memory** (10 tasks)
Allocation patterns: large lists, dictionaries, object creation, copying.
- *Agent challenge*: Efficient data structure choices

### 6. **Concurrency** (10 tasks)
Threading, async/await, multiprocessing, synchronization.
- *Agent challenge*: Correct concurrent programming patterns

### 7. **Enterprise Patterns** (16 tasks)
Real-world workflows: ETL, state machines, circuit breakers, retry logic.
- *Agent challenge*: Understanding patterns and implementing them correctly

## Comparing Approaches

PTC-Bench runs the same tasks with both paradigms to enable direct comparison:

| Approach | Pattern | Execution |
|----------|---------|-----------|
| **PTC** (Programmatic Tool Calling) | LLM generates Python code that imports/calls tools | Code runs in sandbox |
| **FC** (Function Calling) | LLM emits JSON tool calls; framework executes; results fed back | Multiple LLM rounds |

### Running the Comparison

```bash
# Run PTC only (default)
python -m benchmarks run --backend opensandbox --llm-provider openai --approach ptc

# Run Function Calling only
python -m benchmarks run --backend opensandbox --llm-provider openai --approach function_calling

# Run both and compare
python -m benchmarks run --backend opensandbox --llm-provider openai --approach both --output results/comparison.md
```

### Comparison Metrics

When running `--approach both`, the report includes:

| Metric | Description |
|--------|-------------|
| **Success Rate** | % of tasks passed (per approach) |
| **Avg Time** | Execution time including LLM generation |
| **Avg Cost** | Estimated from token usage |
| **LLM Calls** | Number of LLM calls (FC typically higher for multi-step) |
| **Tool Calls** | Number of tool executions |
| **Retries** | Error recovery attempts |

### Interpreting Results

- **PTC wins**: Code-based orchestration is faster/more reliable for your task type
- **FC wins**: Simplicity and framework overhead favor JSON tool calls
- **Mixed**: Consider hybrid—FC for simple tasks, PTC for complex workflows

See [RESULTS.md](../benchmarks/RESULTS.md) for expected patterns and interpretation guidelines.

### PTC vs Standalone Code: What's the Difference?

| Aspect | PTC Tasks | Compute Tasks |
|--------|-----------|---------------|
| **Code pattern** | `from client.mock_mcp_client import call_mcp_tool` | Standalone functions |
| **External deps** | Yes - calls external tools | No - pure algorithms |
| **Tests** | Tool API understanding, argument passing | Algorithm correctness |
| **Example** | `call_mcp_tool('calculator', 'add', {'a': 10, 'b': 20})` | `def add(a, b): return a + b` |
| **Real PTC?** | ✅ Yes | ❌ No (code execution benchmark) |

## The Agent Evaluation Metrics

For each task, MRBS reports:

| Metric | Meaning | Why It Matters |
|--------|---------|--------------|
| **Success Rate** | % of agent tasks completed correctly | Can the backend support agent workflows? |
| **Time-to-Success (TTS)** | Total time from prompt to valid output | User-perceived agent latency |
| **Iterations** | How many retries needed | Agent robustness on this backend |
| **LLM Generation Time** | Time spent in code generation | Overhead of agent reasoning |
| **Execution Time** | Time spent running generated code | Runtime efficiency |

## Running the Benchmark

### Quick Start (Agent Mode with LLM)

Run with LLM-generated code to measure real-world agent performance:

```bash
# Run with Azure OpenAI (uses .env config)
python -m benchmarks run --backend opensandbox --llm-provider azure_openai

# Run with specific model (recommended for reliable results)
python -m benchmarks run --backend opensandbox --llm-provider azure_openai --llm-model gpt-5.2-chat

# Run specific categories
python -m benchmarks run --backend opensandbox --categories compute,io --llm-provider azure_openai

# Full suite with statistical confidence (N=5 runs per task)
python -m benchmarks run --backend opensandbox --runs 5 --llm-provider azure_openai --output report.md

# Include RLM (infinite-context) tasks: use RecursiveAgent and ask_llm
python -m benchmarks run --backend opensandbox --llm-provider azure_openai --recursive

# RLM tasks only (find-in-log, find-secret-in-doc, etc.)
python -m benchmarks run --backend opensandbox --categories rlm --llm-provider azure_openai --recursive --runs 1
```

**Running the same tasks with vs without `--recursive`:**
- **Without `--recursive`**: All tasks run, including RLM. For RLM tasks the executor injects **only `CONTEXT_DATA`** (no `ask_llm`). The agent can generate code that uses `CONTEXT_DATA` directly (e.g. search in a loop); if it generates code that calls `ask_llm`, that call will fail at runtime.
- **With `--recursive`**: Same RLM tasks run via **RecursiveAgent** with **`CONTEXT_DATA` + `ask_llm`** injected, so the agent can reason over chunks with the LLM.
- You can compare results: run once with `--recursive` and once without to see how the same RLM tasks perform with vs without recursive (chunked) reasoning.

**Note:** With LLM mode, pass rates are typically 80-90% (not 100%) because:
- LLM may generate code with syntax errors
- Output format may not exactly match expected
- Some tasks require specific algorithmic approaches

**Realistic LLM Results (OpenSandbox + gpt-5.2-chat):**

Baseline mode (no LLM) achieves ~100% because it runs hand-written reference code.
With actual LLM code generation, pass rates are lower due to generation variability:

| Difficulty | Pass Rate | Example Tasks |
|------------|-----------|---------------|
| Easy | 90-100% | FizzBuzz, Fibonacci - simple algorithms usually correct |
| Medium | 50-85% | Binary search, Merge sort - occasional logic errors |
| Hard | 60-100% | N-Queens, Sudoku, TSP - complex but often succeed |
| **Overall** | **70-90%** | Depends on model quality and task selection |

**Sample Run (4 representative tasks):**
- Medium (Binary search): ✅ Pass
- Medium (Merge sort): ❌ Fail (50% for medium)
- Hard (Sudoku): ✅ Pass
- Hard (TSP): ✅ Pass (100% for this sample)

Individual task timing: 10-40s per task (includes LLM generation + execution)

### Baseline Mode (Reference Code, No LLM)

For measuring pure runtime speed without LLM overhead:

```bash
# Test OpenSandbox infrastructure (default backend)
python -m benchmarks run --backend opensandbox --llm-provider none
```

This runs pre-written reference code and should achieve ~100% pass rate:
- **OpenSandbox:** ~100% (19/19 tasks) - all categories supported

> **Why 100% in baseline mode?** It's running hand-written correct code, not generating from prompts. Use this to verify infrastructure, then use LLM mode for realistic agent performance testing.

### Expected LLM Mode Pass Rates (Realistic)

When using actual LLM code generation, pass rates are lower due to generation variability:

| Difficulty | Typical Pass Rate | Why |
|------------|-------------------|-----|
| Easy | 80-100% | Simple algorithms, usually correct |
| Medium | 60-85% | More complex, occasional logic errors |
| Hard | 40-75% | Complex algorithms, higher failure rate |
| **Overall** | **65-85%** | Depends on model quality |

Example with `gpt-5.2-chat` on OpenSandbox:
- Easy: 2/2 (100%)
- Medium: 1/2 (50%) 
- Hard: 2/2 (100%)
- **Overall: 5/6 (83%)**

### Which Numbers to Report

**For Research Publications & Model Evaluation:**
Use **LLM Mode** and report:
- Pass rate (e.g., "Our agent achieves 83% on MRBS")
- Breakdown by difficulty (e.g., "Easy: 100%, Medium: 50%, Hard: 100%")
- Average Time-to-Success (e.g., "17s per task including LLM generation")
- Model name (e.g., "gpt-5.2-chat")

**For Backend Performance Comparisons:**
Use **Baseline Mode** and report:
- Execution time per task (e.g., "Docker: 0.4s vs OpenSandbox: 3s")
- Task coverage (e.g., "Docker: 19/19 tasks, OpenSandbox: 19/19 tasks")
- Cold start latency

**Never Report:**
- Baseline mode pass rates as "agent performance" (it's just infrastructure verification)
- 100% LLM pass rates without scrutiny (may indicate task leakage or too-easy tasks)

### Running with LLM (.env)

The benchmark loads `.env` from the project root. Set your API key and (for Azure) endpoint and deployment:

- **OpenAI**: `OPENAI_API_KEY=sk-...`
- **Azure**: `AZURE_OPENAI_API_KEY=...`, `AZURE_OPENAI_ENDPOINT=https://...`, and either `AZURE_OPENAI_CHAT_DEPLOYMENT=gpt-5.2-chat` or `AZURE_OPENAI_DEPLOYMENT_NAME=...`

For agent mode the benchmark prefers `AZURE_OPENAI_CHAT_DEPLOYMENT` when set (chat-capable models work best for code generation). If the LLM fails or returns no executable code, the runner falls back to reference code so the run still produces meaningful results.

### Backend Setup

**OpenSandbox** (Docker via server) - ✅ **Recommended Backend**
1. Install: `pip install opensandbox opensandbox-server`
2. Configure once: `opensandbox-server init-config ~/.sandbox.toml --example docker`
3. **Start Docker Desktop** (or Colima/Rancher Desktop).
4. Run the benchmark - the CLI auto-starts the server:
   ```bash
   python -m benchmarks run --backend opensandbox --categories compute --runs 1 --llm-provider none
   ```
Results: 100% on compute (19/19), ~75% on PTC (6/8) - ~3s per task

**Subprocess** (development only)
```bash
python -m benchmarks run --backend subprocess --categories compute --runs 1 --llm-provider none
```
Results: 100% pass rate - ~0.1s per task (no isolation, host process)

### Compare OpenSandbox vs Subprocess

```bash
# Compare OpenSandbox (production) vs Subprocess (development)
python -m benchmarks compare --backends opensandbox,subprocess --runs 3
```

## Command Options

- `--backend [opensandbox|subprocess]`: Execution environment (OpenSandbox recommended)
- `--categories [list]`: Comma-separated task categories (e.g. `compute`, `rlm`, `ptc`)
- `--runs [int]`: Number of repetitions per task for statistical significance
- `--llm-provider [openai|anthropic|azure_openai|none]`: LLM for agent code generation
- `--recursive`: Enable full RLM (Recursive Language Model) for tasks with `context_data_source`: use RecursiveAgent and inject `ask_llm` in addition to `CONTEXT_DATA`. Without `--recursive`, the same RLM tasks still run but only `CONTEXT_DATA` is injected (no `ask_llm`), so you can compare pass rates with and without recursive reasoning.
- `--llm-model [name]`: Specific model to use
- `--output [file.md]`: Save report to file

## Interpreting Results

### Example: Agent Task Success

```
Backend: opensandbox
- Success Rate: 87% (65/75 tasks passed on first try)
- Avg Time-to-Success: 3.2s
- Avg Iterations: 1.2 (some tasks needed retry)
- Pass Rate Breakdown:
  - compute: 93%
  - import_heavy: 82% (pandas compatibility issues)
  - io: 91%
  - concurrency: 76% (threading limitations)
```

**Insight**: OpenSandbox works well for compute and I/O but struggles with some import-heavy and concurrency tasks—agents using it should expect occasional retries for those categories.

### Example: Runtime Comparison

```
OpenSandbox Performance

| Category | Pass Rate | Avg Time | Notes |
|----------|-----------|----------|-------|
| compute  | 100%      | ~3s      | All 19 tasks pass |
| ptc      | 75%       | ~3s      | True PTC with tool calling |
| io       | 100%      | ~3s      | Full filesystem support |
| import   | 100%      | ~3s      | Package loading works |

**Insight**: OpenSandbox provides reliable sandboxing with full Docker container isolation. All tasks pass, including PTC (Programmatic Tool Calling) tasks that require proper setup file handling.
```

## NeurIPS-Grade Statistical Rigor

MRBS follows benchmarking best practices:

1. **Multiple Runs**: Default N=5 runs per task for variance analysis
2. **Trimmed Means**: Outlier-resistant timing statistics
3. **Confidence Intervals**: Report uncertainty bounds
4. **Cold/Warm Start**: Separate metrics for first-run vs. cached performance
5. **Category Breakdowns**: Per-category success rates reveal workload characteristics

## Supported Backends

| Backend | Type | Best For | Status | Speed | Notes |
|---------|------|----------|--------|-------|-------|
| **OpenSandbox** | Docker (via server) | General benchmarking | ✅ 100% (19/19) | ~3s | **Recommended** - reliable, full PTC support |
| **Subprocess** | Raw host process | Development/debugging | ✅ 100% (19/19) | ~0.2s | No isolation, fastest |

### Recommendation Summary

**Use OpenSandbox** (the default backend):
- 100% pass rate on all tasks
- Full PTC (Programmatic Tool Calling) support
- Reliable setup file handling
- Requires OpenSandbox server running

**Use Subprocess** for development only:
- Fastest possible execution
- No isolation (runs on host)
- Good for quick iteration, not production

## Debugging Failed Tasks

When a task fails in agent mode, use the debug command to see:
- The natural language prompt
- The LLM-generated code
- The execution output and error
- The validation result

```bash
python -m benchmarks debug --task A01 --backend opensandbox
```

## Architecture

MRBS consists of:

- **Task Definitions** (`benchmarks/tasks/`): 75 JSON task files with natural language prompts
- **Runner** (`benchmarks/runner.py`): Agent loop orchestrator
- **Validator** (`benchmarks/validators.py`): Output correctness checking
- **Metrics** (`benchmarks/metrics.py`): Statistical aggregation
- **Reports** (`benchmarks/reports.py`): Human-readable output

## Citation

If you use PTC-Bench in research, please cite:

```bibtex
@software{ptcbench2025,
  title = {PTC-Bench: The Programmatic Tool Calling Benchmark},
  author = {Klein, Tassilo},
  year = {2025},
  url = {https://github.com/TJKlein/mcpruntime}
}
```

## Contributing Tasks

To add a new benchmark task:

1. Create a JSON entry in the appropriate `benchmarks/tasks/{category}/tasks.json`
2. Include:
   - `prompt`: Natural language task description (for agent)
   - `reference_code`: Reference implementation (for baseline)
   - `expected_output` or `custom_validator`: Validation criteria
   - `supported_backends`: Which runtimes can execute this
3. Test with: `python -m benchmarks debug --task YOUR_ID --backend opensandbox`

## License

MIT License - See LICENSE file for details.
