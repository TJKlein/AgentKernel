"""
Spider 2.0 Same-Schema family loader - for testing schema heterogeneity hypothesis.

Unlike spider2.py which selects tasks from different databases,
this loader creates a drift chain from tasks on the SAME database
to test whether skills help when schema is constant but queries drift.
"""

import logging
import random
from pathlib import Path
from typing import Any, Dict, List, Optional

from benchmarks.tasks.schema import DriftTask
from benchmarks.conceptdrift.families.spider2 import _row_to_drift_task

logger = logging.getLogger(__name__)

# Drift types for SQL evolution (same as cross-schema)
SPIDER2_DRIFT_CHAIN = [
    (1, "none", "none"),
    (2, "schema_rename", "minor"),  # Actually query pattern change since schema is fixed
    (3, "field_addition", "minor"),   # Query complexity increases
    (4, "structure_change", "moderate"),  # JOIN patterns change
    (5, "logic_change", "moderate"),  # WHERE/aggregation logic changes
    (6, "combined", "major"),  # Complex multi-table with subqueries
]

# Database with many tasks for same-schema experiments
TARGET_DATABASES = [
    "works_cycles",  # 383 tasks
    "public_review_platform",  # 256 tasks
    "movie_3",  # 223 tasks
    "mondial_geo",  # 211 tasks
]


def _load_bird_dataset() -> Any:
    """Load BIRD-SQL from HuggingFace."""
    try:
        from datasets import load_dataset
    except ImportError as e:
        raise ImportError("Spider 2.0/BIRD loader requires 'datasets'. Install with: pip install datasets") from e
    return load_dataset("birdsql/bird23-train-filtered", split="train")


class Spider2SameSchemaLoader:
    """Loader for Family C using Spider 2.0 / BIRD with SAME database schema."""
    
    family_id = "C"
    family_name = "Text-to-SQL Same Schema (Spider 2.0 / BIRD)"
    source_benchmark = "BIRD-SQL"
    
    def load_tasks(self, data_dir: Path, seed: int = 42, limit: Optional[int] = None, db_id: Optional[str] = None) -> List[DriftTask]:
        """Load tasks all from the same database to test schema consistency.
        
        Args:
            data_dir: Data directory (unused, kept for API compatibility)
            seed: Random seed
            limit: Max tasks (default 6 for drift chain)
            db_id: Specific database to use (default: pick from TARGET_DATABASES)
        """
        dataset = _load_bird_dataset()
        n = limit or 6
        
        # Select target database
        if db_id is None:
            rng = random.Random(seed)
            db_id = rng.choice(TARGET_DATABASES)
        
        # Get all tasks for this database
        db_tasks = [dict(row) for row in dataset if row['db_id'] == db_id]
        
        if len(db_tasks) < n:
            logger.warning(f"Database {db_id} only has {len(db_tasks)} tasks, need {n}")
            # Fall back to any database with enough tasks
            db_tasks = [dict(row) for row in dataset if row['db_id'] == "works_cycles"]
        
        # Sample n tasks deterministically
        rng = random.Random(seed)
        rng.shuffle(db_tasks)
        selected = db_tasks[:n]
        
        logger.info(f"Selected {len(selected)} tasks from database '{db_id}'")
        
        # Create drift chain
        tasks: List[DriftTask] = []
        for i, row in enumerate(selected):
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
        
        return tasks
    
    def get_drift_chain(self) -> List[tuple]:
        return [(f"C{i}", dt, f"C{i-1}" if i > 1 else None) for i, (_, dt, _) in enumerate(SPIDER2_DRIFT_CHAIN, 1)]
