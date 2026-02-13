from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class FactcheckCreate(BaseModel):
    session_id: str = Field(min_length=1, max_length=100)


class FactcheckRequestResponse(BaseModel):
    id: UUID
    turn_id: UUID
    debate_id: UUID
    claim_hash: str
    request_count: int
    status: str
    session_id: str
    created_at: datetime

    model_config = {"from_attributes": True}


class FactcheckResultResponse(BaseModel):
    id: UUID
    request_id: UUID
    turn_id: UUID
    verdict: str
    citation_url: str | None
    citation_accessible: bool | None
    content_match: bool | None
    logic_valid: bool | None
    details: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}
