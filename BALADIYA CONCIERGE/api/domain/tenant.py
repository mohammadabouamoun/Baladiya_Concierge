from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr
from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.infra.db import Base

TenantStatus = Literal["active", "suspended", "erased"]
UserRole = Literal["platform_manager", "tenant_admin", "visitor"]


# ── SQLAlchemy ORM models ──────────────────────────────────────────────────

class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    plan: Mapped[str] = mapped_column(String(50), nullable=False, default="standard")
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )
    settings: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    admins: Mapped[list[TenantAdmin]] = relationship(
        "TenantAdmin", back_populates="tenant", cascade="all, delete-orphan"
    )


class TenantAdmin(Base):
    __tablename__ = "tenant_admins"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    hashed_password: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(30), nullable=False, default="tenant_admin")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    tenant: Mapped[Tenant] = relationship("Tenant", back_populates="admins")


class PlatformManager(Base):
    __tablename__ = "platform_managers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    hashed_password: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(30), nullable=False, default="platform_manager")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


# ── Pydantic schemas ───────────────────────────────────────────────────────

class TenantCreate(BaseModel):
    name: str
    admin_email: EmailStr
    admin_password: str
    plan: str = "standard"


class TenantRead(BaseModel):
    id: uuid.UUID
    name: str
    plan: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TenantAdminRead(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    email: str
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}
