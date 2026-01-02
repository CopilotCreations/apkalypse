"""
System Architect Agent.

Designs the technical architecture for the generated application.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from .base import Agent, PromptTemplate
from .registry import AgentRegistry


class ArchitectInput(BaseModel):
    """Input for the System Architect Agent."""

    app_name: str = Field(description="Application name")
    functional_requirements: list[dict[str, Any]] = Field(description="Functional requirements")
    non_functional_requirements: list[dict[str, Any]] = Field(description="Non-functional requirements")
    screen_specs: list[dict[str, Any]] = Field(description="Screen specifications")
    data_entities: list[str] = Field(description="Data entities")
    api_endpoints: list[dict[str, Any]] = Field(default_factory=list, description="Detected API patterns")


class ModuleSpec(BaseModel):
    """Specification for an architecture module."""

    module_name: str
    module_type: str  # app, feature, core, data, domain
    purpose: str
    dependencies: list[str]
    key_interfaces: list[str]


class ADR(BaseModel):
    """Architecture Decision Record."""

    adr_id: str
    title: str
    context: str
    decision: str
    consequences: list[str]


class TechChoice(BaseModel):
    """Technology choice with rationale."""

    category: str
    technology: str
    version: str
    rationale: str


class SecurityConsideration(BaseModel):
    """Security consideration."""

    concern: str
    mitigation: str
    priority: str


class ArchitectOutput(BaseModel):
    """Output from the System Architect Agent."""

    architecture_pattern: str = Field(description="MVVM, MVI, etc.")
    architecture_rationale: str
    modules: list[ModuleSpec] = Field(default_factory=list)
    adrs: list[ADR] = Field(default_factory=list)
    technology_stack: list[TechChoice] = Field(default_factory=list)
    security_considerations: list[SecurityConsideration] = Field(default_factory=list)
    data_layer_design: str = Field(default="")
    dependency_injection_approach: str = Field(default="")


@AgentRegistry.register
class SystemArchitectAgent(Agent[ArchitectInput, ArchitectOutput]):
    """Agent for designing system architecture.

    Creates a comprehensive technical architecture for the generated
    Android application based on behavioral specifications.
    """

    NAME = "system_architect"

    @property
    def name(self) -> str:
        return self.NAME

    @property
    def description(self) -> str:
        return "Designs technical architecture for Android applications"

    @property
    def input_type(self) -> type[ArchitectInput]:
        return ArchitectInput

    @property
    def output_type(self) -> type[ArchitectOutput]:
        return ArchitectOutput

    def get_prompt_template(self) -> PromptTemplate:
        return PromptTemplate(
            template_id="system_architect_v1",
            version="1.0.0",
            system_prompt="""You are a System Architect specialized in modern Android application architecture.

Your role is to design clean, maintainable, and testable architectures for Android apps
using Kotlin and Jetpack Compose. You follow industry best practices and SOLID principles.

DESIGN PRINCIPLES:
1. Clean Architecture - separate concerns into layers
2. Dependency Inversion - depend on abstractions
3. Single Responsibility - each module has one reason to change
4. Testability - design for easy testing
5. Scalability - support future growth

TECHNOLOGY PREFERENCES:
- Kotlin as the primary language
- Jetpack Compose for UI
- Coroutines and Flow for async
- Hilt for dependency injection
- Room for local persistence
- Retrofit/Ktor for networking
- MVVM or MVI for presentation

Generate architectures that are:
- Modular and maintainable
- Following Android best practices
- Production-ready
""",
            user_prompt_template="""Design the architecture for the following Android application.

## Application
Name: {app_name}

## Functional Requirements
{functional_requirements}

## Non-Functional Requirements
{non_functional_requirements}

## Screen Specifications
{screen_specs}

## Data Entities
{data_entities}

## Detected API Patterns
{api_endpoints}

Generate a comprehensive architecture design as JSON:
{{
    "architecture_pattern": "MVVM or MVI",
    "architecture_rationale": "Why this pattern was chosen",
    "modules": [
        {{
            "module_name": ":app",
            "module_type": "app",
            "purpose": "Main application module",
            "dependencies": [":feature:home", ":core:ui"],
            "key_interfaces": []
        }},
        {{
            "module_name": ":feature:home",
            "module_type": "feature",
            "purpose": "Home screen feature",
            "dependencies": [":core:domain", ":core:ui"],
            "key_interfaces": ["HomeViewModel", "HomeScreen"]
        }}
    ],
    "adrs": [
        {{
            "adr_id": "ADR-001",
            "title": "Use MVVM Pattern",
            "context": "Need a presentation architecture",
            "decision": "Use MVVM with Compose",
            "consequences": ["Clean separation", "Easy testing"]
        }}
    ],
    "technology_stack": [
        {{
            "category": "language",
            "technology": "Kotlin",
            "version": "1.9.22",
            "rationale": "Modern, expressive, Android-first"
        }},
        {{
            "category": "ui",
            "technology": "Jetpack Compose",
            "version": "1.5.4",
            "rationale": "Modern declarative UI"
        }}
    ],
    "security_considerations": [
        {{
            "concern": "Data at rest",
            "mitigation": "Encrypt sensitive local data",
            "priority": "high"
        }}
    ],
    "data_layer_design": "Description of data layer approach",
    "dependency_injection_approach": "Hilt with module structure"
}}
""",
            output_format_instructions="Respond with valid JSON only.",
        )

    def prepare_input(self, input_data: ArchitectInput) -> dict[str, Any]:
        import json
        return {
            "app_name": input_data.app_name,
            "functional_requirements": json.dumps(input_data.functional_requirements[:20], indent=2),
            "non_functional_requirements": json.dumps(input_data.non_functional_requirements[:10], indent=2),
            "screen_specs": json.dumps(input_data.screen_specs[:15], indent=2),
            "data_entities": ", ".join(input_data.data_entities),
            "api_endpoints": json.dumps(input_data.api_endpoints[:10], indent=2),
        }

    def validate_output(self, output: ArchitectOutput) -> list[str]:
        warnings = []
        if not output.modules:
            warnings.append("No modules defined")
        if not output.adrs:
            warnings.append("No ADRs provided")
        if output.architecture_pattern not in ["MVVM", "MVI", "MVP"]:
            warnings.append(f"Unusual architecture pattern: {output.architecture_pattern}")
        return warnings
