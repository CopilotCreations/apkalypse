"""
Ingestion Service.

Handles APK intake, normalization, hash computation, and provenance tracking.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET
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
        """Compute SHA-256, SHA-1, and MD5 hashes of a file.

        Args:
            file_path: Path to the file to hash.

        Returns:
            A tuple containing (sha256_hash, sha1_hash, md5_hash) as hex strings.
        """
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
        """Validate that the file is a valid APK.

        Checks that the file exists, has an .apk extension, is a valid ZIP archive,
        and contains required APK files (AndroidManifest.xml and DEX files).

        Args:
            apk_path: Path to the APK file to validate.

        Raises:
            ValidationError: If the APK is invalid or missing required files.
        """
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
        """Extract basic info from APK without full decompilation.

        Extracts file size, resource counts, and detects common embedded libraries
        by inspecting the APK's ZIP contents.

        Args:
            apk_path: Path to the APK file.

        Returns:
            A dictionary containing file_size, file_name, resource_counts,
            and embedded_libraries.
        """
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


class QuickAPKInfo(BaseModel):
    """Quick APK metadata extracted without full analysis."""

    package_name: str = Field(description="Package name from AndroidManifest.xml")
    app_name: str = Field(description="Application label or derived name")


def extract_quick_apk_info(apk_path: Path) -> QuickAPKInfo:
    """Extract package name and app name from APK without full decompilation.

    This uses aapt2 if available, otherwise falls back to apktool or manual extraction.

    Args:
        apk_path: Path to the APK file

    Returns:
        QuickAPKInfo with package_name and app_name
    """
    import shutil

    package_name = "unknown"
    app_name = ""

    # Try aapt2 first (fastest)
    aapt2 = shutil.which("aapt2")
    logger.info("Checking for aapt2", found=bool(aapt2), path=aapt2)
    if aapt2:
        try:
            logger.info("Running aapt2 dump badging...")
            result = subprocess.run(
                [aapt2, "dump", "badging", str(apk_path)],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                logger.info("aapt2 succeeded")
                output = result.stdout
                # Extract package name
                pkg_match = re.search(r"package:\s*name='([^']+)'", output)
                if pkg_match:
                    package_name = pkg_match.group(1)
                # Extract application label
                label_match = re.search(r"application-label:'([^']+)'", output)
                if label_match:
                    app_name = label_match.group(1)
            else:
                logger.warning("aapt2 failed", returncode=result.returncode, stderr=result.stderr[:200] if result.stderr else None)
        except subprocess.TimeoutExpired:
            logger.warning("aapt2 timed out after 30s")
        except FileNotFoundError:
            logger.warning("aapt2 not found")

    # Try aapt if aapt2 didn't work
    if package_name == "unknown":
        aapt = shutil.which("aapt")
        logger.info("Checking for aapt", found=bool(aapt), path=aapt)
        if aapt:
            try:
                logger.info("Running aapt dump badging...")
                result = subprocess.run(
                    [aapt, "dump", "badging", str(apk_path)],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if result.returncode == 0:
                    logger.info("aapt succeeded")
                    output = result.stdout
                    pkg_match = re.search(r"package:\s*name='([^']+)'", output)
                    if pkg_match:
                        package_name = pkg_match.group(1)
                    label_match = re.search(r"application-label:'([^']+)'", output)
                    if label_match:
                        app_name = label_match.group(1)
                else:
                    logger.warning("aapt failed", returncode=result.returncode, stderr=result.stderr[:200] if result.stderr else None)
            except subprocess.TimeoutExpired:
                logger.warning("aapt timed out after 30s")
            except FileNotFoundError:
                logger.warning("aapt not found")

    # Fallback: try apktool decode + parse XML
    if package_name == "unknown":
        apktool = shutil.which("apktool")
        logger.info("Checking for apktool", found=bool(apktool), path=apktool)
        if apktool:
            try:
                logger.info("Running apktool decode (this may take a while)...")
                with tempfile.TemporaryDirectory() as temp_dir:
                    temp_path = Path(temp_dir)
                    result = subprocess.run(
                        [apktool, "d", "-s", "-f", "-o", str(temp_path / "decoded"), str(apk_path)],
                        capture_output=True,
                        text=True,
                        timeout=120,
                    )
                    if result.returncode == 0:
                        logger.info("apktool decode succeeded")
                        manifest_path = temp_path / "decoded" / "AndroidManifest.xml"
                        if manifest_path.exists():
                            package_name, app_name = _parse_manifest_quick(manifest_path, app_name)
                    else:
                        logger.warning("apktool decode failed", returncode=result.returncode, stderr=result.stderr[:200] if result.stderr else None)
            except subprocess.TimeoutExpired:
                logger.warning("apktool timed out after 120s")
            except FileNotFoundError:
                logger.warning("apktool not found")
        else:
            logger.warning("No APK extraction tools found (aapt2, aapt, or apktool)")

    # Final fallback: derive app name from APK filename if still empty
    if not app_name:
        logger.info("Deriving app name from filename")
        # Convert filename to readable app name
        stem = apk_path.stem
        # Remove common suffixes like version numbers, _signed, etc.
        stem = re.sub(r'[_-]?(v?\d+[\d.]*|signed|release|debug|unsigned)$', '', stem, flags=re.IGNORECASE)
        # Convert underscores/hyphens to spaces and title case
        app_name = stem.replace('_', ' ').replace('-', ' ').title()

    logger.info("APK info extraction complete", package_name=package_name, app_name=app_name)
    return QuickAPKInfo(package_name=package_name, app_name=app_name)


def _parse_manifest_quick(manifest_path: Path, existing_app_name: str) -> tuple[str, str]:
    """Parse AndroidManifest.xml quickly for package name and app label.

    Args:
        manifest_path: Path to the decoded AndroidManifest.xml file.
        existing_app_name: Previously extracted app name to use as fallback.

    Returns:
        A tuple containing (package_name, app_name). Returns "unknown" for
        package_name if parsing fails.
    """
    package_name = "unknown"
    app_name = existing_app_name

    try:
        tree = ET.parse(manifest_path)
        root = tree.getroot()
        package_name = root.get("package", "unknown")

        if not app_name:
            ns = {"android": "http://schemas.android.com/apk/res/android"}
            application = root.find("application")
            if application is not None:
                label = application.get(f"{{{ns['android']}}}label", "")
                if label and not label.startswith("@"):
                    app_name = label
    except ET.ParseError:
        pass

    return package_name, app_name
