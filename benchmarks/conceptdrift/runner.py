"""
ConceptDrift Runner

Runs 30 ConceptDrift tasks under 4 experimental conditions:
1. NO_SKILLS — baseline, generate code from scratch each time
2. RUNTIME_EVOLVED — accumulate skills as tasks are solved in family order
3. ORACLE_RETRIEVAL — correct prior-task skill provided, agent decides how to use it
4. CROSS_FAMILY — all accumulated skills from every family available

Tasks are always run in family+drift_index order (A1→A6, B1→B6, … E1→E6)
so that skill inheritance chains are respected.
"""

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from benchmarks.tasks.schema import DriftTask, TaskResult
from benchmarks.skillsbench.skill_conditions import SkillCondition, ConditionManager
from benchmarks.skillsbench.runner import SkillsBenchRunner
from .generator import DriftTaskGenerator, get_validator
from .metrics import DriftTaskResult, DriftMetrics, compute_drift_metrics, comparison_table

logger = logging.getLogger(__name__)

# Conditions supported by ConceptDriftBench
CONCEPTDRIFT_CONDITIONS = [
    SkillCondition.NO_SKILLS,
    SkillCondition.RUNTIME_EVOLVED_SKILLS,
    SkillCondition.ORACLE_RETRIEVAL,
    SkillCondition.CROSS_FAMILY,
]

CONDITION_KEYS = {
    SkillCondition.NO_SKILLS: "no_skills",
    SkillCondition.RUNTIME_EVOLVED_SKILLS: "runtime_evolved",
    SkillCondition.ORACLE_RETRIEVAL: "oracle_retrieval",
    SkillCondition.CROSS_FAMILY: "cross_family",
}


class ConceptDriftRunner:
    """
    Orchestrates ConceptDrift evaluation across all conditions.

    Generates tasks, writes input files, runs each condition, collects
    drift-aware metrics, and produces the comparison report + raw JSON.
    """

    def __init__(
        self,
        backend: str = "subprocess",
        llm_config: Any = None,
        workspace_dir: Optional[str] = None,
        output_dir: Optional[str] = None,
        seed: int = 42,
        source: str = "synthetic",
    ):
        self.backend = backend
        self.llm_config = llm_config
        # Align with executor workspace (config uses ./workspace by default)
        if workspace_dir:
            self.workspace_dir = str(Path(workspace_dir).resolve())
        else:
            try:
                from config.loader import load_config
                cfg = load_config(Path(__file__).resolve().parent.parent.parent / "config.yaml")
                self.workspace_dir = str(Path(cfg.execution.workspace_dir).resolve())
            except Exception:
                self.workspace_dir = str(Path("workspace").resolve())
        self.output_dir = Path(output_dir) if output_dir else Path("results/conceptdrift")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.seed = seed
        self.source = source or "synthetic"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_all_conditions(
        self,
        conditions: Optional[List[SkillCondition]] = None,
        limit: Optional[int] = None,
        families: Optional[List[str]] = None,
    ) -> Dict[str, DriftMetrics]:
        """
        Run the full ConceptDrift evaluation.

        Args:
            conditions: Which conditions to run (default: all four).
            limit: Max tasks per family (for quick test runs).
            families: Restrict to certain families (e.g. ["A", "B"]).

        Returns:
            Mapping condition_key -> DriftMetrics.
        """
        conditions = conditions or CONCEPTDRIFT_CONDITIONS

        # --- Generate tasks and data files ---
        gen = DriftTaskGenerator(
            output_dir=str(self.output_dir / "data"),
            seed=self.seed,
            source=self.source,
        )
        tasks = gen.generate()
        gen.write_task_files(tasks)
        gen.write_manifest(tasks)
        logger.info(f"Generated {len(tasks)} tasks, data written to {gen.output_dir}")

        # Filter by family / limit
        if families:
            tasks = [t for t in tasks if t.family in families]
        if limit:
            filtered: List[DriftTask] = []
            seen: Dict[str, int] = {}
            for t in tasks:
                seen.setdefault(t.family, 0)
                if seen[t.family] < limit:
                    filtered.append(t)
                    seen[t.family] += 1
            tasks = filtered

        # Sort by family then drift_index
        tasks.sort(key=lambda t: (t.family, t.drift_index))
        logger.info(f"Running {len(tasks)} tasks across {len(set(t.family for t in tasks))} families")

        all_metrics: Dict[str, DriftMetrics] = {}

        for condition in conditions:
            key = CONDITION_KEYS[condition]
            logger.info(f"\n{'='*70}\n  Condition: {condition.name}\n{'='*70}")
            drift_results = self._run_condition(tasks, condition, gen.output_dir)
            metrics = compute_drift_metrics(drift_results, condition=key)
            all_metrics[key] = metrics

            # Save per-condition results
            self._save_condition_results(key, drift_results, metrics)

        # Save comparison report
        report = comparison_table(all_metrics)
        report_path = self.output_dir / "comparison_report.md"
        report_path.write_text(report)
        logger.info(f"Comparison report saved to {report_path}")

        # Print summary
        self._print_summary(all_metrics)

        return all_metrics

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run_condition(
        self,
        tasks: List[DriftTask],
        condition: SkillCondition,
        data_dir: Path,
    ) -> List[DriftTaskResult]:
        """Run all tasks under a single condition, respecting family order."""
        runner = SkillsBenchRunner(
            condition=_map_condition(condition),
            backend=self.backend,
            llm_config=self.llm_config,
            workspace_dir=self.workspace_dir,
        )
        # Isolate skills: clear any skills from previous conditions so we don't leak.
        runner.skill_manager.clear_all_skills()

        # For ORACLE_RETRIEVAL, we need to pre-load oracle skills after each task completes
        # For CROSS_FAMILY, all skills remain available (same as RUNTIME_EVOLVED but across families)
        # The SkillsBenchRunner already handles RUNTIME_EVOLVED skill accumulation.

        # Track completed-task code so we can inject oracle skills for the next task
        completed_code: Dict[str, str] = {}  # task_id -> generated_code

        results: List[DriftTaskResult] = []

        try:
            from tqdm import tqdm
            iterator = tqdm(tasks, desc=f"{condition.name[:18]:<18}", unit="task",
                            bar_format="{desc} |{bar:20}| {n_fmt}/{total_fmt} "
                                       "[{elapsed}<{remaining}, {rate_fmt}] | {postfix}")
        except ImportError:
            iterator = tasks  # type: ignore[assignment]

        for i, task in enumerate(iterator):
            if hasattr(iterator, "set_postfix"):
                iterator.set_postfix(task=task.id, drift=task.drift_level)

            # --- ORACLE_RETRIEVAL setup ---
            # Save oracle skill as proper skill so agent sees capability, not raw code
            # Use reference_code (ground truth) so oracle is always available even if prior task failed
            if condition == SkillCondition.ORACLE_RETRIEVAL and task.oracle_skill_id:
                # Find the prior task to get its reference code (ground truth)
                prior_task = None
                for t in tasks:
                    if t.id == task.oracle_skill_id:
                        prior_task = t
                        break
                oracle_code = prior_task.reference_code if prior_task else ""
                if oracle_code:
                    # Save with THIS task's ID as the skill name (e.g., oracle_c2 for C2's oracle)
                    # This makes lookup simple: task C2 looks for oracle_c2
                    skill_name = f"oracle_{task.id.lower()}"
                    # Save as proper skill (like runtime-evolved) so get_skill_listing() works
                    skill_name = f"oracle_{task.oracle_skill_id.lower()}"
                    skill_file = runner.skill_manager.skills_dir / f"{skill_name}.py"
                    if skill_file.exists():
                        runner.skill_manager.update_skill(
                            name=skill_name,
                            code=oracle_code,
                            description=f"Oracle skill from {task.oracle_skill_id}",
                            tags=["oracle", task.oracle_skill_id],
                        )
                    else:
                        runner.skill_manager.save_skill(
                            name=skill_name,
                            code=oracle_code,
                            description=f"Oracle skill from {task.oracle_skill_id}",
                            tags=["oracle", task.oracle_skill_id],
                            source_task=task.oracle_skill_id,
                        )
                    # Also set for direct access
                    runner.condition_manager.set_oracle_skill(task.id, oracle_code)
                    runner.condition_manager.set_oracle_skill(task.name, oracle_code)

            # Copy input data files into workspace so the subprocess can find them
            self._stage_input_files(task, data_dir)

            start = time.time()
            try:
                task_result: TaskResult = runner.run_task(task)
                elapsed = time.time() - start

                success = task_result.success
                error = task_result.error or (
                    getattr(task_result, "skip_reason", None) if getattr(task_result, "skipped", False) else None
                )

                generated_code = getattr(task_result, "generated_code", None) or ""

                # Validate with objective function if present
                if task.ground_truth and task.objective_fn_name:
                    validator = get_validator(task.objective_fn_name)
                    if task.objective_fn_name == "ds1000_execution":
                        # DS-1000: validate generated code via test_execution (no answer.json).
                        # Override success with validator result — our execution may fail due to env diff.
                        if generated_code:
                            try:
                                success = validator(generated_code, task.ground_truth)
                                if not success:
                                    error = "DS-1000 validation failed: test_execution did not pass."
                            except Exception as ve:
                                success = False
                                error = f"DS-1000 validation error: {ve}"
                        else:
                            success = False
                            error = "No generated code to validate"
                    elif task.objective_fn_name == "bigcode_execution":
                        # BigCodeBench: validate via unit tests
                        if generated_code:
                            try:
                                success = validator(generated_code, task.ground_truth)
                                if not success:
                                    error = "BigCodeBench validation failed: unit tests did not pass."
                            except Exception as ve:
                                success = False
                                error = f"BigCodeBench validation error: {ve}"
                        else:
                            success = False
                            error = "No generated code to validate"
                    elif task.objective_fn_name == "humaneval_execution":
                        # HumanEval: validate via test execution
                        if generated_code:
                            try:
                                success = validator(generated_code, task.ground_truth)
                                if not success:
                                    error = "HumanEval validation failed: tests did not pass."
                            except Exception as ve:
                                success = False
                                error = f"HumanEval validation error: {ve}"
                        else:
                            success = False
                            error = "No generated code to validate"
                    elif task.objective_fn_name == "spider_sql":
                        # Spider: validate SQL syntax
                        if generated_code:
                            try:
                                success = validator(generated_code, task.ground_truth)
                                if not success:
                                    error = "Spider validation failed: SQL syntax error or invalid query."
                            except Exception as ve:
                                success = False
                                error = f"Spider validation error: {ve}"
                        else:
                            success = False
                            error = "No generated code to validate"
                    elif task.objective_fn_name == "spider2_sql":
                        # Spider 2.0 / BIRD: validate advanced SQL
                        if generated_code:
                            try:
                                success = validator(generated_code, task.ground_truth)
                                if not success:
                                    error = "Spider 2.0 validation failed: SQL execution did not match ground truth."
                                else:
                                    error = None  # Clear any stale error from base validator
                            except Exception as ve:
                                success = False
                                error = f"Spider 2.0 validation error: {ve}"
                        else:
                            success = False
                            error = "No generated code to validate"
                    else:
                        # Standard: validate answer.json
                        if success:
                            answer_path = Path(self.workspace_dir) / "answer.json"
                            if answer_path.exists():
                                try:
                                    output = json.loads(answer_path.read_text())
                                    if not validator(output, task.ground_truth):
                                        success = False
                                        error = "Validation failed: output did not match ground truth."
                                except Exception as ve:
                                    success = False
                                    error = f"Validation error: {ve}"
                            else:
                                success = False
                                error = "answer.json not found in workspace"
                if success and generated_code:
                    completed_code[task.id] = generated_code
                    
                    # Extract runtime skill for successful execution (with validation override)
                    if condition == SkillCondition.RUNTIME_EVOLVED_SKILLS:
                        runner.condition_manager.extract_and_save_runtime_skill(
                            task_id=task.id,
                            code=generated_code,
                            output=task_result.output if 'task_result' in dir() else None,
                            description=task.prompt or f"Skill for {task.name}",
                        )

            except Exception as exc:
                elapsed = time.time() - start
                success = False
                error = str(exc)
                generated_code = ""

            dr = DriftTaskResult(
                task_id=task.id,
                family=task.family,
                drift_level=task.drift_level,
                drift_index=task.drift_index,
                prior_task_id=task.prior_task_id,
                drift_type=getattr(task, "drift_type", "none"),
                success=success,
                execution_time=elapsed,
                error=error,
                skill_used=bool(
                    condition in (SkillCondition.ORACLE_RETRIEVAL, SkillCondition.CROSS_FAMILY)
                    and task.oracle_skill_id
                    and task.oracle_skill_id in completed_code
                ),
                oracle_skill_used=(
                    condition == SkillCondition.ORACLE_RETRIEVAL
                    and task.oracle_skill_id is not None
                    and task.oracle_skill_id in completed_code
                ),
                generated_code=generated_code,
            )
            results.append(dr)

            status = "pass" if success else "FAIL"
            if hasattr(iterator, "set_postfix"):
                iterator.set_postfix(task=task.id, status=status, t=f"{elapsed:.1f}s")
            else:
                logger.info(f"  [{i+1}/{len(tasks)}] {task.id} ({task.drift_level}): {status} ({elapsed:.1f}s)")

        return results

    def _stage_input_files(self, task: DriftTask, data_dir: Path) -> None:
        """Copy task input files from data_dir into the execution workspace."""
        ws = Path(self.workspace_dir)
        ws.mkdir(parents=True, exist_ok=True)

        if not task.input_data:
            return

        # Collect all filenames referenced in input_data
        filenames: List[str] = []
        for key, val in task.input_data.items():
            if isinstance(val, str) and ("." in val) and not val.startswith("/"):
                filenames.append(val)
            elif key in ("file", "file1", "file2", "spy_file",
                         "gdp_file", "cpi_file", "consumption_file",
                         "investment_file", "descriptions_file",
                         "stock_file", "issues_file"):
                filenames.append(val)
        if "files" in task.input_data and isinstance(task.input_data["files"], list):
            filenames.extend(task.input_data["files"])

        for fname in filenames:
            src = data_dir / fname
            dst = ws / fname
            if src.exists() and not dst.exists():
                dst.write_bytes(src.read_bytes())

    def _save_condition_results(
        self,
        key: str,
        results: List[DriftTaskResult],
        metrics: DriftMetrics,
    ) -> None:
        """Persist per-condition results to JSON."""
        path = self.output_dir / f"{key}_results.json"
        payload = {
            "condition": key,
            "metrics": metrics.to_dict(),
            "tasks": [
                {
                    "task_id": r.task_id,
                    "family": r.family,
                    "drift_level": r.drift_level,
                    "drift_index": r.drift_index,
                    "success": r.success,
                    "execution_time": r.execution_time,
                    "error": r.error,
                    "skill_used": r.skill_used,
                    "oracle_skill_used": r.oracle_skill_used,
                }
                for r in results
            ],
        }
        with open(path, "w") as f:
            json.dump(payload, f, indent=2)
        logger.info(f"  Results saved to {path}")

    def _print_summary(self, all_metrics: Dict[str, DriftMetrics]) -> None:
        print("\n" + "=" * 70)
        print("  ConceptDriftBench Summary")
        print("=" * 70)
        for key, m in all_metrics.items():
            print(f"  {key:25s}: Pass rate = {m.pass_rate:.1%}, "
                  f"Avg time = {m.avg_execution_time:.2f}s, "
                  f"Iters = {m.avg_iterations:.1f}")
        print("=" * 70)


def _map_condition(condition: SkillCondition) -> SkillCondition:
    """
    Map ConceptDrift conditions to SkillsBench runner conditions.

    ORACLE_RETRIEVAL and CROSS_FAMILY are handled by ConceptDriftRunner
    on top of the base condition behaviour.
    """
    if condition == SkillCondition.CROSS_FAMILY:
        return SkillCondition.RUNTIME_EVOLVED_SKILLS
    return condition
