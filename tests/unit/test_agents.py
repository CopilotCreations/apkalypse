"""Unit tests for agents."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.agents.base import Agent, AgentContext, AgentResponse, PromptTemplate
from src.agents.behavioral_observer import (
    BehavioralObserverAgent,
    BehavioralObserverInput,
    BehavioralObserverOutput,
)
from src.agents.product_spec import (
    ProductSpecAuthorAgent,
    ProductSpecInput,
)


class TestPromptTemplate:
    """Tests for prompt templates."""

    def test_render_system(self):
        """Test system prompt rendering.

        Verifies that the system prompt is rendered correctly without
        any template substitutions.
        """
        template = PromptTemplate(
            template_id="test",
            version="1.0.0",
            system_prompt="You are a helpful assistant.",
            user_prompt_template="Process: {input}",
        )
        assert template.render_system() == "You are a helpful assistant."

    def test_render_user(self):
        """Test user prompt rendering.

        Verifies that template variables are correctly substituted
        in the user prompt.
        """
        template = PromptTemplate(
            template_id="test",
            version="1.0.0",
            system_prompt="System",
            user_prompt_template="Process: {input}",
        )
        rendered = template.render_user(input="test data")
        assert "test data" in rendered

    def test_render_user_with_format_instructions(self):
        """Test user prompt with format instructions.

        Verifies that output format instructions are appended to the
        rendered user prompt when provided.
        """
        template = PromptTemplate(
            template_id="test",
            version="1.0.0",
            system_prompt="System",
            user_prompt_template="Process: {input}",
            output_format_instructions="Return JSON.",
        )
        rendered = template.render_user(input="test")
        assert "Return JSON." in rendered

    def test_get_hash(self):
        """Test deterministic hash generation.

        Verifies that the template hash is consistent across multiple
        calls and has the expected length.
        """
        template = PromptTemplate(
            template_id="test",
            version="1.0.0",
            system_prompt="System",
            user_prompt_template="User {var}",
        )
        hash1 = template.get_hash()
        hash2 = template.get_hash()
        assert hash1 == hash2
        assert len(hash1) == 16


class TestBehavioralObserverAgent:
    """Tests for the behavioral observer agent."""

    def test_agent_properties(self):
        """Test agent property accessors.

        Verifies that the agent exposes the correct name, input type,
        and output type properties.
        """
        agent = BehavioralObserverAgent()
        assert agent.name == "behavioral_observer"
        assert agent.input_type == BehavioralObserverInput
        assert agent.output_type == BehavioralObserverOutput

    def test_prepare_input(self):
        """Test input preparation.

        Verifies that the agent correctly transforms structured input
        into a dictionary suitable for prompt template rendering.
        """
        agent = BehavioralObserverAgent()
        input_data = BehavioralObserverInput(
            screen_hierarchy="<root><button/></root>",
            screen_screenshot_description="A login screen",
            current_activity="com.example.LoginActivity",
            previous_screens=["Home", "Welcome"],
            observed_actions=["tap_login", "type_email"],
        )
        prepared = agent.prepare_input(input_data)
        
        assert "screen_hierarchy" in prepared
        assert "screen_screenshot_description" in prepared
        assert "current_activity" in prepared
        assert "Home, Welcome" in prepared["previous_screens"]

    def test_validate_output_low_confidence(self):
        """Test output validation with low confidence.

        Verifies that the agent generates warnings when the output
        confidence score falls below the acceptable threshold.
        """
        agent = BehavioralObserverAgent()
        from src.agents.behavioral_observer import ScreenObservation
        
        output = BehavioralObserverOutput(
            observation=ScreenObservation(
                screen_name="Test",
                screen_purpose="Testing",
                primary_elements=[],
                possible_actions=[],
                navigation_options=[],
                data_displayed=[],
            ),
            confidence=0.3,
        )
        warnings = agent.validate_output(output)
        assert len(warnings) > 0
        assert any("confidence" in w.lower() for w in warnings)


class TestProductSpecAuthorAgent:
    """Tests for the product spec author agent."""

    def test_agent_properties(self):
        """Test agent property accessors.

        Verifies that the agent exposes the correct name and description
        indicating its implementation-agnostic nature.
        """
        agent = ProductSpecAuthorAgent()
        assert agent.name == "product_spec_author"
        assert "implementation-agnostic" in agent.description.lower()

    def test_prepare_input(self):
        """Test input preparation.

        Verifies that the agent correctly transforms structured input
        including app metadata, screens, intents, and navigation flows.
        """
        agent = ProductSpecAuthorAgent()
        input_data = ProductSpecInput(
            app_name="Test App",
            app_description="A test application",
            screens_summary=[{"id": "s1", "name": "Home"}],
            user_intents=[{"id": "i1", "name": "Login"}],
            navigation_flows=[{"from": "s1", "to": "s2"}],
            data_entities=["User", "Product"],
        )
        prepared = agent.prepare_input(input_data)
        
        assert prepared["app_name"] == "Test App"
        assert "User, Product" in prepared["data_entities"]


class TestAgentContext:
    """Tests for agent context."""

    def test_context_creation(self):
        """Test context creation.

        Verifies that an AgentContext can be created with required
        fields and that optional fields default to None.
        """
        context = AgentContext(
            run_id="run_123",
            stage="analysis",
        )
        assert context.run_id == "run_123"
        assert context.stage == "analysis"
        assert context.temperature_override is None

    def test_context_with_overrides(self):
        """Test context with overrides.

        Verifies that temperature and max_tokens overrides are correctly
        stored in the context when provided.
        """
        context = AgentContext(
            run_id="run_123",
            stage="analysis",
            temperature_override=0.5,
            max_tokens_override=4096,
        )
        assert context.temperature_override == 0.5
        assert context.max_tokens_override == 4096


class TestAgentResponse:
    """Tests for agent responses."""

    def test_response_creation(self):
        """Test response creation.

        Verifies that a successful AgentResponse correctly stores
        output data and token usage statistics.
        """
        response = AgentResponse(
            success=True,
            output={"key": "value"},
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        )
        assert response.success
        assert response.total_tokens == 150

    def test_failed_response(self):
        """Test failed response.

        Verifies that a failed AgentResponse correctly stores the error
        message and has no output data.
        """
        response = AgentResponse(
            success=False,
            error="API error",
        )
        assert not response.success
        assert response.error == "API error"
        assert response.output is None
