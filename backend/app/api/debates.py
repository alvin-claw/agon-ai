import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.database import get_db
from app.models.agent import Agent
from app.models.debate import Debate, DebateParticipant
from app.schemas.debate import DebateCreate, DebateListResponse, DebateResponse, ParticipantResponse

router = APIRouter(prefix="/api/debates", tags=["debates"])
limiter = Limiter(key_func=get_remote_address)

# Keep strong references to background tasks to prevent GC
_background_tasks: set[asyncio.Task] = set()


@router.get("", response_model=list[DebateListResponse])
async def list_debates(
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Debate).where(Debate.is_sandbox == False).order_by(Debate.created_at.desc())
    if status:
        query = query.where(Debate.status == status)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("", response_model=DebateResponse, status_code=201)
@limiter.limit("10/minute")
async def create_debate(
    request: Request,
    body: DebateCreate,
    db: AsyncSession = Depends(get_db),
):
    # Validate agents exist
    agent_ids = body.agent_ids
    result = await db.execute(select(Agent).where(Agent.id.in_(agent_ids)))
    agents = result.scalars().all()
    if len(agents) != len(agent_ids):
        raise HTTPException(status_code=422, detail="One or more agents not found")

    # Verify external agents are active
    for ag in agents:
        if not ag.is_builtin and ag.status != "active":
            raise HTTPException(
                status_code=422,
                detail=f"Agent '{ag.name}' is not active (status: {ag.status}). Complete sandbox validation first.",
            )

    # Create debate with format-aware defaults
    debate = Debate(
        topic=body.topic,
        format=body.format,
        max_turns=body.max_turns,
        mode=body.mode,
    )
    db.add(debate)
    await db.flush()

    # Assign sides and team_id based on format
    # For NvN: first half is pro (team A), second half is con (team B)
    agent_count = len(agent_ids)
    half = agent_count // 2
    participants = []
    for i, agent_id in enumerate(agent_ids):
        side = "pro" if i < half else "con"
        team_id = "A" if i < half else "B"
        participant = DebateParticipant(
            debate_id=debate.id,
            agent_id=agent_id,
            side=side,
            team_id=team_id if body.format != "1v1" else None,
            turn_order=i,
        )
        db.add(participant)
        participants.append(participant)

    # Set interleaved round-robin turn_order: pro1, con1, pro2, con2, ...
    pro_participants = [p for p in participants if p.side == "pro"]
    con_participants = [p for p in participants if p.side == "con"]
    order = 0
    for pro_p, con_p in zip(pro_participants, con_participants):
        pro_p.turn_order = order
        order += 1
        con_p.turn_order = order
        order += 1

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
@limiter.limit("5/minute")
async def start_debate(request: Request, debate_id: UUID, db: AsyncSession = Depends(get_db)):
    from sqlalchemy.sql import func

    from app.database import async_session
    from app.engine.debate_manager import DebateManager

    # Use FOR UPDATE to prevent race condition on concurrent start requests
    result = await db.execute(
        select(Debate)
        .where(Debate.id == debate_id)
        .with_for_update()
        .options(selectinload(Debate.participants).selectinload(DebateParticipant.agent))
    )
    debate = result.scalar_one_or_none()
    if not debate:
        raise HTTPException(status_code=404, detail="Debate not found")
    if debate.status != "scheduled":
        raise HTTPException(status_code=422, detail=f"Cannot start debate in '{debate.status}' status")

    debate.status = "in_progress"
    debate.started_at = func.now()
    debate.current_turn = 0
    await db.commit()
    await db.refresh(debate)

    # Launch debate engine in background with strong reference
    manager = DebateManager(debate_id=debate.id, db_factory=async_session)
    task = asyncio.create_task(manager.run())
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    return _debate_to_response(debate)


def _debate_to_response(debate: Debate) -> DebateResponse:
    participants = []
    for p in debate.participants:
        agent = p.agent if hasattr(p, "agent") and p.agent else None
        participants.append(ParticipantResponse(
            agent_id=p.agent_id,
            agent_name=agent.name if agent else "Unknown",
            side=p.side,
            team_id=p.team_id,
            turn_order=p.turn_order,
        ))
    return DebateResponse(
        id=debate.id,
        topic=debate.topic,
        status=debate.status,
        format=debate.format,
        mode=debate.mode,
        max_turns=debate.max_turns,
        current_turn=debate.current_turn,
        viewer_count=debate.viewer_count,
        participants=participants,
        created_at=debate.created_at,
        started_at=debate.started_at,
        completed_at=debate.completed_at,
    )
