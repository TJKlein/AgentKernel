"""
Spider 2.0 / BIRD family loader — advanced text-to-SQL benchmark.

Uses BIRD-SQL dataset from HuggingFace for Family C (advanced SQL).
BIRD-SQL is significantly harder than Spider 1.0 with complex queries,
external knowledge requirements, and real-world database schemas.

Uses bird23-train-filtered which has SQL solutions (6,601 tasks).

Requires: pip install datasets
"""

import logging
import random
from pathlib import Path
from typing import Any, Dict, List, Optional

from benchmarks.tasks.schema import DriftTask

logger = logging.getLogger(__name__)

# Drift types for SQL evolution (schema drift, query complexity)
SPIDER2_DRIFT_CHAIN = [
    (1, "none", "none"),
    (2, "schema_rename", "minor"),
    (3, "field_addition", "minor"),
    (4, "structure_change", "moderate"),
    (5, "logic_change", "moderate"),
    (6, "combined", "major"),
]


def _load_bird_dataset() -> Any:
    """Load BIRD-SQL from HuggingFace (Spider 2.0 equivalent).
    
    Uses bird23-train-filtered which has SQL solutions (unlike blind test sets).
    """
    try:
        from datasets import load_dataset
    except ImportError as e:
        raise ImportError(
            "Spider 2.0/BIRD loader requires 'datasets'. Install with: pip install datasets"
        ) from e
    # BIRD 2023 train filtered: 6,601 tasks with SQL solutions
    return load_dataset(
        "birdsql/bird23-train-filtered",
        split="train"
    )


def _select_tasks(dataset: Any, seed: int, limit: int = 6) -> List[Dict[str, Any]]:
    """Select up to `limit` tasks deterministically."""
    indices = list(range(len(dataset)))
    rng = random.Random(seed)
    rng.shuffle(indices)
    selected = indices[:limit]
    return [dict(dataset[i]) for i in selected]


def _select_tasks_from_list(rows: List[Dict], seed: int, limit: int = 6) -> List[Dict[str, Any]]:
    """Select up to `limit` tasks from a pre-filtered list."""
    rng = random.Random(seed)
    rng.shuffle(rows)
    return rows[:limit]


def _extract_schema_info(row: Dict[str, Any]) -> str:
    """Extract schema information from the row."""
    db_id = row.get("db_id") or "unknown"
    return f"Database: {db_id} (schema available in external database files)"


def _row_to_drift_task(
    row: Dict[str, Any],
    task_id: str,
    drift_index: int,
    drift_type: str,
    drift_level: str,
    prior_task_id: Optional[str],
    oracle_skill_id: Optional[str],
) -> DriftTask:
    """Convert a BIRD/Spider 2.0 row to a DriftTask."""
    # BIRD 2023 train-filtered dataset fields
    question = row.get("question") or ""
    sql = row.get("SQL") or ""
    db_id = row.get("db_id") or ""
    evidence = row.get("evidence") or ""
    difficulty = row.get("difficulty") or "medium"
    instance_id = str(row.get("index", task_id))
    
    if not question:
        raise ValueError(f"Spider 2.0 task {task_id} has no question")
    
    schema_info = _extract_schema_info(row)
    
    full_prompt = f"Database: {db_id}\nSchema:\n{schema_info}\n\n"
    if evidence:
        full_prompt += f"External Knowledge:\n{evidence}\n\n"
    full_prompt += f"Question: {question}\n\nWrite a SQL query to answer this. Output ONLY the SQL."
    
    ground_truth: Dict[str, Any] = {
        "sql": sql,
        "db_id": db_id,
        "difficulty": difficulty,
        "validator": "spider2_sql",
    }
    
    # Wrap SQL in executable Python script for reference/fallback execution
    import os
    db_dir = os.environ.get("BIRD_DATABASES_DIR", "/Users/d065243/Downloads/bird_train/train")
    reference_python = f'''import sqlite3
import sys

# Connect to database
db_path = "{db_dir}/train_databases/{db_id}/{db_id}.sqlite"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Execute query
cursor.execute("""{sql}""")
result = cursor.fetchall()
conn.close()

# Output result
for row in result:
    print(row)
'''
    
    return DriftTask(
        id=task_id,
        name=f"{instance_id}_spider2_{db_id}",
        description=f"Spider 2.0 SQL task {drift_index} ({difficulty})",
        difficulty=difficulty,
        family="C",
        drift_level=drift_level,
        drift_type=drift_type,
        drift_index=drift_index,
        prior_task_id=prior_task_id,
        oracle_skill_id=oracle_skill_id,
        drift_description=f"SQL drift (type: {drift_type})",
        prompt=full_prompt,
        validation_type="custom",
        reference_code=reference_python,
        supported_backends=["opensandbox", "subprocess"],
        input_data={"db_id": db_id},
        ground_truth=ground_truth,
        objective_fn_name="spider2_sql",
    )


class Spider2FamilyLoader:
    """Loader for Family C using Spider 2.0 / BIRD text-to-SQL tasks."""
    
    family_id = "C"
    family_name = "Text-to-SQL (Spider 2.0 / BIRD)"
    source_benchmark = "BIRD-SQL"
    
    def load_tasks(self, data_dir: Path, seed: int = 42, limit: Optional[int] = None, difficulty_filter: Optional[List[str]] = None) -> List[DriftTask]:
        """Load 6 BIRD-SQL tasks as a drift chain.
        
        Args:
            data_dir: Data directory (unused, kept for API compatibility)
            seed: Random seed
            limit: Max tasks (default 6)
            difficulty_filter: Filter by difficulty levels (e.g., ['medium', 'hard', 'challenging'])
        """
        dataset = _load_bird_dataset()
        n = limit or 6
        
        # Filter by difficulty if specified
        difficulty_filter = difficulty_filter or ['medium', 'hard', 'challenging']
        filtered_rows = [dict(row) for row in dataset if row.get('difficulty') in difficulty_filter]
        
        if len(filtered_rows) < n:
            logger.warning(f"Only {len(filtered_rows)} tasks match difficulty filter {difficulty_filter}, need {n}")
            # Fall back to all tasks if not enough hard ones
            filtered_rows = [dict(row) for row in dataset]
        
        # Sample from filtered set
        rows = _select_tasks_from_list(filtered_rows, seed=seed, limit=n)
        
        tasks: List[DriftTask] = []
        for i, row in enumerate(rows):
            idx = i + 1
            drift_type, drift_level = SPIDER2_DRIFT_CHAIN[idx - 1][1], SPIDER2_DRIFT_CHAIN[idx - 1][2]
            task_id = f"C{idx}"
            prior = f"C{idx - 1}" if idx > 1 else None
            oracle = prior
            
            tasks.append(_row_to_drift_task(
                row=row, task_id=task_id, drift_index=idx,
                drift_type=drift_type, drift_level=drift_level,
                prior_task_id=prior, oracle_skill_id=oracle,
            ))
        
        logger.info(f"Loaded {len(tasks)} Spider 2.0/BIRD tasks (difficulty: {difficulty_filter})")
        return tasks
    
    def get_drift_chain(self) -> List[tuple]:
        return [(f"C{i}", dt, f"C{i-1}" if i > 1 else None) for i, (_, dt, _) in enumerate(SPIDER2_DRIFT_CHAIN, 1)]
