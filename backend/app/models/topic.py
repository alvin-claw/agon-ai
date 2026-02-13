import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="scheduled")
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    max_comments_per_agent: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    polling_interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    created_at: Mapped[str] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    started_at: Mapped[str | None] = mapped_column(TIMESTAMP(timezone=True))
    closes_at: Mapped[str | None] = mapped_column(TIMESTAMP(timezone=True))
    closed_at: Mapped[str | None] = mapped_column(TIMESTAMP(timezone=True))

    participants: Mapped[list["TopicParticipant"]] = relationship(back_populates="topic", cascade="all, delete-orphan")
    comments: Mapped[list["Comment"]] = relationship(back_populates="topic", cascade="all, delete-orphan")


class TopicParticipant(Base):
    __tablename__ = "topic_participants"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    topic_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("topics.id", ondelete="CASCADE"), nullable=False)
    agent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    max_comments: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    comment_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    joined_at: Mapped[str] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    topic: Mapped["Topic"] = relationship(back_populates="participants")
    agent: Mapped["Agent"] = relationship()


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    topic_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("topics.id", ondelete="CASCADE"), nullable=False)
    agent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    references_: Mapped[list | None] = mapped_column("references_", JSONB, default=list)
    citations: Mapped[list | None] = mapped_column(JSONB, default=list)
    stance: Mapped[str | None] = mapped_column(String(20))
    token_count: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[str] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    topic: Mapped["Topic"] = relationship(back_populates="comments")
    agent: Mapped["Agent"] = relationship()


from app.models.agent import Agent  # noqa: E402
