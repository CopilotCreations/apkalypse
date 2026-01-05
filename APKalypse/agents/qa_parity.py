"""
QA / Parity Agent.

Validates behavioral parity between original and generated applications.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from .base import Agent, PromptTemplate
from .registry import AgentRegistry


class ParityInput(BaseModel):
    """Input for the QA Parity Agent."""

    test_scenario: str = Field(description="Description of the test scenario")
    original_behavior: dict[str, Any] = Field(description="Observed behavior in original app")
    generated_behavior: dict[str, Any] = Field(description="Observed behavior in generated app")
    screen_states_original: list[dict[str, Any]] = Field(default_factory=list)
    screen_states_generated: list[dict[str, Any]] = Field(default_factory=list)


class ParityIssue(BaseModel):
    """A parity issue found during verification."""

    issue_id: str
    severity: str  # critical, major, minor
    category: str  # ui, navigation, data, behavior
    description: str
    original_value: str
    generated_value: str
    suggested_fix: str


class ParityOutput(BaseModel):
    """Output from the QA Parity Agent."""

    scenario_name: str
    overall_parity: float = Field(ge=0.0, le=1.0, description="0-1 parity score")
    passed: bool
    issues: list[ParityIssue] = Field(default_factory=list)
    matching_behaviors: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


@AgentRegistry.register
class QAParityAgent(Agent[ParityInput, ParityOutput]):
    """Agent for verifying behavioral parity.

    Compares observed behaviors between original and generated applications,
    identifying discrepancies and producing parity reports.
    """

    NAME = "qa_parity"

    @property
    def name(self) -> str:
        """Get the agent's unique identifier.

        Returns:
            str: The agent name 'qa_parity'.
        """
        return self.NAME

    @property
    def description(self) -> str:
        """Get the agent's description.

        Returns:
            str: A brief description of the agent's purpose.
        """
        return "Verifies behavioral parity between applications"

    @property
    def input_type(self) -> type[ParityInput]:
        """Get the expected input type for this agent.

        Returns:
            type[ParityInput]: The ParityInput model class.
        """
        return ParityInput

    @property
    def output_type(self) -> type[ParityOutput]:
        """Get the expected output type for this agent.

        Returns:
            type[ParityOutput]: The ParityOutput model class.
        """
        return ParityOutput

    def get_prompt_template(self) -> PromptTemplate:
        """Get the prompt template for parity verification.

        Returns:
            PromptTemplate: A template containing system and user prompts
                for comparing application behaviors.
        """
        return PromptTemplate(
            template_id="qa_parity_v1",
            version="1.0.0",
            system_prompt="""You are a QA Parity Agent specialized in verifying behavioral parity
between applications. Your role is to compare observed behaviors and identify discrepancies.

PARITY VERIFICATION RULES:
1. Focus on USER-FACING behavior, not implementation
2. Ignore cosmetic differences that don't affect functionality
3. Flag critical differences in navigation flow
4. Flag missing or different functionality
5. Consider data handling and error states

SEVERITY LEVELS:
- critical: Breaks core functionality or user journey
- major: Significant difference in behavior or UX
- minor: Cosmetic or minor behavioral difference

CATEGORIES:
- ui: Visual differences
- navigation: Flow/routing differences
- data: Data handling differences
- behavior: Interaction behavior differences

Be thorough but practical - focus on what matters to users.
""",
            user_prompt_template="""Verify behavioral parity for the following test scenario.

## Scenario
{test_scenario}

## Original App Behavior
{original_behavior}

## Generated App Behavior
{generated_behavior}

## Original Screen States
{screen_states_original}

## Generated Screen States
{screen_states_generated}

Analyze the parity and generate a report as JSON:
{{
    "scenario_name": "Name of this scenario",
    "overall_parity": 0.95,
    "passed": true,
    "issues": [
        {{
            "issue_id": "PAR-001",
            "severity": "minor",
            "category": "ui",
            "description": "Description of the issue",
            "original_value": "What original does",
            "generated_value": "What generated does",
            "suggested_fix": "How to fix"
        }}
    ],
    "matching_behaviors": ["List of behaviors that match"],
    "notes": ["Additional observations"]
}}
""",
            output_format_instructions="Respond with valid JSON only.",
        )

    def prepare_input(self, input_data: ParityInput) -> dict[str, Any]:
        """Prepare input data for the prompt template.

        Serializes behaviors and screen states to JSON format for
        inclusion in the prompt.

        Args:
            input_data: The parity input containing test scenario,
                original and generated behaviors, and screen states.

        Returns:
            dict[str, Any]: A dictionary with serialized values ready
                for template substitution.
        """
        import json
        return {
            "test_scenario": input_data.test_scenario,
            "original_behavior": json.dumps(input_data.original_behavior, indent=2),
            "generated_behavior": json.dumps(input_data.generated_behavior, indent=2),
            "screen_states_original": json.dumps(input_data.screen_states_original[:10], indent=2),
            "screen_states_generated": json.dumps(input_data.screen_states_generated[:10], indent=2),
        }

    def validate_output(self, output: ParityOutput) -> list[str]:
        """Validate the parity output for consistency issues.

        Checks for logical inconsistencies such as passing with critical
        issues or very low parity scores.

        Args:
            output: The parity verification output to validate.

        Returns:
            list[str]: A list of warning messages for any detected issues.
        """
        warnings = []
        critical_issues = [i for i in output.issues if i.severity == "critical"]
        if critical_issues and output.passed:
            warnings.append("Scenario passed despite critical issues")
        if output.overall_parity < 0.5:
            warnings.append("Very low parity score")
        return warnings
