"""Base agent interface and factory for built-in agents."""

from abc import ABC, abstractmethod

from app.models.agent import Agent
from app.models.debate import Turn


class BaseDebateAgent(ABC):
    """Abstract base class for debate agents."""

    def __init__(self, agent: Agent, side: str):
        self.agent = agent
        self.side = side

    @abstractmethod
    async def generate_turn(
        self,
        topic: str,
        side: str,
        previous_turns: list[Turn],
        turn_number: int,
    ) -> dict:
        """Generate a debate turn response.

        Returns dict with: stance, claim, argument, citations, rebuttal_target, token_count
        """
        ...


def get_builtin_agent(agent: Agent, side: str) -> BaseDebateAgent:
    """Factory: return the appropriate agent implementation."""
    if agent.is_builtin:
        from app.agents.claude_agent import ClaudeDebateAgent
        return ClaudeDebateAgent(agent, side)
    raise ValueError(f"External agents not yet supported: {agent.name}")
