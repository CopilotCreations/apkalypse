# Behavior2Build Documentation

Welcome to the Behavior2Build documentation. This folder contains detailed technical documentation about the system architecture, pipeline stages, and implementation details.

## Documentation Index

| Document | Description |
|----------|-------------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | System architecture overview, layers, and design principles |
| [PIPELINE.md](PIPELINE.md) | Detailed explanation of each pipeline stage |
| [AGENTS.md](AGENTS.md) | AI agent system documentation |
| [DATA_MODELS.md](DATA_MODELS.md) | Pydantic data models and JSON schemas |
| [LEGAL_COMPLIANCE.md](LEGAL_COMPLIANCE.md) | Legal safety mechanisms and compliance |

## Quick Links

### Getting Started

- [Main README](../README.md) - Installation and quick start guide
- [Pipeline Overview](PIPELINE.md#pipeline-overview) - High-level pipeline flow

### Architecture

- [System Overview](ARCHITECTURE.md#system-overview) - Component diagram
- [Layer Architecture](ARCHITECTURE.md#layer-architecture) - Detailed layer breakdown
- [Data Flow](ARCHITECTURE.md#data-flow) - How data moves through the system

### Pipeline Stages

1. [APK Ingestion](PIPELINE.md#stage-1-apk-ingestion) - Validation and provenance
2. [Static Analysis](PIPELINE.md#stage-2-static-analysis) - Structural extraction
3. [Dynamic Analysis](PIPELINE.md#stage-3-dynamic-analysis) - Runtime behavior capture
4. [Behavior Model](PIPELINE.md#stage-4-behavior-model-building) - Canonical model
5. [Spec Generation](PIPELINE.md#stage-5-specification-generation) - Requirements
6. [Architecture](PIPELINE.md#stage-6-architecture-synthesis) - Design decisions
7. [Code Generation](PIPELINE.md#stage-7-code-generation) - Kotlin/Compose output
8. [Verification](PIPELINE.md#stage-8-parity-verification) - Quality assurance
9. [Compliance](PIPELINE.md#stage-9-compliance-guard) - Legal safety checks

### AI Agents

- [Agent Architecture](AGENTS.md#agent-architecture) - Base class and patterns
- [Behavioral Observer](AGENTS.md#agent-1-behavioral-observer) - UI interpretation
- [Product Spec Author](AGENTS.md#agent-2-product-spec-author) - Specification writing
- [System Architect](AGENTS.md#agent-3-system-architect) - Architecture design
- [Android Implementation](AGENTS.md#agent-4-android-implementation) - Code generation
- [QA Parity](AGENTS.md#agent-5-qa-parity) - Verification

### Data Models

- [APK Models](DATA_MODELS.md#apk-models-modelsapkpy) - Metadata and manifest
- [Behavior Models](DATA_MODELS.md#behavior-models-modelsbehaviorpy) - Behavioral representation
- [Specification Models](DATA_MODELS.md#specification-models-modelsspecpy) - Requirements
- [Code Generation Models](DATA_MODELS.md#code-generation-models-modelscodegenpy) - Project structure

### Legal & Compliance

- [Compliance Guarantees](LEGAL_COMPLIANCE.md#compliance-guarantees) - Safety mechanisms
- [Audit Trail](LEGAL_COMPLIANCE.md#audit-and-reporting) - Provenance tracking
- [Best Practices](LEGAL_COMPLIANCE.md#best-practices) - Recommended usage

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Behavior2Build Pipeline                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐      │
│  │ Ingestion│───▶│  Static  │───▶│ Dynamic  │───▶│ Behavior │      │
│  │ Service  │    │ Analysis │    │ Analysis │    │  Model   │      │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘      │
│                                                         │            │
│                                                         ▼            │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐      │
│  │   Code   │◀───│  Arch    │◀───│   Spec   │◀───│ Behavior │      │
│  │   Gen    │    │ Synthesis│    │Generation│    │  Model   │      │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘      │
│        │                                                             │
│        ▼                                                             │
│  ┌──────────┐    ┌──────────┐                                       │
│  │ Verify   │───▶│Compliance│───▶ ✓ Greenfield Android App         │
│  │ Parity   │    │  Guard   │                                       │
│  └──────────┘    └──────────┘                                       │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## Technology Stack

| Category | Technology |
|----------|------------|
| **Orchestration** | Prefect 2.14+ |
| **Data Validation** | Pydantic 2.5+ |
| **Static Analysis** | apktool, aapt2 |
| **Dynamic Analysis** | UIAutomator, Frida |
| **AI Agents** | OpenAI GPT-4o / Anthropic |
| **Generated Code** | Kotlin 1.9+ / Jetpack Compose |
| **Architecture** | MVVM + Hilt |

## Contributing to Documentation

When updating documentation:

1. Keep diagrams in sync with code changes
2. Update the index when adding new documents
3. Cross-reference related sections
4. Include code examples where helpful
5. Keep the legal compliance documentation up-to-date

## Questions?

- Check the [main README](../README.md) for usage examples
- Review [ARCHITECTURE.md](ARCHITECTURE.md) for system design
- See [PIPELINE.md](PIPELINE.md) for stage-specific details
