"""T-030: Direct asyncpg connection verifies RLS per-tenant isolation.

Sets the session variable to Tenant A → query returns only Tenant A rows.
Sets to Tenant B → returns only Tenant B rows.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.domain.tenant import TenantAdmin
from tests.conftest import TEST_DATABASE_URL


@pytest.mark.asyncio
async def test_rls_tenant_a_sees_only_own_rows(db_session: AsyncSession, tenant_a, tenant_b):
    tenant_a_obj, admin_a = tenant_a
    tenant_b_obj, admin_b = tenant_b

    # Drop superuser privilege so RLS is enforced (superusers bypass RLS in PG)
    await db_session.execute(text("SET LOCAL ROLE baladiya_app"))
    # Set session variable to Tenant A — UUID is hex+hyphen only, f-string is safe
    await db_session.execute(
        text(f"SET LOCAL app.current_tenant = '{tenant_a_obj.id}'")
    )

    result = await db_session.execute(text("SELECT id, tenant_id FROM tenant_admins"))
    rows = result.fetchall()

    tenant_ids_seen = {row.tenant_id for row in rows}
    assert tenant_b_obj.id not in tenant_ids_seen, (
        "RLS VIOLATION: Tenant A session can see Tenant B's admin rows"
    )
    assert tenant_a_obj.id in tenant_ids_seen, (
        "Tenant A should see its own rows"
    )


@pytest.mark.asyncio
async def test_rls_tenant_b_sees_only_own_rows(db_session: AsyncSession, tenant_a, tenant_b):
    tenant_a_obj, _ = tenant_a
    tenant_b_obj, _ = tenant_b

    await db_session.execute(text("SET LOCAL ROLE baladiya_app"))
    await db_session.execute(
        text(f"SET LOCAL app.current_tenant = '{tenant_b_obj.id}'")
    )

    result = await db_session.execute(text("SELECT id, tenant_id FROM tenant_admins"))
    rows = result.fetchall()

    tenant_ids_seen = {row.tenant_id for row in rows}
    assert tenant_a_obj.id not in tenant_ids_seen, (
        "RLS VIOLATION: Tenant B session can see Tenant A's admin rows"
    )
    assert tenant_b_obj.id in tenant_ids_seen


@pytest.mark.asyncio
async def test_rls_no_session_variable_returns_no_rows(db_session: AsyncSession, tenant_a, tenant_b):
    """Without the session variable, RLS should block all rows (NULL != uuid)."""
    await db_session.execute(text("SET LOCAL ROLE baladiya_app"))
    await db_session.execute(text("RESET app.current_tenant"))

    result = await db_session.execute(text("SELECT id FROM tenant_admins"))
    rows = result.fetchall()
    assert rows == [], (
        "Without app.current_tenant set, RLS should return zero rows"
    )
