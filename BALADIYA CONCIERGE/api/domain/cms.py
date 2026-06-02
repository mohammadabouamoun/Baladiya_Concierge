"""CMS domain: SQLAlchemy models + Pydantic schemas for CMS entries and RAG chunks."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from api.infra.db import Base

EmbeddingStatus = Literal["pending", "done", "failed"]
CmsLang = Literal["en", "ar"]
CmsCategory = Literal[
    "roads", "water", "electricity", "waste", "permits", "taxes", "environment", "general"
]


# ── SQLAlchemy ORM models ──────────────────────────────────────────────────

class CmsEntry(Base):
    __tablename__ = "cms_entries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="general")
    lang: Mapped[str] = mapped_column(String(10), nullable=False, default="en")
    embedding_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CmsChunk(Base):
    __tablename__ = "cms_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cms_entries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    # embedding stored as vector(1536) — column added by migration via raw SQL;
    # SQLAlchemy treats it as opaque text here. Use raw SQL for similarity search.
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)


# ── Pydantic schemas ───────────────────────────────────────────────────────

class CmsEntryCreate(BaseModel):
    title: str
    body: str
    category: str = "general"
    lang: str = "en"


class CmsEntryUpdate(BaseModel):
    title: str | None = None
    body: str | None = None
    category: str | None = None
    lang: str | None = None


class CmsEntryRead(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    title: str
    body: str
    category: str
    lang: str
    embedding_status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RagSearchResult(BaseModel):
    chunk_id: uuid.UUID
    entry_id: uuid.UUID
    chunk_text: str
    source_title: str
    lang: str
    similarity: float
    category: str
