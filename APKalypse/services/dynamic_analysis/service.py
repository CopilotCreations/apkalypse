"""
Dynamic Analysis Service.

Performs runtime analysis of APKs using Android emulator and UI automation.
Records screen transitions, user actions, and network activity.
"""

from __future__ import annotations

import asyncio
import base64
import json
import re
import shutil
import subprocess
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from ...core.config import EmulatorConfig, get_config
from ...core.exceptions import EmulatorError, ServiceError
from ...core.logging import get_logger
from ...core.types import ServiceResult
from ...models.apk import APKMetadata
from ...models.behavior import (
    ActionType,
    ScreenModel,
    SideEffect,
    SideEffectType,
    StateTransition,
    UIElement,
    UIElementType,
    UserAction,
)
from ...storage import StorageBackend

logger = get_logger(__name__)


class NetworkCall(BaseModel):
    """Recorded network call metadata."""

    method: str
    url: str
    request_headers: dict[str, str] = Field(default_factory=dict)
    response_status: int = 0
    request_body_schema: dict[str, Any] | None = None
    response_body_schema: dict[str, Any] | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class DynamicAnalysisInput(BaseModel):
    """Input for dynamic analysis."""

    apk_path: str = Field(description="Storage key for APK")
    apk_metadata: APKMetadata
    exploration_time_seconds: int = Field(default=300, description="Max exploration time")
    capture_screenshots: bool = Field(default=True)
    capture_network: bool = Field(default=True)


class DynamicAnalysisOutput(BaseModel):
    """Output from dynamic analysis."""

    screens: list[ScreenModel] = Field(default_factory=list)
    transitions: list[StateTransition] = Field(default_factory=list)
    network_calls: list[NetworkCall] = Field(default_factory=list)
    exploration_coverage: float = Field(default=0.0)
    total_actions: int = Field(default=0)


@dataclass
class EmulatorSession:
    """Manages an Android emulator session."""

    config: EmulatorConfig
    process: subprocess.Popen | None = None
    serial: str = ""
    adb_path: Path | None = None
    is_ready: bool = False

    async def start(self) -> None:
        """Start the emulator."""
        sdk_root = get_config().tools.android_sdk_root
        
        # Find emulator binary
        emulator_path = sdk_root / "emulator" / "emulator"
        if not emulator_path.exists():
            emulator_path = sdk_root / "emulator" / "emulator.exe"
        
        if not emulator_path.exists():
            # Try to use emulator from PATH
            emulator_str = shutil.which("emulator")
            if emulator_str:
                emulator_path = Path(emulator_str)
            else:
                raise EmulatorError(
                    message="Emulator not found",
                    avd_name=self.config.avd_name,
                    context={"sdk_root": str(sdk_root)},
                )

        # Find adb
        self.adb_path = sdk_root / "platform-tools" / "adb"
        if not self.adb_path.exists():
            self.adb_path = sdk_root / "platform-tools" / "adb.exe"
        if not self.adb_path.exists():
            adb_str = shutil.which("adb")
            if adb_str:
                self.adb_path = Path(adb_str)
            else:
                raise EmulatorError(
                    message="adb not found",
                    avd_name=self.config.avd_name,
                )

        # Start emulator
        cmd = [
            str(emulator_path),
            "-avd", self.config.avd_name,
            "-port", str(self.config.adb_port),
            "-gpu", self.config.gpu,
            "-memory", str(self.config.memory_mb),
        ]

        if self.config.headless:
            cmd.extend(["-no-window", "-no-audio"])

        logger.info("Starting emulator", cmd=" ".join(cmd[:5]))

        # Use DEVNULL for stdout/stderr to prevent pipe buffer blocking
        # On Windows, piping without reading causes the child process to hang
        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        self.serial = f"emulator-{self.config.adb_port}"

        # Wait for boot
        await self._wait_for_boot()
        self.is_ready = True

    async def _wait_for_boot(self) -> None:
        """Wait for emulator to boot."""
        timeout = self.config.boot_timeout_seconds
        start = asyncio.get_event_loop().time()
        
        logger.info(
            "Waiting for emulator to boot (first run may take longer than usual)",
            serial=self.serial,
            timeout_seconds=timeout,
        )

        while asyncio.get_event_loop().time() - start < timeout:
            try:
                result = await self._adb("shell", "getprop", "sys.boot_completed")
                if result.strip() == "1":
                    logger.info("Emulator booted", serial=self.serial)
                    return
            except Exception:
                pass
            await asyncio.sleep(5)

        raise EmulatorError(
            message="Emulator boot timeout",
            avd_name=self.config.avd_name,
            adb_port=self.config.adb_port,
        )

    async def _adb(self, *args: str) -> str:
        """Run adb command."""
        if not self.adb_path:
            raise EmulatorError(message="adb not initialized", avd_name=self.config.avd_name)

        cmd = [str(self.adb_path), "-s", self.serial, *args]
        cmd_str = " ".join(cmd)
        logger.debug("Running adb command", command=cmd_str)
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        stdout_str = stdout.decode()
        stderr_str = stderr.decode()
        
        if proc.returncode != 0:
            logger.warning("adb command failed", command=cmd_str, stderr=stderr_str[:500])
            raise EmulatorError(
                message=f"adb command failed: {stderr_str}",
                avd_name=self.config.avd_name,
            )
        
        if len(stdout_str) < 500:
            logger.debug("adb command completed", output=stdout_str)
        else:
            logger.debug("adb command completed", output_len=len(stdout_str))
        
        return stdout_str

    async def install_apk(self, apk_path: Path) -> None:
        """Install APK on emulator."""
        await self._adb("install", "-r", str(apk_path))
        logger.info("APK installed", path=str(apk_path))

    async def launch_app(self, package_name: str, activity: str | None = None) -> None:
        """Launch the app."""
        if activity:
            await self._adb("shell", "am", "start", "-n", f"{package_name}/{activity}")
        else:
            await self._adb("shell", "monkey", "-p", package_name, "-c", "android.intent.category.LAUNCHER", "1")
        await asyncio.sleep(2)

    async def get_ui_hierarchy(self) -> str:
        """Dump UI hierarchy."""
        await self._adb("shell", "uiautomator", "dump", "/sdcard/ui_dump.xml")
        result = await self._adb("shell", "cat", "/sdcard/ui_dump.xml")
        return result

    async def take_screenshot(self) -> bytes:
        """Take a screenshot."""
        await self._adb("shell", "screencap", "-p", "/sdcard/screen.png")
        result = await self._adb("exec-out", "cat", "/sdcard/screen.png")
        return result.encode("latin-1")

    async def tap(self, x: int, y: int) -> None:
        """Tap at coordinates."""
        await self._adb("shell", "input", "tap", str(x), str(y))

    async def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: int = 300) -> None:
        """Swipe gesture."""
        await self._adb("shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(duration))

    async def input_text(self, text: str) -> None:
        """Input text."""
        escaped = text.replace(" ", "%s").replace("'", "\\'")
        await self._adb("shell", "input", "text", escaped)

    async def press_back(self) -> None:
        """Press back button."""
        await self._adb("shell", "input", "keyevent", "KEYCODE_BACK")

    async def get_current_activity(self) -> str:
        """Get current foreground activity."""
        result = await self._adb("shell", "dumpsys", "activity", "activities")
        match = re.search(r"mResumedActivity.*?(\S+/\S+)", result)
        if match:
            return match.group(1)
        return ""

    async def stop(self) -> None:
        """Stop the emulator."""
        if self.process:
            self.process.terminate()
            await asyncio.sleep(1)
            if self.process.poll() is None:
                self.process.kill()
            self.process = None
        self.is_ready = False


class UIExplorer:
    """Explores app UI automatically."""

    def __init__(self, session: EmulatorSession, storage: StorageBackend) -> None:
        self.session = session
        self.storage = storage
        self.visited_states: set[str] = set()
        self.screens: list[ScreenModel] = []
        self.transitions: list[StateTransition] = []
        self.actions: list[UserAction] = []
        self.action_count = 0

    def _parse_ui_hierarchy(self, xml_content: str) -> tuple[list[UIElement], str]:
        """Parse UI hierarchy XML into elements."""
        import xml.etree.ElementTree as ET

        elements = []
        state_hash = ""

        try:
            root = ET.fromstring(xml_content)
            state_parts = []

            def parse_node(node: ET.Element, parent_id: str = "") -> UIElement | None:
                bounds_str = node.get("bounds", "[0,0][0,0]")
                # Parse bounds [x1,y1][x2,y2]
                match = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds_str)
                if not match:
                    return None

                x1, y1, x2, y2 = map(int, match.groups())
                screen_width = 1080  # Assume standard width
                screen_height = 1920

                resource_id = node.get("resource-id", "")
                text = node.get("text", "")
                content_desc = node.get("content-desc", "")
                class_name = node.get("class", "")

                # Determine element type
                element_type = UIElementType.UNKNOWN
                class_lower = class_name.lower()
                if "button" in class_lower:
                    element_type = UIElementType.BUTTON
                elif "edittext" in class_lower:
                    element_type = UIElementType.TEXT_FIELD
                elif "textview" in class_lower:
                    element_type = UIElementType.TEXT_VIEW
                elif "imageview" in class_lower:
                    element_type = UIElementType.IMAGE
                elif "recyclerview" in class_lower or "listview" in class_lower:
                    element_type = UIElementType.LIST

                element_id = resource_id or f"elem_{len(elements)}"
                state_parts.append(f"{element_id}:{text[:20]}")

                children = []
                for child in node:
                    child_elem = parse_node(child, element_id)
                    if child_elem:
                        children.append(child_elem)

                return UIElement(
                    element_id=element_id,
                    element_type=element_type,
                    resource_id=resource_id if resource_id else None,
                    content_description=content_desc if content_desc else None,
                    text=text if text else None,
                    bounds_left=x1 / screen_width,
                    bounds_top=y1 / screen_height,
                    bounds_right=x2 / screen_width,
                    bounds_bottom=y2 / screen_height,
                    is_clickable=node.get("clickable") == "true",
                    is_focusable=node.get("focusable") == "true",
                    is_editable="edittext" in class_lower,
                    is_scrollable=node.get("scrollable") == "true",
                    is_enabled=node.get("enabled") == "true",
                    is_visible=True,
                    children=children,
                )

            for child in root:
                elem = parse_node(child)
                if elem:
                    elements.append(elem)

            state_hash = hash(tuple(sorted(state_parts)))

        except ET.ParseError as e:
            logger.warning("Failed to parse UI hierarchy", error=str(e))

        return elements, str(state_hash)

    def _get_clickable_elements(self, elements: list[UIElement]) -> list[UIElement]:
        """Get all clickable elements recursively."""
        clickable = []

        def collect(elem: UIElement) -> None:
            if elem.is_clickable and elem.is_visible and elem.is_enabled:
                clickable.append(elem)
            for child in elem.children:
                collect(child)

        for elem in elements:
            collect(elem)

        return clickable

    async def explore(self, package_name: str, max_actions: int = 50) -> None:
        """Explore the app UI."""
        logger.info("Starting UI exploration", package=package_name, max_actions=max_actions)

        current_screen_id: str | None = None

        for _ in range(max_actions):
            try:
                # Get current state
                hierarchy = await self.session.get_ui_hierarchy()
                activity = await self.session.get_current_activity()
                elements, state_hash = self._parse_ui_hierarchy(hierarchy)

                # Check if new state
                if state_hash not in self.visited_states:
                    self.visited_states.add(state_hash)

                    # Create screen model
                    screen = ScreenModel(
                        screen_id=f"screen_{len(self.screens)}",
                        screen_name=activity.split("/")[-1] if activity else f"Screen {len(self.screens)}",
                        activity_name=activity,
                        root_elements=elements,
                        interactive_elements=[e.element_id for e in self._get_clickable_elements(elements)],
                    )
                    self.screens.append(screen)

                    # Record transition if applicable
                    if current_screen_id and len(self.actions) > 0:
                        last_action = self.actions[-1]
                        transition = StateTransition(
                            transition_id=f"trans_{len(self.transitions)}",
                            from_screen_id=current_screen_id,
                            to_screen_id=screen.screen_id,
                            triggered_by_action=last_action,
                        )
                        self.transitions.append(transition)

                    current_screen_id = screen.screen_id

                # Find something to click
                clickable = self._get_clickable_elements(elements)
                if not clickable:
                    # Try scrolling or going back
                    await self.session.swipe(540, 1500, 540, 500)
                    await asyncio.sleep(0.5)
                    continue

                # Click a random unexplored element
                import random
                target = random.choice(clickable)

                # Calculate center coordinates
                screen_width = 1080
                screen_height = 1920
                x = int((target.bounds_left + target.bounds_right) / 2 * screen_width)
                y = int((target.bounds_top + target.bounds_bottom) / 2 * screen_height)

                # Record action
                action = UserAction(
                    action_id=f"action_{self.action_count}",
                    action_type=ActionType.TAP,
                    target_element_id=target.element_id,
                    coordinates=(target.bounds_left + target.bounds_right, target.bounds_top + target.bounds_bottom),
                    source_screen_id=current_screen_id or "",
                    description=f"Tap on {target.text or target.resource_id or 'element'}",
                )
                self.actions.append(action)
                self.action_count += 1

                # Perform tap
                await self.session.tap(x, y)
                await asyncio.sleep(1)

            except Exception as e:
                logger.warning("Exploration step failed", error=str(e))
                # Try to recover by pressing back
                await self.session.press_back()
                await asyncio.sleep(1)

        logger.info(
            "Exploration completed",
            screens=len(self.screens),
            transitions=len(self.transitions),
            actions=self.action_count,
        )


class DynamicAnalysisService:
    """Service for dynamic analysis of Android applications.

    Uses Android emulator with UI automation to explore app behavior,
    recording screen transitions, user actions, and network activity.
    """

    def __init__(self, storage: StorageBackend) -> None:
        """Initialize the dynamic analysis service."""
        self.storage = storage
        self.config = get_config()
        self._emulator: EmulatorSession | None = None

    async def analyze(self, input_data: DynamicAnalysisInput) -> ServiceResult[DynamicAnalysisOutput]:
        """Perform dynamic analysis on an APK.

        Args:
            input_data: Dynamic analysis input

        Returns:
            ServiceResult containing DynamicAnalysisOutput
        """
        import time

        start_time = time.perf_counter()

        try:
            logger.info("Starting dynamic analysis", apk_key=input_data.apk_path)

            # Get APK file
            local_path = self.storage.get_local_path(input_data.apk_path)
            if not local_path:
                apk_bytes = await self.storage.load_bytes(input_data.apk_path)
                temp_dir = Path(tempfile.mkdtemp(prefix="b2b_dynamic_"))
                local_path = temp_dir / "app.apk"
                with open(local_path, "wb") as f:
                    f.write(apk_bytes)

            # Start emulator
            self._emulator = EmulatorSession(config=self.config.emulator)

            try:
                await self._emulator.start()
            except EmulatorError as e:
                logger.warning("Emulator not available, using mock analysis", error=str(e))
                return await self._mock_analysis(input_data)

            # Install APK
            await self._emulator.install_apk(local_path)

            # Get package name and launcher
            package_name = input_data.apk_metadata.manifest.package_name
            launcher = input_data.apk_metadata.manifest.launcher_activity

            # Launch app
            await self._emulator.launch_app(
                package_name,
                launcher.name if launcher else None,
            )

            # Explore UI
            explorer = UIExplorer(self._emulator, self.storage)
            max_actions = input_data.exploration_time_seconds // 5
            await explorer.explore(package_name, max_actions=max_actions)

            # Calculate coverage
            total_activities = len(input_data.apk_metadata.manifest.activities)
            coverage = len(explorer.screens) / max(total_activities, 1)

            output = DynamicAnalysisOutput(
                screens=explorer.screens,
                transitions=explorer.transitions,
                network_calls=[],  # Would need mitmproxy integration
                exploration_coverage=min(coverage, 1.0),
                total_actions=explorer.action_count,
            )

            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.info(
                "Dynamic analysis completed",
                screens=len(explorer.screens),
                transitions=len(explorer.transitions),
                duration_ms=duration_ms,
            )

            return ServiceResult.ok(output, duration_ms=duration_ms)

        except Exception as e:
            logger.error("Dynamic analysis failed", error=str(e))
            return await self._mock_analysis(input_data)

        finally:
            if self._emulator:
                await self._emulator.stop()

    async def _mock_analysis(self, input_data: DynamicAnalysisInput) -> ServiceResult[DynamicAnalysisOutput]:
        """Provide mock analysis when emulator is not available."""
        logger.info("Using mock dynamic analysis")

        # Create screens from static analysis activities
        screens = []
        for i, activity in enumerate(input_data.apk_metadata.manifest.activities):
            screen = ScreenModel(
                screen_id=f"screen_{i}",
                screen_name=activity.simple_name,
                activity_name=activity.name,
                description=f"Screen for {activity.simple_name}",
                has_navigation=activity.is_launcher,
            )
            screens.append(screen)

        # Create basic transitions
        transitions = []
        for i in range(len(screens) - 1):
            action = UserAction(
                action_id=f"action_{i}",
                action_type=ActionType.TAP,
                source_screen_id=screens[i].screen_id,
                description=f"Navigate from {screens[i].screen_name}",
            )
            transition = StateTransition(
                transition_id=f"trans_{i}",
                from_screen_id=screens[i].screen_id,
                to_screen_id=screens[i + 1].screen_id,
                triggered_by_action=action,
            )
            transitions.append(transition)

        output = DynamicAnalysisOutput(
            screens=screens,
            transitions=transitions,
            network_calls=[],
            exploration_coverage=0.3,  # Low coverage since mock
            total_actions=len(transitions),
        )

        return ServiceResult.with_warnings(
            output,
            ["Emulator not available - using mock analysis based on static data"],
        )
