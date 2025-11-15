"""Guardrails integration and validators."""

import re
import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from client.base import GuardrailValidator, ValidationResult
from client.validators import SecurityValidator, PathValidator, SchemaValidator
from config.schema import GuardrailConfig

logger = logging.getLogger(__name__)


@dataclass
class PIIToken:
    """Represents a tokenized PII value."""

    token: str
    original_value: str
    pii_type: str


class PIIDetector:
    """Detects and tokenizes PII in data."""

    # Patterns for common PII
    EMAIL_PATTERN = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
    PHONE_PATTERN = r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"
    SSN_PATTERN = r"\b\d{3}-\d{2}-\d{4}\b"
    CREDIT_CARD_PATTERN = r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b"

    def __init__(self):
        """Initialize PII detector."""
        self.token_map: Dict[str, PIIToken] = {}
        self.token_counter = 0

    def detect_pii(self, text: str) -> List[Dict[str, str]]:
        """Detect PII in text."""
        detected: List[Dict[str, str]] = []

        # Check for emails
        for match in re.finditer(self.EMAIL_PATTERN, text):
            detected.append({"type": "email", "value": match.group(), "start": match.start()})

        # Check for phones
        for match in re.finditer(self.PHONE_PATTERN, text):
            detected.append({"type": "phone", "value": match.group(), "start": match.start()})

        # Check for SSN
        for match in re.finditer(self.SSN_PATTERN, text):
            detected.append({"type": "ssn", "value": match.group(), "start": match.start()})

        # Check for credit cards
        for match in re.finditer(self.CREDIT_CARD_PATTERN, text):
            detected.append({"type": "credit_card", "value": match.group(), "start": match.start()})

        return detected

    def tokenize(self, value: str, pii_type: str) -> str:
        """Tokenize a PII value."""
        token = f"[{pii_type.upper()}_{self.token_counter}]"
        self.token_counter += 1
        self.token_map[token] = PIIToken(token=token, original_value=value, pii_type=pii_type)
        return token

    def untokenize(self, token: str) -> Optional[str]:
        """Untokenize a token back to original value."""
        pii_token = self.token_map.get(token)
        return pii_token.original_value if pii_token else None

    def tokenize_data(self, data: Any) -> Any:
        """Recursively tokenize PII in data structures."""
        if isinstance(data, str):
            detected = self.detect_pii(data)
            if detected:
                result = data
                # Replace from end to start to preserve indices
                for item in reversed(detected):
                    token = self.tokenize(item["value"], item["type"])
                    result = result[: item["start"]] + token + result[item["start"] + len(item["value"]) :]
                return result
            return data
        elif isinstance(data, dict):
            return {k: self.tokenize_data(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self.tokenize_data(item) for item in data]
        else:
            return data


class GuardrailValidatorImpl(GuardrailValidator):
    """Implementation of guardrail validator."""

    def __init__(self, config: GuardrailConfig):
        """Initialize guardrail validator."""
        self.config = config
        self.security_validator = SecurityValidator()
        self.path_validator = PathValidator(
            allowed_dirs=config.allowed_networks if hasattr(config, "allowed_networks") else []
        )
        self.schema_validator = SchemaValidator()
        self.pii_detector = PIIDetector() if config.pii_detection else None

    def validate_input(self, data: Any, context: Dict[str, Any]) -> ValidationResult:
        """Validate input data."""
        if not self.config.enabled:
            return ValidationResult(valid=True, errors=[], warnings=[])

        errors: List[str] = []
        warnings: List[str] = []

        # Content filtering
        if self.config.content_filtering:
            if isinstance(data, str):
                # Check for blocked patterns
                for pattern in self.config.blocked_patterns:
                    if pattern in data:
                        errors.append(f"Blocked pattern detected in input: {pattern}")

        # Privacy protection
        if self.config.privacy_protection and self.pii_detector:
            if isinstance(data, (str, dict, list)):
                detected = self.pii_detector.detect_pii(str(data))
                if detected:
                    if self.config.strict_mode:
                        errors.append("PII detected in input data")
                    else:
                        warnings.append(f"PII detected in input: {len(detected)} items")

        # Schema validation if provided
        if "schema" in context:
            schema_result = self.schema_validator.validate_against_schema(data, context["schema"])
            errors.extend(schema_result.errors)
            warnings.extend(schema_result.warnings)

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    def validate_output(self, data: Any, context: Dict[str, Any]) -> ValidationResult:
        """Validate output data."""
        if not self.config.enabled:
            return ValidationResult(valid=True, errors=[], warnings=[])

        errors: List[str] = []
        warnings: List[str] = []

        # Content filtering
        if self.config.content_filtering:
            if isinstance(data, str):
                for pattern in self.config.blocked_patterns:
                    if pattern in data:
                        errors.append(f"Blocked pattern detected in output: {pattern}")

        # Schema validation if provided
        if "schema" in context:
            schema_result = self.schema_validator.validate_against_schema(data, context["schema"])
            errors.extend(schema_result.errors)
            warnings.extend(schema_result.warnings)

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    def validate_code(self, code: str, context: Dict[str, Any]) -> ValidationResult:
        """Validate code before execution."""
        if not self.config.enabled:
            return ValidationResult(valid=True, errors=[], warnings=[])

        errors: List[str] = []
        warnings: List[str] = []

        # Security checks
        if self.config.security_checks:
            security_result = self.security_validator.validate_code(code)
            errors.extend(security_result.errors)
            warnings.extend(security_result.warnings)

        # Check blocked patterns
        for pattern in self.config.blocked_patterns:
            if pattern in code:
                errors.append(f"Blocked pattern detected in code: {pattern}")

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    def tokenize_sensitive_data(self, data: Any) -> Any:
        """Tokenize sensitive data in the input."""
        if self.pii_detector:
            return self.pii_detector.tokenize_data(data)
        return data

    def untokenize_sensitive_data(self, data: Any) -> Any:
        """Untokenize sensitive data in the output."""
        if not self.pii_detector:
            return data

        if isinstance(data, str):
            # Find all tokens and replace them
            tokens = re.findall(r"\[[A-Z_]+\d+\]", data)
            for token in tokens:
                original = self.pii_detector.untokenize(token)
                if original:
                    data = data.replace(token, original)
            return data
        elif isinstance(data, dict):
            return {k: self.untokenize_sensitive_data(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self.untokenize_sensitive_data(item) for item in data]
        else:
            return data

