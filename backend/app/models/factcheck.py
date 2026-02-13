import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class FactcheckRequest(Base):
    __tablename__ = "factcheck_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    turn_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("turns.id", ondelete="CASCADE"), nullable=False)
    debate_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("debates.id", ondelete="CASCADE"), nullable=False)
    claim_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    request_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    session_id: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[str] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())


class FactcheckResult(Base):
    __tablename__ = "factcheck_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("factcheck_requests.id", ondelete="CASCADE"), nullable=False, unique=True)
    turn_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("turns.id", ondelete="CASCADE"), nullable=False)
    verdict: Mapped[str] = mapped_column(String(30), nullable=False)
    citation_url: Mapped[str | None] = mapped_column(Text)
    citation_accessible: Mapped[bool | None] = mapped_column(Boolean)
    content_match: Mapped[bool | None] = mapped_column(Boolean)
    logic_valid: Mapped[bool | None] = mapped_column(Boolean)
    details: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[str] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
