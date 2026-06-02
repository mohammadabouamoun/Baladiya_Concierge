from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
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


class EraseConfirmation(TenantCreate):
    pass


from pydantic import BaseModel  # noqa: E402


class EraseRequest(BaseModel):
    confirm_tenant_id: uuid.UUID


@router.delete("/tenants/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def erase_tenant(
    tenant_id: uuid.UUID,
    body: EraseRequest,
    token: Annotated[TokenClaims, Depends(require_platform_manager)],
    session: Annotated[AsyncSession, Depends(_get_platform_db)],
) -> None:
    if body.confirm_tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="confirm_tenant_id must match the URL tenant_id",
        )
    try:
        await platform_service.erase_tenant(session, tenant_id, token.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
