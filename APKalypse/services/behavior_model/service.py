"""
Behavior Model Service.

Builds the canonical behavioral model from static and dynamic analysis results.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from ...agents import AgentContext, BehavioralObserverAgent
from ...core.logging import get_logger
from ...core.types import ServiceResult
from ...models.apk import APKMetadata
from ...models.behavior import (
    BehaviorModel,
    DataFlow,
    NavigationRule,
    ScreenModel,
    StateTransition,
    UserIntent,
)
from ...services.static_analysis.service import StaticAnalysisOutput
from ...services.dynamic_analysis.service import DynamicAnalysisOutput
from ...storage import StorageBackend

logger = get_logger(__name__)


class BehaviorModelInput(BaseModel):
    """Input for behavior model building."""

    apk_metadata: APKMetadata
    static_analysis: StaticAnalysisOutput
    dynamic_analysis: DynamicAnalysisOutput
    run_id: str = Field(description="Pipeline run ID")


class BehaviorModelOutput(BaseModel):
    """Output from behavior model building."""

    behavior_model: BehaviorModel
    storage_key: str = Field(description="Storage key for persisted model")


class BehaviorModelService:
    """Service for building canonical behavioral models.

    Combines static and dynamic analysis results into a unified,
    implementation-agnostic behavioral model. Uses AI agents to
    enrich the model with semantic understanding.
    """

    def __init__(self, storage: StorageBackend) -> None:
        """Initialize the behavior model service.

        Args:
            storage: Backend for persisting behavior models.
        """
        self.storage = storage
        self.observer_agent = BehavioralObserverAgent()

    def _merge_screens(
        self,
        static_output: StaticAnalysisOutput,
        dynamic_output: DynamicAnalysisOutput,
    ) -> list[ScreenModel]:
        """Merge screen information from static and dynamic analysis.

        Combines screens discovered through dynamic exploration with
        activities declared in the manifest that weren't encountered dynamically.

        Args:
            static_output: Results from static analysis containing manifest data.
            dynamic_output: Results from dynamic analysis containing discovered screens.

        Returns:
            A unified list of screen models from both analysis sources.
        """
        screens = []
        seen_activities: set[str] = set()

        # Start with dynamically discovered screens (more reliable)
        for screen in dynamic_output.screens:
            if screen.activity_name:
                seen_activities.add(screen.activity_name)
            screens.append(screen)

        # Add screens from static analysis that weren't discovered dynamically
        for activity in static_output.manifest.activities:
            if activity.name not in seen_activities:
                screen = ScreenModel(
                    screen_id=f"static_{len(screens)}",
                    screen_name=activity.simple_name,
                    activity_name=activity.name,
                    description=f"Screen for {activity.simple_name} (from static analysis)",
                    discovery_method="static",
                    has_navigation=activity.is_launcher,
                )
                screens.append(screen)

        return screens

    def _infer_navigation_rules(
        self,
        screens: list[ScreenModel],
        transitions: list[StateTransition],
    ) -> list[NavigationRule]:
        """Infer high-level navigation rules from transitions.

        Analyzes observed state transitions to derive semantic navigation
        rules that describe how users can move between screens.

        Args:
            screens: List of all discovered screens in the application.
            transitions: List of observed state transitions between screens.

        Returns:
            A list of navigation rules describing possible screen flows.
        """
        rules = []
        transition_map: dict[str, list[str]] = {}

        for transition in transitions:
            if transition.from_screen_id not in transition_map:
                transition_map[transition.from_screen_id] = []
            if transition.to_screen_id not in transition_map[transition.from_screen_id]:
                transition_map[transition.from_screen_id].append(transition.to_screen_id)

        for from_id, to_ids in transition_map.items():
            from_screen = next((s for s in screens if s.screen_id == from_id), None)
            for to_id in to_ids:
                to_screen = next((s for s in screens if s.screen_id == to_id), None)

                rule = NavigationRule(
                    rule_id=f"nav_{len(rules)}",
                    name=f"Navigate to {to_screen.screen_name if to_screen else to_id}",
                    description=f"Navigate from {from_screen.screen_name if from_screen else from_id}",
                    from_screens=[from_id],
                    to_screen=to_id,
                    is_back_navigation="back" in (to_screen.screen_name.lower() if to_screen else ""),
                )
                rules.append(rule)

        return rules

    def _infer_user_intents(
        self,
        screens: list[ScreenModel],
        manifest: Any,
    ) -> list[UserIntent]:
        """Infer user intents from screens and manifest.

        Analyzes screen names and manifest data to infer what user goals
        the application supports (e.g., login, registration, browsing).

        Args:
            screens: List of all discovered screens in the application.
            manifest: Parsed Android manifest containing app metadata.

        Returns:
            A list of inferred user intents with priority and frequency info.
        """
        intents = []

        # Infer basic intents based on common patterns
        screen_names = [s.screen_name.lower() for s in screens]

        # Login intent
        if any("login" in n or "signin" in n or "auth" in n for n in screen_names):
            intents.append(UserIntent(
                intent_id="intent_login",
                name="User Login",
                description="Authenticate user with the application",
                is_primary=True,
                estimated_frequency="high",
            ))

        # Registration intent
        if any("register" in n or "signup" in n for n in screen_names):
            intents.append(UserIntent(
                intent_id="intent_register",
                name="User Registration",
                description="Create a new user account",
                is_primary=True,
                estimated_frequency="medium",
            ))

        # Browse/List intent
        if any("list" in n or "browse" in n or "home" in n for n in screen_names):
            intents.append(UserIntent(
                intent_id="intent_browse",
                name="Browse Content",
                description="View and browse available content",
                is_primary=True,
                estimated_frequency="high",
            ))

        # Detail view intent
        if any("detail" in n or "view" in n for n in screen_names):
            intents.append(UserIntent(
                intent_id="intent_view_detail",
                name="View Details",
                description="View detailed information about an item",
                is_primary=False,
                estimated_frequency="high",
            ))

        # Settings intent
        if any("setting" in n or "preference" in n for n in screen_names):
            intents.append(UserIntent(
                intent_id="intent_settings",
                name="Manage Settings",
                description="Configure application settings",
                is_primary=False,
                estimated_frequency="low",
            ))

        # Profile intent
        if any("profile" in n or "account" in n for n in screen_names):
            intents.append(UserIntent(
                intent_id="intent_profile",
                name="Manage Profile",
                description="View and edit user profile",
                is_primary=False,
                estimated_frequency="medium",
            ))

        # Search intent
        if any("search" in n for n in screen_names):
            intents.append(UserIntent(
                intent_id="intent_search",
                name="Search",
                description="Search for content in the application",
                is_primary=True,
                estimated_frequency="high",
            ))

        return intents

    def _infer_data_flows(
        self,
        screens: list[ScreenModel],
        network_calls: list[Any],
    ) -> list[DataFlow]:
        """Infer data flows from screens and network activity.

        Analyzes screen properties and observed network calls to determine
        how data moves through the application between UI and backend.

        Args:
            screens: List of all discovered screens in the application.
            network_calls: List of observed network API calls.

        Returns:
            A list of data flow descriptions connecting sources to destinations.
        """
        flows = []

        # Infer flows from screen types
        for screen in screens:
            if screen.has_app_bar:
                # App bar likely displays data from somewhere
                flows.append(DataFlow(
                    flow_id=f"flow_{len(flows)}",
                    name=f"App bar data for {screen.screen_name}",
                    source_type="api",
                    source_id="app_state",
                    destination_type="screen",
                    destination_id=screen.screen_id,
                    data_type="navigation_state",
                ))

        # Infer flows from network calls
        for call in network_calls:
            flows.append(DataFlow(
                flow_id=f"flow_{len(flows)}",
                name=f"API call to {call.url}",
                source_type="api",
                source_id=call.url,
                destination_type="screen",
                destination_id="unknown",
                data_type="api_response",
            ))

        return flows

    async def build(self, input_data: BehaviorModelInput) -> ServiceResult[BehaviorModelOutput]:
        """Build the behavioral model.

        Combines static and dynamic analysis results into a unified,
        implementation-agnostic behavioral model. The model captures screens,
        transitions, navigation rules, user intents, and data flows.

        Args:
            input_data: Input containing APK metadata and analysis results
                from both static and dynamic analysis phases.

        Returns:
            ServiceResult containing the built BehaviorModel and storage key
            on success, or an error message on failure.
        """
        import time

        start_time = time.perf_counter()

        try:
            logger.info("Building behavior model", run_id=input_data.run_id)

            # Merge screens from both analyses
            screens = self._merge_screens(
                input_data.static_analysis,
                input_data.dynamic_analysis,
            )

            # Get transitions from dynamic analysis
            transitions = input_data.dynamic_analysis.transitions

            # Infer navigation rules
            navigation_rules = self._infer_navigation_rules(screens, transitions)

            # Infer user intents
            user_intents = self._infer_user_intents(
                screens,
                input_data.static_analysis.manifest,
            )

            # Infer data flows
            data_flows = self._infer_data_flows(
                screens,
                input_data.dynamic_analysis.network_calls,
            )

            # Find entry screen
            entry_screen_id = None
            launcher = input_data.static_analysis.manifest.launcher_activity
            if launcher:
                for screen in screens:
                    if screen.activity_name == launcher.name:
                        entry_screen_id = screen.screen_id
                        break
            if not entry_screen_id and screens:
                entry_screen_id = screens[0].screen_id

            # Create behavior model
            model = BehaviorModel(
                model_id=str(uuid.uuid4()),
                app_package=input_data.apk_metadata.manifest.package_name,
                screens=screens,
                transitions=transitions,
                navigation_rules=navigation_rules,
                user_intents=user_intents,
                data_flows=data_flows,
                entry_screen_id=entry_screen_id,
                auth_required=any(i.intent_id == "intent_login" for i in user_intents),
                offline_capable=False,  # Would need deeper analysis
                coverage_score=input_data.dynamic_analysis.exploration_coverage,
            )
            model.update_statistics()

            # Store model
            storage_key = f"models/{input_data.apk_metadata.provenance.sha256_hash}/behavior_model.json"
            await self.storage.store_model(storage_key, model)

            output = BehaviorModelOutput(
                behavior_model=model,
                storage_key=storage_key,
            )

            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.info(
                "Behavior model built",
                screens=model.total_screens,
                transitions=model.total_transitions,
                intents=model.total_user_intents,
                duration_ms=duration_ms,
            )

            return ServiceResult.ok(output, duration_ms=duration_ms)

        except Exception as e:
            logger.error("Behavior model building failed", error=str(e))
            return ServiceResult.fail(str(e))
