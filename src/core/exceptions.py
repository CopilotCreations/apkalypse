"""
Custom exception hierarchy for APKalypse.

All exceptions inherit from APKalypseError to enable consistent error handling
across the pipeline. Each exception type includes context for debugging and logging.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class APKalypseError(Exception):
    """Base exception for all APKalypse errors."""

    message: str
    context: dict[str, Any] = field(default_factory=dict)
    cause: Exception | None = None

    def __str__(self) -> str:
        ctx = f" | context: {self.context}" if self.context else ""
        cause = f" | caused by: {self.cause}" if self.cause else ""
        return f"{self.message}{ctx}{cause}"


@dataclass
class ValidationError(APKalypseError):
    """Raised when input or output validation fails."""

    field_name: str | None = None
    expected_type: str | None = None
    actual_value: Any = None

    def __str__(self) -> str:
        base = super().__str__()
        if self.field_name:
            return f"Validation failed for '{self.field_name}': {base}"
        return f"Validation failed: {base}"


@dataclass
class ServiceError(APKalypseError):
    """Raised when a service operation fails."""

    service_name: str = ""
    operation: str = ""
    retryable: bool = False

    def __str__(self) -> str:
        base = super().__str__()
        retry_hint = " (retryable)" if self.retryable else " (non-retryable)"
        return f"[{self.service_name}.{self.operation}]{retry_hint}: {base}"


@dataclass
class PipelineError(APKalypseError):
    """Raised when pipeline orchestration fails."""

    stage: str = ""
    pipeline_run_id: str = ""

    def __str__(self) -> str:
        base = super().__str__()
        return f"Pipeline error at stage '{self.stage}' (run: {self.pipeline_run_id}): {base}"


@dataclass
class ComplianceViolationError(APKalypseError):
    """Raised when a compliance rule is violated.

    This is a critical error that blocks pipeline execution when strict
    compliance mode is enabled.
    """

    rule_id: str = ""
    artifact_path: str = ""
    violation_type: str = ""

    def __str__(self) -> str:
        return (
            f"COMPLIANCE VIOLATION [{self.rule_id}]: {self.message} | "
            f"type: {self.violation_type} | artifact: {self.artifact_path}"
        )


@dataclass
class EmulatorError(ServiceError):
    """Raised when emulator operations fail."""

    avd_name: str = ""
    adb_port: int = 0

    def __post_init__(self) -> None:
        self.service_name = "emulator"


@dataclass
class ToolNotFoundError(APKalypseError):
    """Raised when a required external tool is not available."""

    tool_name: str = ""
    expected_path: str = ""
    install_hint: str = ""

    def __str__(self) -> str:
        hint = f" Install hint: {self.install_hint}" if self.install_hint else ""
        return f"Tool '{self.tool_name}' not found at '{self.expected_path}'.{hint}"


@dataclass
class AgentError(ServiceError):
    """Raised when an LLM agent operation fails."""

    agent_name: str = ""
    prompt_hash: str = ""

    def __post_init__(self) -> None:
        self.service_name = "agent"

    def __str__(self) -> str:
        base = super().__str__()
        return f"[Agent: {self.agent_name}] {base}"
