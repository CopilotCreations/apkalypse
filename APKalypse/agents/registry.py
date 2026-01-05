"""
Agent registry for managing and retrieving agents.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import Agent

# Global registry of agents
_AGENT_REGISTRY: dict[str, type[Agent]] = {}


class AgentRegistry:
    """Registry for managing agent types."""

    @classmethod
    def register(cls, agent_class: type[Agent]) -> type[Agent]:
        """Register an agent class.

        Can be used as a decorator:
            @AgentRegistry.register
            class MyAgent(Agent):
                ...

        Args:
            agent_class: The agent class to register. Must be a subclass of Agent.

        Returns:
            The registered agent class (allows use as a decorator).
        """
        # Get name from an instance (need to instantiate temporarily)
        # or use class name as fallback
        name = getattr(agent_class, "NAME", agent_class.__name__)
        _AGENT_REGISTRY[name] = agent_class
        return agent_class

    @classmethod
    def get(cls, name: str) -> type[Agent] | None:
        """Get an agent class by name.

        Args:
            name: The registered name of the agent class to retrieve.

        Returns:
            The agent class if found, None otherwise.
        """
        return _AGENT_REGISTRY.get(name)

    @classmethod
    def list_agents(cls) -> list[str]:
        """List all registered agent names.

        Returns:
            A list of all registered agent names.
        """
        return list(_AGENT_REGISTRY.keys())

    @classmethod
    def clear(cls) -> None:
        """Clear the registry.

        Primarily intended for testing purposes to reset the registry state.
        """
        _AGENT_REGISTRY.clear()


def get_agent(name: str) -> type[Agent] | None:
    """Get an agent class by name.

    Convenience function that delegates to AgentRegistry.get().

    Args:
        name: The registered name of the agent class to retrieve.

    Returns:
        The agent class if found, None otherwise.
    """
    return AgentRegistry.get(name)
