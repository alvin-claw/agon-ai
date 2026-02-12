"""External debate agent that calls a developer-hosted endpoint via HTTP POST."""

import logging

import httpx
import tiktoken

from app.agents.base import BaseDebateAgent
from app.models.agent import Agent
from app.models.debate import Turn

logger = logging.getLogger(__name__)

_TIKTOKEN_ENCODING = None


def _get_encoding():
    global _TIKTOKEN_ENCODING
    if _TIKTOKEN_ENCODING is None:
        _TIKTOKEN_ENCODING = tiktoken.get_encoding("cl100k_base")
    return _TIKTOKEN_ENCODING


class ExternalDebateAgent(BaseDebateAgent):
    def __init__(self, agent: Agent, side: str):
        super().__init__(agent, side)
        self.endpoint_url = agent.endpoint_url

    async def generate_turn(
        self,
        topic: str,
        side: str,
        previous_turns: list[Turn],
        turn_number: int,
    ) -> dict:
        previous = [
            {
                "turn_number": t.turn_number,
                "side": t.stance,
                "claim": t.claim,
                "argument": t.argument,
            }
            for t in previous_turns
        ]

        payload = {
            "topic": topic,
            "side": side,
            "turn_number": turn_number,
            "previous_turns": previous,
            "timeout_seconds": 120,
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{self.endpoint_url}/turn",
                json=payload,
                headers={"Content-Type": "application/json"},
            )

        if resp.status_code != 200:
            raise RuntimeError(
                f"External agent returned status {resp.status_code}: {resp.text[:200]}"
            )

        data = resp.json()

        required = ["stance", "claim", "argument", "citations"]
        missing = [f for f in required if f not in data]
        if missing:
            raise ValueError(f"Missing required fields: {missing}")

        # Count tokens
        try:
            enc = _get_encoding()
            token_count = len(enc.encode(data.get("argument", "")))
        except Exception:
            token_count = len(data.get("argument", "").split()) * 2

        return {
            "stance": data["stance"],
            "claim": data["claim"],
            "argument": data["argument"],
            "citations": data["citations"],
            "rebuttal_target": data.get("rebuttal_target"),
            "token_count": token_count,
        }
