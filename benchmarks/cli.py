"""Command Line Interface for the Benchmark Suite."""

import argparse
import os
import sys
import time
from pathlib import Path

# Load .env from project root so benchmark uses same LLM config as app/tests
_benchmark_root = Path(__file__).resolve().parent.parent
try:
    from dotenv import load_dotenv
    _env_path = _benchmark_root / ".env"
    if _env_path.exists():
        load_dotenv(_env_path, override=False)
except ImportError:
    pass

from .runner import BenchmarkRunner
from .metrics import compute_metrics
from .reports import ReportGenerator
from .debug import debug_task
from .opensandbox_server import ensure_opensandbox_server
from config.schema import LLMConfig

def main():
    parser = argparse.ArgumentParser(description="PTC-Bench: The Programmatic Tool Calling Benchmark")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # RUN command
    run_parser = subparsers.add_parser("run", help="Run benchmarks on a single backend")
    run_parser.add_argument("--backend", type=str, required=True, choices=["opensandbox", "subprocess"],
                           help="Backend to run on. OpenSandbox is the recommended backend.")
    run_parser.add_argument("--categories", type=str, help="Comma-separated list of categories (e.g. compute,io)")
    run_parser.add_argument("--difficulties", type=str, help="Comma-separated list of difficulties (e.g. easy,medium)")
    run_parser.add_argument("--tags", type=str, help="Comma-separated list of tags")
    run_parser.add_argument("--runs", type=int, default=1, help="Number of runs per task")
    run_parser.add_argument("--warm", action="store_true", help="Use warm start (reuse sandbox instance)")
    run_parser.add_argument("--output", type=str, help="Save report to file")
    
    # NEW: Approach selection for PTC vs FC comparison
    run_parser.add_argument("--approach", type=str, default="ptc",
                           choices=["ptc", "function_calling", "both"],
                           help="Approach to benchmark: 'ptc' (Programmatic Tool Calling - code in sandbox), "
                                "'function_calling' (traditional JSON tool calls), or 'both' for comparison. Default: ptc")
    
    # LLM Settings (Agent Mode)
    run_parser.add_argument("--llm-provider", type=str, default="openai",
                           choices=["openai", "anthropic", "google", "azure_openai", "none"],
                           help="LLM Provider for agent code generation. Default: openai. Use 'none' for baseline mode (reference code only).")
    run_parser.add_argument("--llm-model", type=str, default="gpt-4o",
                           help="LLM Model name (default: gpt-4o). For Azure, this is the deployment name.")
    run_parser.add_argument("--recursive", action="store_true",
                           help="Enable RLM (Recursive Language Model) for tasks with context_data: use RecursiveAgent and ask_llm. Without this, RLM tasks are skipped in LLM mode.")

    # COMPARE command
    cmp_parser = subparsers.add_parser("compare", help="Compare multiple backends")
    cmp_parser.add_argument("--backends", type=str, required=True, help="Comma-separated list of backends")
    cmp_parser.add_argument("--categories", type=str, help="Comma-separated categories")
    cmp_parser.add_argument("--difficulties", type=str, help="Comma-separated list of difficulties (e.g. easy,medium)")
    cmp_parser.add_argument("--tags", type=str, help="Comma-separated list of tags")
    cmp_parser.add_argument("--runs", type=int, default=1, help="Number of runs per task")
    cmp_parser.add_argument("--format", type=str, default="markdown", choices=["markdown", "csv", "latex"], help="Matrix output format")
    cmp_parser.add_argument("--output", type=str, help="Save report to file")
    
    # LLM Settings (Agent Mode)
    cmp_parser.add_argument("--llm-provider", type=str, default="openai",
                           choices=["openai", "anthropic", "google", "azure_openai", "none"],
                           help="LLM Provider for agent code generation. Default: openai. Use 'none' for baseline mode.")
    cmp_parser.add_argument("--llm-model", type=str, default="gpt-4o",
                           help="LLM Model name (default: gpt-4o).")
    cmp_parser.add_argument("--recursive", action="store_true",
                           help="Enable RLM for tasks with context_data (both control and test).")

    # DEBUG command
    dbg_parser = subparsers.add_parser("debug", help="Debug a single task")
    dbg_parser.add_argument("--task", type=str, required=True, help="Task ID (e.g. compute_001)")
    dbg_parser.add_argument("--backend", type=str, default="opensandbox", help="Backend to run on")
    
    args = parser.parse_args()
    
    if args.command == "debug":
        debug_task(args.task, args.backend)
        return
        
    categories = args.categories.split(",") if args.categories else None
    
    if getattr(args, "difficulties", None):
        difficulties = args.difficulties.split(",")
    else:
        difficulties = None
        
    if getattr(args, "tags", None):
        tags = args.tags.split(",")
    else:
        tags = None
        
    llm_config = None
    if getattr(args, "llm_provider", "none") != "none":
        # Prefer app config from .env (same as tests) so Azure/OpenAI credentials and provider are correct
        provider = args.llm_provider
        model = getattr(args, "llm_model", "gpt-4o")
        azure_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
        # For agent/benchmark use a chat-capable deployment; fall back to generic deployment name
        azure_deployment = (
            os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT")
            or os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME")
            or os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME")
        )
        # Auto-detect Azure when .env has Azure config and user didn't force a different provider
        if azure_endpoint and provider == "openai" and (os.environ.get("OPENAI_API_KEY") or os.environ.get("AZURE_OPENAI_API_KEY")):
            if os.environ.get("AZURE_OPENAI_API_KEY"):
                provider = "azure_openai"
                model = azure_deployment or model
        if provider == "azure_openai" and azure_deployment:
            model = azure_deployment
        llm_config = LLMConfig(
            provider=provider,
            model=model,
            enabled=True,
            api_key=os.environ.get("AZURE_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY"),
            azure_endpoint=azure_endpoint,
            azure_deployment_name=azure_deployment or (model if provider == "azure_openai" else None),
            azure_api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-12-01-preview"),
        )
        
    if args.command == "run":
        if args.backend == "opensandbox":
            if not ensure_opensandbox_server():
                sys.exit(1)
        runner = BenchmarkRunner(
            backend=args.backend,
            n_runs=args.runs,
            cold_start=not args.warm,
            llm_config=llm_config,
            use_rlm=getattr(args, "recursive", False),
            approach=getattr(args, "approach", "ptc"),
        )
        tasks = runner.load_tasks(categories, difficulties, tags)
        
        if not tasks:
            print("No tasks found matching criteria.")
            sys.exit(1)
            
        print(f"Loaded {len(tasks)} tasks.")
        
        start_time = time.time()
        results = runner.run_suite(tasks)
        end_time = time.time()
        
        metrics = compute_metrics(results)
        report = ReportGenerator.markdown_report(metrics, args.backend, results, approach=getattr(args, "approach", "ptc"))
        
        print("\n" + "="*50 + "\n")
        print(report)
        print("\n" + "="*50 + "\n")
        print(f"Total benchmark elapsed time: {end_time - start_time:.2f}s")
        
        if getattr(args, "output", None):
            ReportGenerator.save_report(report, args.output)
            print(f"Report saved to {args.output}")
            
        # If running both approaches, also save a standalone comparison report
        if getattr(args, "approach", "ptc") == "both" and getattr(args, "output", None):
            comparison_report = ReportGenerator.approach_comparison_report(metrics)
            comparison_path = Path(args.output).parent / "ptc_vs_fc_comparison.md"
            ReportGenerator.save_report(comparison_report, str(comparison_path))
            print(f"PTC vs FC comparison saved to {comparison_path}")
            
    elif args.command == "compare":
        # Ensure we have exactly two backends to compare
        backends = [b.strip() for b in args.backends.split(",")]
        if len(backends) != 2:
            print("The --backends argument must contain exactly two comma-separated backends (Control,Test).")
            sys.exit(1)
            
        control_backend, test_backend = backends[0], backends[1]
        
        if control_backend == "opensandbox" or test_backend == "opensandbox":
            if not ensure_opensandbox_server():
                sys.exit(1)
        
        print(f"Comparing {control_backend} (Control) vs {test_backend} (Test)")
        
        # Run Control
        print(f"\n--- Running Control: {control_backend} ---")
        use_rlm = getattr(args, "recursive", False)
        control_runner = BenchmarkRunner(backend=control_backend, n_runs=args.runs, llm_config=llm_config, use_rlm=use_rlm)
        tasks = control_runner.load_tasks(categories, difficulties, tags)
        if not tasks:
            print("No tasks found matching criteria.")
            sys.exit(1)
        control_results = control_runner.run_suite(tasks)
        control_metrics = compute_metrics(control_results)
        
        # Run Test
        print(f"\n--- Running Test: {test_backend} ---")
        test_runner = BenchmarkRunner(backend=test_backend, n_runs=args.runs, llm_config=llm_config, use_rlm=use_rlm)
        test_results = test_runner.run_suite(tasks)
        test_metrics = compute_metrics(test_results)
        
        # Retrieve format preference
        fmt = getattr(args, "format", "markdown")
        
        print("\n" + "="*50 + "\n")
        report = ReportGenerator.comparison_matrix(control_metrics, control_backend, test_metrics, test_backend, format=fmt)
        print(report)
        print("\n" + "="*50 + "\n")
        
        if getattr(args, "output", None):
            ReportGenerator.save_report(report, args.output)
            print(f"Saved to {args.output}")

if __name__ == "__main__":
    main()
