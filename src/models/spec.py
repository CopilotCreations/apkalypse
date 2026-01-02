"""
Specification data models.

These models represent the output of the spec generation and architecture agents,
providing implementation-agnostic specifications for the generated application.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class RequirementPriority(str, Enum):
    """Priority levels for requirements."""

    MUST = "must"
    SHOULD = "should"
    COULD = "could"
    WONT = "wont"


class RequirementStatus(str, Enum):
    """Status of a requirement."""

    DRAFT = "draft"
    APPROVED = "approved"
    IMPLEMENTED = "implemented"
    VERIFIED = "verified"


class FunctionalRequirement(BaseModel):
    """A functional requirement derived from behavioral analysis."""

    req_id: str = Field(description="Unique requirement ID (e.g., FR-001)")
    title: str = Field(description="Short requirement title")
    description: str = Field(description="Detailed requirement description")
    
    priority: RequirementPriority = Field(default=RequirementPriority.SHOULD)
    status: RequirementStatus = Field(default=RequirementStatus.DRAFT)
    
    # Traceability
    derived_from_screens: list[str] = Field(default_factory=list)
    derived_from_intents: list[str] = Field(default_factory=list)
    derived_from_transitions: list[str] = Field(default_factory=list)
    
    # Acceptance criteria
    acceptance_criteria: list[str] = Field(default_factory=list)
    
    # Dependencies
    depends_on: list[str] = Field(default_factory=list)
    
    # Categories
    category: str = Field(default="general", description="Requirement category")
    tags: list[str] = Field(default_factory=list)


class NFRCategory(str, Enum):
    """Categories of non-functional requirements."""

    PERFORMANCE = "performance"
    SECURITY = "security"
    USABILITY = "usability"
    RELIABILITY = "reliability"
    MAINTAINABILITY = "maintainability"
    PORTABILITY = "portability"
    ACCESSIBILITY = "accessibility"
    SCALABILITY = "scalability"


class NonFunctionalRequirement(BaseModel):
    """A non-functional requirement."""

    req_id: str = Field(description="Unique requirement ID (e.g., NFR-001)")
    title: str = Field(description="Short requirement title")
    description: str = Field(description="Detailed requirement description")
    
    category: NFRCategory = Field(description="NFR category")
    priority: RequirementPriority = Field(default=RequirementPriority.SHOULD)
    
    # Measurable criteria
    metric: str | None = Field(default=None, description="Measurable metric")
    target_value: str | None = Field(default=None, description="Target value for metric")
    
    # Testing
    test_approach: str = Field(default="", description="How to verify this requirement")


class UIComponentSpec(BaseModel):
    """Specification for a UI component."""

    component_id: str = Field(description="Unique component identifier")
    component_type: str = Field(description="Type of component")
    name: str = Field(description="Component name")
    
    # Appearance
    description: str = Field(default="")
    visual_style: str = Field(default="", description="Style guidance")
    
    # Behavior
    interactions: list[str] = Field(default_factory=list)
    states: list[str] = Field(default_factory=list)
    
    # Data
    data_bindings: list[str] = Field(default_factory=list)
    
    # Accessibility
    content_description: str | None = Field(default=None)
    accessibility_role: str | None = Field(default=None)


class ScreenSpec(BaseModel):
    """Complete specification for a screen."""

    screen_id: str = Field(description="Unique screen identifier")
    screen_name: str = Field(description="Human-readable screen name")
    description: str = Field(description="Screen purpose description")
    
    # UI specification
    layout_type: str = Field(default="column", description="Primary layout type")
    components: list[UIComponentSpec] = Field(default_factory=list)
    
    # Navigation
    entry_points: list[str] = Field(default_factory=list, description="How to reach this screen")
    exit_points: list[str] = Field(default_factory=list, description="Where user can go from here")
    
    # State management
    state_properties: list[str] = Field(default_factory=list)
    loading_states: list[str] = Field(default_factory=list)
    error_states: list[str] = Field(default_factory=list)
    
    # Requirements trace
    implements_requirements: list[str] = Field(default_factory=list)
    
    # Wireframe reference
    wireframe_hash: str | None = Field(default=None)


class ErrorCase(BaseModel):
    """Specification for an error case."""

    error_id: str = Field(description="Unique error identifier")
    error_type: str = Field(description="Type of error")
    
    trigger_conditions: list[str] = Field(default_factory=list)
    user_message: str = Field(description="Message shown to user")
    recovery_actions: list[str] = Field(default_factory=list)
    
    is_recoverable: bool = Field(default=True)
    retry_strategy: str | None = Field(default=None)


class ErrorHandlingSpec(BaseModel):
    """Complete error handling specification."""

    global_error_handler: str = Field(default="", description="Global error handling strategy")
    error_cases: list[ErrorCase] = Field(default_factory=list)
    
    # Logging
    log_errors: bool = Field(default=True)
    error_reporting_endpoint: str | None = Field(default=None)
    
    # Offline behavior
    offline_error_message: str = Field(default="No internet connection")
    offline_retry_strategy: str = Field(default="exponential_backoff")


class ModuleType(str, Enum):
    """Types of architecture modules."""

    APP = "app"
    FEATURE = "feature"
    CORE = "core"
    DATA = "data"
    DOMAIN = "domain"
    UI = "ui"
    COMMON = "common"


class ModuleDefinition(BaseModel):
    """Definition of an architecture module."""

    module_id: str = Field(description="Unique module identifier")
    module_name: str = Field(description="Module name (Gradle module name)")
    module_type: ModuleType = Field(description="Module type")
    
    description: str = Field(default="")
    
    # Dependencies
    depends_on: list[str] = Field(default_factory=list)
    
    # Responsibilities
    responsibilities: list[str] = Field(default_factory=list)
    public_api: list[str] = Field(default_factory=list, description="Public interfaces")
    
    # Implementation hints
    suggested_packages: list[str] = Field(default_factory=list)
    key_classes: list[str] = Field(default_factory=list)


class DataFlowNode(BaseModel):
    """A node in the data flow diagram."""

    node_id: str
    node_type: str  # source, process, store, sink
    name: str
    description: str = ""


class DataFlowEdge(BaseModel):
    """An edge in the data flow diagram."""

    from_node: str
    to_node: str
    data_type: str
    description: str = ""


class DataFlowDiagram(BaseModel):
    """Data flow diagram for the architecture."""

    diagram_id: str
    name: str
    description: str = ""
    
    nodes: list[DataFlowNode] = Field(default_factory=list)
    edges: list[DataFlowEdge] = Field(default_factory=list)


class TechnologyChoice(BaseModel):
    """A technology choice with rationale."""

    technology: str = Field(description="Technology name")
    version: str = Field(default="latest", description="Version to use")
    purpose: str = Field(description="What this technology is used for")
    rationale: str = Field(description="Why this technology was chosen")
    alternatives_considered: list[str] = Field(default_factory=list)


class TechnologyDecision(BaseModel):
    """Complete technology stack decision."""

    decision_id: str
    category: str  # language, framework, library, tool
    
    choices: list[TechnologyChoice] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)


class ArchitectureDecisionRecord(BaseModel):
    """Architecture Decision Record (ADR)."""

    adr_id: str = Field(description="ADR identifier (e.g., ADR-001)")
    title: str = Field(description="Decision title")
    date: datetime = Field(default_factory=datetime.utcnow)
    status: str = Field(default="accepted", description="proposed/accepted/deprecated/superseded")
    
    # ADR sections
    context: str = Field(description="Problem context")
    decision: str = Field(description="The decision made")
    consequences: list[str] = Field(default_factory=list, description="Consequences of the decision")
    
    # Traceability
    related_requirements: list[str] = Field(default_factory=list)
    supersedes: str | None = Field(default=None, description="ADR this supersedes")


class BehavioralSpec(BaseModel):
    """Complete behavioral specification document."""

    spec_version: str = Field(default="1.0.0")
    spec_id: str = Field(description="Unique spec identifier")
    app_name: str = Field(description="Application name")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Overview
    executive_summary: str = Field(default="")
    scope: str = Field(default="")
    
    # Requirements
    functional_requirements: list[FunctionalRequirement] = Field(default_factory=list)
    non_functional_requirements: list[NonFunctionalRequirement] = Field(default_factory=list)
    
    # Screen specifications
    screen_specs: list[ScreenSpec] = Field(default_factory=list)
    
    # Error handling
    error_handling: ErrorHandlingSpec = Field(default_factory=ErrorHandlingSpec)
    
    # Source traceability
    source_behavior_model_id: str = Field(description="ID of source behavior model")


class ArchitectureSpec(BaseModel):
    """Complete architecture specification."""

    spec_version: str = Field(default="1.0.0")
    spec_id: str = Field(description="Unique spec identifier")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Architecture pattern
    architecture_pattern: str = Field(default="MVVM", description="MVI/MVVM/MVP")
    architecture_rationale: str = Field(default="")
    
    # Module structure
    modules: list[ModuleDefinition] = Field(default_factory=list)
    
    # Data flow
    data_flow_diagrams: list[DataFlowDiagram] = Field(default_factory=list)
    
    # Technology decisions
    technology_decisions: list[TechnologyDecision] = Field(default_factory=list)
    
    # ADRs
    adrs: list[ArchitectureDecisionRecord] = Field(default_factory=list)
    
    # Security
    security_considerations: list[str] = Field(default_factory=list)
    threat_model: dict[str, Any] = Field(default_factory=dict)
    
    # Source traceability
    source_behavioral_spec_id: str = Field(description="ID of source behavioral spec")
