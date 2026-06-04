"""Admin API: tenant admin views for capture_requests, escalation_tickets, and settings.

Supports the Streamlit admin pages.
All routes require tenant_admin role and are scoped to the token's tenant_id.
"""
from __future__ import annotations

from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.api.cms.deps import require_tenant_admin
from api.core.security import TokenClaims
from api.domain.capture_request import CaptureRequestRead, EscalationTicketRead
from api.infra.db import get_db
from api.repositories.capture_repo import CaptureRequestRepository
from api.repositories.escalation_repo import EscalationTicketRepository
from api.repositories.tenant_repo import PlatformTenantRepository

logger = structlog.get_logger(__name__)
router = APIRouter()


# ── Settings schemas ───────────────────────────────────────────────────────

class TenantSettingsResponse(BaseModel):
    guardrail_config: dict[str, Any] | None = None
    persona: str | None = None
    requests_per_minute: int | None = None


class TenantSettingsPatch(BaseModel):
    guardrail_config: dict[str, Any] | None = None
    persona: str | None = None


async def _get_tenant_db(
    token: Annotated[TokenClaims, Depends(require_tenant_admin)],
) -> AsyncSession:
    async for session in get_db(token):
        yield session


@router.get("/capture-requests", response_model=list[CaptureRequestRead])
async def list_capture_requests(
    token: Annotated[TokenClaims, Depends(require_tenant_admin)],
    session: Annotated[AsyncSession, Depends(_get_tenant_db)],
    status: str | None = None,
) -> list[CaptureRequestRead]:
    repo = CaptureRequestRepository(session, token.tenant_id)
    filters = {}
    if status:
        filters["status"] = status
    records = await repo.list(**filters)
    return [CaptureRequestRead.model_validate(r) for r in records]


@router.get("/escalation-tickets", response_model=list[EscalationTicketRead])
async def list_escalation_tickets(
    token: Annotated[TokenClaims, Depends(require_tenant_admin)],
    session: Annotated[AsyncSession, Depends(_get_tenant_db)],
    status: str | None = None,
) -> list[EscalationTicketRead]:
    repo = EscalationTicketRepository(session, token.tenant_id)
    filters = {}
    if status:
        filters["status"] = status
    tickets = await repo.list(**filters)
    return [EscalationTicketRead.model_validate(t) for t in tickets]


# ── Tenant settings ────────────────────────────────────────────────────────

@router.get("/settings", response_model=TenantSettingsResponse)
async def get_settings(
    token: Annotated[TokenClaims, Depends(require_tenant_admin)],
    session: Annotated[AsyncSession, Depends(_get_tenant_db)],
) -> TenantSettingsResponse:
    """Return tenant-configurable settings (guardrail_config, persona)."""
    repo = PlatformTenantRepository(session)
    tenant = await repo.get(token.tenant_id)
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    s = tenant.settings or {}
    return TenantSettingsResponse(
        guardrail_config=s.get("guardrail_config"),
        persona=s.get("persona"),
        requests_per_minute=s.get("requests_per_minute"),
    )


@router.patch("/settings", response_model=TenantSettingsResponse)
async def patch_settings(
    body: TenantSettingsPatch,
    token: Annotated[TokenClaims, Depends(require_tenant_admin)],
    session: Annotated[AsyncSession, Depends(_get_tenant_db)],
) -> TenantSettingsResponse:
    """Update tenant-configurable settings. Unset fields are left unchanged."""
    repo = PlatformTenantRepository(session)
    tenant = await repo.get(token.tenant_id)
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    settings = dict(tenant.settings or {})
    if body.guardrail_config is not None:
        settings["guardrail_config"] = body.guardrail_config
    if body.persona is not None:
        settings["persona"] = body.persona

    # Persist via JSONB update
    from sqlalchemy import update
    from api.domain.tenant import Tenant
    await session.execute(
        update(Tenant)
        .where(Tenant.id == token.tenant_id)
        .values(settings=settings)
    )
    await session.commit()

    logger.info(
        "admin.settings_updated",
        tenant_id=str(token.tenant_id),
        fields=list(body.model_fields_set),
    )
    return TenantSettingsResponse(
        guardrail_config=settings.get("guardrail_config"),
        persona=settings.get("persona"),
        requests_per_minute=settings.get("requests_per_minute"),
    )
