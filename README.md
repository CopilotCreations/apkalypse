# APKalypse

Automated APK Behavioral Analysis and Greenfield Android App Generation

APKalypse is a production-ready, end-to-end system that:

- Takes a third-party Android app (APK + public metadata)
- Extracts observable behavior (NOT source code reuse)
- Produces formal, implementation-agnostic behavioral specifications
- Synthesizes modern software architecture
- Generates a clean, greenfield Android application
- Verifies behavioral parity using automated testing

## 🔒 Legal Safety

**Critical Design Principle:** This system is designed to be legally safe for creating applications that replicate *behavior* without copying *code*.

### Compliance Guarantees

1. **No Source Code Reuse**: Decompiled source code is NEVER persisted or passed to code generation
2. **Transient Analysis Only**: Decompiled artifacts are used as read-only signals and deleted after analysis
3. **Similarity Detection**: Generated code is checked against decompiled source to ensure no copying
4. **Audit Trail**: Complete provenance tracking for all artifacts
5. **Behavioral Focus**: Only user-facing behaviors are extracted, not implementation details

## 🏗️ Architecture

```text
┌─────────────────────────────────────────────────────────────────────┐
│                        APKalypse Pipeline                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐       │
│  │ Ingestion│───>│  Static  │───>│ Dynamic  │───>│ Behavior │       │
│  │ Service  │    │ Analysis │    │ Analysis │    │  Model   │       │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘       │
│                                                         │           │
│                                                         ▼           │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐       │
│  │   Code   │<───│  Arch    │<───│   Spec   │<───│ Behavior │       │
│  │   Gen    │    │ Synthesis│    │Generation│    │  Model   │       │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘       │
│        │                                                            │
│        ▼                                                            │
│  ┌──────────┐    ┌──────────┐                                       │
│  │ Verify   │───>│Compliance│───>  Greenfield Android App           │
│  │ Parity   │    │  Guard   │                                       │
│  └──────────┘    └──────────┘                                       │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## 📦 Installation

### Prerequisites

- Python 3.11+
- Java 17+ (required for jadx and apktool)
- Android SDK with platform-tools (for static/dynamic analysis)
- Optional: Android Emulator (for dynamic analysis)

See [PREREQUISITES.md](PREREQUISITES.md) for detailed requirements.

### Quick Install (Windows)

Run the automated prerequisites installer (requires Administrator for winget):

```powershell
# Install all prerequisites (Java, Python, Android tools, jadx, apktool, etc.)
.\install-prerequisites.ps1

# Optional flags:
#   -SkipWinget    Skip winget installations
#   -SkipPip       Skip pip installations (frida-tools, objection)
#   -SkipApktool   Skip apktool download
#   -ApktoolPath   Custom apktool install path (default: C:\apktool)
```

The script installs:
- **Java 17** (OpenJDK via winget)
- **Python 3.11** (via winget)
- **Android Platform Tools** (adb, fastboot via winget)
- **jadx** (DEX to Java decompiler via winget)
- **mitmproxy** (network traffic capture via winget)
- **apktool** (APK decompilation via direct download)
- **frida-tools** (dynamic instrumentation via pip)
- **objection** (runtime mobile exploration via pip)

### Manual Install

```bash
# Install Python dependencies
pip install -r requirements.txt

# Install package in development mode
pip install -e .
```

### Development Install

```bash
pip install -e ".[dev]"
```

### Environment Variables

After installation, set the required environment variables:

```powershell
# Required: Set at least one LLM API key
$env:OPENAI_API_KEY = "your-openai-key"
# OR
$env:ANTHROPIC_API_KEY = "your-anthropic-key"

# Optional: Android SDK path (if not using default)
$env:ANDROID_SDK_ROOT = "C:\Android"
```

## 🚀 Quick Start

### CLI Usage

```bash
# Full pipeline
APKalypse run app.apk \
    --name "My App" \
    --package com.example.myapp \
    --output ./generated

# Analysis only (no code generation)
APKalypse analyze app.apk --output ./analysis

# Show configuration
APKalypse config
```

### Python API

```python
import asyncio
from pathlib import Path
from APKalypse.orchestration import run_pipeline

async def main():
    result = await run_pipeline(
        apk_path=Path("app.apk"),
        app_name="My App",
        package_name="com.example.myapp",
        exploration_time=300,  # seconds
    )
    
    if result.success:
        print(f"Generated: {result.output_directory}")
        print(f"Parity Score: {result.parity_score:.1%}")
    else:
        print(f"Failed: {result.error}")

asyncio.run(main())
```

## 🔧 Configuration

Configuration is managed through environment variables:

| Variable | Description | Default |
| -------- | ----------- | ------- |
| `OPENAI_API_KEY` | OpenAI API key for agents | Required |
| `ANTHROPIC_API_KEY` | Anthropic API key (alternative) | - |
| `B2B_LOG_LEVEL` | Logging level | INFO |
| `B2B_AGENT_PROVIDER` | LLM provider (openai/anthropic) | openai |
| `B2B_AGENT_MODEL` | Model to use | gpt-4o |
| `B2B_OUTPUT_PATH` | Output directory | ./output |
| `B2B_EMULATOR_HEADLESS` | Run emulator headless | true |
| `B2B_COMPLIANCE_STRICT` | Block on compliance violations | true |

## 📋 Pipeline Stages

### 1. Ingestion Service

- Validates APK integrity
- Computes cryptographic hashes (SHA-256, SHA-1, MD5)
- Tracks provenance
- Stores normalized inputs

### 2. Static Analysis Service

- Extracts AndroidManifest.xml
- Parses permissions, activities, services
- Extracts layout hierarchies
- Identifies embedded libraries
- **Does NOT persist decompiled source**

### 3. Dynamic Analysis Service

- Boots Android emulator
- Installs and launches APK
- Automatically explores UI
- Records screen transitions
- Captures network call metadata (schemas only)
- Outputs state transition graphs

### 4. Behavior Model Builder

- Merges static and dynamic analysis
- Creates canonical screen representations
- Infers navigation rules
- Identifies user intents
- Maps data flows

### 5. Spec Generation Agent

- Consumes behavior model
- Produces functional requirements
- Produces non-functional requirements
- Generates screen specifications
- Documents error handling

### 6. Architecture Agent

- Designs module structure
- Creates data flow diagrams
- Makes technology decisions
- Produces ADRs (Architecture Decision Records)

### 7. Code Generation Service

- Generates greenfield Kotlin code
- Uses Jetpack Compose for UI
- Follows MVVM pattern
- Produces buildable Gradle project

### 8. Verification Service

- Validates screen coverage
- Checks navigation implementation
- Verifies architectural compliance
- Produces parity report

### 9. Compliance Guard

- Ensures no source code copying
- Detects suspicious patterns
- Enforces similarity thresholds
- Creates audit trail

## 🤖 AI Agents

The system uses five specialized AI agents:

| Agent | Purpose | Read-Only |
| ----- | ------- | --------- |
| Behavioral Observer | Interprets UI states | ✅ |
| Product Spec Author | Writes specifications | ✅ |
| System Architect | Designs architecture | ✅ |
| Android Implementation | Generates code | ✅ |
| QA Parity | Verifies behavior | ✅ |

All agents:

- Only see sanitized inputs (never decompiled source)
- Have versioned, deterministic prompts
- Include output validation
- Support automatic retries

## 📁 Generated Project Structure

```text
generated/
└── my-app/
    ├── build.gradle.kts
    ├── settings.gradle.kts
    ├── gradle.properties
    ├── app/
    │   ├── build.gradle.kts
    │   └── src/main/
    │       ├── AndroidManifest.xml
    │       ├── kotlin/com/example/myapp/
    │       │   ├── MyAppApplication.kt
    │       │   ├── MainActivity.kt
    │       │   ├── navigation/AppNavigation.kt
    │       │   └── feature/home/
    │       │       ├── HomeScreen.kt
    │       │       └── HomeViewModel.kt
    │       └── res/values/
    │           ├── strings.xml
    │           └── themes.xml
    ├── core/
    │   ├── ui/
    │   ├── domain/
    │   └── data/
    └── project.json
```

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific tests
pytest tests/unit/test_models.py
```

## 📊 Output Artifacts

| Artifact | Format | Description |
| -------- | ------ | ----------- |
| `behavior_model.json` | JSON | Canonical behavioral model |
| `behavioral_spec.json` | JSON | Product specification |
| `architecture_spec.json` | JSON | Architecture design |
| `parity_report.json` | JSON | Verification results |
| `compliance_report.json` | JSON | Legal compliance audit |
| `project/` | Directory | Generated Android project |

## 🔌 Extension Points

### Custom Storage Backend

```python
from APKalypse.storage import StorageBackend

class S3StorageBackend(StorageBackend):
    async def store_bytes(self, key: str, data: bytes, metadata=None) -> str:
        # Implement S3 storage
        ...
```

### Custom Agent Provider

```python
from APKalypse.agents import Agent

class CustomAgent(Agent[MyInput, MyOutput]):
    def get_prompt_template(self) -> PromptTemplate:
        return PromptTemplate(...)
```

### Pipeline Customization

```python
from prefect import flow
from APKalypse.orchestration.tasks import *

@flow
async def custom_pipeline(apk_path: Path):
    # Use individual tasks
    ingestion = await ingest_apk(apk_path)
    static = await run_static_analysis(...)
    # Skip dynamic analysis
    behavior = await build_behavior_model(...)
    ...
```

## ⚠️ Known Limitations

1. **Dynamic Analysis**: Requires Android emulator; falls back to static-only mode if unavailable
2. **Network Capture**: mitmproxy integration is best-effort
3. **Complex Apps**: Apps with heavy native code may have limited analysis
4. **Authentication**: Apps requiring login may have limited exploration
5. **Generated Code**: May require manual refinement for complex business logic

## 🛠️ Technology Stack

| Category | Technology | Version |
| -------- | ---------- | ------- |
| **Orchestration** | Prefect | 2.14+ |
| **Data Validation** | Pydantic | 2.5+ |
| **Static Analysis** | apktool, aapt2 | - |
| **Dynamic Analysis** | UIAutomator, Frida | - |
| **AI Agents** | OpenAI / Anthropic | GPT-4o |
| **Generated Code** | Kotlin + Compose | 1.9+ |
| **Architecture** | MVVM | - |
| **DI** | Hilt | 2.48 |

## 📝 Architecture Decision: Prefect vs Temporal

We chose **Prefect** for orchestration because:

- Simpler deployment (no separate server required for local use)
- Native Python async support
- Built-in retry and caching
- Excellent observability dashboard
- Better suited for pipeline-style workflows

Temporal would be preferred for:

- Long-running workflows (hours/days)
- Complex compensation/rollback logic
- Multi-service coordination

## 📜 License

MIT License - See LICENSE file for details.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Run `pytest` and `ruff check`
5. Submit a pull request

## 📧 Support

For questions or issues, please open a GitHub issue.
