from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.agent import Agent
from app.schemas.agent import AgentCreate, AgentResponse

router = APIRouter(prefix="/api/agents", tags=["agents"])


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


@router.post("", response_model=AgentResponse, status_code=201)
async def register_agent(
    body: AgentCreate,
    db: AsyncSession = Depends(get_db),
):
    agent = Agent(
        name=body.name,
        model_name=body.model_name,
        description=body.description,
        endpoint_url=body.endpoint_url,
        status="registered",
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent
