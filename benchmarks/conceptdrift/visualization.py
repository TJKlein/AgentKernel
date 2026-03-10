"""
Visualization for ConceptDriftBench results.

Generates the main figure: task success rate vs drift level, one line per condition.
Also produces per-family heatmaps and adaptation-rate bar charts.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DRIFT_ORDER = ["none", "minor", "moderate", "major"]
DRIFT_COLORS = {
    "no_skills": "#2196F3",           # blue
    "runtime_evolved": "#4CAF50",     # green
    "oracle_retrieval": "#FF9800",    # orange
    "cross_family": "#9C27B0",        # purple
}
DRIFT_LABELS = {
    "no_skills": "NO_SKILLS",
    "runtime_evolved": "RUNTIME_EVOLVED",
    "oracle_retrieval": "ORACLE_RETRIEVAL",
    "cross_family": "CROSS_FAMILY",
}


def plot_adaptation_by_drift(
    metrics_by_condition: Dict[str, Any],
    output_path: Optional[str] = None,
    title: str = "ConceptDriftBench: Task Success Rate by Drift Level",
) -> Optional[str]:
    """
    Main figure: X = drift level, Y = pass rate, one line per condition.

    Args:
        metrics_by_condition: {condition_key: DriftMetrics} or dicts with to_dict().
        output_path: Where to save the PNG (default: results/conceptdrift/main_figure.png).
        title: Plot title.

    Returns:
        Path to the saved figure, or None on failure.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        logger.warning("matplotlib not installed — skipping plot generation")
        return None

    output_path = output_path or "results/conceptdrift/main_figure.png"
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(10, 6))

    for cond_key, metrics in metrics_by_condition.items():
        if hasattr(metrics, "success_by_drift"):
            data = metrics.success_by_drift
        elif isinstance(metrics, dict):
            data = metrics.get("success_by_drift", {})
        else:
            continue

        rates = []
        for d in DRIFT_ORDER:
            info = data.get(d, {})
            rates.append(info.get("pass_rate", 0.0) if isinstance(info, dict) else 0.0)

        color = DRIFT_COLORS.get(cond_key, "#607D8B")
        label = DRIFT_LABELS.get(cond_key, cond_key)
        ax.plot(DRIFT_ORDER, rates, marker="o", linewidth=2.5,
                color=color, label=label, markersize=8)

    ax.set_xlabel("Drift Level", fontsize=13)
    ax.set_ylabel("Task Success Rate", fontsize=13)
    ax.set_title(title, fontsize=14, fontweight="bold")
    ax.set_ylim(-0.05, 1.05)
    ax.legend(fontsize=11, loc="lower left")
    ax.grid(True, alpha=0.3)
    ax.tick_params(labelsize=11)

    fig.tight_layout()
    fig.savefig(output_path, dpi=300)
    plt.close(fig)
    logger.info(f"Main figure saved to {output_path}")
    return output_path


def plot_adaptation_rate(
    metrics_by_condition: Dict[str, Any],
    output_path: Optional[str] = None,
) -> Optional[str]:
    """
    Bar chart: adaptation rate per drift level per condition.

    Shows whether the agent reused/adapted a prior skill vs generating from scratch.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        logger.warning("matplotlib/numpy not installed — skipping adaptation rate plot")
        return None

    output_path = output_path or "results/conceptdrift/adaptation_rate.png"
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    conditions = [k for k in metrics_by_condition if k != "no_skills"]
    n_drift = len(DRIFT_ORDER)
    n_cond = len(conditions)
    if n_cond == 0:
        return None

    x = np.arange(n_drift)
    width = 0.8 / n_cond

    fig, ax = plt.subplots(figsize=(10, 6))

    for idx, cond_key in enumerate(conditions):
        metrics = metrics_by_condition[cond_key]
        if hasattr(metrics, "adaptation_by_drift"):
            data = metrics.adaptation_by_drift
        elif isinstance(metrics, dict):
            data = metrics.get("adaptation_by_drift", {})
        else:
            continue

        rates = []
        for d in DRIFT_ORDER:
            info = data.get(d, {})
            rates.append(info.get("adaptation_rate", 0.0) if isinstance(info, dict) else 0.0)

        color = DRIFT_COLORS.get(cond_key, "#607D8B")
        label = DRIFT_LABELS.get(cond_key, cond_key)
        ax.bar(x + idx * width, rates, width, color=color, label=label, alpha=0.85)

    ax.set_xlabel("Drift Level", fontsize=13)
    ax.set_ylabel("Adaptation Rate", fontsize=13)
    ax.set_title("Skill Adaptation Rate by Drift Level", fontsize=14, fontweight="bold")
    ax.set_xticks(x + width * (n_cond - 1) / 2)
    ax.set_xticklabels(DRIFT_ORDER)
    ax.set_ylim(0, 1.1)
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.2, axis="y")

    fig.tight_layout()
    fig.savefig(output_path, dpi=300)
    plt.close(fig)
    logger.info(f"Adaptation rate plot saved to {output_path}")
    return output_path


def plot_family_heatmap(
    metrics_by_condition: Dict[str, Any],
    output_path: Optional[str] = None,
) -> Optional[str]:
    """
    Heatmap: family × condition showing pass rate.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        logger.warning("matplotlib/numpy not installed — skipping heatmap")
        return None

    output_path = output_path or "results/conceptdrift/family_heatmap.png"
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    families = ["A", "B", "C", "D", "E", "F"]
    family_labels = [
        "A: Stock Analysis", "B: Portfolio Risk", "C: Economic",
        "D: GitHub Issues", "E: Fusion", "F: Composition",
    ]
    conditions = list(metrics_by_condition.keys())

    data = np.zeros((len(families), len(conditions)))
    for j, cond_key in enumerate(conditions):
        metrics = metrics_by_condition[cond_key]
        if hasattr(metrics, "success_by_family"):
            fam_data = metrics.success_by_family
        elif isinstance(metrics, dict):
            fam_data = metrics.get("success_by_family", {})
        else:
            continue

        for i, fam in enumerate(families):
            info = fam_data.get(fam, {})
            data[i, j] = info.get("pass_rate", 0.0) if isinstance(info, dict) else 0.0

    fig, ax = plt.subplots(figsize=(10, 6))
    im = ax.imshow(data, cmap="RdYlGn", aspect="auto", vmin=0, vmax=1)

    ax.set_xticks(range(len(conditions)))
    ax.set_xticklabels([DRIFT_LABELS.get(c, c) for c in conditions], rotation=30, ha="right")
    ax.set_yticks(range(len(families)))
    ax.set_yticklabels(family_labels)

    for i in range(len(families)):
        for j in range(len(conditions)):
            ax.text(j, i, f"{data[i, j]:.0%}", ha="center", va="center",
                    color="black" if data[i, j] > 0.5 else "white", fontsize=12)

    fig.colorbar(im, label="Pass Rate")
    ax.set_title("Pass Rate: Family × Condition", fontsize=14, fontweight="bold")
    fig.tight_layout()
    fig.savefig(output_path, dpi=300)
    plt.close(fig)
    logger.info(f"Family heatmap saved to {output_path}")
    return output_path


def plot_adaptation_stacked_bar(
    metrics_by_condition: Dict[str, Any],
    output_path: Optional[str] = None,
) -> Optional[str]:
    """
    Figure 2: Stacked bar for RUNTIME_EVOLVED — direct reuse vs adapted vs new.

    Shows the transition from reuse to adaptation to generation as drift increases.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        logger.warning("matplotlib/numpy not installed — skipping stacked bar")
        return None

    output_path = output_path or "results/conceptdrift/adaptation_stacked.png"
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    metrics = metrics_by_condition.get("runtime_evolved")
    if not metrics:
        return None
    if hasattr(metrics, "adaptation_by_drift"):
        data = metrics.adaptation_by_drift
    elif isinstance(metrics, dict):
        data = metrics.get("adaptation_by_drift", {})
    else:
        return None

    reused = [data.get(d, {}).get("reused", 0) for d in DRIFT_ORDER]
    adapted = [data.get(d, {}).get("adapted", 0) for d in DRIFT_ORDER]
    new_gen = [data.get(d, {}).get("new", 0) for d in DRIFT_ORDER]

    x = np.arange(len(DRIFT_ORDER))
    width = 0.6

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.bar(x, reused, width, label="Direct reuse", color="#4CAF50", alpha=0.9)
    ax.bar(x, adapted, width, bottom=reused, label="Adapted reuse", color="#FF9800", alpha=0.9)
    ax.bar(x, new_gen, width, bottom=np.array(reused) + np.array(adapted),
           label="New generation", color="#2196F3", alpha=0.9)

    ax.set_xlabel("Drift Level", fontsize=13)
    ax.set_ylabel("Proportion", fontsize=13)
    ax.set_title("RUNTIME_EVOLVED: Reuse vs Adaptation vs New Generation", fontsize=14, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(DRIFT_ORDER)
    ax.set_ylim(0, 1.05)
    ax.legend(loc="upper right", fontsize=11)
    ax.grid(True, alpha=0.2, axis="y")
    fig.tight_layout()
    fig.savefig(output_path, dpi=300)
    plt.close(fig)
    logger.info(f"Adaptation stacked bar saved to {output_path}")
    return output_path


def plot_compounding_curve(
    task_results_by_condition: Dict[str, List[Dict[str, Any]]],
    output_path: Optional[str] = None,
) -> Optional[str]:
    """
    Figure 3: Token cost vs task position within family.

    Shows cost reduction as skill library grows. Requires task-level results
    with keys: task_id, family, drift_index, tokens_prompt, tokens_completion.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        logger.warning("matplotlib/numpy not installed — skipping compounding curve")
        return None

    output_path = output_path or "results/conceptdrift/compounding_curve.png"
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(10, 6))
    for cond_key, results in task_results_by_condition.items():
        if not results:
            continue
        # Sort by family then drift_index to get task order
        sorted_r = sorted(results, key=lambda r: (r.get("family", ""), r.get("drift_index", 0)))
        positions = list(range(1, len(sorted_r) + 1))
        tokens = []
        cumulative = 0
        for r in sorted_r:
            tp = r.get("tokens_prompt", 0) or 0
            tc = r.get("tokens_completion", 0) or 0
            cumulative += tp + tc
            tokens.append(cumulative)
        color = DRIFT_COLORS.get(cond_key, "#607D8B")
        label = DRIFT_LABELS.get(cond_key, cond_key)
        ax.plot(positions, tokens, color=color, label=label, linewidth=2)

    ax.set_xlabel("Task Position (cumulative)", fontsize=13)
    ax.set_ylabel("Cumulative Tokens", fontsize=13)
    ax.set_title("Token Cost: Cumulative by Task Order", fontsize=14, fontweight="bold")
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_path, dpi=300)
    plt.close(fig)
    logger.info(f"Compounding curve saved to {output_path}")
    return output_path


def generate_all_figures(
    metrics_by_condition: Dict[str, Any],
    output_dir: str = "results/conceptdrift",
    task_results_by_condition: Optional[Dict[str, List[Dict[str, Any]]]] = None,
) -> List[str]:
    """Generate all ConceptDrift figures and return list of file paths."""
    paths = []
    p = plot_adaptation_by_drift(
        metrics_by_condition, f"{output_dir}/main_figure.png")
    if p:
        paths.append(p)

    p = plot_adaptation_rate(
        metrics_by_condition, f"{output_dir}/adaptation_rate.png")
    if p:
        paths.append(p)

    p = plot_adaptation_stacked_bar(
        metrics_by_condition, f"{output_dir}/adaptation_stacked.png")
    if p:
        paths.append(p)

    p = plot_family_heatmap(
        metrics_by_condition, f"{output_dir}/family_heatmap.png")
    if p:
        paths.append(p)

    if task_results_by_condition:
        p = plot_compounding_curve(
            task_results_by_condition, f"{output_dir}/compounding_curve.png")
        if p:
            paths.append(p)

    return paths
