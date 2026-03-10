"""
HumanEval family loader — OpenAI's code generation benchmark.

Uses HuggingFace openai_humaneval dataset for Family A (code generation).
Each task has a function signature, docstring, and test cases.
Validation via test execution.

Requires: pip install datasets
"""

import logging
import random
from pathlib import Path
from typing import Any, Dict, List, Optional

from benchmarks.tasks.schema import DriftTask

logger = logging.getLogger(__name__)

# Drift types for code evolution
HUMANEVAL_DRIFT_CHAIN = [
    (1, "none", "none"),
    (2, "api_deprecation", "moderate"),
    (3, "field_addition", "minor"),
    (4, "structure_change", "moderate"),
    (5, "logic_change", "moderate"),
    (6, "combined", "major"),
]


def _load_humaneval_dataset() -> Any:
    """Load HumanEval from HuggingFace."""
    try:
        from datasets import load_dataset
    except ImportError as e:
        raise ImportError(
            "HumanEval loader requires 'datasets'. Install with: pip install datasets"
        ) from e
    return load_dataset("openai_humaneval", split="test")


def _select_tasks(dataset: Any, seed: int, limit: int = 6) -> List[Dict[str, Any]]:
    """Select up to `limit` tasks deterministically."""
    indices = list(range(len(dataset)))
    rng = random.Random(seed)
    rng.shuffle(indices)
    selected = indices[:limit]
    return [dict(dataset[i]) for i in selected]


def _row_to_drift_task(
    row: Dict[str, Any],
    task_id: str,
    drift_index: int,
    drift_type: str,
    drift_level: str,
    prior_task_id: Optional[str],
    oracle_skill_id: Optional[str],
) -> DriftTask:
    """Convert a HumanEval row to a DriftTask."""
    prompt = row.get("prompt") or ""
    test = row.get("test") or ""
    entry_point = row.get("entry_point") or ""
    canonical_solution = row.get("canonical_solution") or ""

    if not prompt:
        raise ValueError(f"HumanEval task {task_id} has no prompt")

    # HumanEval prompt already has function signature + docstring
    # Just add instructions to complete the implementation
    full_prompt = (
        f"Complete this Python function:\n\n"
        f"{prompt}\n"
        f"    # Complete the implementation here\n\n"
        f"Write the function body with proper 4-space indentation. "
        f"Include all code inside the function. Output ONLY the Python code."
    )

    # Ground truth for validation
    ground_truth: Dict[str, Any] = {
        "test_code": test,
        "canonical_solution": canonical_solution,
        "entry_point": entry_point,
        "validator": "humaneval_execution",
    }

    return DriftTask(
        id=task_id,
        name=f"{task_id}_humaneval_{entry_point}",
        description=f"HumanEval code task {drift_index}",
        difficulty="medium",
        family="A",
        drift_level=drift_level,
        drift_type=drift_type,
        drift_index=drift_index,
        prior_task_id=prior_task_id,
        oracle_skill_id=oracle_skill_id,
        drift_description=f"HumanEval code evolution (drift: {drift_type})",
        prompt=full_prompt,
        validation_type="custom",
        reference_code=canonical_solution,
        supported_backends=["opensandbox", "subprocess"],
        input_data={},
        ground_truth=ground_truth,
        objective_fn_name="humaneval_execution",
    )


class HumanEvalLoader:
    """
    Loader for Family A using HumanEval code generation tasks.
    
    Fetches from HuggingFace, selects 6 diverse tasks, maps to DriftTask
    with execution-based validation via test cases.
    """

    family_id = "A"
    family_name = "Code Generation (HumanEval)"
    source_benchmark = "HumanEval"

    def load_tasks(
        self,
        data_dir: Path,
        seed: int = 42,
        limit: Optional[int] = None,
    ) -> List[DriftTask]:
        """Load 6 HumanEval tasks as a drift chain."""
        dataset = _load_humaneval_dataset()
        n = limit or 6
        rows = _select_tasks(dataset, seed=seed, limit=n)

        tasks: List[DriftTask] = []
        for i, row in enumerate(rows):
            idx = i + 1
            drift_type, drift_level = (
                HUMANEVAL_DRIFT_CHAIN[idx - 1][1],
                HUMANEVAL_DRIFT_CHAIN[idx - 1][2],
            )
            task_id = f"A{idx}"
            prior = f"A{idx - 1}" if idx > 1 else None
            oracle = prior

            tasks.append(
                _row_to_drift_task(
                    row=row,
                    task_id=task_id,
                    drift_index=idx,
                    drift_type=drift_type,
                    drift_level=drift_level,
                    prior_task_id=prior,
                    oracle_skill_id=oracle,
                )
            )

        logger.info(f"Loaded {len(tasks)} HumanEval tasks for family A")
        return tasks

    def get_drift_chain(self) -> List[tuple]:
        """Return the drift chain structure."""
        return [
            (f"A{i}", dt, f"A{i-1}" if i > 1 else None)
            for i, (_, dt, _) in enumerate(HUMANEVAL_DRIFT_CHAIN, 1)
        ]
