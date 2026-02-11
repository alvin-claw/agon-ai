from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AgentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    model_name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    endpoint_url: str | None = None


class AgentResponse(BaseModel):
    id: UUID
    name: str
    model_name: str
    description: str | None
    status: str
    is_builtin: bool
    endpoint_url: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
