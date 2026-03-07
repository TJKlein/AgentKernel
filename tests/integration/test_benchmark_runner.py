"""Integration tests for the benchmark runner using OpenSandbox."""

import os
import pytest
from benchmarks.runner import BenchmarkRunner

def test_runner_load_tasks():
    # PTC-Bench: single category "ptc" with 60 tasks
    runner = BenchmarkRunner(backend="opensandbox", n_runs=1)
    tasks = runner.load_tasks(categories=["ptc"])

    assert len(tasks) == 60
    assert all(t.category == "ptc" for t in tasks)

def test_runner_execution_flow():
    pytest.importorskip("opensandbox", reason="opensandbox required for execution flow test")
    runner = BenchmarkRunner(backend="opensandbox", n_runs=2, cold_start=False)

    tasks = runner.load_tasks(categories=["ptc"])
    task = next((t for t in tasks if t.id == "PTC01"), None)  # Calculator: Basic addition
    assert task is not None

    # With n_runs=2, run_suite returns 1 result per run (so 2 total for 1 task)
    results = runner.run_suite([task])

    assert len(results) == 2  # 1 task × 2 runs

    # Both results should be for the same task
    assert all(r.task_id == task.id for r in results)

    # All runs should have non-negative execution time (structure check)
    for res in results:
        assert res.execution_time >= 0

def test_runner_skips_unsupported_backend():
    # PTC tasks support both opensandbox and subprocess; test that task runs (no skip)
    runner = BenchmarkRunner(backend="subprocess", n_runs=1)
    tasks = runner.load_tasks(categories=["ptc"])

    task = next(t for t in tasks if t.id == "PTC01")

    result = runner.run_task(task)
    # Task should run, not be skipped (since subprocess is supported)
    assert result.skipped is False
    assert result.success is True
