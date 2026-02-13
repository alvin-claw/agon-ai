"""Live event bus for SSE-based real-time debate streaming."""

import asyncio
import logging
from uuid import UUID

logger = logging.getLogger(__name__)


class LiveEventBus:
    """Asyncio Queue-based pub/sub for live debate events."""

    def __init__(self):
        self._subscribers: dict[UUID, list[asyncio.Queue]] = {}

    def subscribe(self, debate_id: UUID) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        if debate_id not in self._subscribers:
            self._subscribers[debate_id] = []
        self._subscribers[debate_id].append(queue)
        logger.info(f"Live subscriber added for debate {debate_id} (total: {len(self._subscribers[debate_id])})")
        return queue

    def unsubscribe(self, debate_id: UUID, queue: asyncio.Queue):
        if debate_id in self._subscribers:
            try:
                self._subscribers[debate_id].remove(queue)
            except ValueError:
                pass
            if not self._subscribers[debate_id]:
                del self._subscribers[debate_id]
            logger.info(f"Live subscriber removed for debate {debate_id}")

    async def publish(self, debate_id: UUID, event: dict):
        if debate_id not in self._subscribers:
            return
        for queue in self._subscribers[debate_id]:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning(f"Queue full for debate {debate_id}, dropping event")

    def viewer_count(self, debate_id: UUID) -> int:
        return len(self._subscribers.get(debate_id, []))


# Singleton instance
event_bus = LiveEventBus()
