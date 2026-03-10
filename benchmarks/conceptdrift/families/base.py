"""
Abstract base for task family loaders.

Implement this interface to plug in external benchmark data sources
(BigCodeBench, FinanceBench, Spider 2.0, DS-1000, WorkArena).
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional

from benchmarks.tasks.schema import DriftTask


class BaseFamilyLoader(ABC):
    """
    Abstract loader for a single task family.
    
    Criteria for external sources (from the plan):
    - Must have: Objective, automated validation
    - Must have: Natural drift vectors documentable from the source
    - Should have: Enterprise relevance
    """

    family_id: str = ""
    family_name: str = ""
    source_benchmark: Optional[str] = None  # e.g. "BigCodeBench", "FinanceBench"
    
    @abstractmethod
    def load_tasks(
        self,
        data_dir: Path,
        seed: int = 42,
        limit: Optional[int] = None,
    ) -> List[DriftTask]:
        """
        Load tasks for this family.
        
        Args:
            data_dir: Directory for input files (write here if generating)
            seed: Random seed for reproducibility
            limit: Max tasks (for quick runs)
            
        Returns:
            Ordered list of DriftTasks (drift chain preserved)
        """
        pass

    @abstractmethod
    def get_drift_chain(self) -> List[tuple]:
        """
        Return the drift chain: [(task_id, drift_type, prior_id), ...].
        
        Used to validate that drift is properly structured.
        """
        pass

    def validate_output(self, task_id: str, output: Any) -> bool:
        """
        Validate task output against ground truth.
        
        Override for custom validation. Default assumes answer.json.
        """
        return True
