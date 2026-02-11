from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.agent import Agent
from app.models.debate import Debate, DebateParticipant
from app.schemas.debate import DebateCreate, DebateListResponse, DebateResponse, ParticipantResponse

router = APIRouter(prefix="/api/debates", tags=["debates"])


@router.get("", response_model=list[DebateListResponse])
async def list_debates(
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Debate).order_by(Debate.created_at.desc())
    if status:
        query = query.where(Debate.status == status)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("", response_model=DebateResponse, status_code=201)
async def create_debate(
    body: DebateCreate,
    db: AsyncSession = Depends(get_db),
):
    # Validate agents exist
    agent_ids = body.agent_ids
    result = await db.execute(select(Agent).where(Agent.id.in_(agent_ids)))
    agents = result.scalars().all()
    if len(agents) != len(agent_ids):
        raise HTTPException(status_code=422, detail="One or more agents not found")

    # For 1v1, first agent is pro, second is con
    debate = Debate(
        topic=body.topic,
        format=body.format,
        max_turns=body.max_turns,
    )
    db.add(debate)
    await db.flush()

    sides = ["pro", "con"]
    for i, agent_id in enumerate(agent_ids):
        participant = DebateParticipant(
            debate_id=debate.id,
            agent_id=agent_id,
            side=sides[i % 2],
            turn_order=i,
        )
        db.add(participant)

    await db.commit()

    # Reload with participants and their agents
    result = await db.execute(
        select(Debate)
        .where(Debate.id == debate.id)
        .options(selectinload(Debate.participants).selectinload(DebateParticipant.agent))
    )
    debate = result.scalar_one()

    return _debate_to_response(debate)


@router.get("/{debate_id}", response_model=DebateResponse)
async def get_debate(debate_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Debate)
        .where(Debate.id == debate_id)
        .options(selectinload(Debate.participants).selectinload(DebateParticipant.agent))
    )
    debate = result.scalar_one_or_none()
    if not debate:
        raise HTTPException(status_code=404, detail="Debate not found")
    return _debate_to_response(debate)


@router.post("/{debate_id}/start", response_model=DebateResponse)
async def start_debate(debate_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Debate)
        .where(Debate.id == debate_id)
        .options(selectinload(Debate.participants).selectinload(DebateParticipant.agent))
    )
    debate = result.scalar_one_or_none()
    if not debate:
        raise HTTPException(status_code=404, detail="Debate not found")
    if debate.status != "scheduled":
        raise HTTPException(status_code=422, detail=f"Cannot start debate in '{debate.status}' status")

    import asyncio

    from sqlalchemy.sql import func

    from app.database import async_session
    from app.engine.debate_manager import DebateManager

    debate.status = "in_progress"
    debate.started_at = func.now()
    debate.current_turn = 0
    await db.commit()
    await db.refresh(debate)

    # Launch debate engine in background
    manager = DebateManager(debate_id=debate.id, db_factory=async_session)
    asyncio.create_task(manager.run())

    return _debate_to_response(debate)


def _debate_to_response(debate: Debate) -> DebateResponse:
    participants = []
    for p in debate.participants:
        agent = p.agent if hasattr(p, "agent") and p.agent else None
        participants.append(ParticipantResponse(
            agent_id=p.agent_id,
            agent_name=agent.name if agent else "Unknown",
            side=p.side,
            turn_order=p.turn_order,
        ))
    return DebateResponse(
        id=debate.id,
        topic=debate.topic,
        status=debate.status,
        format=debate.format,
        max_turns=debate.max_turns,
        current_turn=debate.current_turn,
        participants=participants,
        created_at=debate.created_at,
        started_at=debate.started_at,
        completed_at=debate.completed_at,
    )
