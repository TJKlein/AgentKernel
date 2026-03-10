"""
BigCodeBench family loader — real data from HuggingFace.

Loads Python code generation tasks from bigcode/bigcodebench for Family A (API evolution).
Each task uses execution-based validation via unit tests.

Requires: pip install datasets

Data Fields:
- instruct_prompt: Natural language instruction for code generation
- canonical_solution: Reference solution code
- test: Unit test cases in Python unittest format
- doc_struct: Structured docstring with description
"""

import logging
import random
from pathlib import Path
from typing import Any, Dict, List, Optional

from benchmarks.tasks.schema import DriftTask

logger = logging.getLogger(__name__)

# Drift types simulating API evolution chains
BIGCODE_DRIFT_CHAIN = [
    (1, "none", "none"),
    (2, "api_deprecation", "moderate"),
    (3, "field_addition", "minor"),
    (4, "structure_change", "moderate"),
    (5, "interface_replace", "major"),
    (6, "combined", "major"),
]


def _load_bigcode_dataset() -> Any:
    """Load BigCodeBench from HuggingFace. Lazy import to avoid hard dep."""
    try:
        from datasets import load_dataset
    except ImportError as e:
        raise ImportError(
            "BigCodeBench loader requires 'datasets'. Install with: pip install datasets"
        ) from e
    # BigCodeBench uses version-based splits like 'v0.1.4'
    return load_dataset("bigcode/bigcodebench", split="v0.1.4")


def _select_tasks(dataset: Any, seed: int, limit: int = 6) -> List[Dict[str, Any]]:
    """Select up to `limit` tasks deterministically."""
    # BigCodeBench tasks are diverse; we'll select a random sample
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
    """Convert a BigCodeBench row to a DriftTask."""
    instruct_prompt = row.get("instruct_prompt") or ""
    code_prompt = row.get("code_prompt") or ""
    test_code = row.get("test") or ""
    canonical_solution = row.get("canonical_solution") or ""
    entry_point = row.get("entry_point") or "task_func"

    if not instruct_prompt:
        raise ValueError(f"BigCodeBench task {task_id} has no instruct_prompt")

    # Build prompt that asks for properly indented function body
    # The code_prompt has the function signature, we need the body
    full_prompt = (
        f"Complete this Python function:\n\n"
        f"{code_prompt}\n"
        f"    # Write your implementation here\n\n"
        f"The function signature is already provided above. "
        f"Write ONLY the function body with proper 4-space indentation. "
        f"Do NOT include the 'def' line or any imports. "
        f"Output ONLY the indented code lines."
    )

    # Ground truth for validation
    ground_truth: Dict[str, Any] = {
        "test_code": test_code,
        "canonical_solution": canonical_solution,
        "code_prompt": code_prompt,
        "entry_point": entry_point,
        "validator": "bigcode_execution",
    }

    return DriftTask(
        id=task_id,
        name=f"{task_id}_bigcode_{row.get('task_id', 'task')}",
        description=f"BigCodeBench Python task {drift_index}",
        difficulty="medium",
        family="A",
        drift_level=drift_level,
        drift_type=drift_type,
        drift_index=drift_index,
        prior_task_id=prior_task_id,
        oracle_skill_id=oracle_skill_id,
        drift_description=f"BigCodeBench API/code evolution (drift: {drift_type})",
        prompt=full_prompt,
        validation_type="custom",
        reference_code=canonical_solution,
        supported_backends=["opensandbox", "subprocess"],
        input_data={},
        ground_truth=ground_truth,
        objective_fn_name="bigcode_execution",
    )


class BigCodeBenchLoader:
    """
    Loader for Family A using real BigCodeBench Python tasks.

    Fetches from HuggingFace, selects 6 diverse tasks, maps to DriftTask
    with execution-based validation (unit tests).
    """

    family_id = "A"
    family_name = "API Evolution (BigCodeBench)"
    source_benchmark = "BigCodeBench"

    def load_tasks(
        self,
        data_dir: Path,
        seed: int = 42,
        limit: Optional[int] = None,
    ) -> List[DriftTask]:
        """Load 6 BigCodeBench tasks as a drift chain."""
        dataset = _load_bigcode_dataset()
        n = limit or 6
        rows = _select_tasks(dataset, seed=seed, limit=n)

        tasks: List[DriftTask] = []
        for i, row in enumerate(rows):
            idx = i + 1
            drift_type, drift_level = (
                BIGCODE_DRIFT_CHAIN[idx - 1][1],
                BIGCODE_DRIFT_CHAIN[idx - 1][2],
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

        logger.info(f"Loaded {len(tasks)} BigCodeBench tasks for family A")
        return tasks

    def get_drift_chain(self) -> List[tuple]:
        """Return the drift chain structure."""
        return [
            (f"A{i}", dt, f"A{i-1}" if i > 1 else None)
            for i, (_, dt, _) in enumerate(BIGCODE_DRIFT_CHAIN, 1)
        ]
