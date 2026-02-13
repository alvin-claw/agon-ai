"""Background worker for processing factcheck requests."""

import asyncio
import logging

from sqlalchemy import select

from app.agents.referee_agent import RefereeAgent
from app.database import async_session
from app.models.debate import Turn
from app.models.factcheck import FactcheckRequest, FactcheckResult

logger = logging.getLogger(__name__)


class FactcheckWorker:
    def __init__(self):
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._task: asyncio.Task | None = None
        self._referee = RefereeAgent()

    def start(self):
        """Start the background processing task."""
        self._task = asyncio.create_task(self._process_loop())
        logger.info("FactcheckWorker started")

    async def enqueue(self, request_id: str):
        """Add a factcheck request ID to the processing queue."""
        await self._queue.put(request_id)

    async def recover_pending(self):
        """Re-enqueue any pending/processing requests from DB on startup."""
        async with async_session() as db:
            result = await db.execute(
                select(FactcheckRequest).where(
                    FactcheckRequest.status.in_(["pending", "processing"])
                )
            )
            requests = result.scalars().all()
            for req in requests:
                await self._queue.put(str(req.id))
            if requests:
                logger.info(f"Recovered {len(requests)} pending factcheck requests")

    async def _process_loop(self):
        """Continuously process factcheck requests from the queue."""
        while True:
            try:
                request_id = await self._queue.get()
                await self._process_request(request_id)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Error in factcheck worker loop")

    async def _process_request(self, request_id: str):
        """Process a single factcheck request."""
        async with async_session() as db:
            try:
                # Load the request
                result = await db.execute(
                    select(FactcheckRequest).where(
                        FactcheckRequest.id == request_id
                    )
                )
                req = result.scalar_one_or_none()
                if not req:
                    logger.warning(f"Factcheck request {request_id} not found")
                    return

                # Update status to processing
                req.status = "processing"
                await db.commit()

                # Load the turn to get claim and citations
                result = await db.execute(
                    select(Turn).where(Turn.id == req.turn_id)
                )
                turn = result.scalar_one_or_none()
                if not turn:
                    logger.warning(f"Turn {req.turn_id} not found for factcheck")
                    req.status = "failed"
                    await db.commit()
                    return

                claim = turn.claim or ""
                citations = turn.citations if isinstance(turn.citations, list) else []

                if not citations:
                    # No citations to check
                    fc_result = FactcheckResult(
                        request_id=req.id,
                        turn_id=req.turn_id,
                        verdict="inconclusive",
                        citation_accessible=None,
                        content_match=None,
                        logic_valid=None,
                        details={"reason": "No citations to verify"},
                    )
                    db.add(fc_result)
                    req.status = "completed"
                    await db.commit()
                    return

                # Run the referee agent
                verification = await self._referee.verify_claim(claim, citations)

                # Save result
                fc_result = FactcheckResult(
                    request_id=req.id,
                    turn_id=req.turn_id,
                    verdict=verification["verdict"],
                    citation_url=verification["citation_url"],
                    citation_accessible=verification["citation_accessible"],
                    content_match=verification["content_match"],
                    logic_valid=verification["logic_valid"],
                    details=verification["details"],
                )
                db.add(fc_result)
                req.status = "completed"
                await db.commit()

                logger.info(f"Factcheck {request_id} completed: {verification['verdict']}")

            except Exception:
                logger.exception(f"Failed to process factcheck request {request_id}")
                try:
                    req.status = "failed"
                    await db.commit()
                except Exception:
                    pass

    async def stop(self):
        """Stop the worker and clean up."""
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self._referee.close()


# Singleton instance
factcheck_worker = FactcheckWorker()
