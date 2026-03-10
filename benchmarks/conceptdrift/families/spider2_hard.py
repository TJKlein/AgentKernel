"""
Spider 2.0 Hard family loader - uses BIRD-SQL dev set with difficulty filtering.

This loader selects only moderate/challenging tasks from the BIRD dev set
to ensure a non-trivial baseline (~50-70% pass rate) for cross-schema experiments.
"""

import logging
import random
from pathlib import Path
from typing import Any, Dict, List, Optional

from benchmarks.tasks.schema import DriftTask
from benchmarks.conceptdrift.families.spider2 import (
    _row_to_drift_task, SPIDER2_DRIFT_CHAIN
)

logger = logging.getLogger(__name__)


def _load_bird_dev_dataset() -> Any:
    """Load BIRD-SQL dev set from HuggingFace (has difficulty labels)."""
    try:
        from datasets import load_dataset
    except ImportError as e:
        raise ImportError("BIRD dev loader requires 'datasets'. Install with: pip install datasets") from e
    
    return load_dataset("birdsql/bird_sql_dev_20251106", split="dev_20251106")


def _select_tasks(dataset: Any, seed: int, limit: int = 6) -> List[Dict[str, Any]]:
    """Select up to `limit` tasks deterministically."""
    indices = list(range(len(dataset)))
    rng = random.Random(seed)
    rng.shuffle(indices)
    selected = indices[:limit]
    return [dict(dataset[i]) for i in selected]


class Spider2HardLoader:
    """Loader for Family C using hard BIRD-SQL tasks (moderate/challenging only).
    
    Uses BIRD dev set which has difficulty labels, filtering to only
    moderate and challenging tasks to ensure a non-trivial baseline.
    """
    
    family_id = "C"
    family_name = "Text-to-SQL Hard (Spider 2.0 / BIRD)"
    source_benchmark = "BIRD-SQL-Dev"
    
    def load_tasks(self, data_dir: Path, seed: int = 42, limit: Optional[int] = None, 
                   difficulty_filter: Optional[List[str]] = None) -> List[DriftTask]:
        """Load hard BIRD-SQL tasks for a challenging baseline.
        
        Args:
            data_dir: Data directory (unused, kept for API compatibility)
            seed: Random seed
            limit: Max tasks (default 6)
            difficulty_filter: Difficulty levels to include (default: ['moderate', 'challenging'])
        """
        dataset = _load_bird_dev_dataset()
        n = limit or 6
        
        # Default to moderate and challenging (exclude 'simple')
        difficulty_filter = difficulty_filter or ['moderate', 'challenging']
        
        # Filter by difficulty
        filtered_rows = [dict(row) for row in dataset if row.get('difficulty') in difficulty_filter]
        
        if len(filtered_rows) < n:
            logger.warning(f"Only {len(filtered_rows)} tasks match difficulty {difficulty_filter}, need {n}")
            # Include simple if needed
            if len(filtered_rows) < n:
                simple_rows = [dict(row) for row in dataset if row.get('difficulty') == 'simple']
                filtered_rows.extend(simple_rows[:n - len(filtered_rows)])
        
        logger.info(f"Selected {len(filtered_rows)} {difficulty_filter} tasks from BIRD dev set")
        
        # Sample deterministically
        rows = _select_tasks(filtered_rows, seed=seed, limit=n)
        
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
        
        logger.info(f"Loaded {len(tasks)} hard BIRD-SQL tasks")
        return tasks
    
    def get_drift_chain(self) -> List[tuple]:
        return [(f"C{i}", dt, f"C{i-1}" if i > 1 else None) for i, (_, dt, _) in enumerate(SPIDER2_DRIFT_CHAIN, 1)]
