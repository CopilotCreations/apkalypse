"""
Spec Generation Service.

Generates implementation-agnostic product specifications from behavioral models.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from ...agents import AgentContext, ProductSpecAuthorAgent
from ...agents.product_spec import ProductSpecInput, ProductSpecOutput
from ...core.logging import get_logger
from ...core.types import ServiceResult
from ...models.behavior import BehaviorModel
from ...models.spec import (
    BehavioralSpec,
    ErrorHandlingSpec,
    FunctionalRequirement,
    NonFunctionalRequirement,
    NFRCategory,
    RequirementPriority,
    ScreenSpec,
    UIComponentSpec,
)
from ...storage import StorageBackend

logger = get_logger(__name__)


class SpecGenerationInput(BaseModel):
    """Input for spec generation."""

    behavior_model: BehaviorModel
    app_name: str = Field(description="Name for the generated app")
    run_id: str = Field(description="Pipeline run ID")


class SpecGenerationOutput(BaseModel):
    """Output from spec generation."""

    behavioral_spec: BehavioralSpec
    storage_key: str = Field(description="Storage key for persisted spec")


class SpecGenerationService:
    """Service for generating product specifications.

    Uses AI agents to transform behavioral models into formal,
    implementation-agnostic product specifications.
    """

    def __init__(self, storage: StorageBackend) -> None:
        """Initialize the spec generation service.

        Args:
            storage: Backend for persisting generated specifications.
        """
        self.storage = storage
        self.spec_agent = ProductSpecAuthorAgent()

    def _create_screen_specs(self, behavior_model: BehaviorModel) -> list[ScreenSpec]:
        """Create screen specifications from behavior model.

        Args:
            behavior_model: The behavior model containing screen definitions,
                transitions, and interactive elements.

        Returns:
            A list of ScreenSpec objects representing each screen's
            specification including components, entry points, and exit points.
        """
        specs = []

        for screen in behavior_model.screens:
            # Determine entry/exit points
            entry_points = [
                t.from_screen_id
                for t in behavior_model.get_transitions_to(screen.screen_id)
            ]
            exit_points = [
                t.to_screen_id
                for t in behavior_model.get_transitions_from(screen.screen_id)
            ]

            # Create component specs from interactive elements
            components = []
            for elem_id in screen.interactive_elements[:10]:  # Limit for spec
                components.append(UIComponentSpec(
                    component_id=elem_id,
                    component_type="interactive",
                    name=elem_id.replace("_", " ").title(),
                    interactions=["tap"],
                ))

            spec = ScreenSpec(
                screen_id=screen.screen_id,
                screen_name=screen.screen_name,
                description=screen.description or f"Screen: {screen.screen_name}",
                components=components,
                entry_points=entry_points,
                exit_points=exit_points,
            )
            specs.append(spec)

        return specs

    def _create_functional_requirements(
        self,
        behavior_model: BehaviorModel,
        agent_output: ProductSpecOutput | None,
    ) -> list[FunctionalRequirement]:
        """Create functional requirements from behavior model and agent output.

        Args:
            behavior_model: The behavior model containing navigation rules
                and user intents to derive requirements from.
            agent_output: Optional agent-generated output containing
                pre-formulated requirements. If None, requirements are
                generated from the behavior model directly.

        Returns:
            A list of FunctionalRequirement objects representing the
            functional requirements for the application.
        """
        requirements = []

        # Use agent-generated requirements if available
        if agent_output:
            for req in agent_output.functional_requirements:
                requirements.append(FunctionalRequirement(
                    req_id=req.req_id,
                    title=req.title,
                    description=req.description,
                    priority=RequirementPriority(req.priority),
                    acceptance_criteria=req.acceptance_criteria,
                    derived_from_screens=req.related_screens,
                ))
        else:
            # Generate basic requirements from behavior model
            req_id = 1

            # Navigation requirements
            for rule in behavior_model.navigation_rules:
                requirements.append(FunctionalRequirement(
                    req_id=f"FR-{req_id:03d}",
                    title=rule.name,
                    description=rule.description,
                    priority=RequirementPriority.SHOULD,
                    derived_from_screens=[rule.to_screen],
                ))
                req_id += 1

            # Intent-based requirements
            for intent in behavior_model.user_intents:
                requirements.append(FunctionalRequirement(
                    req_id=f"FR-{req_id:03d}",
                    title=intent.name,
                    description=intent.description,
                    priority=RequirementPriority.MUST if intent.is_primary else RequirementPriority.SHOULD,
                    derived_from_intents=[intent.intent_id],
                ))
                req_id += 1

        return requirements

    def _create_nonfunctional_requirements(
        self,
        behavior_model: BehaviorModel,
    ) -> list[NonFunctionalRequirement]:
        """Create non-functional requirements based on behavior model.

        Generates standard NFRs for performance, usability, accessibility,
        security, and reliability based on the behavior model properties.

        Args:
            behavior_model: The behavior model used to determine applicable
                NFRs (e.g., security requirements if auth is required).

        Returns:
            A list of NonFunctionalRequirement objects covering performance,
            usability, accessibility, security, and reliability categories.
        """
        requirements = []

        # Performance NFRs
        requirements.append(NonFunctionalRequirement(
            req_id="NFR-001",
            title="App Launch Time",
            description="Application should launch and display first screen within acceptable time",
            category=NFRCategory.PERFORMANCE,
            priority=RequirementPriority.SHOULD,
            metric="Cold start time",
            target_value="< 2 seconds",
        ))

        requirements.append(NonFunctionalRequirement(
            req_id="NFR-002",
            title="Screen Transition Performance",
            description="Navigation between screens should be smooth and responsive",
            category=NFRCategory.PERFORMANCE,
            priority=RequirementPriority.SHOULD,
            metric="Frame rate during transitions",
            target_value=">= 60 fps",
        ))

        # Usability NFRs
        requirements.append(NonFunctionalRequirement(
            req_id="NFR-003",
            title="Touch Target Size",
            description="Interactive elements should have adequate touch target size",
            category=NFRCategory.USABILITY,
            priority=RequirementPriority.MUST,
            metric="Minimum touch target",
            target_value=">= 48dp",
        ))

        # Accessibility NFRs
        requirements.append(NonFunctionalRequirement(
            req_id="NFR-004",
            title="Content Descriptions",
            description="All interactive elements should have accessibility labels",
            category=NFRCategory.ACCESSIBILITY,
            priority=RequirementPriority.SHOULD,
        ))

        # Security NFRs
        if behavior_model.auth_required:
            requirements.append(NonFunctionalRequirement(
                req_id="NFR-005",
                title="Secure Authentication",
                description="User credentials must be handled securely",
                category=NFRCategory.SECURITY,
                priority=RequirementPriority.MUST,
            ))

        # Reliability NFRs
        requirements.append(NonFunctionalRequirement(
            req_id="NFR-006",
            title="Offline Handling",
            description="Application should gracefully handle offline scenarios",
            category=NFRCategory.RELIABILITY,
            priority=RequirementPriority.SHOULD,
        ))

        return requirements

    async def generate(self, input_data: SpecGenerationInput) -> ServiceResult[SpecGenerationOutput]:
        """Generate product specification from a behavioral model.

        Uses AI agents to transform a behavioral model into a formal,
        implementation-agnostic product specification. Falls back to
        rule-based generation if the agent fails.

        Args:
            input_data: The specification generation input containing the
                behavior model, app name, and run ID.

        Returns:
            ServiceResult containing SpecGenerationOutput with the generated
            behavioral spec and storage key, or an error if generation fails.
        """
        import time

        start_time = time.perf_counter()

        try:
            logger.info("Generating specification", run_id=input_data.run_id)

            behavior_model = input_data.behavior_model

            # Prepare agent input
            agent_input = ProductSpecInput(
                app_name=input_data.app_name,
                app_description=f"Android application based on {behavior_model.app_package}",
                screens_summary=[
                    {
                        "id": s.screen_id,
                        "name": s.screen_name,
                        "elements": len(s.interactive_elements),
                    }
                    for s in behavior_model.screens[:15]
                ],
                user_intents=[
                    {
                        "id": i.intent_id,
                        "name": i.name,
                        "description": i.description,
                        "is_primary": i.is_primary,
                    }
                    for i in behavior_model.user_intents
                ],
                navigation_flows=[
                    {
                        "from": t.from_screen_id,
                        "to": t.to_screen_id,
                        "action": t.triggered_by_action.description,
                    }
                    for t in behavior_model.transitions[:20]
                ],
                data_entities=[
                    f.data_type
                    for f in behavior_model.data_flows
                    if f.data_type != "unknown"
                ][:10],
            )

            # Call agent
            context = AgentContext(
                run_id=input_data.run_id,
                stage="spec_generation",
            )

            agent_response = await self.spec_agent.invoke(agent_input, context)
            agent_output = agent_response.output if agent_response.success else None

            if not agent_response.success:
                logger.warning("Agent failed, using fallback spec generation", error=agent_response.error)

            # Create screen specs
            screen_specs = self._create_screen_specs(behavior_model)

            # Create requirements
            functional_requirements = self._create_functional_requirements(
                behavior_model, agent_output
            )
            nonfunctional_requirements = self._create_nonfunctional_requirements(
                behavior_model
            )

            # Create behavioral spec
            spec = BehavioralSpec(
                spec_id=str(uuid.uuid4()),
                app_name=input_data.app_name,
                executive_summary=agent_output.executive_summary if agent_output else f"Specification for {input_data.app_name}",
                scope=agent_output.scope if agent_output else "Full application specification",
                functional_requirements=functional_requirements,
                non_functional_requirements=nonfunctional_requirements,
                screen_specs=screen_specs,
                error_handling=ErrorHandlingSpec(),
                source_behavior_model_id=behavior_model.model_id,
            )

            # Store spec
            storage_key = f"specs/{behavior_model.model_id}/behavioral_spec.json"
            await self.storage.store_model(storage_key, spec)

            output = SpecGenerationOutput(
                behavioral_spec=spec,
                storage_key=storage_key,
            )

            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.info(
                "Specification generated",
                requirements=len(functional_requirements),
                screens=len(screen_specs),
                duration_ms=duration_ms,
            )

            return ServiceResult.ok(output, duration_ms=duration_ms)

        except Exception as e:
            logger.error("Spec generation failed", error=str(e))
            return ServiceResult.fail(str(e))
