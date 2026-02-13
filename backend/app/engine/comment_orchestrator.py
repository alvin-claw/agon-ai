"""Comment Orchestrator: manages topic lifecycle and agent polling."""

import asyncio
import hashlib
import logging
import random
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.middleware.content_filter import content_filter
from app.models.factcheck import FactcheckRequest
from app.models.topic import Comment, Topic, TopicParticipant

logger = logging.getLogger(__name__)


class CommentOrchestrator:
    """Orchestrates a free-form comment discussion on a topic."""

    def __init__(self, topic_id: UUID, db_factory):
        self.topic_id = topic_id
        self.db_factory = db_factory

    async def run(self):
        """Run the comment orchestration loop."""
        try:
            await self._run_loop()
        except Exception as e:
            logger.error(f"Topic {self.topic_id} orchestrator failed: {e}", exc_info=True)
            try:
                async with self.db_factory() as db:
                    result = await db.execute(select(Topic).where(Topic.id == self.topic_id))
                    topic = result.scalar_one()
                    topic.status = "closed"
                    topic.closed_at = datetime.now(timezone.utc)
                    await db.commit()
            except Exception:
                logger.error(f"Failed to mark topic {self.topic_id} as closed", exc_info=True)

    async def _run_loop(self):
        """Internal orchestration loop."""
        from app.agents.base import get_agent
        from app.engine.live_event_bus import event_bus

        async with self.db_factory() as db:
            topic = await self._load_topic(db)
            if not topic:
                logger.error(f"Topic {self.topic_id} not found")
                return

            polling_interval = topic.polling_interval_seconds
            logger.info(
                f"Starting topic '{topic.title}' with {len(topic.participants)} participants, "
                f"polling every {polling_interval}s"
            )

        while True:
            # Check if topic should close (time expired)
            async with self.db_factory() as db:
                result = await db.execute(select(Topic).where(Topic.id == self.topic_id))
                topic = result.scalar_one()

                if topic.status != "open":
                    logger.info(f"Topic '{topic.title}' is no longer open (status={topic.status})")
                    break

                now = datetime.now(timezone.utc)
                if topic.closes_at and now >= topic.closes_at.replace(tzinfo=timezone.utc if topic.closes_at.tzinfo is None else topic.closes_at.tzinfo):
                    await self._close_topic(db, topic, "Time expired")
                    break

            # Load participants and existing comments
            async with self.db_factory() as db:
                participants = await db.execute(
                    select(TopicParticipant)
                    .where(TopicParticipant.topic_id == self.topic_id)
                    .options(selectinload(TopicParticipant.agent))
                )
                participants = participants.scalars().all()

                comments_result = await db.execute(
                    select(Comment)
                    .where(Comment.topic_id == self.topic_id)
                    .options(selectinload(Comment.agent))
                    .order_by(Comment.created_at)
                )
                all_comments = comments_result.scalars().all()

            # Build comment context for agents
            existing_comments = [
                {
                    "id": str(c.id),
                    "agent_id": str(c.agent_id),
                    "agent_name": c.agent.name if c.agent else "Unknown",
                    "content": c.content,
                    "references": c.references_ or [],
                    "citations": c.citations or [],
                    "stance": c.stance,
                    "created_at": str(c.created_at),
                }
                for c in all_comments
            ]

            # Check if all agents hit max comments
            all_maxed = all(p.comment_count >= p.max_comments for p in participants)
            if all_maxed:
                async with self.db_factory() as db:
                    result = await db.execute(select(Topic).where(Topic.id == self.topic_id))
                    topic = result.scalar_one()
                    await self._close_topic(db, topic, "All agents reached comment limit")
                break

            # Poll each agent (shuffled order)
            shuffled_participants = list(participants)
            random.shuffle(shuffled_participants)

            for participant in shuffled_participants:
                if participant.comment_count >= participant.max_comments:
                    continue

                agent = participant.agent
                my_comments = [c for c in existing_comments if c["agent_id"] == str(agent.id)]
                remaining = participant.max_comments - participant.comment_count

                try:
                    debate_agent = get_agent(agent, side="")
                    comment_data = await asyncio.wait_for(
                        debate_agent.generate_comment(
                            topic_title=topic.title,
                            topic_description=topic.description,
                            existing_comments=existing_comments,
                            my_previous_comments=my_comments,
                            remaining_comments=remaining,
                        ),
                        timeout=120,
                    )

                    if comment_data is None:
                        logger.info(f"Agent {agent.name} skipped this cycle")
                        await asyncio.sleep(2)
                        continue

                    # Content filter check
                    is_safe, violation_reason = content_filter.check_content(
                        comment_data.get("content", "")
                    )
                    if not is_safe:
                        logger.warning(f"Agent {agent.name} content violation: {violation_reason}")
                        await asyncio.sleep(2)
                        continue

                    # Save comment
                    async with self.db_factory() as db:
                        comment = Comment(
                            topic_id=self.topic_id,
                            agent_id=agent.id,
                            content=comment_data["content"],
                            references_=comment_data.get("references", []),
                            citations=comment_data.get("citations", []),
                            stance=comment_data.get("stance"),
                            token_count=comment_data.get("token_count"),
                        )
                        db.add(comment)

                        # Increment participant comment count
                        part_result = await db.execute(
                            select(TopicParticipant).where(
                                TopicParticipant.topic_id == self.topic_id,
                                TopicParticipant.agent_id == agent.id,
                            )
                        )
                        db_participant = part_result.scalar_one()
                        db_participant.comment_count += 1

                        await db.commit()
                        await db.refresh(comment)

                        comment_id = comment.id

                    # Publish event for realtime
                    await event_bus.publish(self.topic_id, {
                        "type": "new_comment",
                        "data": {
                            "comment_id": str(comment_id),
                            "agent_id": str(agent.id),
                            "agent_name": agent.name,
                        },
                    })

                    # Add to context for subsequent agents in this cycle
                    existing_comments.append({
                        "id": str(comment_id),
                        "agent_id": str(agent.id),
                        "agent_name": agent.name,
                        "content": comment_data["content"],
                        "references": comment_data.get("references", []),
                        "citations": comment_data.get("citations", []),
                        "stance": comment_data.get("stance"),
                        "created_at": str(datetime.now(timezone.utc)),
                    })

                    # Auto-factcheck
                    await self._auto_factcheck(comment_id, comment_data)

                    logger.info(f"Agent {agent.name} commented on topic {self.topic_id}")

                except asyncio.TimeoutError:
                    logger.warning(f"Agent {agent.name} timed out")
                except Exception as e:
                    logger.error(f"Agent {agent.name} error: {e}", exc_info=True)

                # Small delay between agents
                await asyncio.sleep(5)

            # Sleep before next polling cycle
            await asyncio.sleep(polling_interval)

        # Publish topic closed event
        from app.engine.live_event_bus import event_bus
        await event_bus.publish(self.topic_id, {
            "type": "topic_closed",
            "data": {"topic_id": str(self.topic_id)},
        })

    async def _load_topic(self, db: AsyncSession) -> Topic | None:
        result = await db.execute(
            select(Topic)
            .where(Topic.id == self.topic_id)
            .options(selectinload(Topic.participants).selectinload(TopicParticipant.agent))
        )
        return result.scalar_one_or_none()

    async def _close_topic(self, db: AsyncSession, topic: Topic, reason: str):
        topic.status = "closed"
        topic.closed_at = datetime.now(timezone.utc)
        await db.commit()
        logger.info(f"Topic '{topic.title}' closed: {reason}")

    async def _auto_factcheck(self, comment_id: UUID, comment_data: dict):
        """Automatically enqueue a factcheck for a comment with citations."""
        from app.engine.factcheck_worker import factcheck_worker

        try:
            citations = comment_data.get("citations", [])
            if not citations:
                return

            content = comment_data.get("content", "")
            claim_hash = hashlib.sha256(content.encode()).hexdigest()[:64]

            async with self.db_factory() as db:
                existing = await db.execute(
                    select(FactcheckRequest).where(
                        FactcheckRequest.topic_id == self.topic_id,
                        FactcheckRequest.claim_hash == claim_hash,
                    )
                )
                if existing.scalar_one_or_none():
                    return

                fc_request = FactcheckRequest(
                    comment_id=comment_id,
                    topic_id=self.topic_id,
                    claim_hash=claim_hash,
                    session_id="auto",
                )
                db.add(fc_request)
                await db.commit()
                await db.refresh(fc_request)

            await factcheck_worker.enqueue(str(fc_request.id))
            logger.info(f"Auto-factcheck enqueued for comment {comment_id}")
        except Exception:
            logger.exception(f"Failed to enqueue auto-factcheck for comment {comment_id}")
