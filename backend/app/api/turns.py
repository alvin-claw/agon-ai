from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.debate import Debate, Turn
from app.schemas.turn import TurnResponse

router = APIRouter(prefix="/api/debates/{debate_id}/turns", tags=["turns"])


@router.get("", response_model=list[TurnResponse])
async def list_turns(
    debate_id: UUID,
    agent_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
):
    # Verify debate exists
    result = await db.execute(select(Debate).where(Debate.id == debate_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Debate not found")

    query = select(Turn).where(Turn.debate_id == debate_id).order_by(Turn.turn_number)
    if agent_id:
        query = query.where(Turn.agent_id == agent_id)
    result = await db.execute(query)
    return result.scalars().all()
