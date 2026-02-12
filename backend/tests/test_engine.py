"""Tests for debate engine (DebateManager)."""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

from app.engine.debate_manager import DebateManager
from app.models.debate import Turn


@pytest.mark.asyncio
async def test_save_turn_with_valid_data(mock_db, valid_turn_data):
    """Test _save_turn handles valid turn data correctly."""
    turn_id = uuid4()
    turn = Turn(
        id=turn_id,
        debate_id=uuid4(),
        agent_id=uuid4(),
        turn_number=1,
        status="pending",
    )

    # Mock the database query to return our turn
    result_mock = MagicMock()
    result_mock.scalar_one.return_value = turn
    mock_db.execute.return_value = result_mock

    manager = DebateManager(debate_id=uuid4(), db_factory=None)
    await manager._save_turn(mock_db, turn_id, valid_turn_data)

    # Verify turn was updated correctly
    assert turn.stance == "pro"
    assert turn.claim == "AI should be regulated for safety"
    assert turn.argument == "Artificial intelligence poses significant risks that require oversight."
    assert len(turn.citations) == 1
    assert turn.citations[0]["url"] == "https://example.com/ai-safety"
    assert turn.status == "validated"
    assert turn.submitted_at is not None
    assert turn.validated_at is not None
    assert turn.token_count == 20

    # Verify commit was called
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_save_turn_with_korean_rebuttal_target(mock_db, korean_rebuttal_turn_data):
    """Test _save_turn handles non-UUID rebuttal_target gracefully (real bug case)."""
    turn_id = uuid4()
    turn = Turn(
        id=turn_id,
        debate_id=uuid4(),
        agent_id=uuid4(),
        turn_number=2,
        status="pending",
    )

    result_mock = MagicMock()
    result_mock.scalar_one.return_value = turn
    mock_db.execute.return_value = result_mock

    manager = DebateManager(debate_id=uuid4(), db_factory=None)
    await manager._save_turn(mock_db, turn_id, korean_rebuttal_turn_data)

    # Verify that Korean text in rebuttal_target is ignored (set to None)
    assert turn.rebuttal_target_id is None
    assert turn.status == "validated"
    assert turn.claim == "AI regulation is premature"

    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_save_turn_with_valid_uuid_rebuttal_target(mock_db):
    """Test _save_turn accepts valid UUID string for rebuttal_target."""
    turn_id = uuid4()
    target_turn_id = uuid4()
    turn = Turn(
        id=turn_id,
        debate_id=uuid4(),
        agent_id=uuid4(),
        turn_number=3,
        status="pending",
    )

    result_mock = MagicMock()
    result_mock.scalar_one.return_value = turn
    mock_db.execute.return_value = result_mock

    turn_data = {
        "stance": "pro",
        "claim": "Rebutting previous claim",
        "argument": "Here is my rebuttal",
        "citations": [{"url": "https://example.com", "title": "Source", "quote": "Quote"}],
        "rebuttal_target": str(target_turn_id),
        "token_count": 10,
    }

    manager = DebateManager(debate_id=uuid4(), db_factory=None)
    await manager._save_turn(mock_db, turn_id, turn_data)

    # Verify UUID was parsed correctly
    assert turn.rebuttal_target_id == target_turn_id
    assert turn.status == "validated"


@pytest.mark.asyncio
async def test_save_turn_truncates_long_arguments(mock_db):
    """Test _save_turn truncates arguments exceeding 500 tokens."""
    turn_id = uuid4()
    turn = Turn(
        id=turn_id,
        debate_id=uuid4(),
        agent_id=uuid4(),
        turn_number=1,
        status="pending",
    )

    result_mock = MagicMock()
    result_mock.scalar_one.return_value = turn
    mock_db.execute.return_value = result_mock

    # Create data with token_count over 500
    long_argument = " ".join(["word"] * 600)  # Very long argument
    turn_data = {
        "stance": "pro",
        "claim": "Test claim",
        "argument": long_argument,
        "citations": [{"url": "https://example.com", "title": "Source", "quote": "Quote"}],
        "token_count": 600,  # Over limit
    }

    manager = DebateManager(debate_id=uuid4(), db_factory=None)
    await manager._save_turn(mock_db, turn_id, turn_data)

    # Verify token count was capped at 500
    assert turn.token_count == 500
    assert turn.status == "validated"
    # Argument should be truncated (not the full 600-word string)
    assert len(turn.argument) < len(long_argument)


@pytest.mark.asyncio
async def test_timeout_turn(mock_db):
    """Test _timeout_turn sets correct status and messages."""
    turn_id = uuid4()
    turn = Turn(
        id=turn_id,
        debate_id=uuid4(),
        agent_id=uuid4(),
        turn_number=1,
        status="pending",
    )

    result_mock = MagicMock()
    result_mock.scalar_one.return_value = turn
    mock_db.execute.return_value = result_mock

    manager = DebateManager(debate_id=uuid4(), db_factory=None)
    await manager._timeout_turn(mock_db, turn_id)

    # Verify timeout status and messages
    assert turn.status == "timeout"
    assert turn.claim == "[Agent timed out for this turn]"
    assert turn.argument == "[No response received within the time limit]"
    assert turn.citations == []

    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_error_turn_with_message(mock_db):
    """Test _error_turn sets correct status and truncates error message."""
    turn_id = uuid4()
    turn = Turn(
        id=turn_id,
        debate_id=uuid4(),
        agent_id=uuid4(),
        turn_number=1,
        status="pending",
    )

    result_mock = MagicMock()
    result_mock.scalar_one.return_value = turn
    mock_db.execute.return_value = result_mock

    long_error = "X" * 300  # Error longer than 200 chars

    manager = DebateManager(debate_id=uuid4(), db_factory=None)
    await manager._error_turn(mock_db, turn_id, long_error)

    # Verify error status and truncated message
    assert turn.status == "format_error"
    assert turn.claim == "[Technical error occurred]"
    assert "[Agent encountered a technical error:" in turn.argument
    assert len(turn.argument) < 250  # Should be truncated to ~200 + message prefix
    assert turn.citations == []
    assert turn.rebuttal_target_id is None

    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_error_turn_without_message(mock_db):
    """Test _error_turn with no error message."""
    turn_id = uuid4()
    turn = Turn(
        id=turn_id,
        debate_id=uuid4(),
        agent_id=uuid4(),
        turn_number=1,
        status="pending",
    )

    result_mock = MagicMock()
    result_mock.scalar_one.return_value = turn
    mock_db.execute.return_value = result_mock

    manager = DebateManager(debate_id=uuid4(), db_factory=None)
    await manager._error_turn(mock_db, turn_id, "")

    # Verify generic error message
    assert turn.status == "format_error"
    assert turn.claim == "[Technical error occurred]"
    assert turn.argument == "[Agent encountered a technical error for this turn]"

    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_update_current_turn(mock_db, sample_debate):
    """Test _update_current_turn updates the turn number correctly."""
    debate = sample_debate

    result_mock = MagicMock()
    result_mock.scalar_one.return_value = debate
    mock_db.execute.return_value = result_mock

    manager = DebateManager(debate_id=debate.id, db_factory=None)
    await manager._update_current_turn(mock_db, debate.id, 3)

    # Verify current_turn was updated
    assert debate.current_turn == 3

    mock_db.commit.assert_called_once()
