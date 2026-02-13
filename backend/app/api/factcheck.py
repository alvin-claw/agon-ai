import hashlib
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from app.database import get_db
from app.engine.factcheck_worker import factcheck_worker
from app.models.debate import Turn
from app.models.factcheck import FactcheckRequest, FactcheckResult
from app.schemas.factcheck import (
    FactcheckCreate,
    FactcheckRequestResponse,
    FactcheckResultResponse,
)

router = APIRouter(prefix="/api/debates", tags=["factcheck"])
limiter = Limiter(key_func=get_remote_address)


@router.post(
    "/{debate_id}/turns/{turn_id}/factcheck",
    response_model=FactcheckRequestResponse,
    status_code=202,
)
@limiter.limit("1/minute")
async def request_factcheck(
    request: Request,
    debate_id: UUID,
    turn_id: UUID,
    body: FactcheckCreate,
    db: AsyncSession = Depends(get_db),
):
    """Request a fact-check for a specific turn. 60s cooldown per IP."""
    # Verify turn exists and belongs to debate
    result = await db.execute(
        select(Turn).where(Turn.id == turn_id, Turn.debate_id == debate_id)
    )
    turn = result.scalar_one_or_none()
    if not turn:
        raise HTTPException(status_code=404, detail="Turn not found")
    if turn.status != "validated":
        raise HTTPException(status_code=400, detail="Can only factcheck validated turns")

    # Check max 20 factcheck requests per debate
    result = await db.execute(
        select(func.count()).select_from(FactcheckRequest).where(
            FactcheckRequest.debate_id == debate_id
        )
    )
    count = result.scalar()
    if count and count >= 20:
        raise HTTPException(status_code=429, detail="Maximum factcheck requests reached for this debate")

    # Generate claim hash for deduplication
    claim_text = (turn.claim or "") + (turn.argument or "")
    claim_hash = hashlib.sha256(claim_text.encode()).hexdigest()[:64]

    # Check for existing request (dedup by claim_hash within debate)
    result = await db.execute(
        select(FactcheckRequest).where(
            FactcheckRequest.debate_id == debate_id,
            FactcheckRequest.claim_hash == claim_hash,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        # Increment request count
        existing.request_count += 1
        await db.commit()
        await db.refresh(existing)
        return existing

    # Create new factcheck request
    fc_request = FactcheckRequest(
        turn_id=turn_id,
        debate_id=debate_id,
        claim_hash=claim_hash,
        session_id=body.session_id,
    )
    db.add(fc_request)
    await db.commit()
    await db.refresh(fc_request)

    # Enqueue for background processing
    await factcheck_worker.enqueue(str(fc_request.id))

    return fc_request


@router.get(
    "/{debate_id}/factchecks",
    response_model=list[FactcheckResultResponse],
)
async def get_debate_factchecks(
    debate_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get all factcheck results for a debate."""
    result = await db.execute(
        select(FactcheckResult)
        .join(FactcheckRequest, FactcheckResult.request_id == FactcheckRequest.id)
        .where(FactcheckRequest.debate_id == debate_id)
        .order_by(FactcheckResult.created_at)
    )
    return result.scalars().all()


@router.get(
    "/{debate_id}/turns/{turn_id}/factcheck",
    response_model=FactcheckResultResponse | None,
)
async def get_turn_factcheck(
    debate_id: UUID,
    turn_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get factcheck result for a specific turn."""
    result = await db.execute(
        select(FactcheckResult).where(FactcheckResult.turn_id == turn_id)
    )
    fc_result = result.scalar_one_or_none()
    if not fc_result:
        raise HTTPException(status_code=404, detail="Factcheck result not found")
    return fc_result
