"""
Synthetic data family loader — wraps the default DriftTaskGenerator.
"""

from pathlib import Path
from typing import List, Optional

from benchmarks.tasks.schema import DriftTask

from ..generator import (
    DriftTaskGenerator,
    _family_A,
    _family_B,
    _family_C,
    _family_D,
    _family_E,
    _family_F,
    DRIFT_TYPE_BY_INDEX,
)


class SyntheticFamilyLoader:
    """
    Loader that uses the built-in synthetic task generator.
    
    No external data required. All data is deterministic (fixed seed).
    """

    def __init__(self, tickers: Optional[List[str]] = None):
        self._tickers = tickers or ["AAPL", "MSFT", "AMZN", "NVDA", "TSLA"]

    def load_family(
        self,
        family_id: str,
        data_dir: Path,
        seed: int = 42,
    ) -> List[DriftTask]:
        """Load tasks for one family."""
        import random
        random.seed(seed)
        tasks: List[DriftTask] = []
        if family_id == "A":
            tasks = _family_A(self._tickers, data_dir)
        elif family_id == "B":
            tasks = _family_B(self._tickers)
        elif family_id == "C":
            tasks = _family_C()
        elif family_id == "D":
            tasks = _family_D()
        elif family_id == "E":
            tasks = _family_E(self._tickers)
        elif family_id == "F":
            tasks = _family_F(self._tickers)
        else:
            raise ValueError(f"Unknown family: {family_id}")

        for t in tasks:
            t.drift_type = DRIFT_TYPE_BY_INDEX.get(t.drift_index, "none")
        return tasks
