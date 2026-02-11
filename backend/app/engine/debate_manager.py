"""Debate Engine: manages debate lifecycle and turn orchestration."""

import asyncio
import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models.debate import Debate, DebateParticipant, Turn

logger = logging.getLogger(__name__)


class DebateManager:
    """Orchestrates a debate from start to completion."""

    def __init__(self, debate_id: UUID, db_factory):
        self.debate_id = debate_id
        self.db_factory = db_factory  # async_session factory

    async def run(self):
        """Run the full debate loop."""
        from app.agents.base import get_builtin_agent

        async with self.db_factory() as db:
            debate = await self._load_debate(db)
            if not debate:
                logger.error(f"Debate {self.debate_id} not found")
                return

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

            # Get agent response with timeout
            try:
                builtin_agent = get_builtin_agent(agent, participant.side)
                turn_data = await asyncio.wait_for(
                    builtin_agent.generate_turn(
                        topic=debate.topic,
                        side=participant.side,
                        previous_turns=previous_turns,
                        turn_number=turn_number,
                    ),
                    timeout=debate.turn_timeout_seconds,
                )

                # Validate and save turn
                async with self.db_factory() as db:
                    await self._save_turn(db, turn_id, turn_data)
                    await self._update_current_turn(db, self.debate_id, turn_number)

                logger.info(f"Turn {turn_number}: {agent.name} ({participant.side}) - {turn_data.get('stance', 'unknown')}")

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
                await asyncio.sleep(debate.turn_cooldown_seconds)

        # Complete the debate
        async with self.db_factory() as db:
            result = await db.execute(select(Debate).where(Debate.id == self.debate_id))
            debate = result.scalar_one()
            debate.status = "completed"
            debate.completed_at = datetime.now(timezone.utc)
            await db.commit()
            logger.info(f"Debate '{debate.topic}' completed")

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
        turn.argument = data.get("argument")
        turn.citations = data.get("citations", [])
        turn.rebuttal_target_id = data.get("rebuttal_target")
        turn.token_count = data.get("token_count")
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

    async def _error_turn(self, db: AsyncSession, turn_id: UUID, error_msg: str = ""):
        result = await db.execute(select(Turn).where(Turn.id == turn_id))
        turn = result.scalar_one()
        turn.status = "format_error"
        turn.claim = "[Technical error occurred]"
        turn.argument = f"[Error: {error_msg[:400]}]" if error_msg else "[Agent encountered a technical error for this turn]"
        turn.citations = []
        await db.commit()

    async def _update_current_turn(self, db: AsyncSession, debate_id: UUID, turn_number: int):
        result = await db.execute(select(Debate).where(Debate.id == debate_id))
        debate = result.scalar_one()
        debate.current_turn = turn_number
        await db.commit()
