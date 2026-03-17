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
    
    # NEW: Benchmark profiles for one-command runs
    run_parser.add_argument("--profile", type=str, default=None,
                           choices=["quick", "standard", "full"],
                           help="Benchmark profile: 'quick' (10 tasks, ~1 min), "
                                "'standard' (30 tasks, ~5 min), 'full' (89 tasks, ~30 min). "
                                "Overrides --categories if specified.")
    
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

    # SKILL_EVOLUTION command
    evo_parser = subparsers.add_parser("skill-evolution", help="Run skill evolution demo showing implicit skill benefits")
    evo_parser.add_argument("--backend", type=str, default="subprocess", 
                           choices=["opensandbox", "subprocess"],
                           help="Backend to run on")
    evo_parser.add_argument("--categories", type=str, 
                           help="Categories to run (default: skill_evolution)")
    evo_parser.add_argument("--output", type=str, help="Save results to file")
    
    # SKILLSBENCH command
    sb_parser = subparsers.add_parser("skillsbench", help="Run SkillsBench 4-condition evaluation")
    sb_parser.add_argument("--backend", type=str, default="opensandbox",
                         choices=["opensandbox", "subprocess"],
                         help="Backend to run on")
    sb_parser.add_argument("--condition", type=str, default="all",
                         choices=["no_skills", "curated", "self_generated", "runtime_evolved", "all"],
                         help="Skill condition to test. 'all' runs all 4 conditions for comparison.")
    sb_parser.add_argument("--categories", type=str,
                         help="Comma-separated task categories (default: all)")
    sb_parser.add_argument("--difficulties", type=str,
                         help="Comma-separated difficulties (easy,medium,hard)")
    sb_parser.add_argument("--limit", type=int, default=30,
                         help="Maximum tasks to run (default: 30 for cost efficiency)")
    sb_parser.add_argument("--runs", type=int, default=5,
                         help="Runs per task per condition (default: 5 for statistical power)")
    sb_parser.add_argument("--output", type=str, required=True,
                         help="Output directory for results and report")
    sb_parser.add_argument("--llm-provider", type=str, default="openai",
                         choices=["openai", "anthropic", "google", "azure_openai"],
                         help="LLM Provider for agent code generation")
    sb_parser.add_argument("--llm-model", type=str, default="gpt-4o",
                         help="LLM Model name (default: gpt-4o)")
    sb_parser.add_argument("--local-skillsbench", type=str,
                         help="Path to local SkillsBench repo clone (optional)")
    sb_parser.add_argument("--fixed-skill-order", action="store_true", default=True,
                         help="Use fixed skill order for runtime-evolved (recommended for NeurIPS)")
    sb_parser.add_argument("--no-fixed-skill-order", action="store_true",
                         help="Disable fixed skill order (skills accumulate naturally)")
    
    # CONCEPTDRIFT command
    cd_parser = subparsers.add_parser("conceptdrift",
                                      help="Run ConceptDriftBench: skill evolution under controlled concept drift")
    cd_parser.add_argument("--backend", type=str, default="subprocess",
                           choices=["opensandbox", "subprocess"],
                           help="Backend to run on (default: subprocess)")
    cd_parser.add_argument("--condition", type=str, default="all",
                           choices=["no_skills", "self_generated", "static_library", "random_skills", "runtime_evolved", "retrieval_naive", "oracle_retrieval", "cross_family", "desc_only", "code_only", "shuffled_desc", "code_named_v2", "code_none", "all"],
                           help="Condition to test ('all' runs the full NeurIPS set: no_skills, self_generated, static_library, retrieval_naive, runtime_evolved, oracle_retrieval)")
    cd_parser.add_argument("--families", type=str, default=None,
                           help="Comma-separated families to run (e.g. A,B). Default: all five")
    cd_parser.add_argument("--limit", type=int, default=None,
                           help="Max tasks per family (e.g. 3 for a quick test)")
    cd_parser.add_argument("--output", type=str, default="results/conceptdrift",
                           help="Output directory for results")
    cd_parser.add_argument("--seed", type=int, default=42,
                           help="Random seed for data generation (default: 42)")
    cd_parser.add_argument("--seeds", type=str, default=None,
                           help="Comma-separated seeds for multi-seed run (e.g. 42,43,44,45,46). Overrides --seed when set.")
    cd_parser.add_argument("--num-seeds", type=int, default=None,
                           help="Number of seeds to run (e.g. 5 => seeds 42..46). Ignored if --seeds is set.")
    cd_parser.add_argument("--source", type=str, default="synthetic",
                           choices=["synthetic", "ds1000", "ds1000_pandas", "ds1000_sklearn", "ds1000_numpy", "bigcode", "humaneval", "spider", "spider2", "spider2_sameschema", "spider2_hard"],
                           help="Task source: synthetic (default), ds1000 (D), ds1000_pandas (D by cluster), bigcode/humaneval (A), spider/... (C)")
    cd_parser.add_argument("--cluster", type=int, default=None, metavar="ID",
                           help="For --source ds1000_pandas: use only tasks from this cluster (0..k-1 from cluster_labels.json)")
    cd_parser.add_argument("--cluster-labels", type=str, default="results/ds1000/cluster_labels.json",
                           help="Path to cluster_labels.json from ds1000_cluster_pandas.py (default: results/ds1000/cluster_labels.json)")
    cd_parser.add_argument("--llm-provider", type=str, default="openai",
                           choices=["openai", "anthropic", "google", "azure_openai", "azure_ai"],
                           help="LLM provider (azure_ai = Azure AI Foundry serverless, e.g. Llama/Phi)")
    cd_parser.add_argument("--llm-model", type=str, default="gpt-4o",
                           help="LLM model name (litellm prefix supported, e.g. 'deepseek/deepseek-chat')")
    cd_parser.add_argument("--llm-base-url", type=str, default=None,
                           help="Custom base URL for OpenAI-compatible endpoints (e.g. Azure AI Foundry, vLLM). Overrides provider routing.")
    cd_parser.add_argument("--llm-api-key", type=str, default=None,
                           help="API key for the LLM provider. Falls back to LLM_API_KEY / OPENAI_API_KEY env vars.")
    cd_parser.add_argument("--check-embed", action="store_true",
                           help="Check if embedding is enabled for pattern-aware retrieval, then exit")
    cd_parser.add_argument("--report-only", action="store_true",
                           help="Regenerate comparison_report.md from existing seed_* dirs (no execution). Use after selective rerun.")
    cd_parser.add_argument("--rerun-stats", type=str, default=None, metavar="DIR",
                           help="Rerun significance report only: load DIR's seed_* results, regenerate comparison_report.md (incl. McNemar p-value). Same as --output DIR --report-only. Requires scipy for p-values.")
    cd_parser.add_argument("--preseed", type=str, default=None, metavar="PATH",
                           help="Path to preseed_skills.json from a prior no_skills run (--export-preseed). Load this library before runtime_evolved/naive so retrieval chooses from 20-30 skills from task T1 (retrieval-quality experiment).")
    cd_parser.add_argument("--export-preseed", type=str, default=None, metavar="DIR",
                           help="When running no_skills, export successful (task_id, generated_code, task_prompt) to DIR/preseed_skills.json (or preseed_skills_seed_N.json per seed). Use as input for a second run with --preseed DIR/preseed_skills.json on a different task set.")
    cd_parser.add_argument("--save-skills-to", type=str, default=None, metavar="DIR",
                           help="Phase 1: after no_skills run, save all successful solutions as a full skill library in DIR/skills/ (with pattern metadata). Use with --condition no_skills. Example: libraries/sql_sameschema_library")
    cd_parser.add_argument("--load-skills-from", type=str, default=None, metavar="DIR",
                           help="Phase 2: load a pre-seeded library from DIR (expects DIR/skills/). No accumulation during run (preseed-only retrieval test). Use with --condition all to compare no_skills vs pattern-aware vs naive.")

    # DEBUG command
    dbg_parser = subparsers.add_parser("debug", help="Debug a single task")
    dbg_parser.add_argument("--task", type=str, required=True, help="Task ID (e.g. compute_001)")
    dbg_parser.add_argument("--backend", type=str, default="opensandbox", help="Backend to run on")
    
    args = parser.parse_args()
    
    if args.command == "debug":
        debug_task(args.task, args.backend)
        return
    
    if args.command == "skillsbench":
        # Enable benchmark mode to bypass security validation (we run in subprocess sandbox)
        os.environ["MCP_BENCHMARK_MODE"] = "1"
        # Suppress litellm "Provider List" and other verbose messages during benchmarks
        os.environ.setdefault("LITELLM_LOG", "ERROR")
        
        # Import SkillsBench modules
        from .skillsbench import SkillsBenchRunner, SkillCondition, SkillsBenchLoader
        from .skillsbench.metrics import SkillMetricsAnalyzer
        from pathlib import Path
        import json
        
        print("="*70)
        print("SkillsBench 4-Condition Evaluation")
        print("="*70)
        print("\nResearch Question:")
        print("Does execution-grounded skill evolution outperform speculation-based")
        print("self-generation on diverse real-world tasks?\n")
        
        # Setup output directory
        output_dir = Path(args.output)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Configure LLM
        llm_config = None
        if args.llm_provider != "none":
            azure_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
            azure_deployment = (
                os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT")
                or os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME")
                or os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME")
            )
            provider = args.llm_provider
            model = args.llm_model
            if azure_endpoint and provider == "openai" and os.environ.get("AZURE_OPENAI_API_KEY"):
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
        
        # Load SkillsBench tasks
        print("Loading SkillsBench tasks...")
        loader = SkillsBenchLoader(
            local_path=args.local_skillsbench,
            use_github_api=True,
        )
        
        categories = args.categories.split(",") if args.categories else None
        difficulties = args.difficulties.split(",") if args.difficulties else None
        
        tasks = loader.load_tasks(
            categories=categories,
            difficulties=difficulties,
            limit=args.limit,
        )
        
        if not tasks:
            print("❌ No tasks loaded. Check SkillsBench access or use --local-skillsbench")
            sys.exit(1)
        
        print(f"✅ Loaded {len(tasks)} tasks")
        print(f"   Categories: {categories or 'all'}")
        print(f"   Difficulties: {difficulties or 'all'}")
        print(f"   Output directory: {output_dir}")
        print(f"   Runs per task: {args.runs}")
        print()
        
        # NEURIPS: Fixed skill order control
        use_fixed_skill_order = args.fixed_skill_order and not args.no_fixed_skill_order
        if use_fixed_skill_order and args.condition == "all" and args.runs > 1:
            print("✅ Using FIXED skill order for runtime-evolved condition")
            print("   (All runs will see the same skill library per task position)")
        
        # Determine which conditions to run
        if args.condition == "all":
            conditions = [
                SkillCondition.NO_SKILLS,
                SkillCondition.CURATED_SKILLS,
                SkillCondition.SELF_GENERATED_SKILLS,
                SkillCondition.RUNTIME_EVOLVED_SKILLS,
            ]
        else:
            condition_map = {
                "no_skills": SkillCondition.NO_SKILLS,
                "curated": SkillCondition.CURATED_SKILLS,
                "self_generated": SkillCondition.SELF_GENERATED_SKILLS,
                "runtime_evolved": SkillCondition.RUNTIME_EVOLVED_SKILLS,
            }
            conditions = [condition_map[args.condition]]
        
        # Run evaluation
        all_results = {}
        
        # NEURIPS: For condition=all with fixed order, use compare_all_conditions
        if args.condition == "all" and use_fixed_skill_order and args.runs > 1:
            print(f"\n{'='*70}")
            print("Running all 4 conditions with controlled comparison")
            print(f"{'='*70}")
            
            runner = SkillsBenchRunner(
                condition=SkillCondition.NO_SKILLS,  # Will be overridden
                backend=args.backend,
                n_runs=args.runs,
                llm_config=llm_config,
            )
            all_results = runner.compare_all_conditions(
                tasks,
                use_fixed_skill_order=True,
            )
            
            # Save results
            for name, result in all_results.items():
                result_file = output_dir / f"{name}_results.json"
                with open(result_file, 'w') as f:
                    json.dump(result.metrics.to_dict(), f, indent=2)
                print(f"💾 {name} results saved")
        else:
            # Standard per-condition execution
            for condition in conditions:
                print(f"\n{'='*70}")
                print(f"Running: {condition.name}")
                print(f"{'='*70}")
                
                runner = SkillsBenchRunner(
                    condition=condition,
                    backend=args.backend,
                    n_runs=args.runs,
                    llm_config=llm_config,
                )
                
                # Pass loader as curated_provider for curated skills condition
                curated_provider = loader if condition == SkillCondition.CURATED_SKILLS else None
                result = runner.run_suite_with_condition(tasks, curated_provider=curated_provider)
                all_results[condition.name.lower()] = result
                
                # Save intermediate results
                result_file = output_dir / f"{condition.name.lower()}_results.json"
                with open(result_file, 'w') as f:
                    json.dump(result.metrics.to_dict(), f, indent=2)
                print(f"\n💾 Results saved to {result_file}")
        
        # Generate comparison report if all conditions were run
        if len(conditions) == 4:
            print(f"\n{'='*70}")
            print("Generating comparison report...")
            print(f"{'='*70}")
            
            analyzer = SkillMetricsAnalyzer()
            report = analyzer.generate_comparison_report(
                no_skills_metrics=all_results["no_skills"].metrics,
                curated_metrics=all_results["curated_skills"].metrics,
                self_gen_metrics=all_results["self_generated_skills"].metrics,
                runtime_evolved_metrics=all_results["runtime_evolved_skills"].metrics,
            )
            
            report_file = output_dir / "comparison_report.md"
            with open(report_file, 'w') as f:
                f.write(report)
            print(f"✅ Comparison report saved to {report_file}")
            print("\n" + "="*70)
            print("Summary:")
            print("="*70)
            for name, result in all_results.items():
                m = result.metrics
                print(f"{name:20s}: Pass rate = {m.pass_rate*100:5.1f}%, "
                      f"Time = {m.avg_execution_time:.2f}s")
        
        print(f"\n✅ SkillsBench evaluation complete!")
        print(f"   Results directory: {output_dir}")
        return

    if args.command == "conceptdrift":
        os.environ["MCP_BENCHMARK_MODE"] = "1"
        os.environ.setdefault("LITELLM_LOG", "ERROR")

        from .conceptdrift.runner import ConceptDriftRunner, CONCEPTDRIFT_CONDITIONS, _check_embed_enabled
        from .conceptdrift.visualization import generate_all_figures
        from .skillsbench.skill_conditions import SkillCondition
        from pathlib import Path as _CDPath
        import json as _cdjson

        # LLM config (needed for --check-embed and for run)
        llm_config = None
        azure_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
        azure_deployment = (
            os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT")
            or os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME")
            or os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME")
        )
        provider = args.llm_provider
        model = args.llm_model
        # --llm-base-url: custom OpenAI-compatible endpoint (Azure AI Foundry, vLLM, etc.)
        # When set, skip Azure auto-detection and use openai provider with custom base_url
        custom_base_url = getattr(args, "llm_base_url", None) or os.environ.get("LLM_BASE_URL")
        custom_api_key = (
            getattr(args, "llm_api_key", None)
            or os.environ.get("LLM_API_KEY")
            or os.environ.get("AZURE_OPENAI_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
        )
        # Whether --llm-model was explicitly provided (not just the default)
        explicit_model = args.llm_model != "gpt-4o"  # default is gpt-4o
        azure_ai_endpoint = os.environ.get("AZURE_AI_ENDPOINT")
        if not custom_base_url:
            if provider == "azure_ai":
                # Azure AI Foundry: use AZURE_AI_ENDPOINT (set in .env)
                custom_base_url = azure_ai_endpoint or custom_base_url
            elif azure_endpoint and provider == "openai" and os.environ.get("AZURE_OPENAI_API_KEY"):
                provider = "azure_openai"
                # Only fall back to env deployment name if user didn't specify a model
                if not explicit_model:
                    model = azure_deployment or model
        # Deployment name: explicit --llm-model always wins over env var
        effective_deployment = model if (explicit_model or not azure_deployment) else azure_deployment
        llm_config = LLMConfig(
            provider=provider,
            model=model,
            enabled=True,
            api_key=custom_api_key,
            base_url=custom_base_url,
            azure_endpoint=azure_endpoint if not custom_base_url and provider == "azure_openai" else None,
            azure_deployment_name=effective_deployment if provider == "azure_openai" else None,
            azure_api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-12-01-preview") if provider == "azure_openai" else None,
        )

        if getattr(args, "check_embed", False):
            if getattr(llm_config, "provider", None) == "azure_openai":
                ep = getattr(llm_config, "azure_endpoint", None) or os.environ.get("AZURE_OPENAI_ENDPOINT") or os.environ.get("AZURE_API_BASE")
                dep = os.environ.get("AZURE_OPENAI_EMBED_DEPLOYMENT") or os.environ.get("AZURE_OPENAI_EMBEDDING_DEPLOYMENT") or "(default: text-embedding-ada-002)"
                print("Azure embed config: endpoint =", ep)
                print("Azure embed config: deployment =", dep)
            ok, msg = _check_embed_enabled(llm_config)
            print("Embedding check:", msg)
            print("Pattern-aware retrieval:", "enabled" if ok else "disabled (will fall back to all skills)")
            if not ok and getattr(llm_config, "provider", None) == "azure_openai":
                print("Tip: In Azure Portal, open your resource -> Model deployments and use the exact deployment name (e.g. text-embedding-3-small). Set AZURE_OPENAI_EMBED_DEPLOYMENT to that name.")
            return

        print("=" * 70)
        print("ConceptDriftBench: Skill Evolution Under Controlled Concept Drift")
        print("=" * 70)
        print("\nHypothesis: execution-grounded skills outperform from-scratch")
        print("generation specifically under moderate and major drift.\n")

        # Parse conditions
        condition_map = {
            "no_skills": SkillCondition.NO_SKILLS,
            "self_generated": SkillCondition.SELF_GENERATED_SKILLS,
            "static_library": SkillCondition.STATIC_LIBRARY,
            "random_skills": SkillCondition.RANDOM_SKILLS,
            "runtime_evolved": SkillCondition.RUNTIME_EVOLVED_SKILLS,
            "retrieval_naive": SkillCondition.RUNTIME_EVOLVED_NAIVE,
            "oracle_retrieval": SkillCondition.ORACLE_RETRIEVAL,
            # Legacy aliases
            "runtime_evolved_naive": SkillCondition.RUNTIME_EVOLVED_NAIVE,
            "cross_family": SkillCondition.CROSS_FAMILY,
            # Structural priming ablations (Figure 4)
            "desc_only": SkillCondition.DESC_ONLY,
            "code_only": SkillCondition.CODE_ONLY,
            "shuffled_desc": SkillCondition.SHUFFLED_DESC,
            # Anchoring mechanism ablations
            "code_named_v2": SkillCondition.CODE_NAMED_V2,
            "code_none": SkillCondition.CODE_NONE,
        }
        if args.condition == "all":
            conditions = CONCEPTDRIFT_CONDITIONS  # NeurIPS set
        else:
            conditions = [condition_map[args.condition]]

        source = getattr(args, "source", "synthetic")
        families = args.families.split(",") if args.families else None
        if source in ("ds1000_pandas", "ds1000_sklearn", "ds1000_numpy") and not families:
            families = ["D"]

        # Resolve seeds list for multi-seed runs
        seeds = None
        if getattr(args, "seeds", None):
            seeds = [int(s.strip()) for s in args.seeds.split(",") if s.strip()]
        elif getattr(args, "num_seeds", None) and args.num_seeds and args.num_seeds > 1:
            base = getattr(args, "seed", 42)
            seeds = list(range(base, base + args.num_seeds))

        if getattr(args, "rerun_stats", None):
            args.output = args.rerun_stats
            args.report_only = True

        cluster_id = getattr(args, "cluster", None)
        cluster_labels_path = getattr(args, "cluster_labels", None)
        if source == "ds1000_pandas" and cluster_id is None:
            print("Error: --source ds1000_pandas requires --cluster ID (e.g. --cluster 3).")
            return 1
        if source == "ds1000_pandas" and not cluster_labels_path:
            cluster_labels_path = str(_CDPath("results/ds1000/cluster_labels.json"))

        runner = ConceptDriftRunner(
            backend=args.backend,
            llm_config=llm_config,
            output_dir=args.output,
            seed=args.seed,
            source=source,
            cluster_id=cluster_id,
            cluster_labels_path=cluster_labels_path,
            preseed_path=getattr(args, "preseed", None),
            export_preseed_dir=getattr(args, "export_preseed", None),
            save_skills_to=getattr(args, "save_skills_to", None),
            load_skills_from=getattr(args, "load_skills_from", None),
        )

        report_only = getattr(args, "report_only", False)
        all_metrics = runner.run_all_conditions(
            conditions=conditions,
            limit=args.limit,
            families=families,
            report_only=report_only,
            seeds=seeds,
        )

        # Generate figures
        print("\nGenerating figures...")
        figs = generate_all_figures(all_metrics, output_dir=args.output)
        for f in figs:
            print(f"  📊 {f}")

        print(f"\n✅ ConceptDriftBench evaluation complete!")
        print(f"   Results directory: {args.output}")
        return

    if args.command == "skill-evolution":
        # Import here to avoid circular imports
        from .skill_evolution_runner import SkillEvolutionRunner
        
        print("🎓 Skill Evolution Demo")
        print("="*60)
        print("Demonstrates implicit benefits from self-growing skills:\n")
        print("1️⃣  Early tasks create foundational skills")
        print("2️⃣  Later tasks see skills in context and naturally reuse")
        print("3️⃣  Result: Speedup without explicit skill instructions\n")
        
        categories = args.categories.split(",") if args.categories else ["skill_evolution"]
        
        # Load tasks
        runner = BenchmarkRunner(backend=args.backend, n_runs=1)
        tasks = runner.load_tasks(categories=categories)
        
        if not tasks:
            print(f"❌ No tasks found in categories: {categories}")
            print("   Make sure tasks exist in benchmarks/tasks/{category}/")
            sys.exit(1)
        
        print(f"📋 Running {len(tasks)} tasks with skill evolution enabled\n")
        
        # Run with skill evolution
        evo_runner = SkillEvolutionRunner(
            backend=args.backend,
            n_runs=1,
            enable_skill_evolution=True
        )
        
        results, metrics = evo_runner.run_suite_with_evolution(tasks)
        
        # Save if requested
        if getattr(args, "output", None):
            import json
            output_data = {
                "metrics": {
                    "total_tasks": metrics.total_tasks,
                    "skills_created": metrics.skills_created,
                    "skills_reused": metrics.skills_reused,
                    "time_speedup": metrics.time_speedup,
                    "cost_savings": metrics.cost_savings,
                    "llm_call_reduction": metrics.llm_call_reduction,
                },
                "skill_catalog": metrics.skill_catalog,
                "task_results": metrics.task_results
            }
            with open(args.output, 'w') as f:
                json.dump(output_data, f, indent=2)
            print(f"\n💾 Results saved to {args.output}")
        
        return
        
    # Handle benchmark profiles
    profile = getattr(args, "profile", None)
    if profile:
        # Map profile to categories and runs
        if profile == "quick":
            categories = ["compute", "ptc"]
            difficulties = None
            # Override runs to 1 for speed
            if args.runs == 1:  # Only override if user didn't specify
                args.runs = 1
            print(f"🏃 Quick profile: ~10 tasks, ~1 minute")
        elif profile == "standard":
            categories = ["compute", "ptc", "io", "import_heavy"]
            difficulties = None
            if args.runs == 1:
                args.runs = 1
            print(f"🏃 Standard profile: ~30 tasks, ~5 minutes")
        elif profile == "full":
            categories = None  # All categories
            difficulties = None
            if args.runs == 1:
                args.runs = 1
            print(f"🏃 Full profile: ~89 tasks, ~30 minutes")
    else:
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
            from pathlib import Path as _Path
            comparison_report = ReportGenerator.approach_comparison_report(metrics)
            comparison_path = _Path(args.output).parent / "ptc_vs_fc_comparison.md"
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
