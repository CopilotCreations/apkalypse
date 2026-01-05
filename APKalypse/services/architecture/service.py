"""
Architecture Service.

Synthesizes technical architecture from behavioral specifications.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from ...agents import AgentContext, SystemArchitectAgent
from ...agents.system_architect import ArchitectInput, ArchitectOutput
from ...core.logging import get_logger
from ...core.types import ServiceResult
from ...models.spec import (
    ArchitectureDecisionRecord,
    ArchitectureSpec,
    BehavioralSpec,
    DataFlowDiagram,
    DataFlowEdge,
    DataFlowNode,
    ModuleDefinition,
    ModuleType,
    TechnologyChoice,
    TechnologyDecision,
)
from ...storage import StorageBackend

logger = get_logger(__name__)


class ArchitectureInput(BaseModel):
    """Input for architecture synthesis."""

    behavioral_spec: BehavioralSpec
    run_id: str = Field(description="Pipeline run ID")


class ArchitectureOutput(BaseModel):
    """Output from architecture synthesis."""

    architecture_spec: ArchitectureSpec
    storage_key: str = Field(description="Storage key for persisted spec")


class ArchitectureService:
    """Service for synthesizing technical architecture.

    Uses AI agents to design a clean, modern Android architecture
    based on behavioral specifications.
    """

    def __init__(self, storage: StorageBackend) -> None:
        """Initialize the architecture service.

        Args:
            storage: Storage backend for persisting architecture specs.
        """
        self.storage = storage
        self.architect_agent = SystemArchitectAgent()

    def _create_default_modules(self, behavioral_spec: BehavioralSpec) -> list[ModuleDefinition]:
        """Create default module structure.

        Args:
            behavioral_spec: The behavioral specification to base modules on.

        Returns:
            A list of module definitions including app, core, and feature modules.
        """
        modules = []

        # App module
        modules.append(ModuleDefinition(
            module_id="app",
            module_name=":app",
            module_type=ModuleType.APP,
            description="Main application module",
            depends_on=[":core:ui", ":core:domain", ":feature:home"],
            responsibilities=["Application entry point", "Navigation host", "Dependency injection setup"],
            suggested_packages=["app", "di", "navigation"],
        ))

        # Core UI module
        modules.append(ModuleDefinition(
            module_id="core_ui",
            module_name=":core:ui",
            module_type=ModuleType.UI,
            description="Shared UI components and theming",
            depends_on=[],
            responsibilities=["Theme definition", "Common composables", "Design tokens"],
            suggested_packages=["theme", "components", "icons"],
        ))

        # Core Domain module
        modules.append(ModuleDefinition(
            module_id="core_domain",
            module_name=":core:domain",
            module_type=ModuleType.DOMAIN,
            description="Domain layer with use cases",
            depends_on=[":core:data"],
            responsibilities=["Use cases", "Domain models", "Business logic"],
            suggested_packages=["usecase", "model", "repository"],
        ))

        # Core Data module
        modules.append(ModuleDefinition(
            module_id="core_data",
            module_name=":core:data",
            module_type=ModuleType.DATA,
            description="Data layer with repositories",
            depends_on=[],
            responsibilities=["Repository implementations", "Data sources", "API clients"],
            suggested_packages=["repository", "local", "remote", "mapper"],
        ))

        # Core Common module
        modules.append(ModuleDefinition(
            module_id="core_common",
            module_name=":core:common",
            module_type=ModuleType.COMMON,
            description="Common utilities and extensions",
            depends_on=[],
            responsibilities=["Extensions", "Utilities", "Constants"],
            suggested_packages=["util", "extension"],
        ))

        # Feature modules based on screens
        screen_groups = self._group_screens_to_features(behavioral_spec.screen_specs)
        for feature_name, screens in screen_groups.items():
            modules.append(ModuleDefinition(
                module_id=f"feature_{feature_name}",
                module_name=f":feature:{feature_name}",
                module_type=ModuleType.FEATURE,
                description=f"Feature module for {feature_name}",
                depends_on=[":core:ui", ":core:domain"],
                responsibilities=[f"UI for {feature_name}", "ViewModels", "Navigation"],
                suggested_packages=["ui", "viewmodel", "navigation"],
                key_classes=[f"{s.screen_name.replace(' ', '')}Screen" for s in screens],
            ))

        return modules

    def _group_screens_to_features(self, screen_specs: list[Any]) -> dict[str, list[Any]]:
        """Group screens into feature modules.

        Args:
            screen_specs: List of screen specifications to group.

        Returns:
            A dictionary mapping feature names to lists of screen specs.
        """
        groups: dict[str, list[Any]] = {}

        for screen in screen_specs:
            # Simple grouping heuristic based on screen name
            name_lower = screen.screen_name.lower()

            if "home" in name_lower or "main" in name_lower:
                feature = "home"
            elif "login" in name_lower or "auth" in name_lower or "signin" in name_lower:
                feature = "auth"
            elif "setting" in name_lower or "preference" in name_lower:
                feature = "settings"
            elif "profile" in name_lower or "account" in name_lower:
                feature = "profile"
            elif "search" in name_lower:
                feature = "search"
            elif "detail" in name_lower:
                feature = "detail"
            else:
                feature = "home"  # Default to home

            if feature not in groups:
                groups[feature] = []
            groups[feature].append(screen)

        return groups

    def _create_default_adrs(self) -> list[ArchitectureDecisionRecord]:
        """Create default Architecture Decision Records.

        Returns:
            A list of ADRs covering MVVM, Compose, Hilt, multi-module,
            and coroutines decisions.
        """
        adrs = []

        adrs.append(ArchitectureDecisionRecord(
            adr_id="ADR-001",
            title="Use MVVM Architecture Pattern",
            context="Need a presentation architecture that supports testability and separation of concerns.",
            decision="Use Model-View-ViewModel (MVVM) pattern with Jetpack Compose and StateFlow.",
            consequences=[
                "Clear separation between UI and business logic",
                "Easy to unit test ViewModels",
                "Reactive UI updates via StateFlow",
                "Learning curve for developers unfamiliar with reactive patterns",
            ],
        ))

        adrs.append(ArchitectureDecisionRecord(
            adr_id="ADR-002",
            title="Use Jetpack Compose for UI",
            context="Need a modern UI framework for building the Android application.",
            decision="Use Jetpack Compose as the primary UI framework.",
            consequences=[
                "Declarative UI with less boilerplate",
                "Better tooling support and previews",
                "Easier state management",
                "Larger APK size due to Compose runtime",
            ],
        ))

        adrs.append(ArchitectureDecisionRecord(
            adr_id="ADR-003",
            title="Use Hilt for Dependency Injection",
            context="Need a dependency injection framework for managing dependencies.",
            decision="Use Hilt (built on Dagger) for dependency injection.",
            consequences=[
                "Compile-time dependency verification",
                "Android-specific lifecycle integration",
                "Reduced boilerplate compared to raw Dagger",
                "Additional build time for annotation processing",
            ],
        ))

        adrs.append(ArchitectureDecisionRecord(
            adr_id="ADR-004",
            title="Use Multi-Module Architecture",
            context="Need to organize code for scalability and build performance.",
            decision="Organize project into feature modules with shared core modules.",
            consequences=[
                "Improved build times through parallelization",
                "Clear ownership boundaries",
                "Enforced dependency rules",
                "More complex Gradle configuration",
            ],
        ))

        adrs.append(ArchitectureDecisionRecord(
            adr_id="ADR-005",
            title="Use Kotlin Coroutines for Async Operations",
            context="Need a concurrency framework for async operations.",
            decision="Use Kotlin Coroutines with Flow for all async operations.",
            consequences=[
                "Structured concurrency",
                "Easy cancellation handling",
                "Good integration with Jetpack libraries",
                "Requires understanding of coroutine concepts",
            ],
        ))

        return adrs

    def _create_default_technology_decisions(self) -> list[TechnologyDecision]:
        """Create default technology decisions.

        Returns:
            A list of technology decisions covering language, UI, DI,
            networking, storage, navigation, and testing.
        """
        decisions = []

        # Language
        decisions.append(TechnologyDecision(
            decision_id="tech_language",
            category="language",
            choices=[
                TechnologyChoice(
                    technology="Kotlin",
                    version="1.9.22",
                    purpose="Primary development language",
                    rationale="Modern, expressive, full Android support, null safety",
                    alternatives_considered=["Java"],
                ),
            ],
        ))

        # UI Framework
        decisions.append(TechnologyDecision(
            decision_id="tech_ui",
            category="ui",
            choices=[
                TechnologyChoice(
                    technology="Jetpack Compose",
                    version="1.5.4",
                    purpose="UI framework",
                    rationale="Modern declarative UI, official Google recommendation",
                    alternatives_considered=["XML Views", "Flutter"],
                ),
                TechnologyChoice(
                    technology="Material 3",
                    version="1.1.2",
                    purpose="Design system",
                    rationale="Modern Material Design implementation",
                ),
            ],
        ))

        # Architecture
        decisions.append(TechnologyDecision(
            decision_id="tech_di",
            category="dependency_injection",
            choices=[
                TechnologyChoice(
                    technology="Hilt",
                    version="2.48",
                    purpose="Dependency injection",
                    rationale="Android-optimized DI with compile-time safety",
                    alternatives_considered=["Koin", "Manual DI"],
                ),
            ],
        ))

        # Networking
        decisions.append(TechnologyDecision(
            decision_id="tech_network",
            category="networking",
            choices=[
                TechnologyChoice(
                    technology="Retrofit",
                    version="2.9.0",
                    purpose="HTTP client",
                    rationale="Type-safe HTTP client with coroutines support",
                ),
                TechnologyChoice(
                    technology="OkHttp",
                    version="4.12.0",
                    purpose="HTTP transport",
                    rationale="Efficient HTTP client with interceptors",
                ),
                TechnologyChoice(
                    technology="Kotlinx Serialization",
                    version="1.6.2",
                    purpose="JSON serialization",
                    rationale="Kotlin-native serialization with good performance",
                    alternatives_considered=["Gson", "Moshi"],
                ),
            ],
        ))

        # Local Storage
        decisions.append(TechnologyDecision(
            decision_id="tech_storage",
            category="local_storage",
            choices=[
                TechnologyChoice(
                    technology="Room",
                    version="2.6.1",
                    purpose="Local database",
                    rationale="SQLite abstraction with compile-time verification",
                ),
                TechnologyChoice(
                    technology="DataStore",
                    version="1.0.0",
                    purpose="Preferences storage",
                    rationale="Modern replacement for SharedPreferences",
                ),
            ],
        ))

        # Navigation
        decisions.append(TechnologyDecision(
            decision_id="tech_navigation",
            category="navigation",
            choices=[
                TechnologyChoice(
                    technology="Navigation Compose",
                    version="2.7.6",
                    purpose="Navigation framework",
                    rationale="Official navigation solution for Compose",
                ),
            ],
        ))

        # Testing
        decisions.append(TechnologyDecision(
            decision_id="tech_testing",
            category="testing",
            choices=[
                TechnologyChoice(
                    technology="JUnit 5",
                    version="5.10.1",
                    purpose="Unit testing framework",
                    rationale="Modern testing framework with better assertions",
                ),
                TechnologyChoice(
                    technology="Compose Testing",
                    version="1.5.4",
                    purpose="UI testing",
                    rationale="Official Compose testing library",
                ),
                TechnologyChoice(
                    technology="Mockk",
                    version="1.13.8",
                    purpose="Mocking framework",
                    rationale="Kotlin-first mocking library",
                ),
            ],
        ))

        return decisions

    def _create_data_flow_diagram(self, behavioral_spec: BehavioralSpec) -> DataFlowDiagram:
        """Create a data flow diagram.

        Args:
            behavioral_spec: The behavioral specification to base the diagram on.

        Returns:
            A data flow diagram showing the main data flow through application layers.
        """
        nodes = [
            DataFlowNode(node_id="user", node_type="source", name="User", description="Application user"),
            DataFlowNode(node_id="ui", node_type="process", name="UI Layer", description="Compose screens"),
            DataFlowNode(node_id="viewmodel", node_type="process", name="ViewModel", description="State management"),
            DataFlowNode(node_id="usecase", node_type="process", name="Use Cases", description="Business logic"),
            DataFlowNode(node_id="repository", node_type="process", name="Repository", description="Data abstraction"),
            DataFlowNode(node_id="remote", node_type="sink", name="Remote API", description="Backend server"),
            DataFlowNode(node_id="local", node_type="store", name="Local DB", description="Room database"),
        ]

        edges = [
            DataFlowEdge(from_node="user", to_node="ui", data_type="user_input", description="User interactions"),
            DataFlowEdge(from_node="ui", to_node="viewmodel", data_type="events", description="UI events"),
            DataFlowEdge(from_node="viewmodel", to_node="ui", data_type="state", description="UI state"),
            DataFlowEdge(from_node="viewmodel", to_node="usecase", data_type="request", description="Use case calls"),
            DataFlowEdge(from_node="usecase", to_node="repository", data_type="data_request", description="Data requests"),
            DataFlowEdge(from_node="repository", to_node="remote", data_type="api_call", description="API calls"),
            DataFlowEdge(from_node="repository", to_node="local", data_type="query", description="DB queries"),
            DataFlowEdge(from_node="remote", to_node="repository", data_type="response", description="API responses"),
            DataFlowEdge(from_node="local", to_node="repository", data_type="data", description="Cached data"),
        ]

        return DataFlowDiagram(
            diagram_id="main_data_flow",
            name="Main Data Flow",
            description="Primary data flow through the application layers",
            nodes=nodes,
            edges=edges,
        )

    async def synthesize(self, input_data: ArchitectureInput) -> ServiceResult[ArchitectureOutput]:
        """Synthesize technical architecture from behavioral specifications.

        Uses AI agents to design a clean, modern Android architecture based on
        the provided behavioral specifications.

        Args:
            input_data: Architecture input containing behavioral spec and run ID.

        Returns:
            ServiceResult containing ArchitectureOutput with the synthesized
            architecture spec and storage key, or an error on failure.
        """
        import time

        start_time = time.perf_counter()

        try:
            logger.info("Synthesizing architecture", run_id=input_data.run_id)

            behavioral_spec = input_data.behavioral_spec

            # Prepare agent input
            agent_input = ArchitectInput(
                app_name=behavioral_spec.app_name,
                functional_requirements=[
                    {
                        "id": r.req_id,
                        "title": r.title,
                        "description": r.description,
                    }
                    for r in behavioral_spec.functional_requirements[:15]
                ],
                non_functional_requirements=[
                    {
                        "id": r.req_id,
                        "title": r.title,
                        "category": r.category.value,
                    }
                    for r in behavioral_spec.non_functional_requirements
                ],
                screen_specs=[
                    {
                        "id": s.screen_id,
                        "name": s.screen_name,
                        "components": len(s.components),
                    }
                    for s in behavioral_spec.screen_specs[:15]
                ],
                data_entities=[],  # Would extract from behavioral spec
            )

            # Call agent
            context = AgentContext(
                run_id=input_data.run_id,
                stage="architecture",
            )

            agent_response = await self.architect_agent.invoke(agent_input, context)
            agent_output = agent_response.output if agent_response.success else None

            if not agent_response.success:
                logger.warning("Agent failed, using fallback architecture", error=agent_response.error)

            # Create modules
            modules = self._create_default_modules(behavioral_spec)

            # Create ADRs
            adrs = self._create_default_adrs()

            # Create technology decisions
            tech_decisions = self._create_default_technology_decisions()

            # Create data flow diagram
            data_flow = self._create_data_flow_diagram(behavioral_spec)

            # Create architecture spec
            spec = ArchitectureSpec(
                spec_id=str(uuid.uuid4()),
                architecture_pattern=agent_output.architecture_pattern if agent_output else "MVVM",
                architecture_rationale=agent_output.architecture_rationale if agent_output else "MVVM with Compose for modern Android development",
                modules=modules,
                data_flow_diagrams=[data_flow],
                technology_decisions=tech_decisions,
                adrs=adrs,
                security_considerations=[
                    "Encrypt sensitive data at rest",
                    "Use HTTPS for all network calls",
                    "Implement certificate pinning",
                    "Secure credential storage in EncryptedSharedPreferences",
                ],
                source_behavioral_spec_id=behavioral_spec.spec_id,
            )

            # Store spec
            storage_key = f"specs/{behavioral_spec.spec_id}/architecture_spec.json"
            await self.storage.store_model(storage_key, spec)

            output = ArchitectureOutput(
                architecture_spec=spec,
                storage_key=storage_key,
            )

            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.info(
                "Architecture synthesized",
                modules=len(modules),
                adrs=len(adrs),
                duration_ms=duration_ms,
            )

            return ServiceResult.ok(output, duration_ms=duration_ms)

        except Exception as e:
            logger.error("Architecture synthesis failed", error=str(e))
            return ServiceResult.fail(str(e))
