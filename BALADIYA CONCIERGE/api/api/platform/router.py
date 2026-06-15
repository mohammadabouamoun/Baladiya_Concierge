from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.api.platform.deps import require_platform_manager
from api.core.security import TokenClaims
from api.domain.tenant import TenantCreate, TenantRead
from api.infra.db import get_db
from api.services import platform_service

router = APIRouter()

# Platform Manager routes use a no-RLS DB session.
# get_db sets the session variable only when token.tenant_id is not None;
# platform_manager tokens have tenant_id=None, so RLS is never set.


async def _get_platform_db(
    token: Annotated[TokenClaims, Depends(require_platform_manager)],
) -> AsyncSession:
    # Reuse get_db but with a platform manager token (tenant_id=None → no RLS set)
    async for session in get_db(token):
        yield session


@router.post(
    "/tenants",
    response_model=TenantRead,
    status_code=status.HTTP_201_CREATED,
)
async def provision_tenant(
    payload: TenantCreate,
    token: Annotated[TokenClaims, Depends(require_platform_manager)],
    session: Annotated[AsyncSession, Depends(_get_platform_db)],
) -> TenantRead:
    tenant = await platform_service.provision_tenant(session, payload, token.user_id)
    return TenantRead.model_validate(tenant)


@router.get("/tenants", response_model=list[TenantRead])
async def list_tenants(
    token: Annotated[TokenClaims, Depends(require_platform_manager)],
    session: Annotated[AsyncSession, Depends(_get_platform_db)],
) -> list[TenantRead]:
    from api.repositories.tenant_repo import PlatformTenantRepository
    repo = PlatformTenantRepository(session)
    tenants = await repo.list_all()
    return [TenantRead.model_validate(t) for t in tenants]


@router.post("/tenants/{tenant_id}/suspend", response_model=TenantRead)
async def suspend_tenant(
    tenant_id: uuid.UUID,
    token: Annotated[TokenClaims, Depends(require_platform_manager)],
    session: Annotated[AsyncSession, Depends(_get_platform_db)],
) -> TenantRead:
    try:
        tenant = await platform_service.suspend_tenant(session, tenant_id, token.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return TenantRead.model_validate(tenant)




@router.delete("/tenants/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def erase_tenant(
    tenant_id: uuid.UUID,
    confirm_tenant_id: Annotated[uuid.UUID, Query()],
    token: Annotated[TokenClaims, Depends(require_platform_manager)],
    session: Annotated[AsyncSession, Depends(_get_platform_db)],
) -> None:
    if confirm_tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="confirm_tenant_id must match the URL tenant_id",
        )
    try:
        await platform_service.erase_tenant(session, tenant_id, token.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/audit-logs", response_model=list)
async def list_audit_logs(
    token: Annotated[TokenClaims, Depends(require_platform_manager)],
    session: Annotated[AsyncSession, Depends(_get_platform_db)],
    limit: int = Query(default=100, le=500),
) -> list:
    from sqlalchemy import select, desc
    from api.domain.audit import AuditLog
    result = await session.execute(
        select(AuditLog).order_by(desc(AuditLog.created_at)).limit(limit)
    )
    logs = result.scalars().all()
    return [
        {
            "id": str(log.id),
            "actor_id": str(log.actor_id),
            "actor_role": log.actor_role,
            "action": log.action,
            "tenant_id": str(log.tenant_id) if log.tenant_id else None,
            "metadata": log.metadata_,
            "created_at": log.created_at.isoformat(),
        }
        for log in logs
    ]
