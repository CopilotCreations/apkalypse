"""
Android Implementation Agent.

Generates Kotlin code for Android applications based on specifications.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from .base import Agent, PromptTemplate
from .registry import AgentRegistry


class CodeGenInput(BaseModel):
    """Input for the Android Implementation Agent."""

    module_name: str = Field(description="Module being generated")
    component_type: str = Field(description="Type of component: viewmodel, screen, repository, etc.")
    component_name: str = Field(description="Name of the component")
    screen_spec: dict[str, Any] | None = Field(default=None, description="Screen specification if UI")
    data_spec: dict[str, Any] | None = Field(default=None, description="Data specification if data layer")
    dependencies: list[str] = Field(default_factory=list, description="Dependencies to inject")
    related_components: list[str] = Field(default_factory=list, description="Related components")


class GeneratedFile(BaseModel):
    """A generated source file."""

    file_name: str
    package_name: str
    relative_path: str
    content: str
    file_type: str  # kotlin, xml, etc.


class CodeGenOutput(BaseModel):
    """Output from the Android Implementation Agent."""

    files: list[GeneratedFile] = Field(default_factory=list)
    additional_dependencies: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


@AgentRegistry.register
class AndroidImplementationAgent(Agent[CodeGenInput, CodeGenOutput]):
    """Agent for generating Android/Kotlin code.

    Generates clean, production-ready Kotlin code following modern
    Android development practices and the specified architecture.
    """

    NAME = "android_implementation"

    @property
    def name(self) -> str:
        return self.NAME

    @property
    def description(self) -> str:
        return "Generates Kotlin code for Android applications"

    @property
    def input_type(self) -> type[CodeGenInput]:
        return CodeGenInput

    @property
    def output_type(self) -> type[CodeGenOutput]:
        return CodeGenOutput

    def get_prompt_template(self) -> PromptTemplate:
        return PromptTemplate(
            template_id="android_implementation_v1",
            version="1.0.0",
            system_prompt="""You are an Android Implementation Agent specialized in generating
production-ready Kotlin code for Android applications.

CODE GENERATION RULES:
1. Generate CLEAN, ORIGINAL code - never copy from any source
2. Follow Kotlin best practices and idioms
3. Use Jetpack Compose for all UI components
4. Follow MVVM pattern with StateFlow for state management
5. Use Hilt for dependency injection
6. Write self-documenting code with KDoc where needed
7. Include proper error handling
8. Make code testable with constructor injection

STYLE GUIDELINES:
- 4-space indentation
- Descriptive naming
- Single responsibility per class
- Prefer immutability
- Use data classes for state
- Use sealed classes for UI state/events

COMPOSE GUIDELINES:
- Use Material 3 components
- Proper modifier usage
- Preview annotations
- Stateless composables where possible
""",
            user_prompt_template="""Generate the following Android component.

## Module
{module_name}

## Component
Type: {component_type}
Name: {component_name}

## Specification
{spec}

## Dependencies
{dependencies}

## Related Components
{related_components}

Generate the component as JSON:
{{
    "files": [
        {{
            "file_name": "ComponentName.kt",
            "package_name": "com.example.app.feature",
            "relative_path": "feature/src/main/kotlin/com/example/app/feature",
            "content": "// Complete Kotlin code here",
            "file_type": "kotlin"
        }}
    ],
    "additional_dependencies": ["dependency:artifact:version"],
    "notes": ["Any implementation notes"]
}}

Generate complete, compilable code. Include all necessary imports.
""",
            output_format_instructions="Respond with valid JSON only. Escape code properly.",
        )

    def prepare_input(self, input_data: CodeGenInput) -> dict[str, Any]:
        import json

        spec = input_data.screen_spec or input_data.data_spec or {}

        return {
            "module_name": input_data.module_name,
            "component_type": input_data.component_type,
            "component_name": input_data.component_name,
            "spec": json.dumps(spec, indent=2),
            "dependencies": ", ".join(input_data.dependencies) or "None",
            "related_components": ", ".join(input_data.related_components) or "None",
        }

    def validate_output(self, output: CodeGenOutput) -> list[str]:
        warnings = []
        if not output.files:
            warnings.append("No files generated")
        for file in output.files:
            if len(file.content) < 50:
                warnings.append(f"File {file.file_name} has very little content")
            if "TODO" in file.content:
                warnings.append(f"File {file.file_name} contains TODO markers")
        return warnings
