# APKalypse Architecture

This document provides a comprehensive overview of the APKalypse system architecture.

## System Overview

APKalypse is a multi-stage pipeline that transforms Android APK files into greenfield Android applications by:

1. **Extracting behavioral specifications** from an existing APK through static and dynamic analysis
2. **Synthesizing a modern architecture** based on the behavioral model
3. **Generating clean Kotlin/Compose code** that replicates functionality without copying source

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           APKalypse System                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌───────────────────────────────────────────────────────────────────┐     │
│   │                        Orchestration Layer                        │     │
│   │                          (Prefect Flows)                          │     │
│   └───────────────────────────────────────────────────────────────────┘     │
│                                    │                                         │
│   ┌────────────┬────────────┬─────┴────────┬─────────────┬────────────┐    │
│   │   Analysis │  Modeling  │ Specification │ Generation  │ Validation │    │
│   │   Services │  Services  │   Services    │  Services   │  Services  │    │
│   └────────────┴────────────┴──────────────┴─────────────┴────────────┘    │
│                                    │                                         │
│   ┌───────────────────────────────────────────────────────────────────┐     │
│   │                          Agent Layer                              │     │
│   │         (AI-powered interpretation and generation)                │     │
│   └───────────────────────────────────────────────────────────────────┘     │
│                                    │                                         │
│   ┌───────────────────────────────────────────────────────────────────┐     │
│   │                         Storage Layer                             │     │
│   │              (Artifact persistence and retrieval)                 │     │
│   └───────────────────────────────────────────────────────────────────┘     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Layer Architecture

### 1. Orchestration Layer

The orchestration layer manages the pipeline execution using **Prefect** for workflow management.

**Key Components:**
- `pipeline.py` - Main flow definition (`APKalypse_flow`)
- `tasks.py` - Individual task wrappers for each service

**Responsibilities:**
- Sequencing pipeline stages
- Handling retries and error recovery
- Logging and observability
- Result persistence between stages

**Design Decisions:**
- Prefect was chosen over Temporal for simpler deployment and native Python async support
- Each task is idempotent and can be retried independently

### 2. Service Layer

Services encapsulate the core business logic for each pipeline stage.

| Service | Purpose | Key Operations |
|---------|---------|----------------|
| `IngestionService` | APK intake and validation | `ingest()` |
| `StaticAnalysisService` | Structural APK analysis | `analyze()` |
| `DynamicAnalysisService` | Runtime behavior capture | `analyze()` |
| `BehaviorModelService` | Behavioral model synthesis | `build()` |
| `SpecGenerationService` | Requirement specification | `generate()` |
| `ArchitectureService` | Architecture design | `synthesize()` |
| `CodegenService` | Code generation | `generate()` |
| `VerificationService` | Parity verification | `verify()` |
| `ComplianceGuard` | Legal compliance checking | `check()` |

**Service Contract:**
```python
async def operation(input: ServiceInput) -> ServiceResult[ServiceOutput]:
    # All services follow this pattern
    # Returns either success with data or failure with error
```

### 3. Agent Layer

AI agents handle complex interpretation and generation tasks that require reasoning.

**Base Architecture:**
```
Agent[InputT, OutputT]
    ├── BehavioralObserverAgent   - Interprets UI states
    ├── ProductSpecAuthorAgent    - Writes specifications
    ├── SystemArchitectAgent      - Designs architecture
    ├── AndroidImplementationAgent - Generates code
    └── QAParityAgent             - Verifies behavior
```

**Agent Features:**
- Type-safe inputs/outputs via Pydantic models
- Automatic retry with exponential backoff
- Versioned, deterministic prompts
- Output validation
- Token usage tracking

### 4. Storage Layer

Abstracted storage backend for artifact persistence.

**Interface:**
```python
class StorageBackend(ABC):
    async def store_bytes(key, data, metadata) -> str
    async def load_bytes(key) -> bytes
    async def store_model(key, model) -> str
    async def load_model(key, model_type) -> T
    async def store_text(key, text) -> str
    async def load_text(key) -> str
```

**Implementations:**
- `LocalStorageBackend` - File system storage (default)
- Extensible for S3, GCS, etc.

## Data Flow

```
APK File ──┐
           ▼
    ┌──────────────┐
    │  Ingestion   │ → APKMetadata + Provenance
    └──────────────┘
           │
           ▼
    ┌──────────────┐
    │   Static     │ → ManifestData + Layouts + Frameworks
    │  Analysis    │
    └──────────────┘
           │
           ▼
    ┌──────────────┐
    │   Dynamic    │ → Screens + Transitions + Network Calls
    │  Analysis    │
    └──────────────┘
           │
           ▼
    ┌──────────────┐
    │  Behavior    │ → BehaviorModel
    │   Model      │   (Canonical representation)
    └──────────────┘
           │
           ▼
    ┌──────────────┐
    │    Spec      │ → BehavioralSpec
    │ Generation   │   (Requirements + Screen Specs)
    └──────────────┘
           │
           ▼
    ┌──────────────┐
    │ Architecture │ → ArchitectureSpec
    │  Synthesis   │   (Modules + ADRs + Tech Decisions)
    └──────────────┘
           │
           ▼
    ┌──────────────┐
    │    Code      │ → AndroidProject
    │ Generation   │   (Kotlin/Compose Code)
    └──────────────┘
           │
           ▼
    ┌──────────────┐
    │ Verification │ → ParityReport
    └──────────────┘
           │
           ▼
    ┌──────────────┐
    │ Compliance   │ → ComplianceReport
    └──────────────┘
           │
           ▼
    ✓ Greenfield Android App
```

## Key Design Principles

### 1. Legal Safety First

The system is architecturally designed to prevent source code copying:
- Decompiled source is **never persisted** to storage
- Analysis outputs are **derived observations**, not code copies
- Similarity detection prevents generated code from matching original
- Complete audit trail for provenance

### 2. Separation of Concerns

Each layer has distinct responsibilities:
- **Orchestration** - Flow control only
- **Services** - Business logic
- **Agents** - AI-powered reasoning
- **Storage** - Persistence abstraction

### 3. Type Safety

All data flowing through the system is validated via Pydantic models:
- Compile-time type checking
- Runtime validation
- Self-documenting schemas

### 4. Observability

Built-in logging and tracing:
- Structured logging via structlog
- Pipeline stage timing
- Token usage tracking for AI agents
- Prefect dashboard integration

## Module Structure

```
APKalypse/
├── src/
│   ├── agents/           # AI agent implementations
│   │   ├── base.py       # Base Agent class
│   │   ├── registry.py   # Agent registration
│   │   └── *.py          # Specific agents
│   ├── core/             # Core utilities
│   │   ├── config.py     # Configuration
│   │   ├── exceptions.py # Custom exceptions
│   │   ├── logging.py    # Logging setup
│   │   └── types.py      # Common types
│   ├── models/           # Data models
│   │   ├── apk.py        # APK metadata models
│   │   ├── behavior.py   # Behavior model
│   │   ├── spec.py       # Specification models
│   │   └── codegen.py    # Code generation models
│   ├── orchestration/    # Pipeline orchestration
│   │   ├── pipeline.py   # Main flow
│   │   └── tasks.py      # Prefect tasks
│   ├── services/         # Business logic services
│   │   ├── ingestion/
│   │   ├── static_analysis/
│   │   ├── dynamic_analysis/
│   │   ├── behavior_model/
│   │   ├── spec_generation/
│   │   ├── architecture/
│   │   ├── codegen/
│   │   ├── verification/
│   │   └── compliance/
│   └── storage/          # Storage backends
│       ├── interface.py  # StorageBackend ABC
│       └── local.py      # Local file storage
├── prompts/              # AI agent prompts
├── schemas/              # JSON schemas
├── templates/            # Code templates
└── tests/                # Test suites
```

## Configuration

Configuration is managed through environment variables and the `Config` class:

| Category | Variables | Purpose |
|----------|-----------|---------|
| Logging | `B2B_LOG_LEVEL` | Log verbosity |
| AI Agents | `B2B_AGENT_PROVIDER`, `B2B_AGENT_MODEL` | LLM configuration |
| Storage | `B2B_OUTPUT_PATH` | Artifact storage location |
| Emulator | `B2B_EMULATOR_*` | Android emulator settings |
| Compliance | `B2B_COMPLIANCE_STRICT` | Blocking mode for violations |

## Extension Points

### Custom Storage Backend

```python
from APKalypse.storage import StorageBackend

class S3StorageBackend(StorageBackend):
    async def store_bytes(self, key, data, metadata=None):
        # Implement S3 storage
        ...
```

### Custom Agent

```python
from APKalypse.agents import Agent

class CustomAgent(Agent[MyInput, MyOutput]):
    @property
    def name(self) -> str:
        return "custom_agent"
    
    def get_prompt_template(self) -> PromptTemplate:
        return PromptTemplate(...)
```

### Pipeline Customization

```python
from prefect import flow
from APKalypse.orchestration.tasks import *

@flow
async def custom_pipeline(apk_path: Path):
    ingestion = await ingest_apk(apk_path)
    static = await run_static_analysis(...)
    # Add custom stages
    ...
```

## Technology Stack Summary

| Layer | Technology | Version |
|-------|------------|---------|
| Orchestration | Prefect | 2.14+ |
| Validation | Pydantic | 2.5+ |
| AI Agents | OpenAI/Anthropic | GPT-4o |
| Static Analysis | apktool, aapt2 | - |
| Dynamic Analysis | UIAutomator, Frida | - |
| Generated Code | Kotlin + Compose | 1.9+ |
| Architecture | MVVM + Hilt | - |
