"""Admin API: tenant admin views for capture_requests and escalation_tickets.

Supports the Streamlit admin pages (T-050, T-051).
All routes require tenant_admin role and are scoped to the token's tenant_id.
"""
from __future__ import annotations

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.api.cms.deps import require_tenant_admin
from api.core.security import TokenClaims
from api.domain.capture_request import CaptureRequestRead, EscalationTicketRead
from api.infra.db import get_db
from api.repositories.capture_repo import CaptureRequestRepository
from api.repositories.escalation_repo import EscalationTicketRepository

logger = structlog.get_logger(__name__)
router = APIRouter()


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
