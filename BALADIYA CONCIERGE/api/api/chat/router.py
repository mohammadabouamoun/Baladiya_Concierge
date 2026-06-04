"""Chat endpoint — inbound resident messages.

POST /chat        — main chat endpoint; widget JWT required (visitor or tenant_admin role)
POST /chat/token  — issues short-lived visitor JWT for a given tenant (public, no auth)
                    Phase 004: no origin check; Phase 006 adds server-side origin verification

T-034: logs handled_by (workflow|agent|spam) per tenant for cost attribution.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

import httpx
import jwt
import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.config import get_settings
from api.core.security import TokenClaims, decode_token, get_current_user
from api.infra.db import get_db

logger = structlog.get_logger(__name__)

router = APIRouter()

# Guardrails passthrough stub — returns allowed=True always.
# Phase 005 wires in the full NeMo Guardrails sidecar HTTP call.
async def _guardrails_check(message: str) -> bool:
    return True


# ── Schemas ────────────────────────────────────────────────────────────────

class WidgetTokenRequest(BaseModel):
    tenant_id: uuid.UUID


class WidgetTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ChatRequest(BaseModel):
    session_id: str
    message: str


class ChatResponse(BaseModel):
    response: str
    handled_by: str  # "workflow" | "agent" | "spam"


# ── Dependencies ───────────────────────────────────────────────────────────

async def _require_tenant_context(
    token: Annotated[TokenClaims, Depends(get_current_user)],
) -> TokenClaims:
    """Accept any JWT that carries a tenant_id (visitor or tenant_admin)."""
    if token.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="tenant_id required for chat",
        )
    return token


async def _get_chat_db(
    token: Annotated[TokenClaims, Depends(_require_tenant_context)],
) -> AsyncSession:
    async for session in get_db(token):
        yield session


# ── Routes ─────────────────────────────────────────────────────────────────

@router.post("/token", response_model=WidgetTokenResponse)
async def get_widget_token(body: WidgetTokenRequest) -> WidgetTokenResponse:
    """Issue a short-lived visitor JWT for a given tenant.

    Public endpoint — no authentication required.
    Phase 006 will add server-side origin verification.
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    claims = {
        "sub": str(uuid.uuid4()),
        "role": "visitor",
        "tenant_id": str(body.tenant_id),
        "exp": now + timedelta(minutes=settings.widget_token_expire_minutes),
        "iat": now,
    }
    token = jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return WidgetTokenResponse(access_token=token)


@router.post("", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    token: Annotated[TokenClaims, Depends(_require_tenant_context)],
    db_session: Annotated[AsyncSession, Depends(_get_chat_db)],
) -> ChatResponse:
    """Process an inbound resident message.

    Flow: guardrails check → router (classify) → workflow or agent → response.
    Spam returns an empty response with handled_by="spam" (silent drop, not an error).
    """
    if not body.message.strip():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="message cannot be empty")

    # Guardrails stub (Phase 005 wires in the full sidecar)
    allowed = await _guardrails_check(body.message)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message blocked by content policy",
        )

    from api.services.router_service import handle
    try:
        response_text, handled_by = await handle(
            text=body.message,
            tenant_id=token.tenant_id,
            session_id=body.session_id,
            db_session=db_session,
        )
    except (httpx.RequestError, httpx.HTTPStatusError) as exc:
        # C2: modelserver down → 503 (spec edge case: "router fails → graceful 503")
        logger.error(
            "chat.modelserver_unavailable",
            tenant_id=str(token.tenant_id),
            session_id=body.session_id,
            error=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The service is temporarily unavailable. Please try again in a moment.",
        )

    # T-034: log workflow vs agent % per tenant
    logger.info(
        "chat.turn",
        tenant_id=str(token.tenant_id),
        session_id=body.session_id,
        handled_by=handled_by,
        response_len=len(response_text),
    )

    return ChatResponse(response=response_text, handled_by=handled_by)
