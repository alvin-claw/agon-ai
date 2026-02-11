from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.debate import Turn
from app.models.reaction import Reaction
from app.schemas.turn import ReactionCreate, ReactionResponse

router = APIRouter(tags=["reactions"])


@router.post(
    "/api/debates/{debate_id}/turns/{turn_id}/reactions",
    response_model=ReactionResponse,
    status_code=201,
)
async def add_reaction(
    debate_id: UUID,
    turn_id: UUID,
    body: ReactionCreate,
    db: AsyncSession = Depends(get_db),
):
    # Verify turn exists and belongs to debate
    result = await db.execute(
        select(Turn).where(Turn.id == turn_id, Turn.debate_id == debate_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Turn not found")

    reaction = Reaction(
        turn_id=turn_id,
        type=body.type,
        session_id=body.session_id,
    )
    db.add(reaction)
    try:
        await db.commit()
        await db.refresh(reaction)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=422, detail="Duplicate reaction")
    return reaction


@router.get(
    "/api/debates/{debate_id}/reactions",
    response_model=dict[str, dict[str, int]],
)
async def get_reaction_counts(
    debate_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get reaction counts grouped by turn_id and type."""
    result = await db.execute(
        select(
            Reaction.turn_id,
            Reaction.type,
            func.count().label("count"),
        )
        .join(Turn, Turn.id == Reaction.turn_id)
        .where(Turn.debate_id == debate_id)
        .group_by(Reaction.turn_id, Reaction.type)
    )
    counts: dict[str, dict[str, int]] = {}
    for row in result.all():
        tid = str(row.turn_id)
        if tid not in counts:
            counts[tid] = {}
        counts[tid][row.type] = row.count
    return counts
