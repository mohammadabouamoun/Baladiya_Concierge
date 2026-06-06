"""Widget token issuance — validates widget_id + origin, signs short-lived JWT.

Widget tokens are now signed with a per-widget key stored in Vault at
baladiya/widget/{widget_id}/signing_key. decode_token in security.py picks
the right key via two-pass verification. See DECISIONS.md §D-Widget-001.
Token TTL: 3600 seconds (1 hour) — FR-008.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import jwt
import structlog
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.config import get_settings
from api.repositories.widget_repo import PlatformWidgetRepository

logger = structlog.get_logger(__name__)


async def issue_token(
    widget_id: uuid.UUID,
    request_origin: str,
    session: AsyncSession,
) -> str:
    """Look up widget, validate origin, return signed JWT.

    Raises 404 if widget not found, 403 if origin not in allowed_origins.
    """
    repo = PlatformWidgetRepository(session)
    widget = await repo.get_by_widget_id(widget_id)

    if widget is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Widget not found")

    normalized_origin = request_origin.rstrip("/").lower()
    allowed = [o.rstrip("/").lower() for o in (widget.allowed_origins or [])]

    if normalized_origin not in allowed:
        logger.warning(
            "widget.token.origin_rejected",
            widget_id=str(widget_id),
            origin=request_origin,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Origin not in widget allowed_origins",
        )

    settings = get_settings()
    now = datetime.now(timezone.utc)
    exp = int(now.timestamp()) + 3600

    claims = {
        "tenant_id": str(widget.tenant_id),
        "widget_id": str(widget_id),
        "role": "visitor",
        "sub": str(uuid.uuid4()),
        "jti": str(uuid.uuid4()),
        "iat": int(now.timestamp()),
        "exp": exp,
    }

    # Sign with the per-widget key from Vault. decode_token selects the same key
    # via two-pass verification using the widget_id claim.
    from api.infra.vault import get_widget_signing_key
    try:
        signing_key = get_widget_signing_key(widget_id)
    except Exception:
        # Vault unavailable — fall back to shared jwt_secret (degraded mode)
        logger.warning("widget.token.vault_fallback", widget_id=str(widget_id))
        signing_key = settings.jwt_secret

    token = jwt.encode(claims, signing_key, algorithm=settings.jwt_algorithm)
    logger.info(
        "widget.token.issued",
        widget_id=str(widget_id),
        tenant_id=str(widget.tenant_id),
        origin=request_origin,
    )
    return token
