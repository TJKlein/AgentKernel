#!/usr/bin/env python3
"""Benchmark sandbox pooling performance.

Usage:
    OPTIMIZATION_SANDBOX_POOLING=true python3 benchmark_pooling.py -n 5
    OPTIMIZATION_SANDBOX_POOLING=true python3 benchmark_pooling.py -n 10 --example examples/01_basic_tool_call.py
"""

import argparse
import time
import sys
import importlib.util
import statistics
import io
import contextlib
import asyncio
import atexit
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# Available examples
EXAMPLES = {
    "01": ("examples/01_basic_tool_call.py", "Example 1: Basic Tool Call", "Simple"),
    "03": ("examples/03_data_filtering.py", "Example 3: Data Filtering", "Medium"),
    "05": ("examples/05_state_persistence.py", "Example 5: State Persistence", "Complex"),
    "07": ("examples/07_filesystem_operations.py", "Example 7: Filesystem Operations", "Medium"),
    "08": ("examples/08_cross_session_persistence.py", "Example 8: Cross-Session Persistence", "Complex"),
}

def load_and_run_example(example_path, suppress_output=False):
    """Load and run an example, returning execution time.
    
    Args:
        example_path: Path to example file
        suppress_output: If True, suppress stdout/stderr during execution
    """
    spec = importlib.util.spec_from_file_location("example", Path(__file__).parent / example_path)
    example = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(example)
    
    start = time.time()
    
    if suppress_output:
        # Suppress output for cleaner benchmark results
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            example.main()
    else:
        example.main()
    
    elapsed = time.time() - start
    return elapsed

def run_benchmark(example_path, example_name, num_runs, verbose=False, run_number=None, total_runs=None):
    """Run benchmark for a specific example."""
    if run_number is not None:
        print(f"\n{'=' * 70}")
        print(f"BENCHMARK [{run_number}/{total_runs}]: {example_name}")
        print(f"{'=' * 70}")
    else:
        print(f"\n{'=' * 70}")
        print(f"BENCHMARK: {example_name}")
        print(f"{'=' * 70}")
    
    if num_runs > 1:
        print(f"Number of runs: {num_runs}")
    print()
    
    times = []
    
    for i in range(1, num_runs + 1):
        if verbose:
            print(f"Run {i}/{num_runs}...", end=" ", flush=True)
        else:
            print(f"Run {i}/{num_runs}...", end="\r", flush=True)
        
        try:
            # Suppress output in sequence mode unless verbose is requested
            suppress = (run_number is not None) and not verbose
            elapsed = load_and_run_example(example_path, suppress_output=suppress)
            times.append(elapsed)
            
            if verbose:
                print(f"✅ {elapsed:.3f}s")
            else:
                print(f"Run {i}/{num_runs}: {elapsed:.3f}s")
        except Exception as e:
            print(f"\n❌ Run {i} failed: {e}")
            if verbose:
                import traceback
                traceback.print_exc()
    
    print()
    return times

def print_statistics(times, example_name):
    """Print detailed statistics."""
    if len(times) < 2:
        print("⚠️  Need at least 2 runs for meaningful statistics")
        return
    
    first_time = times[0]
    subsequent_times = times[1:]
    
    avg_subsequent = statistics.mean(subsequent_times)
    min_subsequent = min(subsequent_times)
    max_subsequent = max(subsequent_times)
    std_dev = statistics.stdev(subsequent_times) if len(subsequent_times) > 1 else 0
    
    speedup = first_time / avg_subsequent
    improvement = ((first_time - avg_subsequent) / first_time) * 100
    time_saved = first_time - avg_subsequent
    
    print("=" * 70)
    print("BENCHMARK RESULTS")
    print("=" * 70)
    print()
    print(f"First run (pool init):     {first_time:7.3f}s")
    print()
    print("Subsequent executions (pooled):")
    print(f"  Count:                   {len(subsequent_times)}")
    print(f"  Average:                  {avg_subsequent:7.3f}s")
    print(f"  Minimum:                  {min_subsequent:7.3f}s")
    print(f"  Maximum:                  {max_subsequent:7.3f}s")
    print(f"  Std Dev:                  {std_dev:7.3f}s")
    print()
    print("Performance Improvements:")
    print(f"  Speedup factor:           {speedup:7.1f}x faster")
    print(f"  Time saved:               {time_saved:7.3f}s per execution")
    print(f"  Improvement:              {improvement:6.1f}% faster")
    print()
    
    if len(subsequent_times) > 1:
        print("Per-Execution Breakdown:")
        for i, t in enumerate(subsequent_times, 2):
            run_speedup = first_time / t
            print(f"  Run {i}: {t:7.3f}s ({run_speedup:6.1f}x faster)")
        print()
    
    print("=" * 70)
    print("VISUAL COMPARISON")
    print("=" * 70)
    print()
    
    # Visual bar chart (scaled)
    bar_length = 50
    first_bar = "█" * bar_length
    subsequent_bar_length = max(1, int((avg_subsequent / first_time) * bar_length))
    subsequent_bar = "█" * subsequent_bar_length
    
    print(f"First run (pool init):     {first_bar} {first_time:.3f}s")
    print(f"Subsequent runs (pooled):  {subsequent_bar} {avg_subsequent:.3f}s")
    print()
    
    print("=" * 70)
    print("CONCLUSION")
    print("=" * 70)
    print()
    
    if avg_subsequent < 1.0:
        print("✅ Sandbox pooling is working perfectly!")
        print(f"   Subsequent executions are {speedup:.1f}x faster than the first run.")
        print(f"   Execution time reduced from {first_time:.3f}s to ~{avg_subsequent:.3f}s")
        print()
        total_saved = time_saved * len(subsequent_times)
        print(f"   With {len(subsequent_times)} pooled executions, you saved:")
        print(f"   - Total time saved: {total_saved:.1f}s")
        print(f"   - Average per execution: {time_saved:.2f}s")
    else:
        print("⚠️  WARNING: Execution times are high - pooling may not be working")
    print()
    print("=" * 70)

def main():
    parser = argparse.ArgumentParser(
        description="Benchmark sandbox pooling performance",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run default example 5 times
  OPTIMIZATION_SANDBOX_POOLING=true python3 benchmark_pooling.py -n 5
  
  # Run specific example 10 times
  OPTIMIZATION_SANDBOX_POOLING=true python3 benchmark_pooling.py -n 10 --example 01
  
  # Run sequence of different examples (tests pooling across examples)
  OPTIMIZATION_SANDBOX_POOLING=true python3 benchmark_pooling.py --sequence 01,03,07,05
  
  # Run mixed sequence with repeats
  OPTIMIZATION_SANDBOX_POOLING=true python3 benchmark_pooling.py --sequence 01,03,01,07,03
  
  # Run with verbose output
  OPTIMIZATION_SANDBOX_POOLING=true python3 benchmark_pooling.py -n 5 -v
  
  # Run all examples
  OPTIMIZATION_SANDBOX_POOLING=true python3 benchmark_pooling.py -n 3 --all
        """
    )
    
    parser.add_argument(
        "-n", "--num-runs",
        type=int,
        default=5,
        help="Number of runs to execute (default: 5)"
    )
    
    parser.add_argument(
        "-e", "--example",
        choices=list(EXAMPLES.keys()) + ["all"],
        default="01",
        help="Example to run (01, 03, 05, 07, or 'all' for all examples)"
    )
    
    parser.add_argument(
        "-s", "--sequence",
        type=str,
        help="Comma-separated list of examples to run in sequence (e.g., '01,03,07,01')"
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show verbose output during execution"
    )
    
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all examples (same as --example all)"
    )
    
    args = parser.parse_args()
    
    # Check if pooling is enabled
    import os
    pooling_enabled = os.environ.get("OPTIMIZATION_SANDBOX_POOLING", "false").lower() == "true"
    
    if not pooling_enabled:
        print("⚠️  WARNING: OPTIMIZATION_SANDBOX_POOLING is not set to 'true'")
        print("   Set it with: export OPTIMIZATION_SANDBOX_POOLING=true")
        print("   Or run: OPTIMIZATION_SANDBOX_POOLING=true python3 benchmark_pooling.py ...")
        print()
        response = input("Continue anyway? (y/N): ")
        if response.lower() != 'y':
            sys.exit(1)
    
    # Determine which examples to run
    if args.sequence:
        # Parse sequence: "01,03,07,01" -> [(01, ...), (03, ...), (07, ...), (01, ...)]
        sequence_ids = [e.strip() for e in args.sequence.split(",")]
        examples_to_run = []
        for example_id in sequence_ids:
            if example_id not in EXAMPLES:
                print(f"❌ Error: Unknown example '{example_id}'. Available: {', '.join(EXAMPLES.keys())}")
                sys.exit(1)
            examples_to_run.append((example_id, EXAMPLES[example_id]))
        print(f"Running sequence: {', '.join(sequence_ids)}")
    elif args.all or args.example == "all":
        examples_to_run = list(EXAMPLES.items())
    else:
        examples_to_run = [(args.example, EXAMPLES[args.example])]
    
    print("=" * 70)
    print("SANDBOX POOLING BENCHMARK")
    print("=" * 70)
    print()
    print(f"Pooling enabled: {pooling_enabled}")
    print(f"Number of runs per example: {args.num_runs}")
    print(f"Examples to run: {len(examples_to_run)}")
    print()
    
    all_results = {}
    
    # If running a sequence, only run each example once (num_runs applies to sequence, not individual examples)
    if args.sequence:
        print(f"Running sequence of {len(examples_to_run)} examples (pooling test across different examples)")
        if not args.verbose:
            print("(Example output suppressed for cleaner results - use -v to see full output)")
        print()
        
        for idx, (example_id, (example_path, example_name, complexity)) in enumerate(examples_to_run, 1):
            times = run_benchmark(example_path, example_name, 1, args.verbose, idx, len(examples_to_run))
            all_results[f"{example_name} (run {idx})"] = times
        
        # Print sequence statistics
        if len(all_results) >= 2:
            print("\n" + "=" * 70)
            print("SEQUENCE BENCHMARK RESULTS")
            print("=" * 70)
            print()
            
            # Filter out failed runs (empty lists)
            valid_results = {k: v for k, v in all_results.items() if v and len(v) > 0}
            
            if len(valid_results) == 0:
                print("No successful runs to report.")
                return
            
            first_time = list(valid_results.values())[0][0]
            subsequent_times = [times[0] for times in list(valid_results.values())[1:]]
            avg_subsequent = statistics.mean(subsequent_times) if subsequent_times else 0
            
            print("Execution Times by Example:")
            for name, times in valid_results.items():
                elapsed = times[0]
                if elapsed == first_time:
                    print(f"  {name:50s} {elapsed:7.3f}s (first - pool init)")
                else:
                    speedup = first_time / elapsed if elapsed > 0 else 0
                    print(f"  {name:50s} {elapsed:7.3f}s ({speedup:5.1f}x faster)")
            
            print()
            print("Performance Analysis:")
            print(f"  First example (pool init):  {first_time:7.3f}s")
            print(f"  Subsequent examples (avg):  {avg_subsequent:7.3f}s")
            if avg_subsequent > 0:
                speedup = first_time / avg_subsequent
                improvement = ((first_time - avg_subsequent) / first_time) * 100
                print(f"  Speedup:                    {speedup:7.1f}x faster")
                print(f"  Improvement:                {improvement:6.1f}% faster")
                print()
                if avg_subsequent < 1.0:
                    print("✅ SUCCESS: Sandbox pooling works across different examples!")
                    print(f"   All examples shared the same sandbox pool.")
                    print(f"   Average execution time for subsequent examples: {avg_subsequent:.3f}s")
            print("=" * 70)
    else:
        # Original behavior: run same example multiple times
        for example_id, (example_path, example_name, complexity) in examples_to_run:
            times = run_benchmark(example_path, example_name, args.num_runs, args.verbose)
            all_results[example_name] = times
            
            if len(times) >= 2:
                print_statistics(times, example_name)
    
    # Summary if multiple examples
    if len(examples_to_run) > 1:
        print("\n" + "=" * 70)
        print("SUMMARY: All Examples")
        print("=" * 70)
        print()
        
        for example_name, times in all_results.items():
            if len(times) >= 2:
                first = times[0]
                subsequent_avg = statistics.mean(times[1:])
                speedup = first / subsequent_avg
                print(f"{example_name:40s} First: {first:6.2f}s, Pooled: {subsequent_avg:6.3f}s ({speedup:5.1f}x)")
        
        print()
        print("=" * 70)


def cleanup_pool():
    """Cleanup sandbox pool at exit."""
    try:
        from client.sandbox_pool import cleanup_global_pool_sync, _global_pool
        if _global_pool is not None:
            # First try async cleanup if event loop is available
            try:
                loop = asyncio.get_event_loop()
                if not loop.is_closed():
                    # Try to run cleanup in existing loop
                    try:
                        if loop.is_running():
                            # Can't use run_until_complete in running loop
                            # Fall back to sync cleanup
                            cleanup_global_pool_sync()
                        else:
                            loop.run_until_complete(_global_pool.cleanup())
                    except Exception:
                        cleanup_global_pool_sync()
                else:
                    # Loop is closed, use sync cleanup
                    cleanup_global_pool_sync()
            except RuntimeError:
                # No event loop, try to create one for async cleanup
                try:
                    asyncio.run(_global_pool.cleanup())
                except Exception:
                    # If that fails, use sync cleanup
                    cleanup_global_pool_sync()
    except Exception:
        # Silently fail on cleanup errors
        pass

# Register cleanup on exit
atexit.register(cleanup_pool)

if __name__ == "__main__":
    try:
        main()
    finally:
        # Ensure cleanup happens
        cleanup_pool()

