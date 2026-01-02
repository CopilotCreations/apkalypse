# Pipeline Stages

This document provides detailed information about each stage of the Behavior2Build pipeline.

## Pipeline Overview

The pipeline consists of 9 sequential stages, each with specific inputs, outputs, and responsibilities:

```
┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
│ 1. APK   │──▶│ 2.Static │──▶│3.Dynamic │──▶│4.Behavior│
│ Ingestion│   │ Analysis │   │ Analysis │   │  Model   │
└──────────┘   └──────────┘   └──────────┘   └──────────┘
                                                   │
┌──────────┐   ┌──────────┐   ┌──────────┐        │
│ 7. Code  │◀──│ 6. Arch  │◀──│ 5. Spec  │◀───────┘
│   Gen    │   │ Synthesis│   │Generation│
└──────────┘   └──────────┘   └──────────┘
      │
      ▼
┌──────────┐   ┌──────────┐
│8. Parity │──▶│9.Complian│──▶ ✓ Complete
│  Verify  │   │ce Guard  │
└──────────┘   └──────────┘
```

---

## Stage 1: APK Ingestion

**Service:** `IngestionService`  
**Task:** `ingest_apk`  
**Retries:** 2 (with 5s delay)

### Purpose

Validates, normalizes, and stores the input APK with full provenance tracking.

### Process

1. **Validation**
   - Verify file exists and has `.apk` extension
   - Confirm valid ZIP structure (APKs are ZIP archives)
   - Check for required files: `AndroidManifest.xml`, `classes*.dex`

2. **Hash Computation**
   - SHA-256 (primary identifier)
   - SHA-1 (for compatibility)
   - MD5 (for legacy systems)

3. **Basic Metadata Extraction**
   - File size
   - Resource counts (DEX files, assets, resources, native libs)
   - Embedded library detection (Kotlin, OkHttp, Retrofit, RxJava)

4. **Storage**
   - APK stored at `apks/{sha256}/{filename}.apk`
   - Metadata stored at `apks/{sha256}/metadata.json`
   - Optional screenshots stored at `apks/{sha256}/screenshots/`

### Input

```python
class IngestionInput:
    apk_path: Path           # Path to APK file
    play_store_url: str | None  # Optional Play Store URL
    screenshots: list[Path]  # Optional screenshots
```

### Output

```python
class IngestionOutput:
    apk_metadata: APKMetadata      # Full metadata object
    normalized_apk_path: str       # Storage key for APK
    screenshots_keys: list[str]    # Storage keys for screenshots
```

### Key Model: APKProvenance

```python
class APKProvenance:
    sha256_hash: str
    sha1_hash: str
    md5_hash: str
    file_size_bytes: int
    file_name: str
    acquired_at: datetime
    play_store_url: str | None
```

---

## Stage 2: Static Analysis

**Service:** `StaticAnalysisService`  
**Task:** `run_static_analysis`  
**Retries:** 1

### Purpose

Extracts structural information from the APK without executing it.

### Process

1. **APK Decompilation**
   - Uses `apktool` for resource extraction (resources only, `-s` flag skips source)
   - Fallback to ZIP extraction if apktool unavailable

2. **Manifest Parsing**
   - Package name, version code/name
   - Min/target SDK versions
   - Activities, services, receivers, providers
   - Permissions with categorization (normal, dangerous, signature)
   - Intent filters and launcher detection

3. **Layout Extraction**
   - Parse XML layouts in `res/layout/`
   - Extract element types, IDs, string references
   - Identify UI component hierarchy

4. **String Resources**
   - Extract `strings.xml` content
   - Map string names to values

5. **Framework Detection**
   - Scan smali directories for known libraries
   - Detect: Retrofit, OkHttp, Glide, Picasso, Dagger, Hilt, RxJava, Coroutines, Compose, Room, Navigation, Firebase

6. **Cleanup** (Compliance)
   - Delete decompiled files after analysis
   - Only derived structural data is persisted

### Input

```python
class StaticAnalysisInput:
    apk_path: str          # Storage key from ingestion
    apk_metadata: APKMetadata
```

### Output

```python
class StaticAnalysisOutput:
    manifest: ManifestData
    layouts: list[UILayoutInfo]
    strings: dict[str, str]
    detected_frameworks: list[str]
```

### Key Model: ManifestData

```python
class ManifestData:
    package_name: str
    version_code: int
    version_name: str
    min_sdk_version: int
    target_sdk_version: int
    activities: list[ActivityInfo]
    services: list[ServiceInfo]
    permissions: list[PermissionInfo]
    # ... more fields
```

---

## Stage 3: Dynamic Analysis

**Service:** `DynamicAnalysisService`  
**Task:** `run_dynamic_analysis`  
**Retries:** 1  
**Timeout:** 600 seconds

### Purpose

Captures runtime behavior by executing the APK in an Android emulator.

### Process

1. **Emulator Management**
   - Start Android emulator (configurable AVD)
   - Wait for boot completion (checks `sys.boot_completed` property)
   - Supports headless mode for CI environments

2. **APK Installation**
   - Install APK via `adb install -r`
   - Launch via monkey or explicit intent

3. **UI Exploration** (via `UIExplorer`)
   - Dump UI hierarchy via `uiautomator`
   - Parse XML to identify clickable elements
   - Automatically explore by clicking elements
   - Track visited states to avoid loops
   - Record screenshots (optional)

4. **Data Collection**
   - Screen models with UI element hierarchy
   - State transitions triggered by actions
   - Network calls (requires mitmproxy integration)

5. **Fallback Mode**
   - If emulator unavailable, creates mock analysis from static data
   - Returns warning in service result

### Input

```python
class DynamicAnalysisInput:
    apk_path: str
    apk_metadata: APKMetadata
    exploration_time_seconds: int = 300
    capture_screenshots: bool = True
    capture_network: bool = True
```

### Output

```python
class DynamicAnalysisOutput:
    screens: list[ScreenModel]
    transitions: list[StateTransition]
    network_calls: list[NetworkCall]
    exploration_coverage: float
    total_actions: int
```

### Key Models

```python
class ScreenModel:
    screen_id: str
    screen_name: str
    activity_name: str | None
    root_elements: list[UIElement]
    interactive_elements: list[str]

class StateTransition:
    transition_id: str
    from_screen_id: str
    to_screen_id: str
    triggered_by_action: UserAction
```

---

## Stage 4: Behavior Model Building

**Service:** `BehaviorModelService`  
**Task:** `build_behavior_model`

### Purpose

Synthesizes a canonical, implementation-agnostic behavioral model from analysis results.

### Process

1. **Screen Merging**
   - Combine screens from dynamic analysis (primary)
   - Add undiscovered screens from static analysis
   - Tag discovery method for each screen

2. **Navigation Rule Inference**
   - Build transition graph from observed transitions
   - Infer navigation patterns (forward, back)

3. **User Intent Recognition**
   - Pattern matching on screen names
   - Identify common intents: Login, Registration, Browse, View Detail, Settings, Profile, Search

4. **Data Flow Inference**
   - Map data sources to destinations
   - Track API calls and local data

5. **Entry Point Identification**
   - Find launcher activity
   - Set as model entry point

### Input

```python
class BehaviorModelInput:
    apk_metadata: APKMetadata
    static_analysis: StaticAnalysisOutput
    dynamic_analysis: DynamicAnalysisOutput
    run_id: str
```

### Output

```python
class BehaviorModelOutput:
    behavior_model: BehaviorModel
    storage_key: str
```

### Key Model: BehaviorModel

```python
class BehaviorModel:
    model_id: str
    app_package: str
    screens: list[ScreenModel]
    transitions: list[StateTransition]
    navigation_rules: list[NavigationRule]
    user_intents: list[UserIntent]
    data_flows: list[DataFlow]
    entry_screen_id: str | None
    auth_required: bool
    offline_capable: bool
    coverage_score: float
```

---

## Stage 5: Specification Generation

**Service:** `SpecGenerationService`  
**Task:** `generate_spec`  
**Agent:** `ProductSpecAuthorAgent`

### Purpose

Transforms the behavioral model into formal product requirements.

### Process

1. **AI Agent Invocation**
   - Prepare summarized input for agent
   - Agent generates functional requirements
   - Fallback to template-based generation if agent fails

2. **Screen Specification**
   - Create spec for each screen
   - Define entry/exit points
   - Document UI components

3. **Functional Requirements**
   - Derive from navigation rules
   - Derive from user intents
   - Apply priority (MUST, SHOULD, COULD, WONT)

4. **Non-Functional Requirements**
   - Performance (launch time, frame rate)
   - Usability (touch targets)
   - Accessibility (content descriptions)
   - Security (if auth required)
   - Reliability (offline handling)

### Input

```python
class SpecGenerationInput:
    behavior_model: BehaviorModel
    app_name: str
    run_id: str
```

### Output

```python
class SpecGenerationOutput:
    behavioral_spec: BehavioralSpec
    storage_key: str
```

### Key Model: BehavioralSpec

```python
class BehavioralSpec:
    spec_id: str
    app_name: str
    executive_summary: str
    scope: str
    functional_requirements: list[FunctionalRequirement]
    non_functional_requirements: list[NonFunctionalRequirement]
    screen_specs: list[ScreenSpec]
    error_handling: ErrorHandlingSpec
```

---

## Stage 6: Architecture Synthesis

**Service:** `ArchitectureService`  
**Task:** `synthesize_architecture`  
**Agent:** `SystemArchitectAgent`

### Purpose

Designs a modern, clean architecture for the generated application.

### Process

1. **Module Definition**
   - `:app` - Main application module
   - `:core:ui` - Shared UI components
   - `:core:domain` - Business logic
   - `:core:data` - Data layer
   - `:core:common` - Utilities
   - `:feature:*` - Feature modules based on screens

2. **Feature Grouping**
   - Group screens by naming patterns
   - Create feature modules: home, auth, settings, profile, search, detail

3. **Architecture Decision Records (ADRs)**
   - Document MVVM pattern decision
   - Document Jetpack Compose choice
   - Document Hilt for DI
   - Document multi-module architecture
   - Document Kotlin Coroutines

4. **Technology Decisions**
   - Language: Kotlin 1.9
   - UI: Jetpack Compose + Material 3
   - DI: Hilt
   - Network: Retrofit + OkHttp
   - Storage: Room + DataStore
   - Navigation: Navigation Compose
   - Testing: JUnit 5 + Compose Testing + Mockk

5. **Data Flow Diagram**
   - User → UI → ViewModel → UseCase → Repository → Remote/Local

### Input

```python
class ArchitectureInput:
    behavioral_spec: BehavioralSpec
    run_id: str
```

### Output

```python
class ArchitectureOutput:
    architecture_spec: ArchitectureSpec
    storage_key: str
```

### Key Model: ArchitectureSpec

```python
class ArchitectureSpec:
    spec_id: str
    architecture_pattern: str  # "MVVM"
    modules: list[ModuleDefinition]
    data_flow_diagrams: list[DataFlowDiagram]
    technology_decisions: list[TechnologyDecision]
    adrs: list[ArchitectureDecisionRecord]
    security_considerations: list[str]
```

---

## Stage 7: Code Generation

**Service:** `CodegenService`  
**Task:** `generate_code`  
**Agent:** `AndroidImplementationAgent`

### Purpose

Generates a complete, buildable Android project from specifications.

### Generated Artifacts

1. **Root Project Files**
   - `build.gradle.kts` - Root build configuration
   - `settings.gradle.kts` - Module includes
   - `gradle.properties` - Build properties

2. **App Module**
   - `AndroidManifest.xml`
   - `{AppName}Application.kt` - Hilt application class
   - `MainActivity.kt` - Entry point activity
   - `AppNavigation.kt` - Navigation graph
   - Feature screens and ViewModels

3. **Core Modules**
   - Theme files (Color, Typography, Theme)
   - Shared composables
   - Domain models and use cases
   - Repository interfaces and implementations

4. **Resources**
   - `strings.xml`
   - `themes.xml`

### Code Patterns

**Screen Pattern:**
```kotlin
@Composable
fun FeatureScreen(
    onNavigate: (String) -> Unit,
    viewModel: FeatureViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    // Compose UI
}
```

**ViewModel Pattern:**
```kotlin
@HiltViewModel
class FeatureViewModel @Inject constructor() : ViewModel() {
    private val _uiState = MutableStateFlow<UiState>(UiState.Loading)
    val uiState: StateFlow<UiState> = _uiState.asStateFlow()
}
```

### Input

```python
class CodegenInput:
    behavioral_spec: BehavioralSpec
    architecture_spec: ArchitectureSpec
    package_name: str
    run_id: str
```

### Output

```python
class CodegenOutput:
    project: AndroidProject
    output_directory: str
```

---

## Stage 8: Parity Verification

**Service:** `VerificationService`  
**Task:** `verify_parity`  
**Agent:** `QAParityAgent`

### Purpose

Verifies that the generated application matches the behavioral model.

### Verification Checks

1. **Screen Coverage**
   - Compare behavior model screens to generated Screen files
   - Calculate coverage percentage
   - Flag missing screens as major issues

2. **Navigation Coverage**
   - Verify navigation file exists
   - Check for route definitions
   - Validate navigation graph completeness

3. **Architectural Compliance**
   - Verify ViewModel pattern usage
   - Verify Hilt annotations present
   - Verify Compose usage

4. **Test Scenario Generation**
   - Navigation scenarios from transitions
   - User intent scenarios
   - Screen presence scenarios

### Scoring

- Overall parity score: Average of all coverage scores
- Pass threshold: ≥ 70% with no critical issues
- Critical issues: Missing navigation, missing core patterns

### Input

```python
class VerificationInput:
    behavior_model: BehaviorModel
    generated_project: AndroidProject
    run_id: str
```

### Output

```python
class VerificationOutput:
    parity_report: ParityReport
    storage_key: str
```

### Key Model: ParityReport

```python
class ParityReport:
    overall_parity_score: float  # 0.0 - 1.0
    passed: bool
    issues: list[ParityIssue]
    matching_behaviors: list[str]
    test_scenarios: list[TestScenario]
    recommendations: list[str]
```

---

## Stage 9: Compliance Guard

**Service:** `ComplianceGuard`  
**Task:** `check_compliance`

### Purpose

Ensures legal safety by preventing source code reuse.

### Compliance Checks

1. **Suspicious Pattern Detection**
   - Scan for decompiler watermarks (jadx, CFR, Procyon)
   - Flag auto-generated comments

2. **Source Similarity Analysis**
   - Normalize code (remove comments, whitespace, string literals)
   - Calculate similarity ratio using SequenceMatcher
   - Flag if similarity exceeds threshold (default: 30%)

3. **Persisted Source Detection**
   - Check storage for suspicious files (.smali, .jadx, .class)
   - Check for suspicious directories (smali, jadx-out, decompiled)

4. **Provenance Tracking**
   - Hash all input artifacts
   - Hash all output artifacts
   - Create audit trail

### Blocking Behavior

If `B2B_COMPLIANCE_STRICT=true` and critical violations found:
- Raises `ComplianceViolationError`
- Blocks pipeline completion
- Preserves compliance report for audit

### Input

```python
class ComplianceInput:
    run_id: str
    apk_hash: str
    generated_files: dict[str, str]  # path → content
    decompiled_artifacts: list[str]  # paths to check against
```

### Output

```python
class ComplianceOutput:
    compliance_report: ComplianceReport
    storage_key: str
```

### Key Model: ComplianceReport

```python
class ComplianceReport:
    passed: bool
    violations: list[ComplianceViolation]
    artifacts_checked: int
    max_similarity_found: float
    input_hashes: dict[str, str]
    output_hashes: dict[str, str]
```

---

## Pipeline Execution

### Running the Full Pipeline

```bash
behavior2build run app.apk \
    --name "My App" \
    --package com.example.myapp \
    --output ./generated
```

### Analysis Only

```bash
behavior2build analyze app.apk --output ./analysis
```

### Programmatic Usage

```python
from behavior2build.orchestration import run_pipeline

result = await run_pipeline(
    apk_path=Path("app.apk"),
    app_name="My App",
    package_name="com.example.myapp",
    exploration_time=300,
    skip_dynamic_analysis=False,
)

if result.success:
    print(f"Parity: {result.parity_score:.1%}")
    print(f"Output: {result.output_directory}")
```

### Pipeline Configuration

| Option | Description | Default |
|--------|-------------|---------|
| `exploration_time` | Dynamic analysis duration | 300s |
| `skip_dynamic_analysis` | Use static-only mode | False |
| `play_store_url` | Additional metadata source | None |
| `screenshots` | Reference screenshots | [] |
