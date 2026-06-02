from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.domain.tenant import Tenant, TenantAdmin
from api.repositories.base import BaseRepository


class TenantAdminRepository(BaseRepository[TenantAdmin]):
    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID) -> None:
        super().__init__(session, tenant_id, TenantAdmin)

    async def get_by_email(self, email: str) -> TenantAdmin | None:
        stmt = self._base_query().filter(TenantAdmin.email == email)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()


class PlatformTenantRepository:
    """Used by Platform Manager routes — no tenant scoping needed here.

    Platform Manager queries cross tenant boundaries by design (read-only metadata only).
    This class intentionally does NOT inherit BaseRepository.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, tenant_id: uuid.UUID) -> Tenant | None:
        result = await self._session.execute(
            select(Tenant).filter(Tenant.id == tenant_id)
        )
        return result.scalar_one_or_none()

    async def get_by_admin_email(self, email: str) -> Tenant | None:
        stmt = (
            select(Tenant)
            .join(TenantAdmin, TenantAdmin.tenant_id == Tenant.id)
            .filter(TenantAdmin.email == email)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(self) -> list[Tenant]:
        result = await self._session.execute(select(Tenant))
        return list(result.scalars().all())

    async def add(self, tenant: Tenant) -> Tenant:
        self._session.add(tenant)
        await self._session.flush()
        return tenant

    async def add_admin(self, admin: TenantAdmin) -> TenantAdmin:
        self._session.add(admin)
        await self._session.flush()
        return admin
