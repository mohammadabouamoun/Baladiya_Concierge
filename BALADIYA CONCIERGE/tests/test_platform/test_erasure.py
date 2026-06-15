"""T-043: Tenant erasure leaves zero orphan rows.

After DELETE /platform/tenants/{id} (via service layer):
- Zero rows in tenant_admins for that tenant_id
- Zero rows in tenants for that id
- Audit log records the erasure
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration

import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from api.domain.audit import AuditLog
from api.domain.tenant import Tenant, TenantAdmin, TenantCreate
from api.services import platform_service


@pytest.mark.asyncio
async def test_erase_removes_all_tenant_data(db_session: AsyncSession, platform_manager):
    email = f"erase-{uuid.uuid4()}@example.com"
    payload = TenantCreate(name="City Erase", admin_email=email, admin_password="pass")
    tenant = await platform_service.provision_tenant(db_session, payload, platform_manager.id)
    tenant_id = tenant.id

    await platform_service.erase_tenant(db_session, tenant_id, platform_manager.id)

    # Verify tenant row is gone
    tenant_result = await db_session.execute(
        select(Tenant).where(Tenant.id == tenant_id)
    )
    assert tenant_result.scalar_one_or_none() is None, "Tenant row must be deleted"

    # Verify no orphan admin rows (bypass RLS — use raw SQL with no session var)
    await db_session.execute(text("RESET app.current_tenant"))
    admin_result = await db_session.execute(
        text("SELECT COUNT(*) FROM tenant_admins WHERE tenant_id = :tid"),
        {"tid": str(tenant_id)},
    )
    count = admin_result.scalar()
    assert count == 0, f"Found {count} orphan tenant_admin rows after erasure"


@pytest.mark.asyncio
async def test_erase_writes_audit_log(db_session: AsyncSession, platform_manager):
    email = f"erase-audit-{uuid.uuid4()}@example.com"
    payload = TenantCreate(name="City Audit", admin_email=email, admin_password="pass")
    tenant = await platform_service.provision_tenant(db_session, payload, platform_manager.id)
    tenant_id = tenant.id

    await platform_service.erase_tenant(db_session, tenant_id, platform_manager.id)

    audit_result = await db_session.execute(
        select(AuditLog)
        .where(AuditLog.tenant_id == tenant_id)
        .where(AuditLog.action == "erase_tenant")
    )
    audit = audit_result.scalar_one_or_none()
    assert audit is not None, "Erasure must write an audit log entry"
    assert audit.actor_id == platform_manager.id
    assert audit.actor_role == "platform_manager"
