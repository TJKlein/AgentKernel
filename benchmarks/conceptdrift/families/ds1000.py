"""
DS-1000 family loader — real data from HuggingFace.

Loads Pandas tasks from xlangai/DS-1000 for Family D (data processing).
Each task uses DS-1000's native execution-based validation (test_execution).

Requires: pip install datasets  (or pip install .[conceptdrift])
"""

import logging
import random
from pathlib import Path
from typing import Any, Dict, List, Optional

from benchmarks.tasks.schema import DriftTask

logger = logging.getLogger(__name__)

# Drift types for DS-1000 tasks (schemas evolve across tasks)
DS1000_DRIFT_CHAIN = [
    (1, "none", "none"),
    (2, "schema_rename", "minor"),
    (3, "field_addition", "minor"),
    (4, "structure_change", "moderate"),
    (5, "format_change", "moderate"),
    (6, "combined", "major"),
]


def _load_ds1000_dataset() -> Any:
    """Load DS-1000 from HuggingFace. Lazy import to avoid hard dep."""
    try:
        from datasets import load_dataset
    except ImportError as e:
        raise ImportError(
            "DS-1000 loader requires 'datasets'. Install with: pip install datasets"
        ) from e
    return load_dataset("xlangai/DS-1000", split="test")


def _select_pandas_tasks(dataset: Any, seed: int, limit: int = 6) -> List[Dict[str, Any]]:
    """Select up to `limit` Pandas tasks deterministically."""
    # Filter by library (column may be 'library' or in metadata)
    indices: List[int] = []
    for i in range(len(dataset)):
        row = dataset[i]
        lib = row.get("library") or (row.get("metadata") or {}).get("library")
        if lib == "Pandas" or (isinstance(lib, str) and "pandas" in lib.lower()):
            indices.append(i)

    if not indices:
        # Fallback: try 'Metadata' or other column names
        for i in range(min(500, len(dataset))):
            row = dataset[i]
            if "pandas" in str(row).lower():
                indices.append(i)
        indices = indices[: limit * 5]  # broader pool

    if not indices:
        raise ValueError("No Pandas tasks found in DS-1000 dataset")

    rng = random.Random(seed)
    rng.shuffle(indices)
    selected = indices[:limit]
    return [dict(dataset[i]) for i in selected]


DS1000_INSTRUCTION = (
    "\n\n---\nTASK: Write Python code that solves the problem above. "
    "The test harness will provide variables (e.g. df, List) — use them directly. "
    "Your code MUST assign the final answer to a variable named `result`. "
    "Output ONLY the Python code, no explanations or markdown."
)


def _row_to_drift_task(
    row: Dict[str, Any],
    task_id: str,
    drift_index: int,
    drift_type: str,
    drift_level: str,
    prior_task_id: Optional[str],
    oracle_skill_id: Optional[str],
) -> DriftTask:
    """Convert a DS-1000 row to a DriftTask."""
    prompt = row.get("prompt") or row.get("Prompt") or ""
    code_context = row.get("code_context") or row.get("Code Context") or ""

    if not prompt:
        raise ValueError(f"DS-1000 task {task_id} has no prompt")

    # Original prompt (for [insert] replacement in validator); agent sees prompt + instruction
    original_prompt = prompt
    prompt = prompt.rstrip() + DS1000_INSTRUCTION

    # Ground truth holds code_context and original prompt for execution-based validation
    ground_truth: Dict[str, Any] = {
        "code_context": code_context,
        "prompt": original_prompt,
        "validator": "ds1000_execution",
    }

    return DriftTask(
        id=task_id,
        name=f"{task_id}_ds1000_pandas",
        description=f"DS-1000 Pandas task {drift_index}",
        difficulty="medium",
        family="D",
        drift_level=drift_level,
        drift_type=drift_type,
        drift_index=drift_index,
        prior_task_id=prior_task_id,
        oracle_skill_id=oracle_skill_id,
        drift_description=f"DS-1000 data processing (drift: {drift_type})",
        prompt=prompt,
        validation_type="custom",
        reference_code="",
        supported_backends=["opensandbox", "subprocess"],
        input_data={},
        ground_truth=ground_truth,
        objective_fn_name="ds1000_execution",
    )


class DS1000FamilyLoader:
    """
    Loader for Family D using real DS-1000 Pandas tasks.

    Fetches from HuggingFace, selects 6 Pandas tasks, maps to DriftTask
    with execution-based validation (test_execution from code_context).
    """

    family_id = "D"
    family_name = "Data Processing (DS-1000)"
    source_benchmark = "DS-1000"

    def load_tasks(
        self,
        data_dir: Path,
        seed: int = 42,
        limit: Optional[int] = None,
    ) -> List[DriftTask]:
        """Load 6 Pandas tasks from DS-1000 as a drift chain."""
        dataset = _load_ds1000_dataset()
        n = limit or 6
        rows = _select_pandas_tasks(dataset, seed=seed, limit=n)

        tasks: List[DriftTask] = []
        for i, row in enumerate(rows):
            idx = i + 1
            drift_type, drift_level = (
                DS1000_DRIFT_CHAIN[idx - 1][1],
                DS1000_DRIFT_CHAIN[idx - 1][2],
            )
            task_id = f"D{idx}"
            prior = f"D{idx - 1}" if idx > 1 else None
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

        logger.info(f"Loaded {len(tasks)} DS-1000 Pandas tasks for family D")
        return tasks

    def get_drift_chain(self) -> List[tuple]:
        """Return the drift chain structure."""
        return [
            (f"D{i}", dt, f"D{i-1}" if i > 1 else None)
            for i, (_, dt, _) in enumerate(DS1000_DRIFT_CHAIN, 1)
        ]
