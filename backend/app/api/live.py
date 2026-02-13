"""SSE endpoint for live debate streaming."""

import asyncio
import json
import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.engine.live_event_bus import event_bus
from app.models.debate import Debate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/debates", tags=["live"])


@router.get("/{debate_id}/live")
async def live_stream(debate_id: UUID):
    """SSE endpoint for live debate events."""
    # Verify debate exists and is in live mode
    async with async_session() as db:
        result = await db.execute(select(Debate).where(Debate.id == debate_id))
        debate = result.scalar_one_or_none()
        if not debate:
            raise HTTPException(status_code=404, detail="Debate not found")
        if debate.mode != "live":
            raise HTTPException(status_code=422, detail="Debate is not in live mode")

    queue = event_bus.subscribe(debate_id)

    async def event_generator():
        try:
            # Send initial viewer count
            count = event_bus.viewer_count(debate_id)
            yield f"event: viewer_count\ndata: {json.dumps({'count': count})}\n\n"

            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    event_type = event.get("type", "message")
                    data = json.dumps(event.get("data", event))
                    yield f"event: {event_type}\ndata: {data}\n\n"

                    if event_type == "debate_complete":
                        break
                except asyncio.TimeoutError:
                    # Send keepalive ping
                    yield f"event: ping\ndata: {{}}\n\n"
        finally:
            event_bus.unsubscribe(debate_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
