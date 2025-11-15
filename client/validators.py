"""Minimal validators for guardrails."""

import re
from typing import List

from client.base import ValidationResult


class SecurityValidator:
    """Basic security validator."""

    def validate_code(self, code: str) -> ValidationResult:
        """Validate code for security issues."""
        errors: List[str] = []
        warnings: List[str] = []

        # Check for dangerous patterns
        dangerous_patterns = [
            (r"eval\s*\(", "eval() usage"),
            (r"exec\s*\(", "exec() usage"),
            (r"__import__\s*\(", "__import__() usage"),
            (r"open\s*\([^)]*['\"][rw]\+?['\"]", "File write access"),
        ]

        for pattern, description in dangerous_patterns:
            if re.search(pattern, code):
                errors.append(f"Security risk: {description}")

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)


class PathValidator:
    """Basic path validator."""

    def __init__(self, allowed_dirs: List[str] = None):
        """Initialize path validator."""
        self.allowed_dirs = allowed_dirs or []

    def validate_path(self, path: str) -> ValidationResult:
        """Validate file path."""
        errors: List[str] = []
        warnings: List[str] = []

        # Check for path traversal
        if ".." in path or path.startswith("/"):
            errors.append("Path traversal detected")

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)


class SchemaValidator:
    """Basic schema validator."""

    def validate_against_schema(self, data, schema) -> ValidationResult:
        """Validate data against schema."""
        # Minimal implementation - always valid
        return ValidationResult(valid=True, errors=[], warnings=[])

