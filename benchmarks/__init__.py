"""
PTC-Bench: The Programmatic Tool Calling Benchmark

The first systematic benchmark comparing Programmatic Tool Calling (PTC) 
vs traditional Function Calling (FC) for AI agents.
"""

# Re-export key components
from .tasks.schema import Task, TaskResult, BenchmarkMetrics

__version__ = "0.1.0"
__all__ = ["Task", "TaskResult", "BenchmarkMetrics"]
