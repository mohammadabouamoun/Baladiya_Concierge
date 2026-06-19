"""T-025: Platform provisioning tests.

- Provision two tenants
- Verify isolation: each tenant admin sees only its own data
- Verify idempotency: second call with same admin_email returns existing tenant
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from api.domain.tenant import TenantCreate
from api.services import platform_service


@pytest.mark.asyncio
async def test_provision_creates_tenant_and_admin(
    db_session: AsyncSession, platform_manager
):
    payload = TenantCreate(
        name="Test City",
        admin_email=f"admin-{uuid.uuid4()}@example.com",
        admin_password="securepass",
        plan="standard",
    )
    tenant = await platform_service.provision_tenant(db_session, payload, platform_manager.id)

    assert tenant.id is not None
    assert tenant.name == "Test City"
    assert tenant.status == "active"


@pytest.mark.asyncio
async def test_provision_idempotent(db_session: AsyncSession, platform_manager):
    email = f"idempotent-{uuid.uuid4()}@example.com"
    payload = TenantCreate(name="City 1", admin_email=email, admin_password="pass")

    tenant1 = await platform_service.provision_tenant(db_session, payload, platform_manager.id)
    tenant2 = await platform_service.provision_tenant(db_session, payload, platform_manager.id)

    assert tenant1.id == tenant2.id


@pytest.mark.asyncio
async def test_tenant_a_cannot_see_tenant_b_data(
    db_session: AsyncSession, platform_manager, tenant_a, tenant_b
):
    tenant_a_obj, admin_a = tenant_a
    tenant_b_obj, admin_b = tenant_b

    from api.repositories.tenant_repo import TenantAdminRepository
    from sqlalchemy import text

    # Scope session to Tenant A — UUID is hex+hyphen only, f-string is safe
    await db_session.execute(
        text(f"SET LOCAL app.current_tenant = '{tenant_a_obj.id}'")
    )

    repo_a = TenantAdminRepository(db_session, tenant_a_obj.id)
    admins = await repo_a.list()

    admin_ids = {a.id for a in admins}
    assert admin_a.id in admin_ids, "Tenant A should see its own admin"
    assert admin_b.id not in admin_ids, "Tenant A must not see Tenant B's admin"


@pytest.mark.asyncio
async def test_suspend_tenant(db_session: AsyncSession, platform_manager):
    email = f"suspend-{uuid.uuid4()}@example.com"
    payload = TenantCreate(name="City Suspend", admin_email=email, admin_password="pass")
    tenant = await platform_service.provision_tenant(db_session, payload, platform_manager.id)

    suspended = await platform_service.suspend_tenant(db_session, tenant.id, platform_manager.id)
    assert suspended.status == "suspended"
