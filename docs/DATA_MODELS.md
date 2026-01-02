# Data Models

This document describes the core data models used throughout the Behavior2Build pipeline.

## Model Organization

Models are organized by domain:

```
models/
├── apk.py        # APK metadata and manifest
├── behavior.py   # Behavioral model
├── spec.py       # Specifications
└── codegen.py    # Code generation
```

All models use **Pydantic v2** for:
- Runtime validation
- JSON serialization/deserialization
- Type hints and documentation
- Schema generation

---

## APK Models (`models/apk.py`)

### APKProvenance

Tracks the origin and identity of an APK file.

```python
class APKProvenance(BaseModel):
    sha256_hash: str              # Primary identifier
    sha1_hash: str                # Secondary hash
    md5_hash: str                 # Legacy hash
    file_size_bytes: int          # File size
    file_name: str                # Original filename
    acquired_at: datetime         # When ingested
    source: str = "file"          # "file", "play_store", "url"
    play_store_url: str | None    # If from Play Store
```

### APKMetadata

Complete metadata for an analyzed APK.

```python
class APKMetadata(BaseModel):
    provenance: APKProvenance
    manifest: ManifestData
    play_store: PlayStoreMetadata | None
    analysis_timestamp: datetime
    embedded_libraries: list[str]
    detected_frameworks: list[str]
    resource_counts: dict[str, int]
```

### ManifestData

Parsed AndroidManifest.xml data.

```python
class ManifestData(BaseModel):
    package_name: str
    version_code: int = 1
    version_name: str = "1.0"
    min_sdk_version: int = 21
    target_sdk_version: int = 33
    
    # Application info
    application_label: str = ""
    application_icon: str = ""
    application_theme: str = ""
    
    # Components
    activities: list[ActivityInfo] = []
    services: list[ServiceInfo] = []
    receivers: list[ReceiverInfo] = []
    providers: list[ProviderInfo] = []
    permissions: list[PermissionInfo] = []
    
    @property
    def launcher_activity(self) -> ActivityInfo | None:
        """Returns the launcher activity if found"""
```

### ActivityInfo

Information about an Android Activity.

```python
class ActivityInfo(BaseModel):
    name: str                           # Full class name
    exported: bool = False
    launch_mode: str = "standard"       # standard, singleTop, etc.
    intent_filters: list[IntentFilterInfo] = []
    is_launcher: bool = False           # Is main launcher
    
    @property
    def simple_name(self) -> str:
        """Returns just the class name (without package)"""
```

### PermissionInfo

Permission with categorization.

```python
class PermissionCategory(str, Enum):
    NORMAL = "normal"
    DANGEROUS = "dangerous"
    SIGNATURE = "signature"

class PermissionInfo(BaseModel):
    name: str
    category: PermissionCategory = PermissionCategory.NORMAL
    is_custom: bool = False
```

---

## Behavior Models (`models/behavior.py`)

### BehaviorModel

The canonical behavioral representation of an application.

```python
class BehaviorModel(BaseModel):
    model_id: str                            # UUID
    app_package: str                         # Package name
    
    # Core behavioral data
    screens: list[ScreenModel] = []
    transitions: list[StateTransition] = []
    navigation_rules: list[NavigationRule] = []
    user_intents: list[UserIntent] = []
    data_flows: list[DataFlow] = []
    
    # Metadata
    entry_screen_id: str | None = None       # Initial screen
    auth_required: bool = False
    offline_capable: bool = False
    coverage_score: float = 0.0              # Dynamic analysis coverage
    
    # Computed statistics
    total_screens: int = 0
    total_transitions: int = 0
    total_user_intents: int = 0
    
    def update_statistics(self) -> None:
        """Update computed fields"""
    
    def get_screen(self, screen_id: str) -> ScreenModel | None:
        """Find screen by ID"""
    
    def get_transitions_from(self, screen_id: str) -> list[StateTransition]:
        """Get all transitions originating from a screen"""
    
    def get_transitions_to(self, screen_id: str) -> list[StateTransition]:
        """Get all transitions ending at a screen"""
```

### ScreenModel

Represents a single screen/UI state.

```python
class ScreenModel(BaseModel):
    screen_id: str
    screen_name: str
    activity_name: str | None = None
    
    # UI structure
    root_elements: list[UIElement] = []
    interactive_elements: list[str] = []      # Element IDs
    
    # Semantics
    description: str | None = None
    purpose: str | None = None
    
    # Navigation
    has_navigation: bool = False
    has_back_button: bool = False
    has_app_bar: bool = False
    has_bottom_nav: bool = False
    
    # Discovery
    discovery_method: str = "dynamic"         # "dynamic" or "static"
    screenshot_key: str | None = None         # Storage key for screenshot
```

### UIElement

Represents a UI component.

```python
class UIElementType(str, Enum):
    BUTTON = "button"
    TEXT_FIELD = "text_field"
    TEXT_VIEW = "text_view"
    IMAGE = "image"
    LIST = "list"
    CHECKBOX = "checkbox"
    SWITCH = "switch"
    CONTAINER = "container"
    UNKNOWN = "unknown"

class UIElement(BaseModel):
    element_id: str
    element_type: UIElementType
    
    # Identification
    resource_id: str | None = None
    content_description: str | None = None
    text: str | None = None
    
    # Bounds (normalized 0.0-1.0)
    bounds_left: float = 0.0
    bounds_top: float = 0.0
    bounds_right: float = 0.0
    bounds_bottom: float = 0.0
    
    # State
    is_clickable: bool = False
    is_focusable: bool = False
    is_editable: bool = False
    is_scrollable: bool = False
    is_enabled: bool = True
    is_visible: bool = True
    
    # Hierarchy
    children: list["UIElement"] = []
```

### StateTransition

A navigation event between screens.

```python
class StateTransition(BaseModel):
    transition_id: str
    from_screen_id: str
    to_screen_id: str
    triggered_by_action: UserAction
    
    # Effects
    side_effects: list[SideEffect] = []
    
    # Analysis
    is_reversible: bool = True
    confidence: float = 1.0                   # How confident in this transition
```

### UserAction

An action performed by the user.

```python
class ActionType(str, Enum):
    TAP = "tap"
    LONG_PRESS = "long_press"
    SWIPE = "swipe"
    SCROLL = "scroll"
    TEXT_INPUT = "text_input"
    BACK = "back"
    MENU = "menu"

class UserAction(BaseModel):
    action_id: str
    action_type: ActionType
    target_element_id: str | None = None
    source_screen_id: str = ""
    description: str = ""
    
    # For tap/press
    coordinates: tuple[float, float] | None = None
    
    # For text input
    text_value: str | None = None
    
    # For swipe/scroll
    direction: str | None = None
```

### UserIntent

A high-level user goal.

```python
class UserIntent(BaseModel):
    intent_id: str
    name: str
    description: str
    
    # Classification
    is_primary: bool = False                  # Core app functionality
    estimated_frequency: str = "medium"       # low, medium, high
    
    # Flow
    entry_screens: list[str] = []             # Where user starts
    exit_screens: list[str] = []              # Where user ends
    
    # Conditions
    preconditions: list[str] = []             # Required state
    success_indicators: list[str] = []        # How to know it succeeded
```

### NavigationRule

A high-level navigation pattern.

```python
class NavigationRule(BaseModel):
    rule_id: str
    name: str
    description: str = ""
    
    from_screens: list[str] = []              # Source screen IDs
    to_screen: str                            # Destination screen ID
    
    trigger_condition: str = ""               # What triggers navigation
    is_back_navigation: bool = False
    requires_auth: bool = False
```

### DataFlow

Data movement through the application.

```python
class DataFlow(BaseModel):
    flow_id: str
    name: str
    
    source_type: str                          # "api", "local", "user_input"
    source_id: str
    destination_type: str                     # "screen", "storage", "api"
    destination_id: str
    
    data_type: str                            # Type of data
    is_sensitive: bool = False
```

---

## Specification Models (`models/spec.py`)

### BehavioralSpec

Complete product specification.

```python
class BehavioralSpec(BaseModel):
    spec_id: str
    app_name: str
    version: str = "1.0"
    created_at: datetime
    
    # Overview
    executive_summary: str = ""
    scope: str = ""
    
    # Requirements
    functional_requirements: list[FunctionalRequirement] = []
    non_functional_requirements: list[NonFunctionalRequirement] = []
    
    # Detailed specs
    screen_specs: list[ScreenSpec] = []
    error_handling: ErrorHandlingSpec
    
    # Traceability
    source_behavior_model_id: str = ""
```

### FunctionalRequirement

A functional requirement (FR).

```python
class RequirementPriority(str, Enum):
    MUST = "MUST"
    SHOULD = "SHOULD"
    COULD = "COULD"
    WONT = "WONT"

class FunctionalRequirement(BaseModel):
    req_id: str                               # e.g., "FR-001"
    title: str
    description: str
    priority: RequirementPriority = RequirementPriority.SHOULD
    
    acceptance_criteria: list[str] = []
    
    # Traceability
    derived_from_screens: list[str] = []
    derived_from_intents: list[str] = []
```

### NonFunctionalRequirement

A non-functional requirement (NFR).

```python
class NFRCategory(str, Enum):
    PERFORMANCE = "performance"
    USABILITY = "usability"
    ACCESSIBILITY = "accessibility"
    SECURITY = "security"
    RELIABILITY = "reliability"
    MAINTAINABILITY = "maintainability"

class NonFunctionalRequirement(BaseModel):
    req_id: str                               # e.g., "NFR-001"
    title: str
    description: str
    category: NFRCategory
    priority: RequirementPriority = RequirementPriority.SHOULD
    
    metric: str = ""                          # What to measure
    target_value: str = ""                    # Target threshold
```

### ScreenSpec

Specification for a single screen.

```python
class ScreenSpec(BaseModel):
    screen_id: str
    screen_name: str
    description: str
    
    # UI components
    components: list[UIComponentSpec] = []
    
    # Navigation
    entry_points: list[str] = []              # Screen IDs that lead here
    exit_points: list[str] = []               # Screen IDs reachable from here
    
    # Data
    data_requirements: list[str] = []
    state_requirements: list[str] = []
```

### ArchitectureSpec

Technical architecture specification.

```python
class ArchitectureSpec(BaseModel):
    spec_id: str
    created_at: datetime
    
    # Pattern
    architecture_pattern: str = "MVVM"
    architecture_rationale: str = ""
    
    # Modules
    modules: list[ModuleDefinition] = []
    
    # Design
    data_flow_diagrams: list[DataFlowDiagram] = []
    technology_decisions: list[TechnologyDecision] = []
    adrs: list[ArchitectureDecisionRecord] = []
    
    # Security
    security_considerations: list[str] = []
    
    # Traceability
    source_behavioral_spec_id: str = ""
```

### ModuleDefinition

Definition of a project module.

```python
class ModuleType(str, Enum):
    APP = "app"
    FEATURE = "feature"
    DOMAIN = "domain"
    DATA = "data"
    UI = "ui"
    COMMON = "common"

class ModuleDefinition(BaseModel):
    module_id: str
    module_name: str                          # e.g., ":feature:home"
    module_type: ModuleType
    description: str = ""
    
    depends_on: list[str] = []                # Module dependencies
    responsibilities: list[str] = []
    suggested_packages: list[str] = []
    key_classes: list[str] = []
```

### ArchitectureDecisionRecord

An ADR documenting a technical decision.

```python
class ArchitectureDecisionRecord(BaseModel):
    adr_id: str                               # e.g., "ADR-001"
    title: str
    status: str = "accepted"                  # proposed, accepted, deprecated
    created_at: datetime
    
    context: str                              # Why decision was needed
    decision: str                             # What was decided
    consequences: list[str] = []              # Implications
    alternatives: list[str] = []              # Options considered
```

---

## Code Generation Models (`models/codegen.py`)

### AndroidProject

Complete generated project.

```python
class AndroidProject(BaseModel):
    project_name: str
    package_name: str
    
    # Versions
    kotlin_version: str = "1.9.22"
    agp_version: str = "8.2.0"
    compose_version: str = "1.5.4"
    
    # Structure
    modules: list[GradleModule] = []
    
    # Generated files
    source_files: dict[str, list[KotlinFile]] = {}    # module → files
    resource_files: dict[str, list[ResourceFile]] = {}
    
    # Build files
    root_build_gradle: str = ""
    settings_gradle: str = ""
    gradle_properties: str = ""
    
    # Traceability
    source_architecture_spec_id: str = ""
    source_behavioral_spec_id: str = ""
    
    def get_module(self, name: str) -> GradleModule | None:
        """Find module by name"""
```

### GradleModule

A Gradle module definition.

```python
class GradleModule(BaseModel):
    module_name: str                          # e.g., ":app"
    module_path: str                          # e.g., "app"
    module_type: str                          # "android-app", "android-library"
    
    android_config: AndroidConfig | None = None
    plugins: list[GradlePlugin] = []
    dependencies: list[GradleDependency] = []
    module_dependencies: list[str] = []       # Other modules
```

### AndroidConfig

Android-specific configuration.

```python
class AndroidConfig(BaseModel):
    namespace: str
    compile_sdk: int = 34
    min_sdk: int = 24
    target_sdk: int = 34
    
    version_code: int = 1
    version_name: str = "1.0.0"
    
    compose_enabled: bool = True
    build_config_enabled: bool = True
    
    jvm_target: str = "17"
    compose_compiler_version: str = "1.5.8"
```

### KotlinFile

A generated Kotlin source file.

```python
class KotlinFile(BaseModel):
    file_name: str                            # Without extension
    package: str
    relative_path: str                        # Within module
    
    imports: list[str] = []
    raw_content: str | None = None            # Full file content
    
    @property
    def full_path(self) -> str:
        """Returns complete file path"""
```

### ResourceFile

A resource file (XML, drawable, etc.).

```python
class ResourceType(str, Enum):
    VALUES = "values"
    LAYOUT = "layout"
    DRAWABLE = "drawable"
    MIPMAP = "mipmap"
    XML = "xml"
    RAW = "raw"

class ResourceFile(BaseModel):
    resource_type: ResourceType
    file_name: str
    content: str
    qualifier: str = ""                       # e.g., "night", "v21"
    
    @property
    def directory_name(self) -> str:
        """Returns res subdirectory name"""
```

### GradleDependency

A Gradle dependency declaration.

```python
class DependencyScope(str, Enum):
    IMPLEMENTATION = "implementation"
    API = "api"
    COMPILE_ONLY = "compileOnly"
    KSP = "ksp"
    KAPT = "kapt"
    TEST_IMPLEMENTATION = "testImplementation"
    ANDROID_TEST_IMPLEMENTATION = "androidTestImplementation"

class GradleDependency(BaseModel):
    group: str
    artifact: str
    version: str
    scope: DependencyScope = DependencyScope.IMPLEMENTATION
    
    @property
    def declaration(self) -> str:
        """Returns Gradle dependency string"""
```

---

## JSON Schemas

JSON schemas are provided in `schemas/` for validation:

| Schema | Purpose |
|--------|---------|
| `behavior-model.schema.json` | BehaviorModel validation |
| `behavioral-spec.schema.json` | BehavioralSpec validation |
| `architecture-spec.schema.json` | ArchitectureSpec validation |

### Generating Schemas

Pydantic models can export JSON schemas:

```python
from behavior2build.models.behavior import BehaviorModel

schema = BehaviorModel.model_json_schema()
```

### Using Schemas

```python
import json
from jsonschema import validate

with open("schemas/behavior-model.schema.json") as f:
    schema = json.load(f)

validate(instance=data, schema=schema)
```
