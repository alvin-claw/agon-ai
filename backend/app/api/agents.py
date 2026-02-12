import hashlib
import secrets
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_developer, optional_developer
from app.database import get_db
from app.models.agent import Agent
from app.models.debate import Debate, DebateParticipant
from app.models.developer import Developer
from app.schemas.agent import AgentCreateExternal, AgentResponse
from app.schemas.developer import ApiKeyResponse

router = APIRouter(prefix="/api/agents", tags=["agents"])


def _generate_api_key() -> tuple[str, str]:
    """Generate a plaintext API key and its SHA-256 hash."""
    raw_key = secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    return raw_key, key_hash


@router.get("", response_model=list[AgentResponse])
async def list_agents(
    status: str | None = None,
    is_builtin: bool | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Agent)
    if status:
        query = query.where(Agent.status == status)
    if is_builtin is not None:
        query = query.where(Agent.is_builtin == is_builtin)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("", status_code=201)
async def register_agent(
    body: AgentCreateExternal,
    developer: Developer = Depends(get_current_developer),
    db: AsyncSession = Depends(get_db),
):
    raw_key, key_hash = _generate_api_key()
    agent = Agent(
        name=body.name,
        model_name=body.model_name,
        description=body.description,
        endpoint_url=body.endpoint_url,
        developer_id=developer.id,
        api_key_hash=key_hash,
        status="registered",
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return {
        "agent": AgentResponse.model_validate(agent),
        "api_key": raw_key,
    }


@router.get("/me", response_model=list[AgentResponse])
async def list_my_agents(
    developer: Developer = Depends(get_current_developer),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Agent).where(Agent.developer_id == developer.id)
    )
    return result.scalars().all()


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.delete("/{agent_id}", status_code=204)
async def delete_agent(
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
    await db.delete(agent)
    await db.commit()


@router.post("/{agent_id}/regenerate-key", response_model=ApiKeyResponse)
async def regenerate_key(
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
    raw_key, key_hash = _generate_api_key()
    agent.api_key_hash = key_hash
    await db.commit()
    return ApiKeyResponse(api_key=raw_key, agent_id=agent.id)
