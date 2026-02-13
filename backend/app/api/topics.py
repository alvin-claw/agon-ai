import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.database import get_db
from app.models.agent import Agent
from app.models.reaction import Reaction
from app.models.topic import Comment, Topic, TopicParticipant
from app.schemas.topic import (
    CommentResponse,
    TopicCreate,
    TopicListResponse,
    TopicParticipantResponse,
    TopicResponse,
)
from app.schemas.turn import ReactionCreate, ReactionResponse

router = APIRouter(prefix="/api/topics", tags=["topics"])
limiter = Limiter(key_func=get_remote_address)

# Keep strong references to background tasks
_background_tasks: set[asyncio.Task] = set()


@router.get("", response_model=list[TopicListResponse])
async def list_topics(
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(
            Topic,
            func.count(TopicParticipant.id.distinct()).label("participant_count"),
            func.count(Comment.id.distinct()).label("comment_count"),
        )
        .outerjoin(TopicParticipant, Topic.id == TopicParticipant.topic_id)
        .outerjoin(Comment, Topic.id == Comment.topic_id)
        .group_by(Topic.id)
        .order_by(Topic.created_at.desc())
    )
    if status:
        query = query.where(Topic.status == status)

    result = await db.execute(query)
    rows = result.all()

    return [
        TopicListResponse(
            id=topic.id,
            title=topic.title,
            description=topic.description,
            status=topic.status,
            duration_minutes=topic.duration_minutes,
            max_comments_per_agent=topic.max_comments_per_agent,
            participant_count=p_count,
            comment_count=c_count,
            created_at=topic.created_at,
            started_at=topic.started_at,
            closes_at=topic.closes_at,
            closed_at=topic.closed_at,
        )
        for topic, p_count, c_count in rows
    ]


@router.post("", response_model=TopicResponse, status_code=201)
@limiter.limit("10/minute")
async def create_topic(
    request: Request,
    body: TopicCreate,
    db: AsyncSession = Depends(get_db),
):
    # Validate agents exist
    unique_ids = list(set(body.agent_ids))
    result = await db.execute(select(Agent).where(Agent.id.in_(unique_ids)))
    agents = result.scalars().all()
    if len(agents) != len(unique_ids):
        raise HTTPException(status_code=422, detail="One or more agents not found")

    # Verify external agents are active
    for ag in agents:
        if not ag.is_builtin and ag.status != "active":
            raise HTTPException(
                status_code=422,
                detail=f"Agent '{ag.name}' is not active (status: {ag.status})",
            )

    topic = Topic(
        title=body.title,
        description=body.description,
        duration_minutes=body.duration_minutes,
        max_comments_per_agent=body.max_comments_per_agent,
        polling_interval_seconds=body.polling_interval_seconds,
        status="scheduled",
    )
    db.add(topic)
    await db.flush()

    for agent_id in body.agent_ids:
        participant = TopicParticipant(
            topic_id=topic.id,
            agent_id=agent_id,
            max_comments=body.max_comments_per_agent,
        )
        db.add(participant)

    await db.commit()

    # Reload with relationships
    result = await db.execute(
        select(Topic)
        .where(Topic.id == topic.id)
        .options(selectinload(Topic.participants).selectinload(TopicParticipant.agent))
    )
    topic = result.scalar_one()
    return _topic_to_response(topic)


@router.get("/{topic_id}", response_model=TopicResponse)
async def get_topic(topic_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Topic)
        .where(Topic.id == topic_id)
        .options(selectinload(Topic.participants).selectinload(TopicParticipant.agent))
    )
    topic = result.scalar_one_or_none()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    return _topic_to_response(topic)


@router.post("/{topic_id}/start", response_model=TopicResponse)
@limiter.limit("5/minute")
async def start_topic(request: Request, topic_id: UUID, db: AsyncSession = Depends(get_db)):
    from datetime import datetime, timedelta, timezone

    from app.database import async_session
    from app.engine.comment_orchestrator import CommentOrchestrator

    result = await db.execute(
        select(Topic)
        .where(Topic.id == topic_id)
        .with_for_update()
        .options(selectinload(Topic.participants).selectinload(TopicParticipant.agent))
    )
    topic = result.scalar_one_or_none()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    if topic.status != "scheduled":
        raise HTTPException(status_code=422, detail=f"Cannot start topic in '{topic.status}' status")

    now = datetime.now(timezone.utc)
    topic.status = "open"
    topic.started_at = now
    topic.closes_at = now + timedelta(minutes=topic.duration_minutes)
    await db.commit()
    await db.refresh(topic)

    # Launch orchestrator in background
    orchestrator = CommentOrchestrator(topic_id=topic.id, db_factory=async_session)
    task = asyncio.create_task(orchestrator.run())
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    # Reload for response
    result = await db.execute(
        select(Topic)
        .where(Topic.id == topic.id)
        .options(selectinload(Topic.participants).selectinload(TopicParticipant.agent))
    )
    topic = result.scalar_one()
    return _topic_to_response(topic)


@router.get("/{topic_id}/comments", response_model=list[CommentResponse])
async def get_topic_comments(topic_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Comment)
        .where(Comment.topic_id == topic_id)
        .options(selectinload(Comment.agent))
        .order_by(Comment.created_at)
    )
    comments = result.scalars().all()
    return [
        CommentResponse(
            id=c.id,
            topic_id=c.topic_id,
            agent_id=c.agent_id,
            agent_name=c.agent.name if c.agent else "Unknown",
            content=c.content,
            references=c.references_ or [],
            citations=c.citations or [],
            stance=c.stance,
            token_count=c.token_count,
            created_at=c.created_at,
        )
        for c in comments
    ]


@router.post(
    "/{topic_id}/comments/{comment_id}/reactions",
    response_model=ReactionResponse,
    status_code=201,
)
async def add_comment_reaction(
    topic_id: UUID,
    comment_id: UUID,
    body: ReactionCreate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Comment).where(Comment.id == comment_id, Comment.topic_id == topic_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Comment not found")

    reaction = Reaction(
        comment_id=comment_id,
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
    "/{topic_id}/reactions",
    response_model=dict[str, dict[str, int]],
)
async def get_topic_reaction_counts(
    topic_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get reaction counts grouped by comment_id and type."""
    result = await db.execute(
        select(
            Reaction.comment_id,
            Reaction.type,
            func.count().label("count"),
        )
        .join(Comment, Comment.id == Reaction.comment_id)
        .where(Comment.topic_id == topic_id)
        .group_by(Reaction.comment_id, Reaction.type)
    )
    counts: dict[str, dict[str, int]] = {}
    for row in result.all():
        cid = str(row.comment_id)
        if cid not in counts:
            counts[cid] = {}
        counts[cid][row.type] = row.count
    return counts


@router.get(
    "/{topic_id}/factchecks",
    response_model=list,
)
async def get_topic_factchecks(
    topic_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get all factcheck results for a topic."""
    from app.models.factcheck import FactcheckRequest, FactcheckResult

    result = await db.execute(
        select(FactcheckResult)
        .join(FactcheckRequest, FactcheckResult.request_id == FactcheckRequest.id)
        .where(FactcheckRequest.topic_id == topic_id)
        .order_by(FactcheckResult.created_at)
    )
    return result.scalars().all()


def _topic_to_response(topic: Topic) -> TopicResponse:
    participants = []
    for p in topic.participants:
        agent = p.agent if hasattr(p, "agent") and p.agent else None
        participants.append(TopicParticipantResponse(
            agent_id=p.agent_id,
            agent_name=agent.name if agent else "Unknown",
            max_comments=p.max_comments,
            comment_count=p.comment_count,
        ))
    return TopicResponse(
        id=topic.id,
        title=topic.title,
        description=topic.description,
        status=topic.status,
        duration_minutes=topic.duration_minutes,
        max_comments_per_agent=topic.max_comments_per_agent,
        polling_interval_seconds=topic.polling_interval_seconds,
        participants=participants,
        created_at=topic.created_at,
        started_at=topic.started_at,
        closes_at=topic.closes_at,
        closed_at=topic.closed_at,
    )
