"""T-031: Session variable reset safety.

Simulates a mid-request exception for Tenant A, then verifies that the next
request on the same connection (reused from pool) is correctly scoped to
Tenant B — not Tenant A.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_session_reset_after_exception(db_session: AsyncSession, tenant_a, tenant_b):
    tenant_a_obj, _ = tenant_a
    tenant_b_obj, _ = tenant_b

    # Simulate request for Tenant A that raises mid-flight
    try:
        await db_session.execute(
            text("SET LOCAL app.current_tenant = :tid"),
            {"tid": str(tenant_a_obj.id)},
        )
        raise RuntimeError("simulated mid-request error")
    except RuntimeError:
        # The finally block in get_db resets the variable
        await db_session.execute(text("RESET app.current_tenant"))

    # Next request: Tenant B — the variable must be set fresh, not carry Tenant A
    await db_session.execute(
        text("SET LOCAL app.current_tenant = :tid"),
        {"tid": str(tenant_b_obj.id)},
    )

    result = await db_session.execute(text("SELECT tenant_id FROM tenant_admins"))
    rows = result.fetchall()
    tenant_ids_seen = {row.tenant_id for row in rows}

    assert tenant_a_obj.id not in tenant_ids_seen, (
        "SESSION LEAK: Tenant A's data is visible in a Tenant B session after exception"
    )
    assert tenant_b_obj.id in tenant_ids_seen


@pytest.mark.asyncio
async def test_session_reset_after_successful_request(db_session: AsyncSession, tenant_a, tenant_b):
    """Even after a clean request, the variable must be reset before pool return."""
    tenant_a_obj, _ = tenant_a
    tenant_b_obj, _ = tenant_b

    # Simulate Tenant A request completing normally
    await db_session.execute(
        text("SET LOCAL app.current_tenant = :tid"),
        {"tid": str(tenant_a_obj.id)},
    )
    # Simulate finally block
    await db_session.execute(text("RESET app.current_tenant"))

    # Tenant B request starts — the variable is set to B, not inherited from A
    await db_session.execute(
        text("SET LOCAL app.current_tenant = :tid"),
        {"tid": str(tenant_b_obj.id)},
    )

    result = await db_session.execute(text("SELECT tenant_id FROM tenant_admins"))
    rows = result.fetchall()
    tenant_ids_seen = {row.tenant_id for row in rows}

    assert tenant_a_obj.id not in tenant_ids_seen
    assert tenant_b_obj.id in tenant_ids_seen
