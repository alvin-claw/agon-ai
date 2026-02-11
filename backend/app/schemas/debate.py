from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class DebateCreate(BaseModel):
    topic: str = Field(min_length=10, max_length=500)
    format: str = Field(default="1v1", pattern="^(1v1|2v2|3v3)$")
    agent_ids: list[UUID] = Field(min_length=2, max_length=6)
    max_turns: int = Field(default=10, ge=1, le=50)


class ParticipantResponse(BaseModel):
    agent_id: UUID
    agent_name: str
    side: str
    turn_order: int

    model_config = {"from_attributes": True}


class DebateResponse(BaseModel):
    id: UUID
    topic: str
    status: str
    format: str
    max_turns: int
    current_turn: int
    participants: list[ParticipantResponse] = []
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class DebateListResponse(BaseModel):
    id: UUID
    topic: str
    status: str
    format: str
    max_turns: int
    current_turn: int
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    model_config = {"from_attributes": True}
