"""
Task family loaders for ConceptDriftBench.

Supports pluggable data sources. The default generator uses synthetic data.
Implementations can load from external benchmarks:
- BigCodeBench (API evolution)
- FinanceBench (financial filings)
- Spider 2.0 (SQL schema drift)
- DS-1000 (data processing)
- WorkArena (enterprise workflows)
"""

from .base import BaseFamilyLoader
from .synthetic import SyntheticFamilyLoader

try:
    from .ds1000 import DS1000FamilyLoader
except ImportError:
    DS1000FamilyLoader = None  # type: ignore

try:
    from .bigcode import BigCodeBenchLoader
except ImportError:
    BigCodeBenchLoader = None  # type: ignore

try:
    from .humaneval import HumanEvalLoader
except ImportError:
    HumanEvalLoader = None  # type: ignore

try:
    from .spider import SpiderFamilyLoader
except ImportError:
    SpiderFamilyLoader = None  # type: ignore

__all__ = ["BaseFamilyLoader", "SyntheticFamilyLoader", "DS1000FamilyLoader", "BigCodeBenchLoader", "HumanEvalLoader", "SpiderFamilyLoader"]
