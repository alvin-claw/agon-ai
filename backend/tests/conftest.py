"""Shared test fixtures and configuration."""

import asyncio
from datetime import datetime, timezone
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent
from app.models.debate import Debate, DebateParticipant, Turn


@pytest.fixture(scope="function")
def event_loop():
    """Create an instance of the default event loop for each test."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_db() -> AsyncMock:
    """Create a mock database session."""
    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.flush = AsyncMock()
    db.add = MagicMock()
    return db


@pytest.fixture
def sample_agent() -> Agent:
    """Create a sample agent for testing."""
    return Agent(
        id=uuid4(),
        name="Test Agent",
        model_name="claude-haiku-4-5-20251001",
        description="A test agent",
        status="active",
        is_builtin=True,
    )


@pytest.fixture
def sample_agent_pro() -> Agent:
    """Create a sample pro agent."""
    return Agent(
        id=uuid4(),
        name="Pro Agent",
        model_name="claude-haiku-4-5-20251001",
        description="Pro side agent",
        status="active",
        is_builtin=True,
    )


@pytest.fixture
def sample_agent_con() -> Agent:
    """Create a sample con agent."""
    return Agent(
        id=uuid4(),
        name="Con Agent",
        model_name="claude-haiku-4-5-20251001",
        description="Con side agent",
        status="active",
        is_builtin=True,
    )


@pytest.fixture
def sample_debate(sample_agent_pro, sample_agent_con) -> Debate:
    """Create a sample debate with participants."""
    debate = Debate(
        id=uuid4(),
        topic="Should AI be regulated?",
        format="1v1",
        status="scheduled",
        max_turns=6,
        current_turn=0,
        turn_timeout_seconds=120,
        turn_cooldown_seconds=5,
        created_at=datetime.now(timezone.utc),
    )
    debate.participants = [
        DebateParticipant(
            id=uuid4(),
            debate_id=debate.id,
            agent_id=sample_agent_pro.id,
            side="pro",
            turn_order=0,
            agent=sample_agent_pro,
        ),
        DebateParticipant(
            id=uuid4(),
            debate_id=debate.id,
            agent_id=sample_agent_con.id,
            side="con",
            turn_order=1,
            agent=sample_agent_con,
        ),
    ]
    return debate


@pytest.fixture
def sample_turn() -> Turn:
    """Create a sample turn."""
    return Turn(
        id=uuid4(),
        debate_id=uuid4(),
        agent_id=uuid4(),
        turn_number=1,
        stance="pro",
        claim="AI should be regulated",
        argument="This is a detailed argument about AI regulation.",
        citations=[
            {
                "url": "https://example.com",
                "title": "AI Safety",
                "quote": "Regulation is necessary",
            }
        ],
        status="validated",
        token_count=15,
        submitted_at=datetime.now(timezone.utc),
        validated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def valid_turn_data() -> dict:
    """Create valid turn data for testing."""
    return {
        "stance": "pro",
        "claim": "AI should be regulated for safety",
        "argument": "Artificial intelligence poses significant risks that require oversight.",
        "citations": [
            {
                "url": "https://example.com/ai-safety",
                "title": "AI Safety Research",
                "quote": "Regulation reduces risks",
            }
        ],
        "rebuttal_target": None,
        "token_count": 20,
    }


@pytest.fixture
def korean_rebuttal_turn_data() -> dict:
    """Create turn data with Korean text in rebuttal_target (bug case)."""
    return {
        "stance": "con",
        "claim": "AI regulation is premature",
        "argument": "Current AI technology is not advanced enough to warrant regulation.",
        "citations": [
            {
                "url": "https://example.com/ai-innovation",
                "title": "AI Innovation",
                "quote": "Too early for regulation",
            }
        ],
        "rebuttal_target": "상대방의 주장에 대한 반박",  # Korean text
        "token_count": 18,
    }
