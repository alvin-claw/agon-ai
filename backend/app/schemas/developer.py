from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class DeveloperResponse(BaseModel):
    id: UUID
    github_login: str
    github_avatar_url: str | None
    email: str | None

    model_config = {"from_attributes": True}


class SandboxCheckResponse(BaseModel):
    check: str
    passed: bool
    detail: str | None = None


class SandboxResultResponse(BaseModel):
    id: UUID
    agent_id: UUID
    status: str
    checks: list[SandboxCheckResponse]
    started_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class ApiKeyResponse(BaseModel):
    api_key: str
    agent_id: UUID
