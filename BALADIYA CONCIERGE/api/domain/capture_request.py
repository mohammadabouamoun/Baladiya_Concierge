"""Domain: CaptureRequest and EscalationTicket — SQLAlchemy models + Pydantic schemas."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, field_validator
from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from api.infra.db import Base

CaptureStatus = Literal["open", "escalated", "resolved"]
EscalationStatus = Literal["open", "closed"]
CaptureIntent = Literal["report", "question", "human"]


# ── SQLAlchemy ORM models ──────────────────────────────────────────────────

class CaptureRequest(Base):
    __tablename__ = "capture_requests"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact: Mapped[str | None] = mapped_column(String(320), nullable=True)
    location: Mapped[str | None] = mapped_column(Text, nullable=True)
    intent: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class EscalationTicket(Base):
    __tablename__ = "escalation_tickets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    capture_request_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("capture_requests.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


# ── Pydantic schemas ───────────────────────────────────────────────────────

class CaptureRequestCreate(BaseModel):
    """Schema for creating a capture request via the agent tool.

    tenant_id is NEVER accepted here — it comes from the JWT token only.
    """
    intent: CaptureIntent
    description: str
    name: str | None = None
    contact: str | None = None
    location: str | None = None

    @field_validator("description")
    @classmethod
    def description_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("description cannot be empty")
        return v

    @field_validator("intent")
    @classmethod
    def valid_intent(cls, v: str) -> str:
        if v not in ("report", "question", "human"):
            raise ValueError(f"invalid intent: {v!r}")
        return v


class CaptureRequestRead(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    session_id: str
    name: str | None
    contact: str | None
    location: str | None
    intent: str
    description: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class EscalationTicketRead(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    capture_request_id: uuid.UUID | None
    reason: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
