from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.domain.widget import Widget
from api.repositories.base import BaseRepository


class WidgetRepository(BaseRepository[Widget]):
    """Tenant-scoped widget repository — for authenticated tenant admin operations."""

    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID) -> None:
        super().__init__(session, tenant_id, Widget)

    async def list_active(self) -> list[Widget]:
        stmt = self._base_query().filter(Widget.is_active == True)  # noqa: E712
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class PlatformWidgetRepository:
    """No-tenant-scope repository used at token exchange time (origin is unknown yet).

    Intentionally does NOT inherit BaseRepository — mirrors PlatformTenantRepository
    pattern. Only performs a lookup by widget id; never writes.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_widget_id(self, widget_id: uuid.UUID) -> Widget | None:
        result = await self._session.execute(
            select(Widget).filter(Widget.id == widget_id, Widget.is_active == True)  # noqa: E712
        )
        return result.scalar_one_or_none()
