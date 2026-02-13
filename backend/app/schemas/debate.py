from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


# Expected agent count per format
FORMAT_AGENT_COUNT = {"1v1": 2, "2v2": 4, "3v3": 6}
# Default max_turns per format (dev-friendly shorter games for team debates)
FORMAT_DEFAULT_MAX_TURNS = {"1v1": 10, "2v2": 8, "3v3": 6}


class DebateCreate(BaseModel):
    topic: str = Field(min_length=10, max_length=500)
    format: str = Field(default="1v1", pattern="^(1v1|2v2|3v3)$")
    agent_ids: list[UUID] = Field(min_length=2, max_length=6)
    max_turns: int | None = Field(default=None, ge=1, le=50)
    mode: str = Field(default="async", pattern="^(async|live)$")

    @model_validator(mode="after")
    def validate_format_agents(self):
        expected = FORMAT_AGENT_COUNT.get(self.format, 2)
        if len(self.agent_ids) != expected:
            raise ValueError(f"Format {self.format} requires exactly {expected} agents, got {len(self.agent_ids)}")
        if self.max_turns is None:
            self.max_turns = FORMAT_DEFAULT_MAX_TURNS.get(self.format, 10)
        return self


class ParticipantResponse(BaseModel):
    agent_id: UUID
    agent_name: str
    side: str
    team_id: str | None = None
    turn_order: int

    model_config = {"from_attributes": True}


class DebateResponse(BaseModel):
    id: UUID
    topic: str
    status: str
    format: str
    mode: str = "async"
    max_turns: int
    current_turn: int
    viewer_count: int = 0
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
    mode: str = "async"
    max_turns: int
    current_turn: int
    viewer_count: int = 0
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    model_config = {"from_attributes": True}
