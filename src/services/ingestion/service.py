"""
Ingestion Service.

Handles APK intake, normalization, hash computation, and provenance tracking.
"""

from __future__ import annotations

import hashlib
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from ...core.exceptions import ServiceError, ValidationError
from ...core.logging import get_logger
from ...core.types import ServiceResult
from ...models.apk import APKMetadata, APKProvenance, ManifestData, PlayStoreMetadata
from ...storage import StorageBackend

logger = get_logger(__name__)


class IngestionInput(BaseModel):
    """Input for the ingestion service."""

    apk_path: Path = Field(description="Path to APK file")
    play_store_url: str | None = Field(default=None, description="Google Play Store URL")
    screenshots: list[Path] = Field(default_factory=list, description="Screenshot files")
    additional_metadata: dict[str, Any] = Field(default_factory=dict)


class IngestionOutput(BaseModel):
    """Output from the ingestion service."""

    apk_metadata: APKMetadata
    normalized_apk_path: str = Field(description="Storage key for normalized APK")
    screenshots_keys: list[str] = Field(default_factory=list)


class IngestionService:
    """Service for ingesting and normalizing APK inputs.

    This service:
    1. Validates APK file integrity
    2. Computes cryptographic hashes
    3. Extracts basic metadata
    4. Stores normalized inputs
    5. Creates provenance records
    """

    def __init__(self, storage: StorageBackend) -> None:
        """Initialize the ingestion service.

        Args:
            storage: Storage backend for artifacts
        """
        self.storage = storage

    def _compute_file_hashes(self, file_path: Path) -> tuple[str, str, str]:
        """Compute SHA-256, SHA-1, and MD5 hashes of a file."""
        sha256 = hashlib.sha256()
        sha1 = hashlib.sha1()
        md5 = hashlib.md5()

        with open(file_path, "rb") as f:
            while chunk := f.read(8192):
                sha256.update(chunk)
                sha1.update(chunk)
                md5.update(chunk)

        return sha256.hexdigest(), sha1.hexdigest(), md5.hexdigest()

    def _validate_apk(self, apk_path: Path) -> None:
        """Validate that the file is a valid APK."""
        if not apk_path.exists():
            raise ValidationError(
                message=f"APK file not found: {apk_path}",
                field_name="apk_path",
            )

        if not apk_path.suffix.lower() == ".apk":
            raise ValidationError(
                message=f"File is not an APK: {apk_path}",
                field_name="apk_path",
            )

        # Verify it's a valid ZIP file (APKs are ZIP archives)
        try:
            with zipfile.ZipFile(apk_path, "r") as zf:
                # Check for required APK files
                names = zf.namelist()
                if "AndroidManifest.xml" not in names:
                    raise ValidationError(
                        message="Invalid APK: missing AndroidManifest.xml",
                        field_name="apk_path",
                    )
                if "classes.dex" not in names and not any(n.startswith("classes") and n.endswith(".dex") for n in names):
                    raise ValidationError(
                        message="Invalid APK: missing DEX files",
                        field_name="apk_path",
                    )
        except zipfile.BadZipFile:
            raise ValidationError(
                message="Invalid APK: not a valid ZIP archive",
                field_name="apk_path",
            )

    def _extract_basic_info(self, apk_path: Path) -> dict[str, Any]:
        """Extract basic info from APK without full decompilation."""
        info = {
            "file_size": apk_path.stat().st_size,
            "file_name": apk_path.name,
        }

        with zipfile.ZipFile(apk_path, "r") as zf:
            # Count resources
            info["resource_counts"] = {
                "dex_files": len([n for n in zf.namelist() if n.endswith(".dex")]),
                "assets": len([n for n in zf.namelist() if n.startswith("assets/")]),
                "resources": len([n for n in zf.namelist() if n.startswith("res/")]),
                "native_libs": len([n for n in zf.namelist() if n.startswith("lib/") and n.endswith(".so")]),
            }

            # Detect embedded libraries
            info["embedded_libraries"] = []
            if any("kotlin" in n.lower() for n in zf.namelist()):
                info["embedded_libraries"].append("kotlin")
            if any("okhttp" in n.lower() for n in zf.namelist()):
                info["embedded_libraries"].append("okhttp")
            if any("retrofit" in n.lower() for n in zf.namelist()):
                info["embedded_libraries"].append("retrofit")
            if any("rxjava" in n.lower() or "rxandroid" in n.lower() for n in zf.namelist()):
                info["embedded_libraries"].append("rxjava")

        return info

    async def ingest(self, input_data: IngestionInput) -> ServiceResult[IngestionOutput]:
        """Ingest an APK and associated metadata.

        Args:
            input_data: Ingestion input with APK path and metadata

        Returns:
            ServiceResult containing IngestionOutput or error
        """
        import time

        start_time = time.perf_counter()

        try:
            logger.info("Starting APK ingestion", apk_path=str(input_data.apk_path))

            # Validate APK
            self._validate_apk(input_data.apk_path)

            # Compute hashes
            sha256, sha1, md5 = self._compute_file_hashes(input_data.apk_path)
            logger.info("Computed file hashes", sha256=sha256[:16])

            # Create provenance record
            provenance = APKProvenance(
                sha256_hash=sha256,
                sha1_hash=sha1,
                md5_hash=md5,
                file_size_bytes=input_data.apk_path.stat().st_size,
                file_name=input_data.apk_path.name,
                acquired_at=datetime.utcnow(),
                play_store_url=input_data.play_store_url,
            )

            # Extract basic info
            basic_info = self._extract_basic_info(input_data.apk_path)

            # Create placeholder manifest (will be filled by static analysis)
            manifest = ManifestData(
                package_name=f"unknown.{sha256[:8]}",  # Placeholder
            )

            # Create metadata object
            metadata = APKMetadata(
                provenance=provenance,
                manifest=manifest,
                play_store=PlayStoreMetadata() if input_data.play_store_url else None,
                analysis_timestamp=datetime.utcnow(),
                embedded_libraries=basic_info.get("embedded_libraries", []),
                resource_counts=basic_info.get("resource_counts", {}),
            )

            # Store APK
            apk_key = f"apks/{sha256}/{input_data.apk_path.name}"
            with open(input_data.apk_path, "rb") as f:
                await self.storage.store_bytes(apk_key, f.read(), {"provenance": provenance.model_dump()})

            # Store metadata
            metadata_key = f"apks/{sha256}/metadata.json"
            await self.storage.store_model(metadata_key, metadata)

            # Store screenshots
            screenshot_keys = []
            for i, screenshot_path in enumerate(input_data.screenshots):
                if screenshot_path.exists():
                    key = f"apks/{sha256}/screenshots/{i:03d}_{screenshot_path.name}"
                    with open(screenshot_path, "rb") as f:
                        await self.storage.store_bytes(key, f.read())
                    screenshot_keys.append(key)

            output = IngestionOutput(
                apk_metadata=metadata,
                normalized_apk_path=apk_key,
                screenshots_keys=screenshot_keys,
            )

            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.info(
                "APK ingestion completed",
                sha256=sha256[:16],
                duration_ms=duration_ms,
            )

            return ServiceResult.ok(output, duration_ms=duration_ms)

        except ValidationError as e:
            return ServiceResult.fail(str(e))
        except Exception as e:
            logger.error("Ingestion failed", error=str(e))
            raise ServiceError(
                message=f"Ingestion failed: {e}",
                service_name="ingestion",
                operation="ingest",
                cause=e,
            )
