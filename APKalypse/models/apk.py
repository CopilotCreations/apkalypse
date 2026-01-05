"""
APK-related data models.

These models represent metadata and structure extracted from Android APKs,
focusing on observable properties rather than implementation details.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class PermissionCategory(str, Enum):
    """Categories of Android permissions."""

    NORMAL = "normal"
    DANGEROUS = "dangerous"
    SIGNATURE = "signature"
    PRIVILEGED = "privileged"


class PermissionInfo(BaseModel):
    """Information about an Android permission."""

    name: str = Field(description="Full permission name (e.g., android.permission.CAMERA)")
    category: PermissionCategory = Field(description="Permission protection level")
    required: bool = Field(default=True, description="Whether the permission is required")
    max_sdk_version: int | None = Field(default=None, description="Max SDK where permission applies")
    description: str = Field(default="", description="Human-readable description")

    @property
    def short_name(self) -> str:
        """Get short permission name without android.permission prefix.

        Returns:
            str: The permission name with the 'android.permission.' prefix removed.
        """
        return self.name.replace("android.permission.", "")


class ActivityInfo(BaseModel):
    """Information about an Android Activity."""

    name: str = Field(description="Fully qualified class name")
    exported: bool = Field(default=False, description="Whether activity is exported")
    launch_mode: str = Field(default="standard", description="Activity launch mode")
    intent_filters: list[IntentFilterInfo] = Field(default_factory=list)
    is_launcher: bool = Field(default=False, description="Is this the launcher activity")
    theme: str | None = Field(default=None, description="Activity theme")
    label: str | None = Field(default=None, description="Activity label")

    @property
    def simple_name(self) -> str:
        """Get simple class name without package.

        Returns:
            str: The class name without the package prefix
                (e.g., 'MainActivity' from 'com.example.MainActivity').
        """
        return self.name.split(".")[-1]


class IntentFilterInfo(BaseModel):
    """Information about an Intent filter."""

    actions: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    data_schemes: list[str] = Field(default_factory=list)
    data_hosts: list[str] = Field(default_factory=list)
    data_paths: list[str] = Field(default_factory=list)


class ServiceInfo(BaseModel):
    """Information about an Android Service."""

    name: str = Field(description="Fully qualified class name")
    exported: bool = Field(default=False)
    intent_filters: list[IntentFilterInfo] = Field(default_factory=list)
    foreground_service_type: str | None = Field(default=None)


class ReceiverInfo(BaseModel):
    """Information about a Broadcast Receiver."""

    name: str = Field(description="Fully qualified class name")
    exported: bool = Field(default=False)
    intent_filters: list[IntentFilterInfo] = Field(default_factory=list)


class ProviderInfo(BaseModel):
    """Information about a Content Provider."""

    name: str = Field(description="Fully qualified class name")
    authorities: list[str] = Field(default_factory=list)
    exported: bool = Field(default=False)
    grant_uri_permissions: bool = Field(default=False)


class ManifestData(BaseModel):
    """Parsed AndroidManifest.xml data."""

    package_name: str = Field(description="Application package name")
    version_code: int = Field(default=1)
    version_name: str = Field(default="1.0")
    min_sdk_version: int = Field(default=21)
    target_sdk_version: int = Field(default=33)
    compile_sdk_version: int | None = Field(default=None)
    
    application_label: str = Field(default="", description="App display name")
    application_icon: str = Field(default="", description="Icon resource reference")
    application_theme: str = Field(default="", description="App theme reference")
    
    permissions: list[PermissionInfo] = Field(default_factory=list)
    activities: list[ActivityInfo] = Field(default_factory=list)
    services: list[ServiceInfo] = Field(default_factory=list)
    receivers: list[ReceiverInfo] = Field(default_factory=list)
    providers: list[ProviderInfo] = Field(default_factory=list)
    
    uses_features: list[str] = Field(default_factory=list)
    uses_libraries: list[str] = Field(default_factory=list)

    @property
    def launcher_activity(self) -> ActivityInfo | None:
        """Get the main launcher activity.

        Returns:
            ActivityInfo | None: The activity marked as the launcher,
                or None if no launcher activity is defined.
        """
        for activity in self.activities:
            if activity.is_launcher:
                return activity
        return None

    @property
    def dangerous_permissions(self) -> list[PermissionInfo]:
        """Get list of dangerous permissions.

        Returns:
            list[PermissionInfo]: All permissions with the DANGEROUS category,
                which require explicit user consent at runtime.
        """
        return [p for p in self.permissions if p.category == PermissionCategory.DANGEROUS]


class APKProvenance(BaseModel):
    """Provenance tracking for APK inputs."""

    sha256_hash: str = Field(description="SHA-256 hash of APK file")
    sha1_hash: str = Field(description="SHA-1 hash of APK file")
    md5_hash: str = Field(description="MD5 hash of APK file")
    file_size_bytes: int = Field(description="APK file size")
    file_name: str = Field(description="Original filename")
    acquired_at: datetime = Field(default_factory=datetime.utcnow)
    source_url: str | None = Field(default=None, description="Download URL if applicable")
    play_store_url: str | None = Field(default=None)
    signing_certificates: list[str] = Field(default_factory=list, description="Certificate fingerprints")


class PlayStoreMetadata(BaseModel):
    """Metadata from Google Play Store."""

    title: str = Field(default="")
    developer: str = Field(default="")
    developer_email: str | None = Field(default=None)
    developer_website: str | None = Field(default=None)
    description: str = Field(default="")
    short_description: str = Field(default="")
    category: str = Field(default="")
    content_rating: str = Field(default="")
    downloads: str = Field(default="")
    rating: float | None = Field(default=None)
    rating_count: int = Field(default=0)
    release_date: str | None = Field(default=None)
    last_updated: str | None = Field(default=None)
    whats_new: str = Field(default="")
    screenshots: list[str] = Field(default_factory=list, description="Screenshot URLs")
    video_url: str | None = Field(default=None)


class APKMetadata(BaseModel):
    """Complete APK metadata combining manifest and external sources."""

    model_version: str = Field(default="1.0.0", description="Schema version for migrations")
    provenance: APKProvenance
    manifest: ManifestData
    play_store: PlayStoreMetadata | None = Field(default=None)
    
    # Analysis metadata
    analysis_timestamp: datetime = Field(default_factory=datetime.utcnow)
    analysis_tool_versions: dict[str, str] = Field(default_factory=dict)
    
    # Additional extracted information
    embedded_libraries: list[str] = Field(default_factory=list)
    detected_frameworks: list[str] = Field(default_factory=list)
    locales: list[str] = Field(default_factory=list)
    resource_counts: dict[str, int] = Field(default_factory=dict)

    class Config:
        json_schema_extra = {
            "title": "APK Metadata",
            "description": "Complete metadata for an analyzed APK"
        }
