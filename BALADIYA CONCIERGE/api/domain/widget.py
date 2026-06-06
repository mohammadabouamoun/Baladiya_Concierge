from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel
from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from api.infra.db import Base


class Widget(Base):
    __tablename__ = "widgets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    allowed_origins: Mapped[list] = mapped_column(
        ARRAY(String), nullable=False, default=list
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class WidgetCreate(BaseModel):
    allowed_origins: list[str]


class WidgetRead(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    allowed_origins: list[str]
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class WidgetUpdate(BaseModel):
    allowed_origins: Optional[list[str]] = None
    is_active: Optional[bool] = None


class WidgetTokenPayload(BaseModel):
    """JWT payload issued to the widget loader."""
    tenant_id: uuid.UUID
    widget_id: uuid.UUID
    jti: str
    exp: int
    iat: int


class WidgetConfig(BaseModel):
    """Returned by GET /widget/config; drawn from tenant.settings.widget_config."""
    greeting_en: str = "Hello! How can I help you today?"
    greeting_ar: str = ""
    theme_color: str = "#1d4ed8"
    logo_url: str = ""
    # Phase 7: tool filter and persona are configurable per widget
    enabled_tools: list[str] = ["rag_search", "capture_request", "escalate"]
    persona: str = ""
