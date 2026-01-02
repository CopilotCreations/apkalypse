"""
Configuration management for APKalypse.

Provides centralized, type-safe configuration with environment variable overrides
and sensible defaults for all pipeline components.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import BaseModel, Field, SecretStr

# Load .env file if it exists (looks in cwd and parent directories)
load_dotenv()


class EmulatorConfig(BaseModel):
    """Android emulator configuration."""

    avd_name: str = Field(default="APKalypse_avd", description="AVD name to use")
    api_level: int = Field(default=33, ge=26, le=35, description="Android API level")
    system_image: str = Field(
        default="system-images;android-33;google_apis;x86_64",
        description="System image for emulator",
    )
    headless: bool = Field(default=False, description="Run emulator without display")
    gpu: Literal["auto", "host", "swiftshader_indirect", "off"] = Field(
        default="swiftshader_indirect", description="GPU acceleration mode"
    )
    memory_mb: int = Field(default=4096, ge=2048, description="Emulator RAM in MB")
    boot_timeout_seconds: int = Field(default=180, ge=60, description="Boot timeout")
    adb_port: int = Field(default=5554, description="ADB port")


class AgentConfig(BaseModel):
    """LLM agent configuration."""

    provider: Literal["openai", "anthropic", "azure_openai"] = Field(
        default="openai", description="LLM provider"
    )
    # Azure OpenAI specific settings
    azure_endpoint: str | None = Field(default=None, description="Azure OpenAI endpoint URL")
    azure_api_version: str = Field(default="2024-02-15-preview", description="Azure OpenAI API version")
    azure_deployment_name: str | None = Field(default=None, description="Azure OpenAI deployment name")
    model: str = Field(default="gpt-4o", description="Model identifier")
    temperature: float = Field(default=0.1, ge=0.0, le=2.0, description="Sampling temperature")
    max_tokens: int = Field(default=8192, ge=256, description="Max output tokens")
    max_retries: int = Field(default=3, ge=1, description="Retry attempts on failure")
    timeout_seconds: int = Field(default=120, ge=30, description="Request timeout")


class StorageConfig(BaseModel):
    """Storage configuration for artifacts."""

    backend: Literal["local", "s3"] = Field(default="local", description="Storage backend")
    base_path: Path = Field(
        default=Path("./output"), description="Base path for local storage"
    )
    s3_bucket: str | None = Field(default=None, description="S3 bucket for remote storage")
    s3_prefix: str = Field(default="APKalypse/", description="S3 key prefix")
    retention_days: int = Field(default=30, ge=1, description="Artifact retention period")


class ToolsConfig(BaseModel):
    """External tools configuration."""

    android_sdk_root: Path = Field(
        default_factory=lambda: Path(os.environ.get("ANDROID_SDK_ROOT", "~/Android/Sdk")).expanduser(),
        description="Android SDK root path",
    )
    apktool_path: Path | None = Field(default=None, description="Custom apktool path")
    jadx_path: Path | None = Field(default=None, description="Custom jadx path")
    frida_server_path: Path | None = Field(default=None, description="Frida server binary path")


class ComplianceConfig(BaseModel):
    """Compliance and legal safety configuration."""

    max_source_similarity_threshold: float = Field(
        default=0.15,
        ge=0.0,
        le=1.0,
        description="Maximum allowed similarity to decompiled source",
    )
    purge_decompiled_after_analysis: bool = Field(
        default=True, description="Delete decompiled artifacts after use"
    )
    audit_log_enabled: bool = Field(default=True, description="Enable compliance audit logging")
    block_on_violation: bool = Field(
        default=True, description="Block pipeline on compliance violation"
    )


class PipelineConfig(BaseModel):
    """Pipeline execution configuration."""

    parallel_stages: bool = Field(
        default=False, description="Enable parallel stage execution where possible"
    )
    checkpoint_enabled: bool = Field(default=True, description="Enable stage checkpointing")
    fail_fast: bool = Field(default=True, description="Stop pipeline on first error")
    dry_run: bool = Field(default=False, description="Validate without executing")


class Config(BaseModel):
    """Root configuration for APKalypse."""

    project_name: str = Field(default="APKalypse", description="Project identifier")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO", description="Logging level"
    )
    emulator: EmulatorConfig = Field(default_factory=EmulatorConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    compliance: ComplianceConfig = Field(default_factory=ComplianceConfig)
    pipeline: PipelineConfig = Field(default_factory=PipelineConfig)

    # API Keys (loaded from environment)
    openai_api_key: SecretStr | None = Field(
        default_factory=lambda: SecretStr(os.environ.get("OPENAI_API_KEY", "")) or None
    )
    anthropic_api_key: SecretStr | None = Field(
        default_factory=lambda: SecretStr(os.environ.get("ANTHROPIC_API_KEY", "")) or None
    )
    azure_openai_api_key: SecretStr | None = Field(
        default_factory=lambda: SecretStr(os.environ.get("AZURE_OPENAI_API_KEY", "")) or None
    )

    model_config = {"extra": "ignore"}

    @classmethod
    def from_env(cls) -> Config:
        """Create configuration from environment variables."""
        return cls(
            log_level=os.environ.get("B2B_LOG_LEVEL", "INFO"),  # type: ignore
            emulator=EmulatorConfig(
                headless=os.environ.get("B2B_EMULATOR_HEADLESS", "true").lower() == "true",
                api_level=int(os.environ.get("B2B_EMULATOR_API_LEVEL", "33")),
            ),
            agent=AgentConfig(
                provider=os.environ.get("B2B_AGENT_PROVIDER", "openai"),  # type: ignore
                model=os.environ.get("B2B_AGENT_MODEL", "gpt-4o"),
                temperature=float(os.environ.get("B2B_AGENT_TEMPERATURE", "0.1")),
                azure_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT"),
                azure_api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
                azure_deployment_name=os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME"),
            ),
            storage=StorageConfig(
                base_path=Path(os.environ.get("B2B_OUTPUT_PATH", "./output")),
            ),
            compliance=ComplianceConfig(
                block_on_violation=os.environ.get("B2B_COMPLIANCE_STRICT", "true").lower() == "true",
            ),
        )


@lru_cache(maxsize=1)
def get_config() -> Config:
    """Get cached configuration instance."""
    return Config.from_env()
