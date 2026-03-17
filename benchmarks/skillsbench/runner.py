"""
SkillsBench Runner

Main execution harness for running SkillsBench tasks under all 4 conditions:
1. No skills (baseline)
2. Curated skills (human-written)
3. Self-generated skills (speculation-based)
4. Runtime-evolved skills (execution-grounded)

This runner enables direct empirical comparison to test the hypothesis:
"Execution-grounded skill evolution succeeds where speculation-based
generation fails."

Usage:
    runner = SkillsBenchRunner(
        condition=SkillCondition.RUNTIME_EVOLVED_SKILLS,
        backend="opensandbox",
        llm_config=config.llm,
    )
    results = runner.run_skillsbench_suite(tasks)
"""

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

from ..runner import BenchmarkRunner
from ..tasks.schema import Task, TaskResult
from client.skill_manager import SkillManager
from client.code_generator import CodeGenerator

from .skill_conditions import SkillCondition, ConditionManager, SelfGeneratedSkillFactory
from .metrics import SkillsBenchMetrics, SkillEcosystemMetrics, SkillMetricsAnalyzer

logger = logging.getLogger(__name__)


@dataclass
class ConditionResult:
    """Results from running a single condition."""
    condition: SkillCondition
    task_results: List[TaskResult]
    metrics: SkillsBenchMetrics
    execution_log: List[Dict[str, Any]] = field(default_factory=list)


class SkillsBenchRunner(BenchmarkRunner):
    """
    Extended benchmark runner for SkillsBench 4-condition evaluation.
    
    Key features:
    - Runs tasks under specified skill condition
    - For RUNTIME_EVOLVED: extracts skills from successful executions
    - Tracks skill provenance and reuse
    - Computes ecosystem-level metrics
    """
    
    def __init__(
        self,
        condition: SkillCondition,
        backend: str = "opensandbox",
        n_runs: int = 1,
        cold_start: bool = True,
        llm_config=None,
        workspace_dir: Optional[str] = None,
        enable_skill_evolution: bool = True,
        **kwargs,
    ):
        """
        Initialize SkillsBench runner.
        
        Args:
            condition: Which of the 4 skill conditions to use
            backend: Execution backend (opensandbox, subprocess)
            n_runs: Number of runs per task
            cold_start: Fresh sandbox per task
            llm_config: LLM configuration for code generation
            workspace_dir: Path for skill storage
            enable_skill_evolution: Enable runtime skill extraction
        """
        super().__init__(
            backend=backend,
            n_runs=n_runs,
            cold_start=cold_start,
            llm_config=llm_config,
            **kwargs,
        )
        
        self.condition = condition
        self.enable_skill_evolution = enable_skill_evolution and (
            condition == SkillCondition.RUNTIME_EVOLVED_SKILLS
        )
        
        # Initialize skill infrastructure
        if workspace_dir:
            self.workspace_dir = Path(workspace_dir)
        else:
            self.workspace_dir = Path(self.config.execution.workspace_dir)
        
        self.skill_manager = SkillManager(workspace_dir=str(self.workspace_dir))
        
        # Initialize condition manager
        self.condition_manager = ConditionManager(
            condition=condition,
            skill_manager=self.skill_manager,
            workspace_dir=str(self.workspace_dir),
        )
        
        # Initialize self-generation factory (for condition 3)
        self.skill_factory = SelfGeneratedSkillFactory(
            llm_client=getattr(self, 'code_generator', None),
        )
        
        # Metrics analyzer
        self.metrics_analyzer = SkillMetricsAnalyzer()
        
        # Track execution for skill extraction
        self._last_generated_code: Optional[str] = None
        self._last_execution_output: Optional[Any] = None
        
        logger.info(f"SkillsBenchRunner initialized: condition={condition.name}")
        logger.info(f"  Skill evolution enabled: {self.enable_skill_evolution}")
    
    def _setup_self_generated_skills(self, tasks: List[Task]) -> None:
        """
        Pre-generate skills for SELF_GENERATED_SKILLS condition.
        
        This simulates SkillsBench's self-generation condition where skills
        are created BEFORE task execution (speculation-based).
        """
        if self.condition != SkillCondition.SELF_GENERATED_SKILLS:
            return
        
        logger.info("Generating self-generated skills (speculation-based)...")
        
        for task in tasks:
            # Generate skill before execution (speculative)
            skill_code = self.skill_factory.generate_skill_for_task(
                task_description=task.prompt or "",
                task_category=task.category,
            )
            
            if skill_code:
                self.condition_manager.set_self_generated_skill(
                    task_id=task.id,
                    skill_content=skill_code,
                )
                logger.info(f"  Generated skill for {task.id}")
            else:
                logger.warning(f"  Failed to generate skill for {task.id}")
    
    def _setup_curated_skills(self, tasks: List[Task], curated_provider) -> None:
        """
        Load curated skills for CURATED_SKILLS condition.
        
        Args:
            tasks: List of tasks
            curated_provider: Callable(task_id) -> skill_content or Loader
        """
        if self.condition != SkillCondition.CURATED_SKILLS:
            return
        
        logger.info("Loading curated skills...")
        
        loaded_count = 0
        for task in tasks:
            # Use task.name (e.g. "3d-scan-calc") for lookup: SkillsBench paths and
            # condition_manager lookup in run_task both use the original task name.
            task_key = task.name
            skill_content = None
            if callable(curated_provider):
                skill_content = curated_provider(task_key)
            elif hasattr(curated_provider, 'get_skill_context'):
                skill_content = curated_provider.get_skill_context(task_key)
            
            if skill_content:
                self.condition_manager.set_curated_skill(
                    task_id=task_key,
                    skill_content=skill_content,
                )
                loaded_count += 1
                logger.info(f"  Loaded curated skill for {task.id} ({task_key})")
            else:
                logger.warning(f"  No curated skill found for {task.id} ({task_key})")
        
        logger.info(f"Loaded {loaded_count}/{len(tasks)} curated skills")
    
    def run_task(self, task: Task) -> TaskResult:
        """
        Run a single task under the current skill condition.
        
        Overrides parent run_task to inject skill context and extract
        runtime skills after successful execution.
        """
        # Get skill context for the current condition
        # Use task.name (original ID like "3d-scan-calc") not task.id (transformed like "3D_SCAN_CALC")
        # Pass task_description for pattern-aware retrieval (RUNTIME_EVOLVED / CROSS_FAMILY)
        task_description = getattr(task, "prompt", None) or getattr(task, "description", None)
        if self.condition in (SkillCondition.RUNTIME_EVOLVED_SKILLS, SkillCondition.CROSS_FAMILY) and not task_description:
            logger.warning("[RUNTIME_DIAG] Task %s: task_description is None — pattern-aware retrieval may fall back to all skills", task.id)
        skill_context = self.condition_manager.get_skill_context(task.name, task_description=task_description)
        
        # DEBUG: Log skill context availability
        if self.condition != SkillCondition.NO_SKILLS:
            ctx_preview = skill_context[:200] if skill_context else "(empty)"
            has_skills = len(skill_context) > 0 if skill_context else False
            logger.info(f"[{self.condition.name}] Task {task.id}: has_skills={has_skills}, context_len={len(skill_context) if skill_context else 0}")
            if skill_context:
                logger.info(f"  Context preview: {ctx_preview!r}...")
        
        # Inject skill context into task prompt
        original_prompt = task.prompt
        if skill_context and task.prompt:
            task.prompt = task.prompt + "\n" + skill_context
            logger.info(f"  -> Injected skill context (prompt now {len(task.prompt)} chars)")
        
        # Subprocess backend: SkillsBench tasks often assume /root; inject workspace root
        # so generated code writes to the actual cwd and does not use /root.
        if self.backend == "subprocess" and task.prompt:
            root = self._benchmark_project_root()
            workspace_abs = (root / self.config.execution.workspace_dir.lstrip("./")).resolve()
            path_note = (
                f"\n\n[Execution: subprocess. Write all output files (e.g. answer.json, reports, CSVs) "
                f"to the current working directory. Workspace root (use this or '.'): {workspace_abs} "
                f"Do not use /root — it is not available in this environment.]"
            )
            task.prompt = task.prompt + path_note
        
        try:
            # Run task using parent class
            result = super().run_task(task)
            
            # For runtime-evolved condition, extract skill from successful execution
            if (
                result.success 
                and self.condition == SkillCondition.RUNTIME_EVOLVED_SKILLS
                and self.enable_skill_evolution
            ):
                self._extract_runtime_skill(task, result)
            
            # Track skill reuse if applicable
            if result.success and hasattr(result, 'output'):
                self._detect_skill_reuse(task.id, result.output or "")
            
            return result
            
        finally:
            # Restore original prompt
            task.prompt = original_prompt
    
    def _extract_runtime_skill(self, task: Task, result: TaskResult) -> None:
        """
        Extract and save a runtime-evolved skill from successful execution.
        
        This is the key MCPRuntime contribution: skills are created from
        code that has ALREADY BEEN VERIFIED to work.
        """
        # Get the generated code from the result
        code = getattr(result, 'generated_code', None)
        output = result.output
        
        logger.info(f"[_extract_runtime_skill] Task {task.id}: success={result.success}, has_code={code is not None}, code_len={len(code) if code else 0}")
        
        if not code:
            logger.warning(f"  No generated code captured for {task.id} - skill cannot be extracted")
            return
        
        # Extract and save skill
        skill_name = self.condition_manager.extract_and_save_runtime_skill(
            task_id=task.id,
            code=code,
            output=output,
            description=task.prompt or f"Skill for {task.name}",
        )
        
        if skill_name:
            logger.info(f"✅ Extracted runtime skill: {skill_name}")
    
    def _detect_skill_reuse(self, task_id: str, output: str) -> None:
        """Detect and track skill reuse in task output/code."""
        if not self.skill_manager:
            return
        
        # Check for skill imports in the output/code
        skills = self.skill_manager.list_skills()
        
        for skill in skills:
            skill_name = skill['name']
            import_patterns = [
                f"from skills.{skill_name} import",
                f"import skills.{skill_name}",
            ]
            
            for pattern in import_patterns:
                if pattern in output:
                    self.condition_manager.track_skill_reuse(
                        skill_name=skill_name,
                        task_id=task_id,
                        code_snippet=pattern,
                    )
                    break
    
    def run_suite_with_condition(
        self,
        tasks: List[Task],
        curated_provider=None,
        fixed_skill_state: Optional[Dict] = None,
    ) -> ConditionResult:
        """
        Run a full suite of tasks under the current condition.
        
        CRITICAL: For runtime-evolved condition with multiple runs, use fixed_skill_state
        to ensure all runs see the same skill availability per task position.
        
        Args:
            tasks: List of tasks to run
            curated_provider: Provider of curated skills (for CURATED condition)
            fixed_skill_state: Pre-built skill library for fixed-order experiments
            
        Returns:
            ConditionResult with metrics
        """
        logger.info(f"\n{'='*70}")
        logger.info(f"Running SkillsBench with condition: {self.condition.name}")
        logger.info(f"Description: {self.condition_manager.get_condition_description()}")
        logger.info(f"{'='*70}\n")
        
        # CRITICAL FIX: For runtime-evolved with fixed_skill_state, preload skills
        # This ensures all runs see the same skill availability per task
        if self.condition == SkillCondition.RUNTIME_EVOLVED_SKILLS and fixed_skill_state:
            logger.info("Using FIXED skill order: pre-loading skills from prior run")
            self._load_fixed_skill_state(fixed_skill_state)
        
        # Pre-setup for conditions that need it
        if self.condition == SkillCondition.SELF_GENERATED_SKILLS:
            self._setup_self_generated_skills(tasks)
        elif self.condition == SkillCondition.CURATED_SKILLS and curated_provider:
            self._setup_curated_skills(tasks, curated_provider)
        
        # Run all tasks with progress bar
        results = []
        execution_log = []
        
        # Try to import tqdm for progress bar
        try:
            from tqdm import tqdm
            use_tqdm = True
        except ImportError:
            use_tqdm = False
        
        if use_tqdm:
            # Custom format with prominent remaining time estimate
            task_iterator = tqdm(
                tasks,
                desc=f"{self.condition.name[:15]:<15}",
                unit="task",
                bar_format="{desc} |{bar:20}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}] ETA: {remaining} | {postfix}"
            )
        else:
            task_iterator = enumerate(tasks)
        
        for i, task in (enumerate(tasks) if not use_tqdm else enumerate(task_iterator)):
            if not use_tqdm:
                logger.info(f"\n[{i+1}/{len(tasks)}] Task: {task.id} ({task.category})")
            else:
                # Update tqdm postfix with current task info
                task_iterator.set_postfix({"task": task.id, "cat": task.category[:10]})
            
            # Track skills BEFORE this task (for position analysis)
            skills_before = len(self.skill_manager.list_skills()) if self.skill_manager else 0
            
            start_time = time.time()
            result = self.run_task(task)
            elapsed = time.time() - start_time
            
            results.append(result)
            
            # Log execution with position info
            execution_log.append({
                "task_id": task.id,
                "task_position": i + 1,
                "success": result.success,
                "execution_time": elapsed,
                "skills_before": skills_before,
                "skills_after": len(self.skill_manager.list_skills()) if self.skill_manager else 0,
            })
            
            # Status
            status = "✅" if result.success else "❌"
            if use_tqdm:
                task_iterator.set_postfix({"task": task.id, "status": status, "time": f"{elapsed:.1f}s"})
            else:
                logger.info(f"  {status} ({elapsed:.2f}s)")
        
        # Compute metrics
        metrics = self._compute_metrics(results, execution_log)
        
        # Add stratified analysis (early/middle/late)
        self._add_stratified_metrics(metrics, execution_log, len(tasks))
        
        return ConditionResult(
            condition=self.condition,
            task_results=results,
            metrics=metrics,
            execution_log=execution_log,
        )
    
    def _load_fixed_skill_state(self, skill_state: Dict) -> None:
        """Load a pre-built skill library for fixed-order experiments."""
        if not self.skill_manager:
            return
        
        # Clear existing skills
        existing = self.skill_manager.list_skills()
        for skill in existing:
            try:
                self.skill_manager.delete_skill(skill['name'])
            except:
                pass
        
        # Load skills from state
        for skill_name, skill_data in skill_state.get('skills', {}).items():
            try:
                self.skill_manager.save_skill(
                    name=skill_name,
                    code=skill_data['code'],
                    description=skill_data.get('description', ''),
                    tags=skill_data.get('tags', []),
                    source_task=skill_data.get('source_task', ''),
                )
            except Exception as e:
                logger.warning(f"Failed to load skill {skill_name}: {e}")
        
        logger.info(f"Loaded {len(skill_state.get('skills', {}))} skills for fixed-order run")
    
    def _add_stratified_metrics(self, metrics: SkillsBenchMetrics, execution_log: List[Dict], total_tasks: int) -> None:
        """Add early/middle/late stratification to detect ordering effects."""
        if total_tasks < 9:
            return  # Not enough tasks to stratify
        
        third = total_tasks // 3
        early = [r for r in execution_log if r['task_position'] <= third]
        middle = [r for r in execution_log if third < r['task_position'] <= 2*third]
        late = [r for r in execution_log if r['task_position'] > 2*third]
        
        def pass_rate(results):
            passed = sum(1 for r in results if r['success'])
            return passed / len(results) if results else 0
        
        metrics.stratified_pass_rates = {
            'early': pass_rate(early),
            'middle': pass_rate(middle),
            'late': pass_rate(late),
            'early_n': len(early),
            'middle_n': len(middle),
            'late_n': len(late),
        }
        
        # Log stratification
        logger.info(f"\n  Stratified results:")
        logger.info(f"    Early (1-{third}):  {metrics.stratified_pass_rates['early']*100:.1f}% pass")
        logger.info(f"    Middle ({third+1}-{2*third}): {metrics.stratified_pass_rates['middle']*100:.1f}% pass")
        logger.info(f"    Late ({2*third+1}-{total_tasks}): {metrics.stratified_pass_rates['late']*100:.1f}% pass")
    
    def _compute_metrics(
        self,
        results: List[TaskResult],
        execution_log: List[Dict],
    ) -> SkillsBenchMetrics:
        """Compute SkillsBench metrics from results with NEURIPS statistical rigor."""
        if not results:
            return SkillsBenchMetrics(condition=self.condition.name)
        
        # Basic metrics
        passed = sum(1 for r in results if r.success)
        total = len(results)
        pass_rate = passed / total if total > 0 else 0
        
        # NEURIPS: Wilson score interval for 95% CI (better for small samples)
        def wilson_ci(p, n, z=1.96):
            if n == 0:
                return 0, 0
            denominator = 1 + z**2/n
            centre = (p + z**2/(2*n)) / denominator
            half_width = z * ((p*(1-p) + z**2/(4*n))/n)**0.5 / denominator
            return max(0, centre - half_width), min(1, centre + half_width)
        
        ci_low, ci_high = wilson_ci(pass_rate, total)
        
        # NEURIPS: Pass@k metrics (if we have multiple runs per task)
        # For single run: pass@1 = pass_rate, pass@3 = pass_rate
        # For multiple runs: would need task-level grouping
        pass_at_1 = pass_rate  # With 1 run, this is equivalent
        pass_at_3 = pass_rate  # With 1 run, this is equivalent
        
        metrics = SkillsBenchMetrics(
            condition=self.condition.name,
            pass_rate=pass_rate,
            pass_at_1=pass_at_1,
            pass_at_3=pass_at_3,
            pass_rate_ci_low=ci_low,
            pass_rate_ci_high=ci_high,
            n_samples=total,
            avg_execution_time=sum(r.execution_time for r in results) / total,
            avg_cost=sum(getattr(r, 'cost', 0) for r in results) / total,
            avg_retries=sum(getattr(r, 'retries', 0) for r in results) / total,
        )
        
        # Condition-specific metrics
        if self.condition == SkillCondition.CURATED_SKILLS:
            metrics.curated_skills_loaded = self.condition_manager.curated_skill_count()
        elif self.condition == SkillCondition.RUNTIME_EVOLVED_SKILLS:
            metrics.skills_verified = len([
                p for p in self.condition_manager.skill_provenance.values()
                if p.execution_verified
            ])
            
            # Compute ecosystem metrics
            metrics.ecosystem = self.metrics_analyzer.compute_ecosystem_metrics(
                skill_manager=self.skill_manager,
                task_results=execution_log,
            )
            
        elif self.condition == SkillCondition.SELF_GENERATED_SKILLS:
            metrics.skills_speculative = len(self.condition_manager.skill_provenance)
            # Verification rate would require running the skills
            metrics.skill_verification_rate = 0.0  # Unknown without execution
        
        # Store task-level results
        metrics.task_results = [
            {
                "task_id": r.task_id,
                "success": r.success,
                "execution_time": r.execution_time,
                "error": r.error,
            }
            for r in results
        ]
        
        return metrics
    
    def compare_all_conditions(
        self,
        tasks: List[Task],
        curated_provider=None,
        baseline_results: Optional[ConditionResult] = None,
        use_fixed_skill_order: bool = True,
    ) -> Dict[str, ConditionResult]:
        """
        Run all 4 conditions and return comparative results.
        
        NEURIPS FIX: For runtime-evolved condition with multiple runs,
        use_fixed_skill_order=True ensures all runs see the same skill
        availability per task position (controlling for accumulation effects).
        
        Args:
            tasks: Tasks to run
            curated_provider: Provider for curated skills
            baseline_results: Optional pre-computed baseline
            use_fixed_skill_order: If True, runtime-evolved uses fixed skill library
            
        Returns:
            Dictionary mapping condition names to results
        """
        results = {}
        
        # NEURIPS: For fixed skill order, we need to run ONE runtime-evolved first
        # to build the skill library, then use that same library for all conditions
        fixed_skill_state = None
        if use_fixed_skill_order and self.n_runs > 1:
            logger.info("\n" + "="*70)
            logger.info("PRE-RUN: Building fixed skill library for runtime-evolved")
            logger.info("="*70)
            pre_runner = SkillsBenchRunner(
                condition=SkillCondition.RUNTIME_EVOLVED_SKILLS,
                backend=self.backend,
                n_runs=1,  # Just one run to build skills
                llm_config=self.llm_config,
                workspace_dir=str(self.workspace_dir),
            )
            pre_result = pre_runner.run_suite_with_condition(tasks)
            
            # Extract skill state for fixed-order runs
            if pre_runner.skill_manager:
                skills = pre_runner.skill_manager.list_skills()
                fixed_skill_state = {
                    'skills': {
                        s['name']: pre_runner.skill_manager.get_skill(s['name'])
                        for s in skills
                    }
                }
                logger.info(f"Built fixed skill library with {len(skills)} skills")
        
        # Define conditions to run with progress tracking
        condition_specs = [
            ("no_skills", SkillCondition.NO_SKILLS, "No Skills (Baseline)", None),
            ("curated_skills", SkillCondition.CURATED_SKILLS, "Curated Skills", curated_provider),
            ("self_generated_skills", SkillCondition.SELF_GENERATED_SKILLS, "Self-Generated Skills (Speculation)", None),
            ("runtime_evolved_skills", SkillCondition.RUNTIME_EVOLVED_SKILLS, "Runtime-Evolved Skills (MCPRuntime)", None),
        ]
        
        # Try to import tqdm for condition-level progress
        try:
            from tqdm import tqdm
            use_condition_tqdm = True
        except ImportError:
            use_condition_tqdm = False
        
        # Run each condition with optional progress bar
        if use_condition_tqdm:
            condition_iterator = tqdm(
                condition_specs,
                desc="Conditions",
                unit="cond",
                bar_format="{desc} |{bar:15}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}] ETA: {remaining} | {postfix}"
            )
        else:
            condition_iterator = condition_specs
        
        for spec in condition_iterator:
            key, condition, name, provider = spec
            
            if use_condition_tqdm:
                condition_iterator.set_postfix({"condition": name[:20]})
            else:
                logger.info("\n" + "="*70)
                logger.info(f"CONDITION: {name}")
                if key == "runtime_evolved_skills" and use_fixed_skill_order and fixed_skill_state:
                    logger.info("Using FIXED skill order (all runs see same skill library)")
                logger.info("="*70)
            
            # Skip if baseline already provided
            if key == "no_skills" and baseline_results:
                results[key] = baseline_results
                continue
            
            runner = SkillsBenchRunner(
                condition=condition,
                backend=self.backend,
                n_runs=self.n_runs,
                llm_config=self.llm_config,
                workspace_dir=str(self.workspace_dir),
            )
            
            # Run with appropriate provider and skill state
            if key == "runtime_evolved_skills":
                results[key] = runner.run_suite_with_condition(
                    tasks, 
                    curated_provider=provider,
                    fixed_skill_state=fixed_skill_state if use_fixed_skill_order else None
                )
            else:
                results[key] = runner.run_suite_with_condition(tasks, curated_provider=provider)
        
        # Compute deltas and statistical tests
        self._compute_comparison_deltas(results)
        self._compute_statistical_tests(results)
        
        return results
    
    def _compute_comparison_deltas(self, results: Dict[str, ConditionResult]) -> None:
        """Compute delta metrics between conditions."""
        baseline = results.get("no_skills")
        curated = results.get("curated_skills")
        self_gen = results.get("self_generated_skills")
        runtime = results.get("runtime_evolved_skills")
        
        if not baseline or not baseline.metrics:
            return
        
        baseline_rate = baseline.metrics.pass_rate
        
        for key, result in results.items():
            if result.metrics:
                result.metrics.delta_vs_no_skills = (
                    result.metrics.pass_rate - baseline_rate
                ) * 100  # percentage points
        
        # Log comparison
        logger.info("\n" + "="*70)
        logger.info("COMPARISON SUMMARY")
        logger.info("="*70)
        
        for key, result in results.items():
            if result.metrics:
                logger.info(f"{key:20s}: {result.metrics.pass_rate*100:5.1f}% "
                          f"(Δ={result.metrics.delta_vs_no_skills:+.1f}pp)")
    
    def _compute_statistical_tests(self, results: Dict[str, ConditionResult]) -> None:
        """Compute statistical significance between conditions (NEURIPS)."""
        import math
        
        runtime = results.get("runtime_evolved_skills")
        self_gen = results.get("self_generated_skills")
        
        if not runtime or not self_gen:
            return
        
        if not runtime.metrics or not self_gen.metrics:
            return
        
        # Two-proportion z-test for runtime-evolved vs self-generated
        # H0: p_runtime = p_self_gen
        # H1: p_runtime > p_self_gen (one-sided)
        
        p1 = runtime.metrics.pass_rate
        n1 = runtime.metrics.n_samples
        p2 = self_gen.metrics.pass_rate
        n2 = self_gen.metrics.n_samples
        
        if n1 == 0 or n2 == 0:
            return
        
        # Pooled proportion
        p_pooled = (p1 * n1 + p2 * n2) / (n1 + n2)
        
        # Standard error
        se = math.sqrt(p_pooled * (1 - p_pooled) * (1/n1 + 1/n2))
        
        if se == 0:
            return
        
        # Z-score
        z = (p1 - p2) / se
        
        # P-value (one-sided)
        # For z > 0: p = 1 - CDF(z)
        # Approximation: p ≈ exp(-0.717*z - 0.416*z^2) for z > 0
        if z > 0:
            p_value = math.exp(-0.717 * z - 0.416 * z * z)
        else:
            p_value = 1.0
        
        # Cohen's h (effect size)
        # h = 2 * (arcsin(sqrt(p1)) - arcsin(sqrt(p2)))
        h = 2 * (math.asin(math.sqrt(p1)) - math.asin(math.sqrt(p2)))
        
        runtime.metrics.p_value_vs_self_generated = p_value
        runtime.metrics.effect_size_vs_self_generated = h
        
        logger.info("\n" + "="*70)
        logger.info("STATISTICAL TESTS (Runtime-Evolved vs Self-Generated)")
        logger.info("="*70)
        logger.info(f"Pass rate difference: {(p1-p2)*100:+.1f} pp")
        logger.info(f"Z-score: {z:.3f}")
        logger.info(f"P-value (one-sided): {p_value:.4f}")
        logger.info(f"Cohen's h (effect size): {h:.3f}")
        if p_value < 0.05:
            logger.info("Result: STATISTICALLY SIGNIFICANT (p < 0.05)")
        elif p_value < 0.10:
            logger.info("Result: MARGINALLY SIGNIFICANT (p < 0.10)")
        else:
            logger.info("Result: NOT SIGNIFICANT (p >= 0.10)")


def run_skillsbench_comparison(
    tasks: List[Task],
    backend: str = "opensandbox",
    llm_config=None,
    output_path: Optional[str] = None,
) -> Dict[str, ConditionResult]:
    """
    Convenience function to run full 4-condition SkillsBench comparison.
    
    Args:
        tasks: SkillsBench tasks to evaluate
        backend: Execution backend
        llm_config: LLM configuration
        output_path: Optional path to save results
        
    Returns:
        Results for all 4 conditions
    """
    runner = SkillsBenchRunner(
        condition=SkillCondition.NO_SKILLS,  # Will be overridden
        backend=backend,
        llm_config=llm_config,
    )
    
    results = runner.compare_all_conditions(tasks)
    
    # Generate report
    if output_path:
        analyzer = SkillMetricsAnalyzer()
        report = analyzer.generate_comparison_report(
            no_skills_metrics=results["no_skills"].metrics,
            curated_metrics=results["curated"].metrics,
            self_gen_metrics=results["self_generated"].metrics,
            runtime_evolved_metrics=results["runtime_evolved"].metrics,
        )
        
        Path(output_path).write_text(report)
        logger.info(f"Report saved to: {output_path}")
    
    return results
