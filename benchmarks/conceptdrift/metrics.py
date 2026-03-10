"""
Drift-aware metrics for ConceptDriftBench.

Primary metric: adaptation_rate per drift level
Secondary: token cost, iterations, cross-family skill usage, oracle utilisation.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

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

    def to_dict(self) -> Dict[str, Any]:
        return {
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
    lines.append("| Condition | Pass Rate | Avg Time | Avg Iterations | Tokens/Task |")
    lines.append("|-----------|-----------|----------|----------------|-------------|")
    for cond in conditions:
        m = metrics_by_condition[cond]
        lines.append(
            f"| {cond} | {m.pass_rate:.1%} | {m.avg_execution_time:.2f}s "
            f"| {m.avg_iterations:.1f} | {m.token_cost_per_task:.0f} |"
        )

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
