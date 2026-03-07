# PTC-Bench: Results & Interpretation Guide

**PTC-Bench: The Programmatic Tool Calling Benchmark**

This document explains how to interpret results from the benchmark comparison of **Programmatic Tool Calling (PTC)** vs **Function Calling (FC)**.

## Running the Comparison

To generate empirical PTC vs FC results:

```bash
# Run both approaches on the same tasks
python -m benchmarks run --backend opensandbox --llm-provider openai --approach both --categories ptc --output results/comparison.md
```

This produces a comparison report with:
- Per-approach success rates
- Execution time (avg and P95)
- Cost estimates (from token usage)
- LLM calls and tool calls
- Retry counts

## Expected Patterns

Based on the benchmark design, here is what we expect to observe:

### Single Tool Tasks

| Metric | Expected FC | Expected PTC | Reason |
|--------|-------------|--------------|--------|
| Success Rate | ~95% | ~92% | Both reliable; FC has less complexity |
| Time | ~1.2s | ~2.1s | FC: 1 LLM call + API; PTC: 1 LLM call + sandbox startup |
| Cost | ~$0.002 | ~$0.003 | PTC has sandbox overhead |
| **Winner** | **FC** | - | FC wins on simple tasks (lower latency) |

### Multi-Tool Tasks (3-5 tools)

| Metric | Expected FC | Expected PTC | Reason |
|--------|-------------|--------------|--------|
| Success Rate | ~70% | ~92% | FC: context loss between steps; PTC: code handles orchestration |
| Time | ~8.5s | ~4.2s | FC: 4 LLM calls × ~2s; PTC: 1 LLM call + execution |
| Cost | ~$0.012 | ~$0.004 | FC: 4 LLM calls; PTC: 1 LLM call |
| **Winner** | - | **PTC** | PTC is 2× faster and 3× cheaper |

### Error Handling Tasks

| Metric | Expected FC | Expected PTC | Reason |
|--------|-------------|--------------|--------|
| Success Rate | ~85% | ~99% | PTC: code handles retries/resilience natively |
| Time | ~12.3s | ~3.1s | FC: multiple LLM reasoning loops for recovery |
| Retries | 4.2 avg | 0 | PTC: retries handled in code, not via LLM |
| **Winner** | - | **PTC** | PTC is 4× faster and more reliable |

## Interpreting Your Results

After running `--approach both`, look for these patterns:

### If PTC wins (higher success + lower time):
- Tasks benefit from code-based orchestration
- Multi-step workflows are faster in code
- Error handling is more robust in code

### If FC wins (higher success + lower time):
- Tasks are simple (single tool)
- Framework overhead is minimal
- LLM reasoning is sufficient

### If mixed results:
- Different task types favor different approaches
- Consider hybrid strategy: FC for simple, PTC for complex

## Reproducing Results

1. **Start OpenSandbox**: `opensandbox-server start`
2. **Run PTC only**: `python -m benchmarks run --backend opensandbox --llm-provider openai --approach ptc`
3. **Run FC only**: `python -m benchmarks run --backend opensandbox --llm-provider openai --approach function_calling`
4. **Run both**: `python -m benchmarks run --backend opensandbox --llm-provider openai --approach both`
5. **Compare specific categories**: Add `--categories ptc` for tool-calling tasks

## Metrics Reported

| Metric | Description |
|--------|-------------|
| **success_rate** | % of tasks where agent output passed validation |
| **avg_time** | Average execution time (including LLM generation) |
| **avg_cost** | Estimated cost from token usage |
| **avg_llm_calls** | Number of LLM calls (FC typically higher) |
| **avg_tool_calls** | Number of tool executions |
| **avg_retries** | Retry/error recovery attempts |

## Full Methodology

For detailed task taxonomy, statistical rigor, and NeurIPS-compliant reporting guidelines, see **[PTC-Bench Guide](../docs/benchmark_guide.md)**.
