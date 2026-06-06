from __future__ import annotations

import uuid
from typing import Annotated, Literal

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from api.core.config import get_settings

_bearer = HTTPBearer(auto_error=True)


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


def decode_token(token: str) -> TokenClaims:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
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
    return decode_token(credentials.credentials)
