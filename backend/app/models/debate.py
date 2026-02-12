import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base


class Debate(Base):
    __tablename__ = "debates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    topic: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="scheduled")
    format: Mapped[str] = mapped_column(String(10), nullable=False, default="1v1")
    max_turns: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    current_turn: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    turn_timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=120)
    turn_cooldown_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    created_at: Mapped[str] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    started_at: Mapped[str | None] = mapped_column(TIMESTAMP(timezone=True))
    completed_at: Mapped[str | None] = mapped_column(TIMESTAMP(timezone=True))

    participants: Mapped[list["DebateParticipant"]] = relationship(back_populates="debate", cascade="all, delete-orphan")
    turns: Mapped[list["Turn"]] = relationship(back_populates="debate", cascade="all, delete-orphan")


class DebateParticipant(Base):
    __tablename__ = "debate_participants"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    debate_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("debates.id", ondelete="CASCADE"), nullable=False)
    agent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    side: Mapped[str] = mapped_column(String(10), nullable=False)
    turn_order: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[str] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    debate: Mapped["Debate"] = relationship(back_populates="participants")
    agent: Mapped["Agent"] = relationship()


class Turn(Base):
    __tablename__ = "turns"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    debate_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("debates.id", ondelete="CASCADE"), nullable=False)
    agent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    turn_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    stance: Mapped[str | None] = mapped_column(String(20))
    claim: Mapped[str | None] = mapped_column(Text)
    argument: Mapped[str | None] = mapped_column(Text)
    citations: Mapped[list | None] = mapped_column(JSONB, default=list)
    rebuttal_target_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("turns.id"))
    token_count: Mapped[int | None] = mapped_column(Integer)
    submitted_at: Mapped[str | None] = mapped_column(TIMESTAMP(timezone=True))
    validated_at: Mapped[str | None] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[str] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    debate: Mapped["Debate"] = relationship(back_populates="turns")
    agent: Mapped["Agent"] = relationship()


from app.models.agent import Agent  # noqa: E402
