"""
DS-1000 family loader — real data from HuggingFace.

Loads Pandas tasks from xlangai/DS-1000 for Family D (data processing).
Each task uses DS-1000's native execution-based validation (test_execution).

Optional: cluster_id + cluster_labels_path to restrict to one cluster (from
scripts/ds1000_cluster_pandas.py --out results/ds1000/cluster_labels.json).

Requires: pip install datasets  (or pip install .[conceptdrift])
"""

import json
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


def _pandas_rows_ordered(dataset: Any) -> List[Dict[str, Any]]:
    """Return all Pandas rows in dataset order (same order as ds1000_cluster_pandas.py)."""
    rows: List[Dict[str, Any]] = []
    for i in range(len(dataset)):
        row = dataset[i]
        lib = (row.get("metadata") or {}).get("library") or row.get("library")
        if lib and "pandas" in str(lib).lower():
            rows.append(dict(row))
    return rows


def _library_rows_ordered(dataset: Any, library: str) -> List[Dict[str, Any]]:
    """Return all rows for a given library (e.g. 'sklearn', 'numpy') in dataset order."""
    rows: List[Dict[str, Any]] = []
    for i in range(len(dataset)):
        row = dataset[i]
        lib = (row.get("metadata") or {}).get("library") or row.get("library")
        if lib and library.lower() in str(lib).lower():
            rows.append(dict(row))
    return rows


def _select_pandas_tasks(
    dataset: Any,
    seed: int,
    limit: int = 6,
    cluster_id: Optional[int] = None,
    cluster_labels_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Select up to `limit` Pandas tasks. If cluster_id and cluster_labels_path are set, filter to that cluster."""
    rows = _pandas_rows_ordered(dataset)
    if not rows:
        raise ValueError("No Pandas tasks found in DS-1000 dataset")

    if cluster_id is not None and cluster_labels_path is not None:
        path = Path(cluster_labels_path)
        if not path.exists():
            raise FileNotFoundError(f"Cluster labels not found: {path}. Run scripts/ds1000_cluster_pandas.py --out {path}")
        with open(path) as f:
            data = json.load(f)
        labels = data.get("labels", [])
        if len(labels) != len(rows):
            raise ValueError(
                f"cluster_labels has {len(labels)} labels but dataset has {len(rows)} Pandas tasks. Re-run ds1000_cluster_pandas.py."
            )
        subset = [rows[j] for j in range(len(rows)) if labels[j] == cluster_id]
        if not subset:
            raise ValueError(f"Cluster {cluster_id} has no tasks. Labels in file: {set(labels)}")
        rng = random.Random(seed)
        rng.shuffle(subset)
        selected = subset[:limit]
        logger.info(f"DS-1000: cluster {cluster_id} has {len(subset)} tasks; selected {len(selected)}")
    else:
        rng = random.Random(seed)
        rng.shuffle(rows)
        selected = rows[:limit]
    return selected


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


class DS1000SklearnFamilyLoader:
    """
    Loader for Family D using real DS-1000 Sklearn tasks.

    Fetches from HuggingFace, selects sklearn tasks (115 available), maps to DriftTask
    with execution-based validation. No clustering needed — all tasks share the same
    fit/transform/predict API pattern structure.
    """

    family_id = "D"
    family_name = "ML API Patterns (DS-1000 Sklearn)"
    source_benchmark = "DS-1000"
    library = "sklearn"

    def load_tasks(
        self,
        data_dir: Path,
        seed: int = 42,
        limit: Optional[int] = None,
    ) -> List[DriftTask]:
        """Load Sklearn tasks from DS-1000."""
        dataset = _load_ds1000_dataset()
        rows = _library_rows_ordered(dataset, self.library)
        if not rows:
            raise ValueError(f"No {self.library} tasks found in DS-1000 dataset")
        rng = random.Random(seed)
        rng.shuffle(rows)
        selected = rows[: (limit or 6)]
        logger.info(f"DS-1000 {self.library}: {len(rows)} tasks available; selected {len(selected)}")

        chain_len = len(DS1000_DRIFT_CHAIN)
        tasks: List[DriftTask] = []
        for i, row in enumerate(selected):
            idx = i + 1
            drift_type, drift_level = (
                DS1000_DRIFT_CHAIN[(idx - 1) % chain_len][1],
                DS1000_DRIFT_CHAIN[(idx - 1) % chain_len][2],
            )
            task_id = f"D{idx}"
            prior = f"D{idx - 1}" if idx > 1 else None
            row_copy = dict(row)
            # Override name so skill lookups use the sklearn family label
            task = _row_to_drift_task(
                row=row_copy,
                task_id=task_id,
                drift_index=idx,
                drift_type=drift_type,
                drift_level=drift_level,
                prior_task_id=prior,
                oracle_skill_id=prior,
            )
            # Relabel name/description for sklearn
            task = DriftTask(
                **{**task.__dict__,
                   "name": f"{task_id}_ds1000_sklearn",
                   "description": f"DS-1000 Sklearn task {idx}",
                   "drift_description": f"DS-1000 ML API evolution (drift: {drift_type})"}
            )
            tasks.append(task)

        logger.info(f"Loaded {len(tasks)} DS-1000 Sklearn tasks for family D")
        return tasks

    def get_drift_chain(self) -> List[tuple]:
        return [
            (f"D{i}", dt, f"D{i-1}" if i > 1 else None)
            for i, (_, dt, _) in enumerate(DS1000_DRIFT_CHAIN, 1)
        ]


class DS1000NumpyFamilyLoader:
    """
    Loader for Family D using real DS-1000 Numpy tasks.

    Fetches from HuggingFace, selects numpy tasks (available in DS-1000), maps to DriftTask
    with execution-based validation. All tasks share array operation patterns.
    """

    family_id = "D"
    family_name = "Array Operations (DS-1000 Numpy)"
    source_benchmark = "DS-1000"
    library = "numpy"

    def load_tasks(
        self,
        data_dir: Path,
        seed: int = 42,
        limit: Optional[int] = None,
    ) -> List[DriftTask]:
        """Load Numpy tasks from DS-1000."""
        dataset = _load_ds1000_dataset()
        rows = _library_rows_ordered(dataset, self.library)
        if not rows:
            raise ValueError(f"No {self.library} tasks found in DS-1000 dataset")
        rng = random.Random(seed)
        rng.shuffle(rows)
        selected = rows[: (limit or 6)]
        logger.info(f"DS-1000 {self.library}: {len(rows)} tasks available; selected {len(selected)}")

        chain_len = len(DS1000_DRIFT_CHAIN)
        tasks: List[DriftTask] = []
        for i, row in enumerate(selected):
            idx = i + 1
            drift_type, drift_level = (
                DS1000_DRIFT_CHAIN[(idx - 1) % chain_len][1],
                DS1000_DRIFT_CHAIN[(idx - 1) % chain_len][2],
            )
            task_id = f"D{idx}"
            prior = f"D{idx - 1}" if idx > 1 else None
            row_copy = dict(row)
            # Override name so skill lookups use the numpy family label
            task = _row_to_drift_task(
                row=row_copy,
                task_id=task_id,
                drift_index=idx,
                drift_type=drift_type,
                drift_level=drift_level,
                prior_task_id=prior,
                oracle_skill_id=prior,
            )
            # Relabel name/description for numpy
            task = DriftTask(
                **{**task.__dict__,
                   "name": f"{task_id}_ds1000_numpy",
                   "description": f"DS-1000 Numpy task {idx}",
                   "drift_description": f"DS-1000 array operation evolution (drift: {drift_type})"}
            )
            tasks.append(task)

        logger.info(f"Loaded {len(tasks)} DS-1000 Numpy tasks for family D")
        return tasks

    def get_drift_chain(self) -> List[tuple]:
        return [
            (f"D{i}", dt, f"D{i-1}" if i > 1 else None)
            for i, (_, dt, _) in enumerate(DS1000_DRIFT_CHAIN, 1)
        ]


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
        cluster_id: Optional[int] = None,
        cluster_labels_path: Optional[Path] = None,
    ) -> List[DriftTask]:
        """Load Pandas tasks from DS-1000. If cluster_id and cluster_labels_path are set, only tasks from that cluster."""
        dataset = _load_ds1000_dataset()
        n = limit or 6
        rows = _select_pandas_tasks(
            dataset,
            seed=seed,
            limit=n,
            cluster_id=cluster_id,
            cluster_labels_path=cluster_labels_path,
        )

        chain_len = len(DS1000_DRIFT_CHAIN)
        tasks: List[DriftTask] = []
        for i, row in enumerate(rows):
            idx = i + 1
            drift_type, drift_level = (
                DS1000_DRIFT_CHAIN[(idx - 1) % chain_len][1],
                DS1000_DRIFT_CHAIN[(idx - 1) % chain_len][2],
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
