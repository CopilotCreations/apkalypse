# AI Agents

This document describes the AI agent system used in Behavior2Build for complex reasoning and generation tasks.

## Agent Architecture

### Overview

Behavior2Build uses five specialized AI agents to handle tasks that require semantic understanding and creative generation. Each agent is:

- **Type-safe**: Inputs and outputs are Pydantic models
- **Deterministic**: Versioned prompts with hash tracking
- **Resilient**: Automatic retry with exponential backoff
- **Observable**: Token usage and latency tracking

```
┌─────────────────────────────────────────────────────────────────┐
│                          Agent[InputT, OutputT]                  │
├─────────────────────────────────────────────────────────────────┤
│  - invoke(input, context) → AgentResponse[OutputT]              │
│  - get_prompt_template() → PromptTemplate                       │
│  - prepare_input(input) → dict                                  │
│  - validate_output(output) → list[str]                          │
└─────────────────────────────────────────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
        ▼                           ▼                           ▼
┌───────────────┐          ┌───────────────┐          ┌───────────────┐
│   Behavioral  │          │  ProductSpec  │          │    System     │
│   Observer    │          │    Author     │          │   Architect   │
└───────────────┘          └───────────────┘          └───────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                                                       │
        ▼                                                       ▼
┌───────────────┐                                      ┌───────────────┐
│   Android     │                                      │   QA Parity   │
│Implementation │                                      │    Agent      │
└───────────────┘                                      └───────────────┘
```

## Base Agent Class

All agents inherit from the `Agent[InputT, OutputT]` generic base class.

### Core Properties

```python
class Agent(ABC, Generic[InputT, OutputT]):
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique agent identifier"""
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Agent description"""
    
    @property
    @abstractmethod
    def input_type(self) -> type[InputT]:
        """Pydantic model for input"""
    
    @property
    @abstractmethod
    def output_type(self) -> type[OutputT]:
        """Pydantic model for output"""
```

### Core Methods

```python
async def invoke(
    self,
    input_data: InputT,
    context: AgentContext,
) -> AgentResponse[OutputT]:
    """Main entry point for agent invocation"""

@abstractmethod
def get_prompt_template(self) -> PromptTemplate:
    """Returns the versioned prompt template"""

@abstractmethod
def prepare_input(self, input_data: InputT) -> dict[str, Any]:
    """Transform input into template variables"""

def validate_output(self, output: OutputT) -> list[str]:
    """Optional output validation, returns warnings"""
```

### Agent Context

```python
class AgentContext:
    run_id: str              # Pipeline run identifier
    stage: str               # Current pipeline stage
    timestamp: datetime      # Invocation time
    
    # Optional overrides
    temperature_override: float | None
    max_tokens_override: int | None
    
    # Traceability
    parent_agent: str | None
    trace_id: str | None
```

### Agent Response

```python
class AgentResponse[OutputT]:
    success: bool
    output: OutputT | None
    error: str | None
    
    # Metrics
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: float
    retry_count: int
    
    # Provenance
    model_used: str
    prompt_hash: str
    timestamp: datetime
```

### Prompt Template

```python
class PromptTemplate:
    template_id: str              # Unique template identifier
    version: str                  # Template version
    system_prompt: str            # System message
    user_prompt_template: str     # User message with {variables}
    output_format_instructions: str
    examples: list[dict]          # Few-shot examples
    
    def render_system(self) -> str
    def render_user(**kwargs) -> str
    def get_hash() -> str         # Deterministic hash for tracking
```

## LLM Provider Support

### Supported Providers

| Provider | Model | Default For |
|----------|-------|-------------|
| OpenAI | gpt-4o | All agents |
| Anthropic | claude-3-opus | Alternative |

### Configuration

```bash
# Environment variables
export B2B_AGENT_PROVIDER=openai  # or anthropic
export B2B_AGENT_MODEL=gpt-4o
export OPENAI_API_KEY=sk-...
export ANTHROPIC_API_KEY=sk-ant-...
```

### Provider Abstraction

```python
async def _call_llm(
    self,
    system_prompt: str,
    user_prompt: str,
    context: AgentContext,
) -> tuple[str, dict[str, int]]:
    """Abstracts OpenAI and Anthropic APIs"""
    
    if self.config.provider == "openai":
        response = await client.chat.completions.create(
            model=self.config.model,
            messages=[...],
            response_format={"type": "json_object"},
        )
    elif self.config.provider == "anthropic":
        response = await client.messages.create(
            model=self.config.model,
            system=system_prompt,
            messages=[...],
        )
```

## Retry Logic

Agents use `tenacity` for automatic retries:

```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    reraise=True,
)
async def _invoke_with_retry(self, ...):
    """LLM call with exponential backoff"""
```

Retry behavior:
- Maximum 3 attempts
- Exponential backoff: 2s → 4s → 8s...
- Maximum wait: 30s
- Re-raises final exception if all retries fail

---

## Agent 1: Behavioral Observer

**Purpose:** Interprets UI states and user interactions from dynamic analysis data.

**File:** `agents/behavioral_observer.py`

### Responsibilities

- Interpret screenshot content
- Identify UI element purposes
- Understand screen semantics
- Recognize user action patterns

### Input

```python
class BehavioralObserverInput:
    screenshot_base64: str       # Base64-encoded screenshot
    ui_hierarchy: dict           # Parsed UI hierarchy
    activity_name: str           # Current activity
    observed_actions: list[dict] # Recent user actions
```

### Output

```python
class BehavioralObserverOutput:
    screen_purpose: str          # What this screen does
    key_elements: list[str]      # Important UI elements
    available_actions: list[str] # What user can do
    data_displayed: list[str]    # Data shown on screen
    navigation_options: list[str] # Where user can go
```

### Prompt Location

`prompts/behavioral_observer.md`

### Read-Only Status

✅ **Read-Only** - Only observes and interprets, never modifies data

---

## Agent 2: Product Spec Author

**Purpose:** Transforms behavioral models into formal product specifications.

**File:** `agents/product_spec.py`

### Responsibilities

- Write functional requirements
- Define acceptance criteria
- Document user journeys
- Specify error handling

### Input

```python
class ProductSpecInput:
    app_name: str
    app_description: str
    screens_summary: list[dict]    # Screen IDs, names, element counts
    user_intents: list[dict]       # Identified user goals
    navigation_flows: list[dict]   # Transition descriptions
    data_entities: list[str]       # Data types in the app
```

### Output

```python
class ProductSpecOutput:
    executive_summary: str
    scope: str
    functional_requirements: list[RequirementSpec]
    
class RequirementSpec:
    req_id: str              # e.g., "FR-001"
    title: str
    description: str
    priority: str            # MUST, SHOULD, COULD, WONT
    acceptance_criteria: list[str]
    related_screens: list[str]
```

### Prompt Location

`prompts/product_spec_author.md`

### Read-Only Status

✅ **Read-Only** - Only generates specifications from provided data

---

## Agent 3: System Architect

**Purpose:** Designs technical architecture based on behavioral specifications.

**File:** `agents/system_architect.py`

### Responsibilities

- Define module structure
- Make technology decisions
- Create architecture decision records
- Design data flows

### Input

```python
class ArchitectInput:
    app_name: str
    functional_requirements: list[dict]     # FR summaries
    non_functional_requirements: list[dict] # NFR summaries
    screen_specs: list[dict]                # Screen information
    data_entities: list[str]                # Data types
```

### Output

```python
class ArchitectOutput:
    architecture_pattern: str         # e.g., "MVVM"
    architecture_rationale: str       # Why this pattern
    module_suggestions: list[dict]    # Recommended modules
    technology_recommendations: list[dict]
    security_notes: list[str]
```

### Prompt Location

`prompts/system_architect.md`

### Read-Only Status

✅ **Read-Only** - Only designs architecture from specifications

---

## Agent 4: Android Implementation

**Purpose:** Generates Kotlin/Compose code for specific components.

**File:** `agents/android_implementation.py`

### Responsibilities

- Generate Composable functions
- Generate ViewModels
- Generate navigation code
- Generate use cases and repositories

### Input

```python
class CodeGenInput:
    component_type: str       # "screen", "viewmodel", "usecase", etc.
    component_name: str       # e.g., "HomeScreen"
    package_name: str         # e.g., "com.example.app"
    specification: dict       # Detailed spec for the component
    dependencies: list[str]   # Required imports/dependencies
```

### Output

```python
class CodeGenOutput:
    file_name: str
    package: str
    imports: list[str]
    code: str              # Generated Kotlin code
    companion_files: list[dict]  # Additional files needed
```

### Prompt Guidelines

- Generate modern Kotlin (1.9+)
- Use Jetpack Compose for UI
- Follow MVVM pattern
- Use Hilt for DI
- Use StateFlow for state management

### Read-Only Status

✅ **Read-Only** - Generates fresh code, never copies from source

---

## Agent 5: QA Parity

**Purpose:** Verifies behavioral parity between original and generated apps.

**File:** `agents/qa_parity.py`

### Responsibilities

- Compare behavioral models
- Identify missing functionality
- Suggest test scenarios
- Assess parity score

### Input

```python
class ParityInput:
    original_behavior: dict    # Behavior model summary
    generated_screens: list[dict]  # Generated screen info
    generated_navigation: dict     # Navigation graph info
    generated_features: list[str]  # Implemented features
```

### Output

```python
class ParityOutput:
    overall_assessment: str
    parity_score: float           # 0.0 - 1.0
    matching_behaviors: list[str]
    missing_behaviors: list[str]
    suggested_tests: list[dict]
    recommendations: list[str]
```

### Read-Only Status

✅ **Read-Only** - Only analyzes and reports, never modifies code

---

## Safety Guarantees

All agents are designed with legal safety in mind:

### 1. Input Sanitization

Agents **never** receive:
- Decompiled source code
- Smali bytecode
- Original implementation details

They only receive:
- Behavioral observations
- Structural summaries
- Semantic descriptions

### 2. Output Validation

Generated content is checked for:
- Decompiler watermarks
- Suspicious patterns
- Source similarity

### 3. Prompt Versioning

All prompts are:
- Version-controlled
- Hash-tracked for auditing
- Deterministic (same input → same prompt)

### 4. Audit Trail

Every agent invocation records:
- Prompt hash
- Token usage
- Model used
- Timestamp
- Input/output hashes

---

## Extending Agents

### Creating a Custom Agent

```python
from behavior2build.agents import Agent, PromptTemplate

class CustomAgent(Agent[MyInput, MyOutput]):
    
    @property
    def name(self) -> str:
        return "custom_agent"
    
    @property
    def description(self) -> str:
        return "My custom agent"
    
    @property
    def input_type(self) -> type[MyInput]:
        return MyInput
    
    @property
    def output_type(self) -> type[MyOutput]:
        return MyOutput
    
    def get_prompt_template(self) -> PromptTemplate:
        return PromptTemplate(
            template_id="custom_v1",
            version="1.0.0",
            system_prompt="You are a helpful assistant...",
            user_prompt_template="Given {input_data}, generate...",
        )
    
    def prepare_input(self, input_data: MyInput) -> dict:
        return {
            "input_data": input_data.model_dump_json(),
        }
    
    def validate_output(self, output: MyOutput) -> list[str]:
        warnings = []
        if not output.some_field:
            warnings.append("some_field is empty")
        return warnings
```

### Registering Custom Agent

```python
from behavior2build.agents import AgentRegistry

registry = AgentRegistry()
registry.register(CustomAgent())

# Use the agent
agent = registry.get("custom_agent")
response = await agent.invoke(input_data, context)
```

---

## Performance Considerations

### Token Optimization

- Summarize large inputs before sending to agents
- Limit list lengths (screens: 15, transitions: 20, etc.)
- Use structured output format (JSON)

### Latency

| Agent | Typical Latency | Max Tokens |
|-------|----------------|------------|
| Behavioral Observer | 2-5s | 2,000 |
| Product Spec Author | 5-10s | 4,000 |
| System Architect | 5-10s | 4,000 |
| Android Implementation | 3-8s | 4,000 |
| QA Parity | 3-6s | 2,000 |

### Cost Estimation

Approximate costs per pipeline run (GPT-4o):
- Total tokens: ~20,000-40,000
- Cost: ~$0.20-0.40 per run

### Caching

Consider caching agent responses for:
- Identical input hashes
- Development/testing scenarios
- Repeated analysis of same APK
