from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CitationSchema(BaseModel):
    url: str
    title: str
    quote: str


class TurnSubmission(BaseModel):
    stance: str = Field(pattern="^(pro|con|modified)$")
    claim: str = Field(max_length=200)
    argument: str
    citations: list[CitationSchema] = Field(min_length=1)
    rebuttal_target: UUID | None = None


class TurnResponse(BaseModel):
    id: UUID
    debate_id: UUID
    agent_id: UUID
    turn_number: int
    status: str
    stance: str | None
    claim: str | None
    argument: str | None
    citations: list[dict] | None
    rebuttal_target_id: UUID | None
    team_id: str | None = None
    support_target_id: UUID | None = None
    token_count: int | None
    submitted_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ReactionCreate(BaseModel):
    type: str = Field(pattern="^(like|logic_error)$")
    session_id: str = Field(min_length=1, max_length=100)


class ReactionResponse(BaseModel):
    id: UUID
    turn_id: UUID
    type: str
    session_id: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AnalysisResponse(BaseModel):
    id: UUID
    debate_id: UUID
    sentiment_data: list | dict | None
    citation_stats: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}
