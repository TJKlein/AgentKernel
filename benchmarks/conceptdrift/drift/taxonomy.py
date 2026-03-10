"""
Formal drift taxonomy for ConceptDriftBench.

Every task is tagged with exactly one drift type. This enables result breakdown
by drift category (structural, interface, semantic, combined) in addition to
drift level (none, minor, moderate, major). Paper reviewers can see which
drift types benefit most from skill evolution.
"""

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class DriftType:
    """Canonical drift type with level and category."""
    level: str       # "none" | "minor" | "moderate" | "major"
    category: str     # "structural" | "surface" | "interface" | "semantic" | "combined"
    description: str
    key: str = ""     # lookup key, set when added to taxonomy


DRIFT_TAXONOMY: Dict[str, DriftType] = {
    "none": DriftType("none", "baseline", "No drift — baseline task", "none"),
    "schema_rename": DriftType("minor", "structural", "Field/column renamed"),
    "field_addition": DriftType("minor", "structural", "New required field added"),
    "format_change": DriftType("minor", "surface", "Value format changed (e.g. date, currency)"),
    "api_deprecation": DriftType("moderate", "interface", "Function/API deprecated"),
    "structure_change": DriftType("moderate", "structural", "Nesting or schema structure changed"),
    "logic_change": DriftType("moderate", "semantic", "Business rule or validation changed"),
    "interface_replace": DriftType("major", "interface", "Replacement API differs in signature/behavior"),
    "schema_redesign": DriftType("major", "structural", "Schema restructured (e.g. table split)"),
    "semantic_shift": DriftType("major", "semantic", "Definition or interpretation changed"),
    "combined": DriftType("major", "combined", "Multiple drift types applied"),
}

# Set keys for all entries
for k, v in DRIFT_TAXONOMY.items():
    v.key = k


def get_drift_type(key: str) -> Optional[DriftType]:
    """Look up drift type by key."""
    return DRIFT_TAXONOMY.get(key)


def drift_types_by_level(level: str) -> list:
    """Return all drift type keys for a given level."""
    return [k for k, v in DRIFT_TAXONOMY.items() if v.level == level]


def drift_types_by_category(category: str) -> list:
    """Return all drift type keys for a given category."""
    return [k for k, v in DRIFT_TAXONOMY.items() if v.category == category]
