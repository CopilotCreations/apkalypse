"""
Agent framework for Behavior2Build.

Provides a reusable abstraction for LLM-based agents with type-safe
inputs/outputs, automatic retries, and output validation.
"""

from .base import Agent, AgentContext, AgentResponse
from .registry import AgentRegistry, get_agent
from .behavioral_observer import BehavioralObserverAgent
from .product_spec import ProductSpecAuthorAgent
from .system_architect import SystemArchitectAgent
from .android_implementation import AndroidImplementationAgent
from .qa_parity import QAParityAgent

__all__ = [
    "Agent",
    "AgentContext",
    "AgentResponse",
    "AgentRegistry",
    "get_agent",
    "BehavioralObserverAgent",
    "ProductSpecAuthorAgent",
    "SystemArchitectAgent",
    "AndroidImplementationAgent",
    "QAParityAgent",
]
