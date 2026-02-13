from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class TopicCreate(BaseModel):
    title: str = Field(min_length=5, max_length=500)
    description: str | None = None
    agent_ids: list[UUID] = Field(min_length=2, max_length=10)
    duration_minutes: int = Field(default=60, ge=1, le=1440)
    max_comments_per_agent: int = Field(default=10, ge=1, le=50)
    polling_interval_seconds: int = Field(default=30, ge=10, le=300)


class TopicParticipantResponse(BaseModel):
    agent_id: UUID
    agent_name: str
    max_comments: int
    comment_count: int

    model_config = {"from_attributes": True}


class CommentReferenceSchema(BaseModel):
    comment_id: str
    type: str  # "agree" | "rebut"
    quote: str


class CitationSchema(BaseModel):
    url: str
    title: str
    quote: str


class CommentResponse(BaseModel):
    id: UUID
    topic_id: UUID
    agent_id: UUID
    agent_name: str
    content: str
    references: list[CommentReferenceSchema] = []
    citations: list[CitationSchema] = []
    stance: str | None = None
    token_count: int | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class TopicResponse(BaseModel):
    id: UUID
    title: str
    description: str | None
    status: str
    duration_minutes: int
    max_comments_per_agent: int
    polling_interval_seconds: int
    participants: list[TopicParticipantResponse] = []
    created_at: datetime
    started_at: datetime | None
    closes_at: datetime | None
    closed_at: datetime | None

    model_config = {"from_attributes": True}


class TopicListResponse(BaseModel):
    id: UUID
    title: str
    description: str | None
    status: str
    duration_minutes: int
    max_comments_per_agent: int
    participant_count: int = 0
    comment_count: int = 0
    created_at: datetime
    started_at: datetime | None
    closes_at: datetime | None
    closed_at: datetime | None

    model_config = {"from_attributes": True}
