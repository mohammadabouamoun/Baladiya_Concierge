"""Agent tool: capture_request — Pydantic-validated civic service request capture.

Security invariants (enforced here, not by the LLM):
- tenant_id ALWAYS from context (JWT), NEVER from tool args.
- Payload Pydantic-validated before any write.
- Per-session rate limit checked before write.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog
from fastapi import HTTPException, status
from pydantic import ValidationError

if TYPE_CHECKING:
    from api.services.agent_service import AgentContext

from api.core.config import get_settings
from api.domain.capture_request import CaptureRequestCreate
from api.infra.redis import get_redis
from api.repositories.capture_repo import CaptureRequestRepository

logger = structlog.get_logger(__name__)

_RATE_LIMIT_WINDOW = 60  # seconds


async def _check_rate_limit(session_id: str, tenant_id: Any) -> None:
    """Raise 429 if session exceeded capture_requests_per_minute."""
    redis = get_redis()
    settings = get_settings()
    key = f"capture_ratelimit:{session_id}:{tenant_id}"

    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, _RATE_LIMIT_WINDOW)

    limit = settings.capture_requests_per_minute
    if count > limit:
        logger.warning(
            "tool.capture_request.rate_limit",
            session_id=session_id,
            tenant_id=str(tenant_id),
            count=count,
            limit=limit,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Capture rate limit exceeded: {limit} requests/minute per session",
        )


async def run(args: dict[str, Any], context: AgentContext) -> dict[str, Any]:
    """Capture a civic service request.

    Returns {id, message} on success or {error} on validation/rate-limit failure.
    tenant_id is ALWAYS sourced from context.tenant_id, never from args.
    """
    # Strip any injected tenant_id from args — never trust agent payload
    args.pop("tenant_id", None)

    try:
        payload = CaptureRequestCreate(**args)
    except ValidationError as exc:
        logger.warning(
            "tool.capture_request.validation_failed",
            tenant_id=str(context.tenant_id),
            errors=exc.errors(),
        )
        return {"error": f"Invalid payload: {exc.errors()}"}

    try:
        await _check_rate_limit(context.session_id, context.tenant_id)
    except HTTPException as exc:
        return {"error": exc.detail, "status_code": exc.status_code}

    try:
        repo = CaptureRequestRepository(context.db_session, context.tenant_id)
        record = await repo.create(payload, context.session_id)
        await context.db_session.commit()
    except Exception as exc:
        logger.error(
            "tool.capture_request.db_failed",
            tenant_id=str(context.tenant_id),
            error=str(exc),
        )
        return {"error": f"Failed to save request: {exc}"}

    logger.info(
        "tool.capture_request.ok",
        id=str(record.id),
        tenant_id=str(context.tenant_id),
        intent=record.intent,
    )
    return {
        "id": str(record.id),
        "message": "Your request has been recorded. Reference number: " + str(record.id)[:8].upper(),
    }
