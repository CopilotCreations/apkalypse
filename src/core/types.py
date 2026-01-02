"""
Core type definitions for Behavior2Build.

Provides type aliases and result types used throughout the pipeline
for type-safe data flow between stages.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field


# Type aliases
ArtifactPath = Path
Hash = str  # SHA-256 hash


class StageStatus(str, Enum):
    """Status of a pipeline stage."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


T = TypeVar("T")


@dataclass
class ServiceResult(Generic[T]):
    """Result wrapper for service operations.

    Provides a consistent return type that includes success/failure status,
    the result data, and any errors or warnings.
    """

    success: bool
    data: T | None = None
    error: str | None = None
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0

    @classmethod
    def ok(cls, data: T, **metadata: Any) -> ServiceResult[T]:
        """Create a successful result."""
        return cls(success=True, data=data, metadata=metadata)

    @classmethod
    def fail(cls, error: str, **metadata: Any) -> ServiceResult[T]:
        """Create a failed result."""
        return cls(success=False, error=error, metadata=metadata)

    @classmethod
    def with_warnings(cls, data: T, warnings: list[str], **metadata: Any) -> ServiceResult[T]:
        """Create a successful result with warnings."""
        return cls(success=True, data=data, warnings=warnings, metadata=metadata)


class StageResult(BaseModel):
    """Result of a pipeline stage execution."""

    stage_name: str = Field(description="Name of the pipeline stage")
    status: StageStatus = Field(description="Execution status")
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = Field(default=None)
    duration_seconds: float = Field(default=0.0)
    input_hash: Hash = Field(default="", description="Hash of stage input")
    output_hash: Hash = Field(default="", description="Hash of stage output")
    artifacts: list[ArtifactPath] = Field(default_factory=list, description="Generated artifacts")
    error_message: str | None = Field(default=None)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def mark_completed(self, output_hash: Hash, artifacts: list[ArtifactPath]) -> None:
        """Mark stage as successfully completed."""
        self.status = StageStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        self.output_hash = output_hash
        self.artifacts = artifacts
        if self.started_at:
            self.duration_seconds = (self.completed_at - self.started_at).total_seconds()

    def mark_failed(self, error: str) -> None:
        """Mark stage as failed."""
        self.status = StageStatus.FAILED
        self.completed_at = datetime.utcnow()
        self.error_message = error
        if self.started_at:
            self.duration_seconds = (self.completed_at - self.started_at).total_seconds()


class PipelineRun(BaseModel):
    """Represents a complete pipeline execution."""

    run_id: str = Field(description="Unique run identifier")
    apk_hash: Hash = Field(description="SHA-256 hash of input APK")
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = Field(default=None)
    stages: list[StageResult] = Field(default_factory=list)
    final_status: StageStatus = Field(default=StageStatus.PENDING)
    compliance_passed: bool = Field(default=False)

    def get_stage(self, name: str) -> StageResult | None:
        """Get a stage result by name."""
        for stage in self.stages:
            if stage.stage_name == name:
                return stage
        return None
