import uuid

from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base


class Developer(Base):
    __tablename__ = "developers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    github_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    github_login: Mapped[str] = mapped_column(String(100), nullable=False)
    github_avatar_url: Mapped[str | None] = mapped_column(String(500))
    email: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[str] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at: Mapped[str] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())


class SandboxResult(Base):
    __tablename__ = "sandbox_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    checks: Mapped[list | None] = mapped_column(JSONB, default=list)
    debate_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("debates.id", ondelete="SET NULL"))
    started_at: Mapped[str] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    completed_at: Mapped[str | None] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[str] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    agent: Mapped["Agent"] = relationship()


from app.models.agent import Agent  # noqa: E402
