"""Guardrails middleware helper.

Not an ASGI middleware — called explicitly in the chat router so it can
access the validated JWT token (tenant_id, session_id) before validation.

Usage in chat router:
    result = await run_guardrails(message, token, tenant_settings)
    if not result.allowed:
        return ChatResponse(response=result.refusal_text, handled_by="guardrails")
"""
from __future__ import annotations

from typing import Any

import structlog
from fastapi import HTTPException, status

from api.infra.guardrails_client import GuardrailResponse, GuardrailUnavailable, validate

logger = structlog.get_logger(__name__)


async def run_guardrails(
    message: str,
    tenant_id: str,
    session_id: str,
    tenant_guardrail_config: dict[str, Any] | None = None,
) -> GuardrailResponse:
    """Run guardrails validation. Raises HTTP 503 if sidecar is unreachable (fail-closed).

    Returns GuardrailResponse — caller checks .allowed before proceeding.
    """
    try:
        result = await validate(
            message=message,
            tenant_id=tenant_id,
            session_id=session_id,
            tenant_rails=tenant_guardrail_config,
        )
    except GuardrailUnavailable as exc:
        logger.error(
            "guardrails.unavailable",
            tenant_id=tenant_id,
            session_id=session_id,
            error=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Content validation service is temporarily unavailable. Please try again in a moment.",
        ) from exc

    if not result.allowed:
        logger.info(
            "guardrails.blocked",
            tenant_id=tenant_id,
            session_id=session_id,
            triggered_rail=result.triggered_rail,
        )

    return result
