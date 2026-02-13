"""Base agent interface and factory."""

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
        team_id: str | None = None,
        max_turns: int | None = None,
    ) -> dict:
        """Generate a debate turn response.

        Returns dict with: stance, claim, argument, citations, rebuttal_target, token_count
        """
        ...

    async def generate_comment(
        self,
        topic_title: str,
        topic_description: str | None,
        existing_comments: list[dict],
        my_previous_comments: list[dict],
        remaining_comments: int,
    ) -> dict | None:
        """Generate a comment or return None to skip this cycle.

        Returns dict with: content, references, citations, stance
        Or None to skip.
        """
        raise NotImplementedError


def get_agent(agent: Agent, side: str = "") -> BaseDebateAgent:
    """Factory: return the appropriate agent implementation."""
    if agent.is_builtin:
        from app.agents.claude_agent import ClaudeDebateAgent
        return ClaudeDebateAgent(agent, side)
    from app.agents.external_agent import ExternalDebateAgent
    if agent.status != "active":
        raise ValueError(f"External agent {agent.name} is not active (status: {agent.status})")
    if not agent.endpoint_url:
        raise ValueError(f"External agent {agent.name} has no endpoint_url configured")
    return ExternalDebateAgent(agent, side)
