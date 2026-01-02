"""
Static Analysis Service.

Extracts structural information from APKs using apktool and aapt2.
Converts resources into structured UI models without persisting decompiled source.
"""

from __future__ import annotations

import asyncio
import re
import shutil
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from ...core.config import get_config
from ...core.exceptions import ServiceError, ToolNotFoundError
from ...core.logging import get_logger
from ...core.types import ServiceResult
from ...models.apk import (
    ActivityInfo,
    APKMetadata,
    IntentFilterInfo,
    ManifestData,
    PermissionCategory,
    PermissionInfo,
    ProviderInfo,
    ReceiverInfo,
    ServiceInfo,
)
from ...storage import StorageBackend

logger = get_logger(__name__)


class UILayoutInfo(BaseModel):
    """Extracted UI layout information."""

    layout_name: str
    layout_type: str  # activity, fragment, include, etc.
    root_element: str
    child_elements: list[str] = Field(default_factory=list)
    referenced_ids: list[str] = Field(default_factory=list)
    referenced_strings: list[str] = Field(default_factory=list)


class StaticAnalysisInput(BaseModel):
    """Input for static analysis."""

    apk_path: str = Field(description="Storage key for APK")
    apk_metadata: APKMetadata


class StaticAnalysisOutput(BaseModel):
    """Output from static analysis."""

    manifest: ManifestData
    layouts: list[UILayoutInfo] = Field(default_factory=list)
    strings: dict[str, str] = Field(default_factory=dict)
    detected_frameworks: list[str] = Field(default_factory=list)


class StaticAnalysisService:
    """Service for static analysis of APK files.

    Uses apktool for resource extraction and aapt2 for manifest parsing.
    Does NOT persist decompiled source code - only derived structural information.
    """

    def __init__(self, storage: StorageBackend) -> None:
        """Initialize the static analysis service."""
        self.storage = storage
        self.config = get_config()
        self._temp_dirs: list[Path] = []

    def _find_tool(self, tool_name: str) -> Path:
        """Find a tool in PATH or configured location."""
        # Check configured paths first
        if tool_name == "apktool" and self.config.tools.apktool_path:
            if self.config.tools.apktool_path.exists():
                return self.config.tools.apktool_path

        if tool_name == "jadx" and self.config.tools.jadx_path:
            if self.config.tools.jadx_path.exists():
                return self.config.tools.jadx_path

        # Check PATH
        tool_path = shutil.which(tool_name)
        if tool_path:
            return Path(tool_path)

        # Check common locations
        common_paths = [
            Path.home() / "tools" / tool_name,
            Path(f"/usr/local/bin/{tool_name}"),
            Path(f"C:/tools/{tool_name}/{tool_name}.bat"),
        ]
        for p in common_paths:
            if p.exists():
                return p

        raise ToolNotFoundError(
            message=f"Tool not found: {tool_name}",
            tool_name=tool_name,
            expected_path=f"PATH or configured location",
            install_hint=f"Install {tool_name} and add to PATH",
        )

    async def _run_command(self, cmd: list[str], cwd: Path | None = None) -> tuple[int, str, str]:
        """Run a shell command asynchronously with real-time output logging."""
        cmd_str = " ".join(cmd)
        logger.info("Running command", command=cmd_str, cwd=str(cwd) if cwd else None)
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        
        stdout_lines: list[str] = []
        stderr_lines: list[str] = []
        
        async def read_stream(stream: asyncio.StreamReader, lines: list[str], stream_name: str) -> None:
            while True:
                line = await stream.readline()
                if not line:
                    break
                decoded = line.decode("utf-8", errors="replace").rstrip()
                lines.append(decoded)
                logger.info(f"[{stream_name}] {decoded}")
        
        # Read stdout and stderr concurrently for real-time output
        await asyncio.gather(
            read_stream(process.stdout, stdout_lines, "stdout"),  # type: ignore
            read_stream(process.stderr, stderr_lines, "stderr"),  # type: ignore
        )
        
        await process.wait()
        stdout_str = "\n".join(stdout_lines)
        stderr_str = "\n".join(stderr_lines)
        
        logger.info("Command completed", returncode=process.returncode or 0, stdout_lines=len(stdout_lines), stderr_lines=len(stderr_lines))
        
        return process.returncode or 0, stdout_str, stderr_str

    async def _decompile_apk(self, apk_path: Path, output_dir: Path) -> None:
        """Decompile APK using apktool (resources only, no source)."""
        try:
            apktool = self._find_tool("apktool")
            logger.info("Found apktool", path=str(apktool))
        except ToolNotFoundError:
            logger.warning("apktool not found, using fallback extraction")
            await self._fallback_extract(apk_path, output_dir)
            return

        logger.info("Starting APK decompilation", apk=str(apk_path), output=str(output_dir))
        cmd = [str(apktool), "d", "-f", "-s", str(apk_path), "-o", str(output_dir)]
        returncode, stdout, stderr = await self._run_command(cmd)

        if returncode != 0:
            logger.warning("apktool failed, using fallback", stderr=stderr[:500])
            await self._fallback_extract(apk_path, output_dir)
        else:
            logger.info("APK decompilation completed successfully")

    async def _fallback_extract(self, apk_path: Path, output_dir: Path) -> None:
        """Fallback extraction using zipfile (limited but always works)."""
        import zipfile

        output_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(apk_path, "r") as zf:
            # Only extract what we need
            for name in zf.namelist():
                if name.startswith("res/") or name == "AndroidManifest.xml":
                    zf.extract(name, output_dir)

    def _parse_manifest(self, manifest_path: Path) -> ManifestData:
        """Parse AndroidManifest.xml into structured data."""
        if not manifest_path.exists():
            return ManifestData(package_name="unknown")

        try:
            tree = ET.parse(manifest_path)
            root = tree.getroot()
        except ET.ParseError:
            # Binary manifest, try to decode
            return self._parse_binary_manifest(manifest_path)

        # Extract namespace
        ns = {"android": "http://schemas.android.com/apk/res/android"}

        package_name = root.get("package", "unknown")
        version_code = int(root.get(f"{{{ns['android']}}}versionCode", "1"))
        version_name = root.get(f"{{{ns['android']}}}versionName", "1.0")

        # Parse uses-sdk
        uses_sdk = root.find("uses-sdk")
        min_sdk = 21
        target_sdk = 33
        if uses_sdk is not None:
            min_sdk = int(uses_sdk.get(f"{{{ns['android']}}}minSdkVersion", "21"))
            target_sdk = int(uses_sdk.get(f"{{{ns['android']}}}targetSdkVersion", "33"))

        # Parse permissions
        permissions = []
        for perm in root.findall("uses-permission"):
            perm_name = perm.get(f"{{{ns['android']}}}name", "")
            if perm_name:
                category = PermissionCategory.NORMAL
                if "CAMERA" in perm_name or "LOCATION" in perm_name or "CONTACTS" in perm_name:
                    category = PermissionCategory.DANGEROUS
                permissions.append(PermissionInfo(name=perm_name, category=category))

        # Parse application
        application = root.find("application")
        app_label = ""
        app_icon = ""
        app_theme = ""
        activities = []
        services = []
        receivers = []
        providers = []

        if application is not None:
            app_label = application.get(f"{{{ns['android']}}}label", "")
            app_icon = application.get(f"{{{ns['android']}}}icon", "")
            app_theme = application.get(f"{{{ns['android']}}}theme", "")

            # Parse activities
            for activity in application.findall("activity"):
                activity_name = activity.get(f"{{{ns['android']}}}name", "")
                exported = activity.get(f"{{{ns['android']}}}exported", "false") == "true"
                launch_mode = activity.get(f"{{{ns['android']}}}launchMode", "standard")

                intent_filters = []
                is_launcher = False
                for intent_filter in activity.findall("intent-filter"):
                    actions = [a.get(f"{{{ns['android']}}}name", "") for a in intent_filter.findall("action")]
                    categories = [c.get(f"{{{ns['android']}}}name", "") for c in intent_filter.findall("category")]
                    if "android.intent.action.MAIN" in actions and "android.intent.category.LAUNCHER" in categories:
                        is_launcher = True
                    intent_filters.append(IntentFilterInfo(actions=actions, categories=categories))

                activities.append(ActivityInfo(
                    name=activity_name,
                    exported=exported or is_launcher,
                    launch_mode=launch_mode,
                    intent_filters=intent_filters,
                    is_launcher=is_launcher,
                ))

            # Parse services
            for service in application.findall("service"):
                service_name = service.get(f"{{{ns['android']}}}name", "")
                exported = service.get(f"{{{ns['android']}}}exported", "false") == "true"
                services.append(ServiceInfo(name=service_name, exported=exported))

            # Parse receivers
            for receiver in application.findall("receiver"):
                receiver_name = receiver.get(f"{{{ns['android']}}}name", "")
                exported = receiver.get(f"{{{ns['android']}}}exported", "false") == "true"
                receivers.append(ReceiverInfo(name=receiver_name, exported=exported))

            # Parse providers
            for provider in application.findall("provider"):
                provider_name = provider.get(f"{{{ns['android']}}}name", "")
                authorities = provider.get(f"{{{ns['android']}}}authorities", "").split(";")
                providers.append(ProviderInfo(name=provider_name, authorities=authorities))

        return ManifestData(
            package_name=package_name,
            version_code=version_code,
            version_name=version_name,
            min_sdk_version=min_sdk,
            target_sdk_version=target_sdk,
            application_label=app_label,
            application_icon=app_icon,
            application_theme=app_theme,
            permissions=permissions,
            activities=activities,
            services=services,
            receivers=receivers,
            providers=providers,
        )

    def _parse_binary_manifest(self, manifest_path: Path) -> ManifestData:
        """Parse binary AndroidManifest.xml (fallback)."""
        # Binary manifest parsing requires additional tools
        # Return minimal manifest for now
        return ManifestData(package_name="unknown.binary")

    def _parse_layouts(self, res_dir: Path) -> list[UILayoutInfo]:
        """Parse layout XML files into structured info."""
        layouts = []
        layout_dir = res_dir / "layout"

        if not layout_dir.exists():
            return layouts

        for layout_file in layout_dir.glob("*.xml"):
            try:
                tree = ET.parse(layout_file)
                root = tree.getroot()

                # Extract referenced IDs and strings
                ids = []
                strings = []
                children = []

                for elem in root.iter():
                    tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                    if tag != root.tag.split("}")[-1]:
                        children.append(tag)

                    for attr, value in elem.attrib.items():
                        if "@+id/" in value or "@id/" in value:
                            ids.append(value.split("/")[-1])
                        elif "@string/" in value:
                            strings.append(value.split("/")[-1])

                root_tag = root.tag.split("}")[-1] if "}" in root.tag else root.tag

                layouts.append(UILayoutInfo(
                    layout_name=layout_file.stem,
                    layout_type="activity" if "activity" in layout_file.stem else "other",
                    root_element=root_tag,
                    child_elements=list(set(children)),
                    referenced_ids=list(set(ids)),
                    referenced_strings=list(set(strings)),
                ))
            except ET.ParseError:
                continue

        return layouts

    def _parse_strings(self, res_dir: Path) -> dict[str, str]:
        """Parse strings.xml into dictionary."""
        strings = {}
        strings_file = res_dir / "values" / "strings.xml"

        if not strings_file.exists():
            return strings

        try:
            tree = ET.parse(strings_file)
            root = tree.getroot()

            for string_elem in root.findall("string"):
                name = string_elem.get("name", "")
                value = string_elem.text or ""
                if name:
                    strings[name] = value
        except ET.ParseError:
            pass

        return strings

    def _detect_frameworks(self, decompiled_dir: Path) -> list[str]:
        """Detect frameworks used in the app."""
        frameworks = []

        # Check smali directories for common libraries
        smali_dirs = list(decompiled_dir.glob("smali*"))

        framework_indicators = {
            "retrofit": ["retrofit2", "retrofit"],
            "okhttp": ["okhttp3", "okhttp"],
            "glide": ["bumptech/glide"],
            "picasso": ["squareup/picasso"],
            "dagger": ["dagger"],
            "hilt": ["hilt"],
            "rxjava": ["io/reactivex"],
            "coroutines": ["kotlinx/coroutines"],
            "compose": ["androidx/compose"],
            "room": ["androidx/room"],
            "navigation": ["androidx/navigation"],
            "viewmodel": ["androidx/lifecycle"],
            "firebase": ["com/google/firebase"],
        }

        for smali_dir in smali_dirs:
            for framework, indicators in framework_indicators.items():
                if framework not in frameworks:
                    for indicator in indicators:
                        if list(smali_dir.glob(f"**/{indicator.replace('/', '/')}*")):
                            frameworks.append(framework)
                            break

        return frameworks

    async def analyze(self, input_data: StaticAnalysisInput) -> ServiceResult[StaticAnalysisOutput]:
        """Perform static analysis on an APK.

        Args:
            input_data: Static analysis input

        Returns:
            ServiceResult containing StaticAnalysisOutput
        """
        import time

        start_time = time.perf_counter()

        try:
            logger.info("Starting static analysis", apk_key=input_data.apk_path)

            # Get APK from storage
            local_path = self.storage.get_local_path(input_data.apk_path)
            if not local_path:
                # Download to temp location
                apk_bytes = await self.storage.load_bytes(input_data.apk_path)
                temp_dir = Path(tempfile.mkdtemp(prefix="b2b_static_"))
                self._temp_dirs.append(temp_dir)
                local_path = temp_dir / "app.apk"
                with open(local_path, "wb") as f:
                    f.write(apk_bytes)

            # Create temp directory for decompilation
            work_dir = Path(tempfile.mkdtemp(prefix="b2b_decompile_"))
            self._temp_dirs.append(work_dir)

            # Decompile APK (resources only)
            await self._decompile_apk(local_path, work_dir)

            # Parse manifest
            manifest_path = work_dir / "AndroidManifest.xml"
            manifest = self._parse_manifest(manifest_path)

            # Parse layouts
            res_dir = work_dir / "res"
            layouts = self._parse_layouts(res_dir) if res_dir.exists() else []

            # Parse strings
            strings = self._parse_strings(res_dir) if res_dir.exists() else {}

            # Detect frameworks
            detected_frameworks = self._detect_frameworks(work_dir)

            # Clean up decompiled files (compliance requirement)
            if self.config.compliance.purge_decompiled_after_analysis:
                await self._cleanup()

            output = StaticAnalysisOutput(
                manifest=manifest,
                layouts=layouts,
                strings=strings,
                detected_frameworks=detected_frameworks,
            )

            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.info(
                "Static analysis completed",
                activities=len(manifest.activities),
                layouts=len(layouts),
                duration_ms=duration_ms,
            )

            return ServiceResult.ok(output, duration_ms=duration_ms)

        except Exception as e:
            logger.error("Static analysis failed", error=str(e))
            await self._cleanup()
            raise ServiceError(
                message=f"Static analysis failed: {e}",
                service_name="static_analysis",
                operation="analyze",
                cause=e,
            )

    async def _cleanup(self) -> None:
        """Clean up temporary directories."""
        for temp_dir in self._temp_dirs:
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
        self._temp_dirs.clear()
