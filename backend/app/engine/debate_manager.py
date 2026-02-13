"""Debate Engine: manages debate lifecycle and turn orchestration."""

import asyncio
import hashlib
import logging
from datetime import datetime, timezone
from uuid import UUID

import tiktoken
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.middleware.content_filter import content_filter
from app.models.agent import Agent
from app.models.debate import Debate, DebateParticipant, Turn
from app.models.factcheck import FactcheckRequest

logger = logging.getLogger(__name__)

# Cache tiktoken encoding
_TIKTOKEN_ENCODING = None


def _get_tiktoken_encoding():
    """Get cached tiktoken encoding."""
    global _TIKTOKEN_ENCODING
    if _TIKTOKEN_ENCODING is None:
        _TIKTOKEN_ENCODING = tiktoken.get_encoding("cl100k_base")
    return _TIKTOKEN_ENCODING


class DebateManager:
    """Orchestrates a debate from start to completion."""

    def __init__(self, debate_id: UUID, db_factory):
        self.debate_id = debate_id
        self.db_factory = db_factory  # async_session factory

    async def run(self):
        """Run the full debate loop."""
        try:
            await self._run_debate()
        except Exception as e:
            logger.error(f"Debate {self.debate_id} failed: {e}", exc_info=True)
            try:
                async with self.db_factory() as db:
                    result = await db.execute(select(Debate).where(Debate.id == self.debate_id))
                    debate = result.scalar_one()
                    debate.status = "failed"
                    debate.completed_at = datetime.now(timezone.utc)
                    await db.commit()
            except Exception:
                logger.error(f"Failed to mark debate {self.debate_id} as failed", exc_info=True)

    async def _run_debate(self):
        """Internal debate loop."""
        from app.agents.base import get_agent
        from app.engine.live_event_bus import event_bus

        async with self.db_factory() as db:
            debate = await self._load_debate(db)
            if not debate:
                logger.error(f"Debate {self.debate_id} not found")
                return

            is_live = debate.mode == "live"
            participants = sorted(debate.participants, key=lambda p: p.turn_order)
            logger.info(f"Starting debate '{debate.topic}' with {len(participants)} participants, {debate.max_turns} turns")

        for turn_number in range(1, debate.max_turns + 1):
            # Determine whose turn it is (round-robin)
            participant = participants[(turn_number - 1) % len(participants)]

            async with self.db_factory() as db:
                # Create pending turn
                turn = Turn(
                    debate_id=self.debate_id,
                    agent_id=participant.agent_id,
                    turn_number=turn_number,
                    status="pending",
                    team_id=participant.team_id,
                )
                db.add(turn)
                await db.commit()
                await db.refresh(turn)
                turn_id = turn.id

                # Load agent info and previous turns for context
                agent_result = await db.execute(
                    select(DebateParticipant)
                    .where(DebateParticipant.id == participant.id)
                    .options(selectinload(DebateParticipant.agent))
                )
                participant_with_agent = agent_result.scalar_one()
                agent = participant_with_agent.agent

                prev_turns = await db.execute(
                    select(Turn)
                    .where(Turn.debate_id == self.debate_id, Turn.status == "validated")
                    .order_by(Turn.turn_number)
                )
                previous_turns = prev_turns.scalars().all()

            # Publish turn_start event for live mode
            if is_live:
                await event_bus.publish(self.debate_id, {
                    "type": "turn_start",
                    "data": {
                        "turn_number": turn_number,
                        "agent_id": str(participant.agent_id),
                        "side": participant.side,
                        "team_id": participant.team_id,
                    },
                })

            # Check concurrent debate limit for external agents
            if not agent.is_builtin:
                async with self.db_factory() as db:
                    concurrent_count = await db.execute(
                        select(DebateParticipant)
                        .join(Debate, DebateParticipant.debate_id == Debate.id)
                        .where(
                            DebateParticipant.agent_id == agent.id,
                            Debate.status == "in_progress",
                            Debate.id != self.debate_id,
                        )
                    )
                    active_debates = len(concurrent_count.scalars().all())
                if active_debates >= 3:
                    async with self.db_factory() as db:
                        await self._error_turn(db, turn_id, "Concurrent debate limit exceeded (max 3)")
                        await self._update_current_turn(db, self.debate_id, turn_number)
                    logger.warning(f"Turn {turn_number}: {agent.name} skipped - concurrent debate limit exceeded")
                    if turn_number < debate.max_turns:
                        await asyncio.sleep(debate.turn_cooldown_seconds)
                    continue

            # Get agent response with timeout
            try:
                debate_agent = get_agent(agent, participant.side)
                turn_data = await asyncio.wait_for(
                    debate_agent.generate_turn(
                        topic=debate.topic,
                        side=participant.side,
                        previous_turns=previous_turns,
                        turn_number=turn_number,
                        team_id=participant.team_id,
                        max_turns=debate.max_turns,
                    ),
                    timeout=debate.turn_timeout_seconds,
                )

                # Content filter check
                is_safe, violation_reason = content_filter.check_content(
                    turn_data.get("argument", "")
                )
                if not is_safe:
                    async with self.db_factory() as db:
                        await self._content_violation_turn(db, turn_id, violation_reason)
                        await self._update_current_turn(db, self.debate_id, turn_number)
                        # Suspend the agent
                        agent_result2 = await db.execute(select(Agent).where(Agent.id == participant.agent_id))
                        db_agent = agent_result2.scalar_one()
                        db_agent.status = "suspended"
                        await db.commit()
                    logger.warning(f"Turn {turn_number}: {agent.name} content violation: {violation_reason}")
                    if turn_number < debate.max_turns:
                        await asyncio.sleep(debate.turn_cooldown_seconds)
                    continue

                # Validate and save turn
                async with self.db_factory() as db:
                    await self._save_turn(db, turn_id, turn_data)
                    await self._update_current_turn(db, self.debate_id, turn_number)

                # Auto-factcheck: enqueue for background verification
                await self._auto_factcheck(turn_id, turn_data)

                logger.info(f"Turn {turn_number}: {agent.name} ({participant.side}) - {turn_data.get('stance', 'unknown')}")

                # Publish turn_complete event for live mode
                if is_live:
                    await event_bus.publish(self.debate_id, {
                        "type": "turn_complete",
                        "data": {
                            "turn_number": turn_number,
                            "agent_id": str(participant.agent_id),
                            "side": participant.side,
                            "team_id": participant.team_id,
                            "stance": turn_data.get("stance"),
                            "claim": turn_data.get("claim"),
                            "argument": turn_data.get("argument"),
                        },
                    })

            except asyncio.TimeoutError:
                async with self.db_factory() as db:
                    await self._timeout_turn(db, turn_id)
                    await self._update_current_turn(db, self.debate_id, turn_number)
                logger.warning(f"Turn {turn_number}: {agent.name} timed out")

            except Exception as e:
                logger.error(f"Turn {turn_number}: {agent.name} error: {e}", exc_info=True)
                async with self.db_factory() as db:
                    await self._error_turn(db, turn_id, str(e))
                    await self._update_current_turn(db, self.debate_id, turn_number)

            # Cooldown between turns
            if turn_number < debate.max_turns:
                if is_live:
                    await event_bus.publish(self.debate_id, {
                        "type": "cooldown_start",
                        "data": {
                            "seconds": debate.turn_cooldown_seconds,
                            "next_turn": turn_number + 1,
                        },
                    })
                await asyncio.sleep(debate.turn_cooldown_seconds)

        # Complete the debate
        async with self.db_factory() as db:
            result = await db.execute(select(Debate).where(Debate.id == self.debate_id))
            debate = result.scalar_one()
            debate.status = "completed"
            debate.completed_at = datetime.now(timezone.utc)
            await db.commit()
            logger.info(f"Debate '{debate.topic}' completed")

        if is_live:
            await event_bus.publish(self.debate_id, {
                "type": "debate_complete",
                "data": {"debate_id": str(self.debate_id)},
            })

    async def _load_debate(self, db: AsyncSession) -> Debate | None:
        result = await db.execute(
            select(Debate)
            .where(Debate.id == self.debate_id)
            .options(selectinload(Debate.participants))
        )
        return result.scalar_one_or_none()

    async def _save_turn(self, db: AsyncSession, turn_id: UUID, data: dict):
        result = await db.execute(select(Turn).where(Turn.id == turn_id))
        turn = result.scalar_one()
        turn.stance = data.get("stance")
        turn.claim = data.get("claim")
        argument = data.get("argument", "")
        token_count = data.get("token_count", 0)

        # Enforce 500 token limit - truncate if exceeded
        if token_count > 500:
            try:
                encoding = _get_tiktoken_encoding()
                tokens = encoding.encode(argument)
                if len(tokens) > 500:
                    truncated_tokens = tokens[:500]
                    argument = encoding.decode(truncated_tokens)
                    token_count = 500
                    logger.warning(
                        f"Turn {turn.turn_number} exceeded 500 token limit "
                        f"({data.get('token_count')} tokens), truncated"
                    )
            except Exception as e:
                logger.error(f"Token truncation failed: {e}, using original argument")

        turn.argument = argument
        turn.citations = data.get("citations", [])
        # LLMs may return text descriptions instead of UUIDs for rebuttal_target.
        # Only accept strings that match UUID format (32-36 hex chars with optional hyphens).
        rebuttal_target = data.get("rebuttal_target")
        turn.rebuttal_target_id = None
        if isinstance(rebuttal_target, str) and 32 <= len(rebuttal_target) <= 36:
            try:
                turn.rebuttal_target_id = UUID(rebuttal_target)
            except Exception:
                pass
        turn.token_count = token_count
        turn.status = "validated"
        turn.submitted_at = datetime.now(timezone.utc)
        turn.validated_at = datetime.now(timezone.utc)
        await db.commit()

    async def _timeout_turn(self, db: AsyncSession, turn_id: UUID):
        result = await db.execute(select(Turn).where(Turn.id == turn_id))
        turn = result.scalar_one()
        turn.status = "timeout"
        turn.claim = "[Agent timed out for this turn]"
        turn.argument = "[No response received within the time limit]"
        turn.citations = []
        await db.commit()

    async def _content_violation_turn(self, db: AsyncSession, turn_id: UUID, reason: str | None):
        result = await db.execute(select(Turn).where(Turn.id == turn_id))
        turn = result.scalar_one()
        turn.status = "format_error"
        turn.claim = f"[Content policy violation: {reason or 'blocked content'}]"
        turn.argument = "[This turn was blocked due to a content policy violation]"
        turn.citations = []
        turn.rebuttal_target_id = None
        await db.commit()

    async def _error_turn(self, db: AsyncSession, turn_id: UUID, error_msg: str = ""):
        result = await db.execute(select(Turn).where(Turn.id == turn_id))
        turn = result.scalar_one()
        turn.status = "format_error"
        turn.claim = "[Technical error occurred]"
        turn.argument = f"[Agent encountered a technical error: {error_msg[:200]}]" if error_msg else "[Agent encountered a technical error for this turn]"
        turn.citations = []
        turn.rebuttal_target_id = None
        await db.commit()

    async def _auto_factcheck(self, turn_id: UUID, turn_data: dict):
        """Automatically enqueue a factcheck for every validated turn."""
        from app.engine.factcheck_worker import factcheck_worker

        try:
            claim_text = (turn_data.get("claim") or "") + (turn_data.get("argument") or "")
            claim_hash = hashlib.sha256(claim_text.encode()).hexdigest()[:64]

            async with self.db_factory() as db:
                # Dedup: skip if already requested for this claim in this debate
                existing = await db.execute(
                    select(FactcheckRequest).where(
                        FactcheckRequest.debate_id == self.debate_id,
                        FactcheckRequest.claim_hash == claim_hash,
                    )
                )
                if existing.scalar_one_or_none():
                    return

                fc_request = FactcheckRequest(
                    turn_id=turn_id,
                    debate_id=self.debate_id,
                    claim_hash=claim_hash,
                    session_id="auto",
                )
                db.add(fc_request)
                await db.commit()
                await db.refresh(fc_request)

            await factcheck_worker.enqueue(str(fc_request.id))
            logger.info(f"Auto-factcheck enqueued for turn {turn_id}")
        except Exception:
            logger.exception(f"Failed to enqueue auto-factcheck for turn {turn_id}")

    async def _update_current_turn(self, db: AsyncSession, debate_id: UUID, turn_number: int):
        result = await db.execute(select(Debate).where(Debate.id == debate_id))
        debate = result.scalar_one()
        debate.current_turn = turn_number
        await db.commit()
