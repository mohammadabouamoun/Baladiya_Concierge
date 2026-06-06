"""Widget service — tenant-scoped widget lifecycle operations.

Keeps ORM mutations out of the router layer (constitution §Engineering Standards: layering).
"""
from __future__ import annotations

import uuid

import structlog
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.domain.widget import Widget, WidgetCreate, WidgetUpdate
from api.repositories.widget_repo import WidgetRepository

logger = structlog.get_logger(__name__)


async def create_widget(
    body: WidgetCreate,
    tenant_id: uuid.UUID,
    db: AsyncSession,
) -> Widget:
    widget = Widget(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        allowed_origins=body.allowed_origins,
        is_active=True,
    )
    db.add(widget)
    await db.flush()
    await db.commit()
    logger.info("widget.created", widget_id=str(widget.id), tenant_id=str(tenant_id))
    return widget


async def update_widget(
    widget_id: uuid.UUID,
    body: WidgetUpdate,
    tenant_id: uuid.UUID,
    db: AsyncSession,
) -> Widget:
    repo = WidgetRepository(db, tenant_id)
    widget = await repo.get(widget_id)
    if widget is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Widget not found")
    if body.allowed_origins is not None:
        widget.allowed_origins = body.allowed_origins
    if body.is_active is not None:
        widget.is_active = body.is_active
    await db.commit()
    logger.info("widget.updated", widget_id=str(widget_id), tenant_id=str(tenant_id))
    return widget
