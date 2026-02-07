"""Base executor class with common functionality."""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from pathlib import Path

from client.base import CodeExecutor, ExecutionResult, ValidationResult
from client.guardrails import GuardrailValidatorImpl
from config.schema import ExecutionConfig, GuardrailConfig, OptimizationConfig

logger = logging.getLogger(__name__)


class BaseExecutor(CodeExecutor, ABC):
    """Base class for code executors providing common validation logic."""

    def __init__(
        self,
        execution_config: ExecutionConfig,
        guardrail_config: Optional[GuardrailConfig] = None,
        optimization_config: Optional[OptimizationConfig] = None,
    ):
        """Initialize executor.
        
        Args:
            execution_config: Execution configuration
            guardrail_config: Guardrail configuration
            optimization_config: Optimization configuration
        """
        self.execution_config = execution_config
        self.guardrail_config = guardrail_config or GuardrailConfig()
        self.optimization_config = optimization_config or OptimizationConfig()
        self.guardrail_validator = GuardrailValidatorImpl(self.guardrail_config)

    def validate_code(self, code: str) -> ValidationResult:
        """Validate code before execution."""
        guardrail_result = self.guardrail_validator.validate_code(code, {})
        return ValidationResult(
            valid=len(guardrail_result.errors) == 0,
            errors=guardrail_result.errors,
            warnings=guardrail_result.warnings,
        )

    def _find_project_root(self) -> Path:
        """Find project root by looking for marker files."""
        current = Path.cwd().resolve()
        
        # Check current directory and parents
        for path in [current] + list(current.parents):
            # Look for project markers
            markers = ["pyproject.toml", "requirements.txt", ".git", "setup.py"]
            if any((path / marker).exists() for marker in markers):
                # Also verify client directory exists
                if (path / "client").exists():
                    return path
        
        if (current / "client").exists():
            return current
        
        logger.warning(f"Could not find project root, using current directory: {current}")
        return current
