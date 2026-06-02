"""Auth endpoint — issues JWT tokens for Tenant Admin and Platform Manager logins.

Used by the Streamlit admin UI (POST /auth/token).
tenant_id in the issued token comes from the DB row — never from the request body.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.config import get_settings
from api.domain.tenant import PlatformManager, TenantAdmin
from api.infra.db import get_session_factory

logger = structlog.get_logger(__name__)

router = APIRouter()


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    tenant_id: uuid.UUID | None


async def _get_plain_session() -> AsyncSession:
    """Yield a session with no RLS set — used for auth lookups that span tables."""
    factory = get_session_factory()
    async with factory() as session:
        yield session


@router.post("/token", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    session: AsyncSession = Depends(_get_plain_session),
) -> TokenResponse:
    """Authenticate a Tenant Admin or Platform Manager and return a signed JWT.

    Lookup order: TenantAdmin → PlatformManager.
    tenant_id is always sourced from the DB row, never from the request.
    """
    settings = get_settings()

    # Try TenantAdmin first
    result = await session.execute(
        select(TenantAdmin).where(TenantAdmin.email == payload.email)
    )
    admin = result.scalar_one_or_none()

    if admin is not None:
        if not bcrypt.checkpw(payload.password.encode(), admin.hashed_password.encode()):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        claims = {
            "sub": str(admin.id),
            "role": "tenant_admin",
            "tenant_id": str(admin.tenant_id),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes),
        }
        token = jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)
        logger.info("auth.login", role="tenant_admin", tenant_id=str(admin.tenant_id))
        return TokenResponse(access_token=token, role="tenant_admin", tenant_id=admin.tenant_id)

    # Try PlatformManager
    result = await session.execute(
        select(PlatformManager).where(PlatformManager.email == payload.email)
    )
    pm = result.scalar_one_or_none()

    if pm is not None:
        if not bcrypt.checkpw(payload.password.encode(), pm.hashed_password.encode()):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        claims = {
            "sub": str(pm.id),
            "role": "platform_manager",
            "tenant_id": None,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes),
        }
        token = jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)
        logger.info("auth.login", role="platform_manager")
        return TokenResponse(access_token=token, role="platform_manager", tenant_id=None)

    # Neither found — same error message to prevent user enumeration
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
