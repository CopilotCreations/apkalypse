"""
Product Spec Author Agent.

Generates implementation-agnostic product specifications from behavioral models.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from .base import Agent, PromptTemplate
from .registry import AgentRegistry


class ProductSpecInput(BaseModel):
    """Input for the Product Spec Author Agent."""

    app_name: str = Field(description="Application name")
    app_description: str = Field(description="Brief app description")
    screens_summary: list[dict[str, Any]] = Field(description="Summary of all screens")
    user_intents: list[dict[str, Any]] = Field(description="Identified user intents")
    navigation_flows: list[dict[str, Any]] = Field(description="Navigation flows")
    data_entities: list[str] = Field(description="Data entities in the app")


class RequirementSpec(BaseModel):
    """A single requirement specification."""

    req_id: str
    title: str
    description: str
    priority: str  # must/should/could
    acceptance_criteria: list[str]
    related_screens: list[str]


class ScreenSpecSummary(BaseModel):
    """Summary specification for a screen."""

    screen_id: str
    screen_name: str
    purpose: str
    key_components: list[str]
    user_actions: list[str]
    error_states: list[str]


class ProductSpecOutput(BaseModel):
    """Output from the Product Spec Author Agent."""

    executive_summary: str = Field(description="High-level app summary")
    scope: str = Field(description="Project scope")
    functional_requirements: list[RequirementSpec] = Field(default_factory=list)
    non_functional_requirements: list[RequirementSpec] = Field(default_factory=list)
    screen_specs: list[ScreenSpecSummary] = Field(default_factory=list)
    out_of_scope: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


@AgentRegistry.register
class ProductSpecAuthorAgent(Agent[ProductSpecInput, ProductSpecOutput]):
    """Agent for authoring product specifications.

    Transforms behavioral models into formal, implementation-agnostic
    product specifications suitable for greenfield development.
    """

    NAME = "product_spec_author"

    @property
    def name(self) -> str:
        """Get the agent's unique identifier name.

        Returns:
            str: The name identifier for this agent.
        """
        return self.NAME

    @property
    def description(self) -> str:
        """Get a human-readable description of the agent's purpose.

        Returns:
            str: A brief description of what this agent does.
        """
        return "Authors implementation-agnostic product specifications"

    @property
    def input_type(self) -> type[ProductSpecInput]:
        """Get the Pydantic model type for agent input.

        Returns:
            type[ProductSpecInput]: The input model class.
        """
        return ProductSpecInput

    @property
    def output_type(self) -> type[ProductSpecOutput]:
        """Get the Pydantic model type for agent output.

        Returns:
            type[ProductSpecOutput]: The output model class.
        """
        return ProductSpecOutput

    def get_prompt_template(self) -> PromptTemplate:
        """Get the prompt template for LLM interaction.

        Returns:
            PromptTemplate: The template containing system and user prompts
                for generating product specifications.
        """
        return PromptTemplate(
            template_id="product_spec_author_v1",
            version="1.0.0",
            system_prompt="""You are a Product Specification Author specialized in writing clear,
implementation-agnostic product specifications for mobile applications.

Your specifications will be used to guide greenfield development of a new application
that replicates the BEHAVIOR of an existing app, without copying its code.

CRITICAL RULES:
1. Write specifications that describe WHAT, not HOW.
2. Focus on user-facing behavior and requirements.
3. Use clear, unambiguous language.
4. Include measurable acceptance criteria.
5. Prioritize requirements using MoSCoW method.
6. Never include implementation details or code.

Your specifications should enable a development team to build an app with the same
user-facing behavior without ever seeing the original codebase.
""",
            user_prompt_template="""Create a comprehensive product specification for the following application.

## Application
Name: {app_name}
Description: {app_description}

## Screens
{screens_summary}

## User Intents
{user_intents}

## Navigation Flows
{navigation_flows}

## Data Entities
{data_entities}

Generate a complete product specification as JSON with this structure:
{{
    "executive_summary": "Brief overview of the application",
    "scope": "What is included in this specification",
    "functional_requirements": [
        {{
            "req_id": "FR-001",
            "title": "Short title",
            "description": "Detailed description",
            "priority": "must|should|could",
            "acceptance_criteria": ["criterion 1", "criterion 2"],
            "related_screens": ["screen_id"]
        }}
    ],
    "non_functional_requirements": [
        {{
            "req_id": "NFR-001",
            "title": "Short title",
            "description": "Detailed description",
            "priority": "must|should|could",
            "acceptance_criteria": ["criterion 1"],
            "related_screens": []
        }}
    ],
    "screen_specs": [
        {{
            "screen_id": "unique_id",
            "screen_name": "Display Name",
            "purpose": "What this screen is for",
            "key_components": ["component1", "component2"],
            "user_actions": ["action1", "action2"],
            "error_states": ["error1", "error2"]
        }}
    ],
    "out_of_scope": ["items not covered"],
    "assumptions": ["assumptions made"]
}}
""",
            output_format_instructions="Respond with valid JSON only.",
        )

    def prepare_input(self, input_data: ProductSpecInput) -> dict[str, Any]:
        """Transform structured input into template variables.

        Converts the ProductSpecInput model into a dictionary of string
        values suitable for formatting into the prompt template.

        Args:
            input_data: The structured input containing app details,
                screens, user intents, navigation flows, and data entities.

        Returns:
            dict[str, Any]: A dictionary with keys matching template
                placeholders and formatted string values.
        """
        import json
        return {
            "app_name": input_data.app_name,
            "app_description": input_data.app_description,
            "screens_summary": json.dumps(input_data.screens_summary, indent=2),
            "user_intents": json.dumps(input_data.user_intents, indent=2),
            "navigation_flows": json.dumps(input_data.navigation_flows, indent=2),
            "data_entities": ", ".join(input_data.data_entities),
        }

    def validate_output(self, output: ProductSpecOutput) -> list[str]:
        """Validate the generated product specification output.

        Checks the output for potential quality issues and returns
        warnings for any detected problems.

        Args:
            output: The generated product specification to validate.

        Returns:
            list[str]: A list of warning messages for any detected issues.
                Empty list if no issues found.
        """
        warnings = []
        if len(output.functional_requirements) < 3:
            warnings.append("Very few functional requirements generated")
        if not output.screen_specs:
            warnings.append("No screen specifications generated")
        return warnings
