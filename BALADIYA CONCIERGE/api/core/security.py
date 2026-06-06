from __future__ import annotations

import uuid
from typing import Annotated, Literal

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from api.core.config import get_settings

_bearer = HTTPBearer(auto_error=True)


async def _get_signing_key(token: str, settings) -> str:
    """Two-pass key selection: peek at widget_id claim, then pick the right key.

    Step 1: decode without signature verification to read widget_id.
    Step 2: if widget_id present, fetch per-widget key from Vault cache (async).
            Otherwise use jwt_secret (backward compatible).
    The unverified widget_id is only used to SELECT the key — no auth decision
    is made on unverified claims.
    """
    try:
        unverified = jwt.decode(token, options={"verify_signature": False}, algorithms=[settings.jwt_algorithm])
    except jwt.DecodeError:
        return settings.jwt_secret

    widget_id_raw = unverified.get("widget_id")
    if not widget_id_raw:
        return settings.jwt_secret

    try:
        from api.infra.vault import get_widget_signing_key
        return await get_widget_signing_key(uuid.UUID(widget_id_raw))
    except Exception:
        # Vault unavailable or key missing — fall through; full decode will reject the token
        return settings.jwt_secret


class TokenClaims:
    def __init__(
        self,
        user_id: uuid.UUID,
        role: Literal["platform_manager", "tenant_admin", "visitor"],
        tenant_id: uuid.UUID | None,
        widget_id: uuid.UUID | None = None,
    ) -> None:
        self.user_id = user_id
        self.role = role
        self.tenant_id = tenant_id  # None for platform_manager
        self.widget_id = widget_id  # set only for widget-issued visitor tokens


async def decode_token(token: str) -> TokenClaims:
    settings = get_settings()
    signing_key = await _get_signing_key(token, settings)
    try:
        payload = jwt.decode(
            token,
            signing_key,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))

    role = payload.get("role")
    if role not in ("platform_manager", "tenant_admin", "visitor"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid role")

    tenant_id_raw = payload.get("tenant_id")
    tenant_id = uuid.UUID(tenant_id_raw) if tenant_id_raw else None

    if role != "platform_manager" and tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="tenant_id missing from token",
        )

    widget_id_raw = payload.get("widget_id")
    widget_id = uuid.UUID(widget_id_raw) if widget_id_raw else None

    return TokenClaims(
        user_id=uuid.UUID(payload["sub"]),
        role=role,
        tenant_id=tenant_id,
        widget_id=widget_id,
    )


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
) -> TokenClaims:
    return await decode_token(credentials.credentials)
