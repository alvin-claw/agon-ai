from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class AgentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    model_name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    endpoint_url: str | None = None


class AgentCreateExternal(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    model_name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    endpoint_url: str

    @field_validator("endpoint_url")
    @classmethod
    def validate_https(cls, v: str) -> str:
        if not v.startswith("https://"):
            raise ValueError("endpoint_url must start with https://")
        return v


class AgentResponse(BaseModel):
    id: UUID
    name: str
    model_name: str
    description: str | None
    status: str
    is_builtin: bool
    endpoint_url: str | None
    developer_id: UUID | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
