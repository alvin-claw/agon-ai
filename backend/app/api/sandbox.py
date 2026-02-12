import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_developer
from app.database import async_session, get_db
from app.models.agent import Agent
from app.models.developer import Developer, SandboxResult
from app.schemas.developer import SandboxResultResponse

router = APIRouter(prefix="/api/agents", tags=["sandbox"])

_background_tasks: set[asyncio.Task] = set()


@router.post("/{agent_id}/sandbox", status_code=202)
async def start_sandbox(
    agent_id: UUID,
    developer: Developer = Depends(get_current_developer),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    if agent.developer_id != developer.id:
        raise HTTPException(status_code=403, detail="Not the owner of this agent")
    if agent.status not in ("registered", "failed"):
        raise HTTPException(status_code=422, detail=f"Agent status '{agent.status}' cannot run sandbox")
    if not agent.endpoint_url:
        raise HTTPException(status_code=422, detail="Agent has no endpoint_url configured")

    from app.engine.sandbox_manager import SandboxManager

    manager = SandboxManager(agent_id=agent_id, db_factory=async_session)
    task = asyncio.create_task(manager.run())
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    return {"status": "started", "agent_id": str(agent_id)}


@router.get("/{agent_id}/sandbox/results", response_model=list[SandboxResultResponse])
async def list_sandbox_results(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SandboxResult)
        .where(SandboxResult.agent_id == agent_id)
        .order_by(SandboxResult.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{agent_id}/sandbox/latest", response_model=SandboxResultResponse)
async def get_latest_sandbox_result(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SandboxResult)
        .where(SandboxResult.agent_id == agent_id)
        .order_by(SandboxResult.created_at.desc())
        .limit(1)
    )
    sr = result.scalar_one_or_none()
    if not sr:
        raise HTTPException(status_code=404, detail="No sandbox results found")
    return sr
