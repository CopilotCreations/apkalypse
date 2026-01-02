# Prerequisites

This document outlines the prerequisites required to run the APKalypse pipeline.

## System Requirements

### Python
- **Python 3.9+** (Python 3.11+ recommended for best performance)

### Java
- **Java 11+** required for jadx and apktool

**Windows (winget):**
```powershell
winget install Microsoft.OpenJDK.17
```

### Android SDK
- **Android SDK** with the following components:
  - `platform-tools` (adb)
  - `build-tools` (aapt2)
  - `emulator` (for dynamic analysis)
  - System image: `system-images;android-33;google_apis;x86_64`

**Windows (winget) - Platform Tools only:**
```powershell
winget install Google.PlatformTools
```

> **Note:** Winget installs only Platform-Tools (adb, fastboot). For the full SDK (sdkmanager, avdmanager, emulator), download the [Command Line Tools](https://developer.android.com/studio#cmdline-tools) manually:
> 1. Download and extract to `C:\Android\cmdline-tools`
> 2. Run `sdkmanager --sdk_root=C:\Android "build-tools;34.0.0" "emulator" "platform-tools"`

Set the `ANDROID_SDK_ROOT` environment variable to your SDK path:
```bash
# Linux/macOS
export ANDROID_SDK_ROOT=~/Android/Sdk

# Windows
set ANDROID_SDK_ROOT=C:\Android
```

### External Tools

| Tool | Purpose | Required | Winget Available |
|------|---------|----------|------------------|
| [apktool](https://apktool.org/) | APK decompilation | Yes | No |
| [jadx](https://github.com/skylot/jadx) | Dex to Java decompilation | Recommended | Yes |
| [Frida](https://frida.re/) | Dynamic instrumentation | Optional | No (use pip) |
| [mitmproxy](https://mitmproxy.org/) | Network traffic capture | Optional | Yes |

**Windows Quick Install (winget + pip):**
```powershell
# Install tools available via winget
winget install Skylot.jadx
winget install mitmproxy

# Install Frida via pip
pip install frida-tools

# Apktool (manual install required)
# Download apktool.jar and apktool.bat from https://apktool.org/docs/install/
# Place in C:\apktool and add to PATH
```

### Android Emulator (Optional)
For dynamic analysis, you need an Android emulator configured:
```bash
# Create AVD
sdkmanager "system-images;android-33;google_apis;x86_64"
avdmanager create avd -n APKalypse_avd -k "system-images;android-33;google_apis;x86_64"
```

## API Keys

At least one LLM provider API key is required:

| Environment Variable | Provider | Required |
|---------------------|----------|----------|
| `OPENAI_API_KEY` | OpenAI (GPT-4o) | Yes* |
| `ANTHROPIC_API_KEY` | Anthropic (Claude) | Alternative* |

*One of these is required.

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key for agents | Required |
| `ANTHROPIC_API_KEY` | Anthropic API key (alternative) | - |
| `ANDROID_SDK_ROOT` | Path to Android SDK | `~/Android/Sdk` |
| `B2B_LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) | INFO |
| `B2B_AGENT_PROVIDER` | LLM provider (openai/anthropic) | openai |
| `B2B_AGENT_MODEL` | Model to use | gpt-4o |
| `B2B_OUTPUT_PATH` | Output directory | ./output |
| `B2B_EMULATOR_HEADLESS` | Run emulator without display | true |
| `B2B_COMPLIANCE_STRICT` | Block on compliance violations | true |

## Installation

### Quick Install
```bash
pip install -r requirements.txt
pip install -e .
```

### Development Install
```bash
pip install -r requirements.txt
pip install -e ".[dev]"
```

## Verification

Verify your setup by running:
```bash
# Check Python version
python --version

# Check Android SDK
adb version
aapt2 version

# Check apktool
apktool --version

# Run tests
pytest
```
