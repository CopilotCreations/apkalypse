"""
Behavior2Build Data Models.

This module contains all Pydantic models used throughout the pipeline for
type-safe, versioned data representation. These models define the canonical
internal representation of extracted behaviors.
"""

from .apk import APKMetadata, APKProvenance, ManifestData, PermissionInfo
from .behavior import (
    ActionType,
    BehaviorModel,
    DataFlow,
    NavigationRule,
    ScreenModel,
    SideEffect,
    StateTransition,
    UserAction,
    UserIntent,
)
from .spec import (
    ArchitectureDecisionRecord,
    DataFlowDiagram,
    ErrorHandlingSpec,
    FunctionalRequirement,
    ModuleDefinition,
    NonFunctionalRequirement,
    ScreenSpec,
    TechnologyDecision,
)
from .codegen import (
    AndroidProject,
    GradleModule,
    KotlinFile,
    ResourceFile,
)

__all__ = [
    # APK models
    "APKMetadata",
    "APKProvenance",
    "ManifestData",
    "PermissionInfo",
    # Behavior models
    "ActionType",
    "BehaviorModel",
    "DataFlow",
    "NavigationRule",
    "ScreenModel",
    "SideEffect",
    "StateTransition",
    "UserAction",
    "UserIntent",
    # Spec models
    "ArchitectureDecisionRecord",
    "DataFlowDiagram",
    "ErrorHandlingSpec",
    "FunctionalRequirement",
    "ModuleDefinition",
    "NonFunctionalRequirement",
    "ScreenSpec",
    "TechnologyDecision",
    # Codegen models
    "AndroidProject",
    "GradleModule",
    "KotlinFile",
    "ResourceFile",
]
