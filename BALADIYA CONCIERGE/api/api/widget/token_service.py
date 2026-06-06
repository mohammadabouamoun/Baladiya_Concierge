"""Widget token issuance — validates widget_id + origin, signs short-lived JWT.

The widget JWT is signed with Settings.jwt_secret (same key used by decode_token)
so the standard auth middleware validates it without a second key lookup.
Settings.widget_signing_key is seeded in Vault but reserved for per-widget key
rotation in a future phase (see DECISIONS.md §Widget).
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

    # Sign with jwt_secret so decode_token (which uses jwt_secret) validates it correctly.
    token = jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    logger.info(
        "widget.token.issued",
        widget_id=str(widget_id),
        tenant_id=str(widget.tenant_id),
        origin=request_origin,
    )
    return token
