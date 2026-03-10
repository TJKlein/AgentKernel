"""
Spider/SQL family loader — simplified text-to-SQL tasks.

Uses Spider 1.0 format from HuggingFace for Family C (SQL/schema drift).
Simplified validation: checks SQL syntax and structure without requiring DB.

Requires: pip install datasets
"""

import logging
import random
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from benchmarks.tasks.schema import DriftTask

logger = logging.getLogger(__name__)

# Drift types for SQL schema evolution
SPIDER_DRIFT_CHAIN = [
    (1, "none", "none"),
    (2, "schema_rename", "minor"),
    (3, "field_addition", "minor"),
    (4, "structure_change", "moderate"),
    (5, "logic_change", "moderate"),
    (6, "combined", "major"),
]


def _load_spider_dataset() -> Any:
    """Load Spider 1.0 from HuggingFace. Lazy import to avoid hard dep."""
    try:
        from datasets import load_dataset
    except ImportError as e:
        raise ImportError(
            "Spider loader requires 'datasets'. Install with: pip install datasets"
        ) from e
    # Use validation split (smaller, more manageable)
    return load_dataset("xlangai/spider", split="validation")


def _select_tasks(dataset: Any, seed: int, limit: int = 6) -> List[Dict[str, Any]]:
    """Select up to `limit` SQL tasks deterministically."""
    indices = list(range(len(dataset)))
    rng = random.Random(seed)
    rng.shuffle(indices)
    selected = indices[:limit]
    return [dict(dataset[i]) for i in selected]


def _validate_sql_simple(query: str) -> bool:
    """Basic SQL syntax validation using SQLite parser."""
    if not query or not query.strip():
        return False
    try:
        # SQLite can parse most standard SQL
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        # Try to parse (but not execute) - EXPLAIN will fail on syntax errors
        cursor.execute(f"EXPLAIN {query}")
        conn.close()
        return True
    except sqlite3.Error:
        return False


def _row_to_drift_task(
    row: Dict[str, Any],
    task_id: str,
    drift_index: int,
    drift_type: str,
    drift_level: str,
    prior_task_id: Optional[str],
    oracle_skill_id: Optional[str],
) -> DriftTask:
    """Convert a Spider row to a DriftTask."""
    question = row.get("question") or ""
    query = row.get("query") or ""
    db_id = row.get("db_id") or "unknown"

    if not question:
        raise ValueError(f"Spider task {task_id} has no question")

    # Build prompt
    full_prompt = (
        f"Database: {db_id}\n"
        f"Question: {question}\n\n"
        f"Write a SQL query to answer this question. "
        f"Output ONLY the SQL query, no explanations or markdown."
    )

    # Ground truth for validation
    ground_truth: Dict[str, Any] = {
        "expected_query": query,
        "db_id": db_id,
        "validator": "spider_sql",
    }

    return DriftTask(
        id=task_id,
        name=f"{task_id}_spider_{db_id}",
        description=f"Spider SQL task {drift_index}",
        difficulty="medium",
        family="C",
        drift_level=drift_level,
        drift_type=drift_type,
        drift_index=drift_index,
        prior_task_id=prior_task_id,
        oracle_skill_id=oracle_skill_id,
        drift_description=f"Spider SQL schema evolution (drift: {drift_type})",
        prompt=full_prompt,
        validation_type="custom",
        reference_code=query,
        supported_backends=["opensandbox", "subprocess"],
        input_data={},
        ground_truth=ground_truth,
        objective_fn_name="spider_sql",
    )


class SpiderFamilyLoader:
    """
    Loader for Family C using Spider text-to-SQL tasks.

    Fetches from HuggingFace, selects 6 diverse SQL tasks, maps to DriftTask
    with SQL-based validation.
    """

    family_id = "C"
    family_name = "SQL/Schema Drift (Spider)"
    source_benchmark = "Spider 1.0"

    def load_tasks(
        self,
        data_dir: Path,
        seed: int = 42,
        limit: Optional[int] = None,
    ) -> List[DriftTask]:
        """Load 6 Spider SQL tasks as a drift chain."""
        dataset = _load_spider_dataset()
        n = limit or 6
        rows = _select_tasks(dataset, seed=seed, limit=n)

        tasks: List[DriftTask] = []
        for i, row in enumerate(rows):
            idx = i + 1
            drift_type, drift_level = (
                SPIDER_DRIFT_CHAIN[idx - 1][1],
                SPIDER_DRIFT_CHAIN[idx - 1][2],
            )
            task_id = f"C{idx}"
            prior = f"C{idx - 1}" if idx > 1 else None
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

        logger.info(f"Loaded {len(tasks)} Spider SQL tasks for family C")
        return tasks

    def get_drift_chain(self) -> List[tuple]:
        """Return the drift chain structure."""
        return [
            (f"C{i}", dt, f"C{i-1}" if i > 1 else None)
            for i, (_, dt, _) in enumerate(SPIDER_DRIFT_CHAIN, 1)
        ]
