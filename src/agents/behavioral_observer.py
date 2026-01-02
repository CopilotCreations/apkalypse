"""
Behavioral Observer Agent.

A read-only agent that observes and interprets UI states, extracting
behavioral information without modifying or storing decompiled source.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from .base import Agent, PromptTemplate
from .registry import AgentRegistry


class BehavioralObserverInput(BaseModel):
    """Input for the Behavioral Observer Agent."""

    screen_hierarchy: str = Field(description="UI hierarchy XML or JSON")
    screen_screenshot_description: str = Field(description="Description of screenshot")
    current_activity: str | None = Field(default=None)
    previous_screens: list[str] = Field(default_factory=list, description="Previous screen names")
    observed_actions: list[str] = Field(default_factory=list, description="Actions taken")


class ScreenObservation(BaseModel):
    """Observation about a screen."""

    screen_name: str = Field(description="Inferred screen name")
    screen_purpose: str = Field(description="Purpose of this screen")
    primary_elements: list[str] = Field(description="Key UI elements identified")
    possible_actions: list[str] = Field(description="Actions user can take")
    navigation_options: list[str] = Field(description="Navigation options available")
    data_displayed: list[str] = Field(description="Types of data displayed")
    is_form: bool = Field(default=False)
    is_list: bool = Field(default=False)
    is_detail: bool = Field(default=False)
    requires_auth: bool = Field(default=False)


class BehavioralObserverOutput(BaseModel):
    """Output from the Behavioral Observer Agent."""

    observation: ScreenObservation
    confidence: float = Field(ge=0.0, le=1.0)
    notes: list[str] = Field(default_factory=list)


@AgentRegistry.register
class BehavioralObserverAgent(Agent[BehavioralObserverInput, BehavioralObserverOutput]):
    """Agent for observing and interpreting UI states.

    This agent is read-only and focuses on extracting behavioral information
    from UI hierarchies and screenshots, without accessing or storing any
    decompiled source code.
    """

    NAME = "behavioral_observer"

    @property
    def name(self) -> str:
        return self.NAME

    @property
    def description(self) -> str:
        return "Observes UI states and extracts behavioral information"

    @property
    def input_type(self) -> type[BehavioralObserverInput]:
        return BehavioralObserverInput

    @property
    def output_type(self) -> type[BehavioralObserverOutput]:
        return BehavioralObserverOutput

    def get_prompt_template(self) -> PromptTemplate:
        return PromptTemplate(
            template_id="behavioral_observer_v1",
            version="1.0.0",
            system_prompt="""You are a Behavioral Observer Agent specialized in analyzing Android UI states.

Your role is to observe and interpret what you see in UI hierarchies and screenshots,
extracting behavioral information about the application's functionality.

CRITICAL RULES:
1. You are READ-ONLY. You do not modify, store, or reproduce any source code.
2. Focus on OBSERVABLE BEHAVIOR, not implementation details.
3. Describe what the user can DO on this screen, not how it's coded.
4. Infer user intent and purpose from UI elements.
5. Never include code snippets or implementation details in your output.

Your observations should be:
- Behavioral (what can users do?)
- User-centric (what is the purpose for the user?)
- Implementation-agnostic (no code, no technical details)
""",
            user_prompt_template="""Analyze the following UI state and provide behavioral observations.

## UI Hierarchy
{screen_hierarchy}

## Screenshot Description
{screen_screenshot_description}

## Current Activity
{current_activity}

## Navigation Context
Previous screens: {previous_screens}
Actions taken to reach here: {observed_actions}

Provide your observation as a JSON object with the following structure:
{{
    "observation": {{
        "screen_name": "descriptive name for this screen",
        "screen_purpose": "what is this screen for",
        "primary_elements": ["list of key UI elements"],
        "possible_actions": ["actions the user can take"],
        "navigation_options": ["where can user navigate from here"],
        "data_displayed": ["types of data shown"],
        "is_form": false,
        "is_list": false,
        "is_detail": false,
        "requires_auth": false
    }},
    "confidence": 0.85,
    "notes": ["any relevant observations"]
}}
""",
            output_format_instructions="Respond with valid JSON only.",
        )

    def prepare_input(self, input_data: BehavioralObserverInput) -> dict[str, Any]:
        return {
            "screen_hierarchy": input_data.screen_hierarchy[:8000],  # Truncate if needed
            "screen_screenshot_description": input_data.screen_screenshot_description,
            "current_activity": input_data.current_activity or "Unknown",
            "previous_screens": ", ".join(input_data.previous_screens[-5:]) or "None",
            "observed_actions": ", ".join(input_data.observed_actions[-5:]) or "None",
        }

    def validate_output(self, output: BehavioralObserverOutput) -> list[str]:
        warnings = []
        if output.confidence < 0.5:
            warnings.append(f"Low confidence observation: {output.confidence}")
        if not output.observation.primary_elements:
            warnings.append("No primary elements identified")
        return warnings
