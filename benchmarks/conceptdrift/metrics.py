"""
Drift-aware metrics for ConceptDriftBench.

Primary metric: adaptation_rate per drift level
Secondary: token cost, iterations, cross-family skill usage, oracle utilisation.
"""

import math
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Lazy import to avoid circular deps
def _get_drift_type(key: str):
    from .drift.taxonomy import get_drift_type
    return get_drift_type(key)


@dataclass
class DriftTaskResult:
    """Result of a single ConceptDrift task execution."""
    task_id: str
    family: str
    drift_level: str
    drift_index: int
    prior_task_id: Optional[str]

    success: bool
    execution_time: float
    error: Optional[str] = None

    # Taxonomy (for success_by_drift_category)
    drift_type: str = "none"

    # Skill tracking
    skill_used: bool = False
    skill_adapted: bool = False
    skill_source_task: Optional[str] = None
    oracle_skill_used: bool = False
    cross_family_skill_used: bool = False
    skill_created: bool = False  # New skill was saved this run

    # Adaptation metrics (core scientific claim)
    adaptation_required: bool = False  # Prior skill needed modification
    adaptation_succeeded: bool = False  # Modification worked
    objective_met: bool = True  # Output passed validation

    # LLM cost tracking
    tokens_prompt: int = 0
    tokens_completion: int = 0
    iterations: int = 1
    generated_code: Optional[str] = None

    # Runtime-evolved diagnostics (save / retrieve / use)
    injected_skill_count: Optional[int] = None   # Number of skills in prompt when task ran
    generated_code_references_skills: Optional[bool] = None  # True if code mentions "skills" / "from skills"

    # Structural alignment: mean cosine similarity between retrieved skill pattern embeddings and task prompt.
    # High score (~0.7+) means retrieved skills are structurally aligned; low score means mismatch.
    # Populated only for RUNTIME_EVOLVED_SKILLS and STATIC_LIBRARY (where embeddings are available).
    alignment_score: Optional[float] = None

    # For preseed export (no_skills successful code -> preseed_skills.json)
    task_prompt: Optional[str] = None


@dataclass
class DriftMetrics:
    """Aggregate metrics for a ConceptDrift evaluation run."""
    condition: str
    total_tasks: int = 0
    passed_tasks: int = 0
    pass_rate: float = 0.0
    avg_execution_time: float = 0.0
    total_tokens: int = 0

    # Per drift-level breakdown
    adaptation_by_drift: Dict[str, Dict[str, float]] = field(default_factory=dict)
    success_by_drift: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    success_by_drift_category: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    success_by_family: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # Skill-specific metrics
    skill_reuse_rate: float = 0.0
    oracle_utilisation_rate: float = 0.0
    cross_family_usage_rate: float = 0.0
    avg_iterations: float = 1.0
    token_cost_per_task: float = 0.0

    # Structural alignment (mean of per-task alignment_score where available)
    avg_alignment_score: Optional[float] = None

    # Optional: when aggregating over multiple seeds
    pass_rate_std: Optional[float] = None
    avg_execution_time_std: Optional[float] = None
    num_seeds: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "condition": self.condition,
            "total_tasks": self.total_tasks,
            "passed_tasks": self.passed_tasks,
            "pass_rate": self.pass_rate,
            "avg_execution_time": self.avg_execution_time,
            "total_tokens": self.total_tokens,
            "adaptation_by_drift": self.adaptation_by_drift,
            "success_by_drift": self.success_by_drift,
            "success_by_drift_category": self.success_by_drift_category,
            "success_by_family": self.success_by_family,
            "skill_reuse_rate": self.skill_reuse_rate,
            "oracle_utilisation_rate": self.oracle_utilisation_rate,
            "cross_family_usage_rate": self.cross_family_usage_rate,
            "avg_iterations": self.avg_iterations,
            "token_cost_per_task": self.token_cost_per_task,
        }
        if self.avg_alignment_score is not None:
            d["avg_alignment_score"] = self.avg_alignment_score
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DriftMetrics":
        """Build DriftMetrics from saved JSON metrics payload."""
        return cls(
            condition=d.get("condition", ""),
            total_tasks=d.get("total_tasks", 0),
            passed_tasks=d.get("passed_tasks", 0),
            pass_rate=float(d.get("pass_rate", 0)),
            avg_execution_time=float(d.get("avg_execution_time", 0)),
            total_tokens=int(d.get("total_tokens", 0)),
            adaptation_by_drift=d.get("adaptation_by_drift") or {},
            success_by_drift=d.get("success_by_drift") or {},
            success_by_drift_category=d.get("success_by_drift_category") or {},
            success_by_family=d.get("success_by_family") or {},
            skill_reuse_rate=float(d.get("skill_reuse_rate", 0)),
            oracle_utilisation_rate=float(d.get("oracle_utilisation_rate", 0)),
            cross_family_usage_rate=float(d.get("cross_family_usage_rate", 0)),
            avg_iterations=float(d.get("avg_iterations", 1.0)),
            token_cost_per_task=float(d.get("token_cost_per_task", 0)),
            avg_alignment_score=float(d["avg_alignment_score"]) if d.get("avg_alignment_score") is not None else None,
        )


def compute_drift_metrics(
    results: List[DriftTaskResult],
    condition: str,
) -> DriftMetrics:
    """
    Compute all drift-aware metrics from a list of task results.
    
    The core metric is adaptation_rate per drift level:
        adaptation_rate = tasks_using_prior_skill / total_tasks_at_drift_level
    """
    if not results:
        return DriftMetrics(condition=condition)

    m = DriftMetrics(condition=condition)
    m.total_tasks = len(results)
    m.passed_tasks = sum(1 for r in results if r.success)
    m.pass_rate = m.passed_tasks / m.total_tasks if m.total_tasks else 0.0
    m.avg_execution_time = sum(r.execution_time for r in results) / m.total_tasks
    m.total_tokens = sum(r.tokens_prompt + r.tokens_completion for r in results)
    m.token_cost_per_task = m.total_tokens / m.total_tasks if m.total_tasks else 0.0
    m.avg_iterations = sum(r.iterations for r in results) / m.total_tasks

    # --- Success by drift level ---
    by_drift: Dict[str, List[DriftTaskResult]] = defaultdict(list)
    for r in results:
        by_drift[r.drift_level].append(r)

    for drift, group in by_drift.items():
        total = len(group)
        passed = sum(1 for r in group if r.success)
        adapted = sum(1 for r in group if r.skill_adapted)
        reused = sum(1 for r in group if r.skill_used and not r.skill_adapted)
        new = sum(1 for r in group if not r.skill_used)

        m.success_by_drift[drift] = {
            "total": total,
            "passed": passed,
            "pass_rate": round(passed / total, 4) if total else 0.0,
            "avg_time": round(sum(r.execution_time for r in group) / total, 4),
        }

        m.adaptation_by_drift[drift] = {
            "adapted": round(adapted / total, 4) if total else 0.0,
            "reused": round(reused / total, 4) if total else 0.0,
            "new": round(new / total, 4) if total else 0.0,
            "adaptation_rate": round((adapted + reused) / total, 4) if total else 0.0,
        }

    # --- Success by drift category (structural, interface, semantic, combined) ---
    by_category: Dict[str, List[DriftTaskResult]] = defaultdict(list)
    for r in results:
        dt = _get_drift_type(r.drift_type)
        cat = dt.category if dt else "baseline"
        by_category[cat].append(r)
    for cat, group in by_category.items():
        total = len(group)
        passed = sum(1 for r in group if r.success)
        m.success_by_drift_category[cat] = {
            "total": total,
            "passed": passed,
            "pass_rate": round(passed / total, 4) if total else 0.0,
        }

    # --- Success by family ---
    by_family: Dict[str, List[DriftTaskResult]] = defaultdict(list)
    for r in results:
        by_family[r.family].append(r)

    for fam, group in by_family.items():
        total = len(group)
        passed = sum(1 for r in group if r.success)
        m.success_by_family[fam] = {
            "total": total,
            "passed": passed,
            "pass_rate": round(passed / total, 4) if total else 0.0,
        }

    # --- Alignment score (structural similarity of retrieved skills to task prompt) ---
    scored = [r.alignment_score for r in results if r.alignment_score is not None]
    if scored:
        m.avg_alignment_score = round(sum(scored) / len(scored), 4)

    # --- Skill metrics ---
    skill_users = [r for r in results if r.skill_used]
    m.skill_reuse_rate = len(skill_users) / m.total_tasks if m.total_tasks else 0.0

    oracle_users = [r for r in results if r.oracle_skill_used]
    oracle_eligible = [r for r in results if r.prior_task_id is not None]
    m.oracle_utilisation_rate = (
        len(oracle_users) / len(oracle_eligible) if oracle_eligible else 0.0
    )

    cross_family_users = [r for r in results if r.cross_family_skill_used]
    m.cross_family_usage_rate = (
        len(cross_family_users) / m.total_tasks if m.total_tasks else 0.0
    )

    return m


def comparison_table(
    metrics_by_condition: Dict[str, DriftMetrics],
) -> str:
    """Generate a markdown comparison table across conditions and drift levels."""
    drift_order = ["none", "minor", "moderate", "major"]
    conditions = list(metrics_by_condition.keys())

    lines = ["## ConceptDriftBench Results\n"]

    # Overall pass rates
    lines.append("### Overall Pass Rate\n")
    lines.append("| Condition | Pass Rate | Avg Time | Avg Iterations | Tokens/Task | Align Score |")
    lines.append("|-----------|-----------|----------|----------------|-------------|-------------|")
    for cond in conditions:
        m = metrics_by_condition[cond]
        pr = f"{m.pass_rate:.1%}" + (f" ± {m.pass_rate_std:.1%}" if m.pass_rate_std is not None else "")
        et = f"{m.avg_execution_time:.2f}s" + (f" ± {m.avg_execution_time_std:.2f}s" if m.avg_execution_time_std is not None else "")
        align = f"{m.avg_alignment_score:.3f}" if m.avg_alignment_score is not None else "—"
        lines.append(f"| {cond} | {pr} | {et} | {m.avg_iterations:.1f} | {m.token_cost_per_task:.0f} | {align} |")

    # Pass rate by drift level
    lines.append("\n### Pass Rate by Drift Level\n")
    header = "| Drift Level | " + " | ".join(conditions) + " |"
    sep = "|-------------|" + "|".join(["--------"] * len(conditions)) + "|"
    lines.append(header)
    lines.append(sep)
    for drift in drift_order:
        row = f"| {drift} |"
        for cond in conditions:
            m = metrics_by_condition[cond]
            info = m.success_by_drift.get(drift, {})
            row += f" {info.get('pass_rate', 0):.1%} |"
        lines.append(row)

    # Adaptation rate by drift level
    lines.append("\n### Adaptation Rate by Drift Level\n")
    lines.append(header)
    lines.append(sep)
    for drift in drift_order:
        row = f"| {drift} |"
        for cond in conditions:
            m = metrics_by_condition[cond]
            info = m.adaptation_by_drift.get(drift, {})
            row += f" {info.get('adaptation_rate', 0):.1%} |"
        lines.append(row)

    # Family breakdown
    lines.append("\n### Pass Rate by Family\n")
    families = ["A", "B", "C", "D", "E", "F"]
    header_f = "| Family | " + " | ".join(conditions) + " |"
    lines.append(header_f)
    lines.append(sep)
    for fam in families:
        row = f"| {fam} ({_family_label(fam)}) |"
        for cond in conditions:
            m = metrics_by_condition[cond]
            info = m.success_by_family.get(fam, {})
            row += f" {info.get('pass_rate', 0):.1%} |"
        lines.append(row)

    return "\n".join(lines)


def _cohens_h(p1: float, p2: float) -> float:
    """Effect size for two proportions (Cohen's h). h = 2(arcsin(sqrt(p1)) - arcsin(sqrt(p2)))."""
    return 2.0 * (math.asin(math.sqrt(min(1.0, max(0.0, p1)))) - math.asin(math.sqrt(min(1.0, max(0.0, p2)))))


def significance_report(
    metrics_per_condition_per_seed: Dict[str, List[DriftMetrics]],
    baseline_key: str = "no_skills",
    treatment_key: str = "runtime_evolved",
) -> str:
    """
    Compute paired t-test and Cohen's h for baseline vs treatment across seeds.
    Returns a markdown string for the comparison report.
    """
    baseline_list = metrics_per_condition_per_seed.get(baseline_key)
    treatment_list = metrics_per_condition_per_seed.get(treatment_key)
    if not baseline_list or not treatment_list or len(baseline_list) != len(treatment_list):
        return ""
    n_seeds = len(baseline_list)
    if n_seeds < 2:
        return ""
    baseline_rates = [m.pass_rate for m in baseline_list]
    treatment_rates = [m.pass_rate for m in treatment_list]
    try:
        import scipy.stats
        t_stat, p_value = scipy.stats.ttest_rel(treatment_rates, baseline_rates)
        p_str = f"p = {p_value:.4f}" if p_value >= 0.0001 else "p < 0.0001"
        significant = p_value < 0.05
    except Exception:
        p_str = "(scipy not available)"
        significant = False
    mean_baseline = sum(baseline_rates) / n_seeds
    mean_treatment = sum(treatment_rates) / n_seeds
    h = _cohens_h(mean_treatment, mean_baseline)
    lines = [
        "\n### Statistical significance\n",
        f"**{treatment_key} vs {baseline_key}** (n = {n_seeds} seeds, 30 tasks/seed):",
        f"- Pass rate: {mean_baseline:.1%} → {mean_treatment:.1%} (Δ = {(mean_treatment - mean_baseline):.1%})",
        f"- Paired t-test (across seeds): {p_str}",
        f"- Cohen's h (effect size for proportions): {h:.3f}",
    ]
    if significant:
        lines.append("- **Result:** difference is statistically significant at α = 0.05.")
    else:
        lines.append("- **Result:** difference is not statistically significant at α = 0.05.")
    return "\n".join(lines)


def mcnemar_report_from_results_dir(
    output_dir: Path,
    baseline_key: str = "no_skills",
    treatment_key: str = "runtime_evolved",
) -> str:
    """
    Task-level McNemar's test using per-task results in seed_*/*_results.json.
    Returns markdown string; empty if no seed dirs or missing files.
    """
    import json
    output_dir = Path(output_dir)
    pairs: List[tuple] = []
    for seed_dir in sorted(output_dir.iterdir()):
        if not seed_dir.is_dir() or not seed_dir.name.startswith("seed_"):
            continue
        bl_path = seed_dir / f"{baseline_key}_results.json"
        tr_path = seed_dir / f"{treatment_key}_results.json"
        if not bl_path.exists() or not tr_path.exists():
            continue
        with open(bl_path) as f:
            bl_data = json.load(f)
        with open(tr_path) as f:
            tr_data = json.load(f)
        bl_tasks = {t["task_id"]: t["success"] for t in bl_data.get("tasks", [])}
        tr_tasks = {t["task_id"]: t["success"] for t in tr_data.get("tasks", [])}
        for tid in bl_tasks:
            if tid in tr_tasks:
                pairs.append((bl_tasks[tid], tr_tasks[tid]))
    if not pairs:
        return ""
    a = sum(1 for bl, tr in pairs if bl and tr)
    b = sum(1 for bl, tr in pairs if bl and not tr)
    c = sum(1 for bl, tr in pairs if not bl and tr)
    d = sum(1 for bl, tr in pairs if not bl and not tr)
    n = len(pairs)
    stat = (abs(b - c) - 1) ** 2 / (b + c) if (b + c) else 0.0
    p_value = None
    try:
        import scipy.stats
        if hasattr(scipy.stats, "mcnemar"):
            table = [[a, b], [c, d]]
            res = scipy.stats.mcnemar(table, exact=False, correction=True)
            p_value, stat = res.pvalue, res.statistic
        else:
            # McNemar chi-sq with continuity correction: 1 df, p = 1 - chi2.cdf(stat, 1)
            p_value = 1.0 - scipy.stats.chi2.cdf(stat, 1)
    except Exception:
        if stat and (b + c) > 0:
            try:
                import scipy.stats
                p_value = 1.0 - scipy.stats.chi2.cdf(stat, 1)
            except Exception:
                pass
    bl_pass = a + b
    tr_pass = a + c
    lines = [
        f"\n**Task-level McNemar** (n = {n} task×seed pairs):",
        f"- Contingency: (both pass, baseline-only, treatment-only, both fail) = ({a}, {b}, {c}, {d})",
        f"- Pass rates: {baseline_key} = {bl_pass/n:.1%}, {treatment_key} = {tr_pass/n:.1%} (Δ = {(tr_pass/n - bl_pass/n):.1%})",
        f"- McNemar's test: statistic = {stat:.4f}, p = {p_value:.4f}" if p_value is not None else f"- McNemar chi-sq: statistic = {stat:.4f} (install scipy for p-value)",
    ]
    if p_value is not None:
        lines.append(f"- **Result:** difference is {'statistically significant' if p_value < 0.05 else 'not statistically significant'} at α = 0.05.")
    return "\n".join(lines)


def load_metrics_per_seed_from_results_dir(output_dir: Path) -> Tuple[Dict[str, List[DriftMetrics]], List[int]]:
    """
    Load per-seed, per-condition metrics from existing seed_*/*_results.json.
    Returns (metrics_per_condition_per_seed, seeds) so you can merge with a partial
    rerun or regenerate the report from disk only (--report-only).
    """
    import json
    output_dir = Path(output_dir)
    seed_dirs = sorted(
        [d for d in output_dir.iterdir() if d.is_dir() and d.name.startswith("seed_")],
        key=lambda d: int(d.name.split("_")[1]) if "_" in d.name else 0,
    )
    if not seed_dirs:
        # Flat layout: single-seed run wrote *_results.json directly into output_dir.
        flat_files = list(output_dir.glob("*_results.json"))
        if not flat_files:
            return {}, []
        import json
        condition_keys = [f.stem.replace("_results", "") for f in flat_files]
        metrics: Dict[str, List[DriftMetrics]] = {}
        for f in flat_files:
            key = f.stem.replace("_results", "")
            with open(f) as fh:
                data = json.load(fh)
            m_dict = data.get("metrics", {})
            metrics[key] = [DriftMetrics.from_dict(m_dict) if m_dict else DriftMetrics(condition=key)]
        return metrics, [0]  # seed list = [0] signals single flat run
    seeds = [int(d.name.split("_")[1]) for d in seed_dirs]
    # Discover condition keys from all seed dirs (in case one seed is missing a condition)
    condition_keys = []
    for seed_dir in seed_dirs:
        for f in seed_dir.glob("*_results.json"):
            key = f.stem.replace("_results", "")
            if key not in condition_keys:
                condition_keys.append(key)
    metrics_per_condition_per_seed: Dict[str, List[DriftMetrics]] = {
        k: [] for k in condition_keys
    }
    for key in condition_keys:
        for seed_dir in seed_dirs:
            path = seed_dir / f"{key}_results.json"
            if not path.exists():
                metrics_per_condition_per_seed[key].append(DriftMetrics(condition=key))
                continue
            with open(path) as f:
                data = json.load(f)
            metrics = data.get("metrics", {})
            if metrics:
                metrics_per_condition_per_seed[key].append(DriftMetrics.from_dict(metrics))
            else:
                metrics_per_condition_per_seed[key].append(DriftMetrics(condition=key))
    return metrics_per_condition_per_seed, seeds


def aggregate_metrics_across_seeds(
    metrics_per_condition_per_seed: Dict[str, List[DriftMetrics]],
) -> Dict[str, DriftMetrics]:
    """
    Aggregate metrics across multiple seeds (e.g. for publication-ready mean ± std).
    Each condition has a list of DriftMetrics (one per seed). Returns one DriftMetrics
    per condition with pass_rate = mean, pass_rate_std = std, etc.
    """
    import statistics
    aggregated: Dict[str, DriftMetrics] = {}
    for cond, list_m in metrics_per_condition_per_seed.items():
        if not list_m:
            continue
        m0 = list_m[0]
        agg = DriftMetrics(condition=cond)
        agg.total_tasks = m0.total_tasks  # same across seeds
        agg.passed_tasks = int(statistics.mean(m.passed_tasks for m in list_m))
        pass_rates = [m.pass_rate for m in list_m]
        agg.pass_rate = statistics.mean(pass_rates)
        agg.pass_rate_std = statistics.stdev(pass_rates) if len(list_m) > 1 else None
        agg.num_seeds = len(list_m)
        times = [m.avg_execution_time for m in list_m]
        agg.avg_execution_time = statistics.mean(times)
        agg.avg_execution_time_std = statistics.stdev(times) if len(list_m) > 1 else None
        agg.total_tokens = int(statistics.mean(m.total_tokens for m in list_m))
        agg.avg_iterations = statistics.mean(m.avg_iterations for m in list_m)
        agg.token_cost_per_task = statistics.mean(m.token_cost_per_task for m in list_m)
        agg.skill_reuse_rate = statistics.mean(m.skill_reuse_rate for m in list_m)
        agg.oracle_utilisation_rate = statistics.mean(m.oracle_utilisation_rate for m in list_m)
        agg.cross_family_usage_rate = statistics.mean(m.cross_family_usage_rate for m in list_m)
        align_vals = [m.avg_alignment_score for m in list_m if m.avg_alignment_score is not None]
        if align_vals:
            agg.avg_alignment_score = round(statistics.mean(align_vals), 4)
        # Average nested breakdowns (no std for brevity)
        drift_order = ["none", "minor", "moderate", "major"]
        for drift in drift_order:
            by_drift = [m.success_by_drift.get(drift, {}) for m in list_m]
            if not any(by_drift):
                continue
            agg.success_by_drift[drift] = {
                "total": by_drift[0].get("total", 0),
                "passed": int(statistics.mean(d.get("passed", 0) for d in by_drift)),
                "pass_rate": statistics.mean(d.get("pass_rate", 0) for d in by_drift),
                "avg_time": statistics.mean(d.get("avg_time", 0) for d in by_drift),
            }
            ad = [m.adaptation_by_drift.get(drift, {}) for m in list_m]
            if ad:
                agg.adaptation_by_drift[drift] = {
                    "adaptation_rate": statistics.mean(d.get("adaptation_rate", 0) for d in ad),
                    "adapted": statistics.mean(d.get("adapted", 0) for d in ad),
                    "reused": statistics.mean(d.get("reused", 0) for d in ad),
                    "new": statistics.mean(d.get("new", 0) for d in ad),
                }
        for fam in ["A", "B", "C", "D", "E", "F"]:
            pr_fam = [m.success_by_family.get(fam, {}).get("pass_rate", 0) for m in list_m]
            if any(pr_fam):
                agg.success_by_family[fam] = {
                    "pass_rate": statistics.mean(pr_fam),
                    "total": m0.success_by_family.get(fam, {}).get("total", 0),
                    "passed": int(statistics.mean(m.success_by_family.get(fam, {}).get("passed", 0) for m in list_m)),
                }
        aggregated[cond] = agg
    return aggregated


def _family_label(fam: str) -> str:
    labels = {
        "A": "Stock Analysis",
        "B": "Portfolio Risk",
        "C": "Economic Indicators",
        "D": "GitHub Issues",
        "E": "Fusion",
        "F": "Composition",
    }
    return labels.get(fam, fam)
