from __future__ import annotations

import uuid
from datetime import datetime, timezone

import bcrypt
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from api.domain.audit import AuditLog
from api.domain.tenant import Tenant, TenantAdmin, TenantCreate
from api.repositories.tenant_repo import PlatformTenantRepository

logger = structlog.get_logger(__name__)


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


async def provision_tenant(
    session: AsyncSession,
    payload: TenantCreate,
    actor_id: uuid.UUID,
) -> Tenant:
    """Create a new tenant + admin user.

    Idempotent: if a tenant admin with the same email already exists,
    return the existing tenant rather than creating a duplicate.
    """
    repo = PlatformTenantRepository(session)

    existing = await repo.get_by_admin_email(payload.admin_email)
    if existing:
        logger.info("provision.idempotent", tenant_id=str(existing.id), email=payload.admin_email)
        return existing

    tenant = Tenant(
        id=uuid.uuid4(),
        name=payload.name,
        plan=payload.plan,
        status="active",
        settings={"requests_per_minute": 60},
    )
    await repo.add(tenant)

    admin = TenantAdmin(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email=payload.admin_email,
        hashed_password=_hash_password(payload.admin_password),
        role="tenant_admin",
    )
    await repo.add_admin(admin)

    audit = AuditLog(
        actor_id=actor_id,
        actor_role="platform_manager",
        action="provision_tenant",
        tenant_id=tenant.id,
        metadata_={"tenant_name": payload.name, "admin_email": payload.admin_email},
    )
    session.add(audit)

    await session.commit()
    logger.info("provision.done", tenant_id=str(tenant.id), name=payload.name)
    return tenant


async def suspend_tenant(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> Tenant:
    repo = PlatformTenantRepository(session)
    tenant = await repo.get(tenant_id)
    if not tenant:
        raise ValueError(f"Tenant {tenant_id} not found")

    tenant.status = "suspended"
    audit = AuditLog(
        actor_id=actor_id,
        actor_role="platform_manager",
        action="suspend_tenant",
        tenant_id=tenant_id,
        metadata_={},
    )
    session.add(audit)
    await session.commit()
    logger.info("suspend.done", tenant_id=str(tenant_id))
    return tenant


async def erase_tenant(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    redis=None,
    minio=None,
) -> None:
    """Hard-delete all tenant data in correct FK order.

    Order (from plan.md):
    1. Redis sessions
    2. pgvector embeddings (future table — skipped if not present)
    3. Tenant content/conversation/request tables (future — skipped)
    4. MinIO blobs
    5. TenantAdmin users
    6. Tenant row
    7. AuditLog entry (platform-scoped connection — no tenant context)
    """
    repo = PlatformTenantRepository(session)
    tenant = await repo.get(tenant_id)
    if not tenant:
        raise ValueError(f"Tenant {tenant_id} not found")

    # 1. Redis sessions — pattern: session:*:{tenant_id}
    if redis is not None:
        pattern = f"session:*:{tenant_id}"
        cursor = 0
        while True:
            cursor, keys = await redis.scan(cursor, match=pattern, count=100)
            if keys:
                await redis.delete(*keys)
            if cursor == 0:
                break
        logger.info("erase.redis_done", tenant_id=str(tenant_id))

    # 2. pgvector embeddings — cms_chunks and cms_entries (feature 003+)
    try:
        from api.repositories.cms_repo import CmsChunkRepository
        from sqlalchemy import delete as sa_delete
        from api.domain.cms import CmsEntry as CmsEntryModel
        chunk_repo = CmsChunkRepository(session=session, tenant_id=tenant_id)
        await chunk_repo.delete_by_tenant()
        await session.execute(
            sa_delete(CmsEntryModel).where(CmsEntryModel.tenant_id == tenant_id)
        )
        logger.info("erase.pgvector_done", tenant_id=str(tenant_id))
    except ImportError:
        pass  # CMS tables not yet created in this deployment

    # 3. Content/conversation/request tables — exist in later features; skip if not present

    # 4. MinIO blobs
    if minio is not None:
        prefix = f"tenants/{tenant_id}/"
        objects = minio.list_objects("baladiya", prefix=prefix, recursive=True)
        for obj in objects:
            minio.remove_object("baladiya", obj.object_name)
        logger.info("erase.minio_done", tenant_id=str(tenant_id))

    # 5. TenantAdmin users (CASCADE handles DB deletion via FK, but be explicit)
    from sqlalchemy import delete
    from api.domain.tenant import TenantAdmin as TenantAdminModel
    await session.execute(
        delete(TenantAdminModel).where(TenantAdminModel.tenant_id == tenant_id)
    )

    # 6. Tenant row
    await session.delete(tenant)

    # 7. Audit entry written BEFORE commit so it lands in the same transaction
    audit = AuditLog(
        actor_id=actor_id,
        actor_role="platform_manager",
        action="erase_tenant",
        tenant_id=tenant_id,
        metadata_={"tenant_name": tenant.name},
    )
    session.add(audit)

    await session.commit()
    logger.info("erase.done", tenant_id=str(tenant_id))
