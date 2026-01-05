"""
Base agent abstraction.

Provides the core Agent interface with type-safe inputs/outputs,
automatic retries, output validation, and LLM provider abstraction.
"""

from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential

from ..core.config import AgentConfig, get_config
from ..core.exceptions import AgentError
from ..core.logging import get_logger

logger = get_logger(__name__)

InputT = TypeVar("InputT", bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)


class AgentContext(BaseModel):
    """Context passed to agent invocations."""

    run_id: str = Field(description="Pipeline run identifier")
    stage: str = Field(description="Current pipeline stage")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Configuration overrides
    temperature_override: float | None = Field(default=None)
    max_tokens_override: int | None = Field(default=None)
    
    # Traceability
    parent_agent: str | None = Field(default=None)
    trace_id: str | None = Field(default=None)


class AgentResponse(BaseModel, Generic[OutputT]):
    """Response from an agent invocation."""

    success: bool = Field(description="Whether the invocation succeeded")
    output: OutputT | None = Field(default=None)
    error: str | None = Field(default=None)
    
    # Metrics
    prompt_tokens: int = Field(default=0)
    completion_tokens: int = Field(default=0)
    total_tokens: int = Field(default=0)
    latency_ms: float = Field(default=0.0)
    retry_count: int = Field(default=0)
    
    # Provenance
    model_used: str = Field(default="")
    prompt_hash: str = Field(default="")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


@dataclass
class PromptTemplate:
    """A versioned prompt template."""

    template_id: str
    version: str
    system_prompt: str
    user_prompt_template: str
    output_format_instructions: str = ""
    examples: list[dict[str, str]] = field(default_factory=list)

    def render_system(self) -> str:
        """Render the system prompt.

        Returns:
            str: The system prompt string.
        """
        return self.system_prompt

    def render_user(self, **kwargs: Any) -> str:
        """Render the user prompt with variables.

        Args:
            **kwargs: Template variables to substitute in the user prompt.

        Returns:
            str: The rendered user prompt with output format instructions appended
                if available.
        """
        prompt = self.user_prompt_template.format(**kwargs)
        if self.output_format_instructions:
            prompt += f"\n\n{self.output_format_instructions}"
        return prompt

    def get_hash(self) -> str:
        """Get deterministic hash of the prompt template.

        Generates a SHA-256 hash from the template ID, version, system prompt,
        and user prompt template for cache invalidation and versioning.

        Returns:
            str: A 16-character hexadecimal hash string.
        """
        content = f"{self.template_id}:{self.version}:{self.system_prompt}:{self.user_prompt_template}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]


class Agent(ABC, Generic[InputT, OutputT]):
    """Base class for all APKalypse agents.

    Agents are stateless, type-safe wrappers around LLM invocations with
    automatic retry logic, output validation, and comprehensive logging.
    """

    def __init__(
        self,
        config: AgentConfig | None = None,
    ) -> None:
        """Initialize the agent.

        Args:
            config: Agent configuration. Uses global config if not provided.
        """
        self.config = config or get_config().agent
        self._client: Any = None

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique agent name.

        Returns:
            str: The unique identifier for this agent.
        """
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Agent description.

        Returns:
            str: A human-readable description of what the agent does.
        """
        ...

    @property
    @abstractmethod
    def input_type(self) -> type[InputT]:
        """Pydantic model type for input.

        Returns:
            type[InputT]: The Pydantic model class used to validate input data.
        """
        ...

    @property
    @abstractmethod
    def output_type(self) -> type[OutputT]:
        """Pydantic model type for output.

        Returns:
            type[OutputT]: The Pydantic model class used to validate output data.
        """
        ...

    @abstractmethod
    def get_prompt_template(self) -> PromptTemplate:
        """Get the prompt template for this agent.

        Returns:
            PromptTemplate: The versioned prompt template containing system
                and user prompts for this agent.
        """
        ...

    @abstractmethod
    def prepare_input(self, input_data: InputT) -> dict[str, Any]:
        """Prepare input data for prompt rendering.

        This method transforms the typed input into a dictionary
        that can be used to render the prompt template.

        Args:
            input_data: The validated input data.

        Returns:
            dict[str, Any]: Dictionary of template variables for prompt rendering.
        """
        ...

    def validate_output(self, output: OutputT) -> list[str]:
        """Validate the agent output and return any warnings.

        Override this method to add custom validation logic.

        Args:
            output: The parsed output model instance.

        Returns:
            list[str]: List of warning messages (empty if valid).
        """
        return []

    def _get_client(self) -> Any:
        """Get or create the LLM client.

        Lazily initializes and caches the appropriate LLM client based on
        the configured provider (openai, anthropic, or azure_openai).

        Returns:
            Any: The async LLM client instance.

        Raises:
            AgentError: If the configured provider is unknown.
        """
        if self._client is not None:
            return self._client

        if self.config.provider == "openai":
            import openai
            self._client = openai.AsyncOpenAI()
        elif self.config.provider == "anthropic":
            import anthropic
            self._client = anthropic.AsyncAnthropic()
        elif self.config.provider == "azure_openai":
            import openai
            self._client = openai.AsyncAzureOpenAI(
                azure_endpoint=self.config.azure_endpoint,
                api_version=self.config.azure_api_version,
            )
        else:
            raise AgentError(
                message=f"Unknown provider: {self.config.provider}",
                agent_name=self.name,
                operation="get_client",
            )

        return self._client

    async def _call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        context: AgentContext,
    ) -> tuple[str, dict[str, int]]:
        """Call the LLM and return the response text and token counts.

        Sends a chat completion request to the configured LLM provider with
        the given prompts and context-based configuration overrides.

        Args:
            system_prompt: The system prompt to set the LLM's behavior.
            user_prompt: The user prompt containing the actual request.
            context: Agent context with configuration overrides and metadata.

        Returns:
            tuple[str, dict[str, int]]: A tuple containing:
                - The response text from the LLM.
                - A dictionary with token counts (prompt_tokens, completion_tokens,
                  total_tokens).

        Raises:
            AgentError: If the configured provider is unknown.
        """
        client = self._get_client()
        
        temperature = context.temperature_override or self.config.temperature
        max_tokens = context.max_tokens_override or self.config.max_tokens

        if self.config.provider == "openai" or self.config.provider == "azure_openai":
            # For Azure OpenAI, use deployment name if specified, otherwise fall back to model
            model_name = self.config.model
            if self.config.provider == "azure_openai" and self.config.azure_deployment_name:
                model_name = self.config.azure_deployment_name
            
            logger.info(
                "LLM request starting",
                provider=self.config.provider,
                model=model_name,
                temperature=temperature,
                max_tokens=max_tokens,
                system_prompt_chars=len(system_prompt),
                user_prompt_chars=len(user_prompt),
            )
            
            response = await client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                max_completion_tokens=max_tokens,
                response_format={"type": "json_object"},
            )
            
            response_text = response.choices[0].message.content or ""
            token_counts = {
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0,
            }
            
            logger.info(
                "LLM response received",
                provider=self.config.provider,
                model=model_name,
                prompt_tokens=token_counts["prompt_tokens"],
                completion_tokens=token_counts["completion_tokens"],
                response_chars=len(response_text),
                finish_reason=response.choices[0].finish_reason if response.choices else None,
            )
            
            return (response_text, token_counts)

        elif self.config.provider == "anthropic":
            logger.info(
                "LLM request starting",
                provider=self.config.provider,
                model=self.config.model,
                max_tokens=max_tokens,
                system_prompt_chars=len(system_prompt),
                user_prompt_chars=len(user_prompt),
            )
            
            response = await client.messages.create(
                model=self.config.model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            
            response_text = response.content[0].text if response.content else ""
            token_counts = {
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
            }
            
            logger.info(
                "LLM response received",
                provider=self.config.provider,
                model=self.config.model,
                prompt_tokens=token_counts["prompt_tokens"],
                completion_tokens=token_counts["completion_tokens"],
                response_chars=len(response_text),
                stop_reason=response.stop_reason,
            )
            
            return (response_text, token_counts)

        raise AgentError(
            message=f"Unknown provider: {self.config.provider}",
            agent_name=self.name,
            operation="call_llm",
        )

    def _parse_output(self, response_text: str) -> OutputT:
        """Parse LLM response into output type.

        Attempts to parse the response as JSON and validate it against
        the agent's output type using Pydantic.

        Args:
            response_text: The raw text response from the LLM.

        Returns:
            OutputT: The validated output model instance.

        Raises:
            AgentError: If JSON parsing fails or output validation fails.
        """
        try:
            # Try to parse as JSON
            data = json.loads(response_text)
            return self.output_type.model_validate(data)
        except json.JSONDecodeError as e:
            raise AgentError(
                message=f"Failed to parse JSON response: {e}",
                agent_name=self.name,
                operation="parse_output",
                cause=e,
            )
        except Exception as e:
            raise AgentError(
                message=f"Failed to validate output: {e}",
                agent_name=self.name,
                operation="parse_output",
                cause=e,
            )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    )
    async def _invoke_with_retry(
        self,
        system_prompt: str,
        user_prompt: str,
        context: AgentContext,
    ) -> tuple[OutputT, dict[str, int]]:
        """Invoke LLM with retry logic.

        Calls the LLM and parses the output with automatic retries using
        exponential backoff (up to 3 attempts, 2-30 second delays).

        Args:
            system_prompt: The system prompt to set the LLM's behavior.
            user_prompt: The user prompt containing the actual request.
            context: Agent context with configuration overrides and metadata.

        Returns:
            tuple[OutputT, dict[str, int]]: A tuple containing:
                - The validated output model instance.
                - A dictionary with token counts.

        Raises:
            AgentError: If all retry attempts fail.
        """
        response_text, token_counts = await self._call_llm(
            system_prompt, user_prompt, context
        )
        output = self._parse_output(response_text)
        return output, token_counts

    async def invoke(
        self,
        input_data: InputT,
        context: AgentContext,
    ) -> AgentResponse[OutputT]:
        """Invoke the agent with the given input.

        Orchestrates the full agent invocation flow: prepares prompts,
        calls the LLM with retries, validates output, and logs metrics.

        Args:
            input_data: Validated input data matching the agent's input type.
            context: Invocation context with run metadata and config overrides.

        Returns:
            AgentResponse[OutputT]: Response containing either the validated output
                or an error message, along with metrics and provenance data.
        """
        import time

        start_time = time.perf_counter()
        prompt_template = self.get_prompt_template()

        try:
            # Prepare prompts
            template_vars = self.prepare_input(input_data)
            system_prompt = prompt_template.render_system()
            user_prompt = prompt_template.render_user(**template_vars)
            prompt_hash = prompt_template.get_hash()

            logger.info(
                "Agent invocation started",
                agent=self.name,
                run_id=context.run_id,
                prompt_hash=prompt_hash,
            )

            # Call LLM with retries
            output, token_counts = await self._invoke_with_retry(
                system_prompt, user_prompt, context
            )

            # Validate output
            warnings = self.validate_output(output)
            if warnings:
                logger.warning(
                    "Agent output warnings",
                    agent=self.name,
                    warnings=warnings,
                )

            latency_ms = (time.perf_counter() - start_time) * 1000

            logger.info(
                "Agent invocation completed",
                agent=self.name,
                latency_ms=latency_ms,
                tokens=token_counts["total_tokens"],
            )

            return AgentResponse(
                success=True,
                output=output,
                prompt_tokens=token_counts["prompt_tokens"],
                completion_tokens=token_counts["completion_tokens"],
                total_tokens=token_counts["total_tokens"],
                latency_ms=latency_ms,
                model_used=self.config.model,
                prompt_hash=prompt_hash,
            )

        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            
            logger.error(
                "Agent invocation failed",
                agent=self.name,
                error=str(e),
                latency_ms=latency_ms,
            )

            return AgentResponse(
                success=False,
                output=None,
                error=str(e),
                latency_ms=latency_ms,
                model_used=self.config.model,
                prompt_hash=prompt_template.get_hash(),
            )
