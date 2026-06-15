"""Phone OTP verification for report filing.

POST /verify/otp/request  — send OTP to phone number
POST /verify/otp/confirm  — verify OTP, mark session as phone-verified

The tenant_id comes from the widget JWT (same token used for chat).
Phone numbers are normalized to E.164, hashed with HMAC-SHA256, and never stored in plaintext.
"""
from __future__ import annotations

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.api.chat.router import _require_tenant_context
from api.core.security import TokenClaims
from api.infra.db import get_db
from api.infra.redis import get_redis
from api.services.otp_service import (
    generate_otp,
    get_session_phone_hash,
    hash_phone,
    mark_session_verified,
    normalize_phone,
    verify_otp,
)
from api.services.sms_service import send_otp

logger = structlog.get_logger(__name__)

router = APIRouter()


class OTPRequestBody(BaseModel):
    phone: str    # raw phone — normalized server-side
    session_id: str


class OTPRequestResponse(BaseModel):
    status: str   # "sent" | "rate_limited"


class OTPConfirmBody(BaseModel):
    phone: str
    code: str
    session_id: str


class OTPConfirmResponse(BaseModel):
    status: str   # "verified" | "invalid"


async def _get_verify_db(
    token: Annotated[TokenClaims, Depends(_require_tenant_context)],
) -> AsyncSession:
    async for session in get_db(token):
        yield session


@router.post("/otp/request", response_model=OTPRequestResponse)
async def request_otp(
    body: OTPRequestBody,
    token: Annotated[TokenClaims, Depends(_require_tenant_context)],
) -> OTPRequestResponse:
    """Normalize phone, generate a 6-digit OTP, send via SMS backend.

    Rate-limited to 3 requests per phone per 10 minutes.
    Phone is never stored plaintext — only its HMAC-SHA256 hash.
    """
    phone_e164 = normalize_phone(body.phone)
    if phone_e164 is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid phone number format. Please use +961XXXXXXXX or local Lebanese format.",
        )

    phone_hash = hash_phone(phone_e164, token.tenant_id)
    redis = get_redis()
    code, rate_limited = await generate_otp(redis, token.tenant_id, phone_hash)

    if rate_limited:
        logger.warning(
            "verify.otp_rate_limited",
            tenant_id=str(token.tenant_id),
            session_id=body.session_id,
        )
        return OTPRequestResponse(status="rate_limited")

    await send_otp(phone_e164, code)

    logger.info(
        "verify.otp_sent",
        tenant_id=str(token.tenant_id),
        session_id=body.session_id,
    )
    return OTPRequestResponse(status="sent")


@router.post("/otp/confirm", response_model=OTPConfirmResponse)
async def confirm_otp(
    body: OTPConfirmBody,
    token: Annotated[TokenClaims, Depends(_require_tenant_context)],
) -> OTPConfirmResponse:
    """Verify the OTP code. On success, mark the session as phone-verified in Redis."""
    phone_e164 = normalize_phone(body.phone)
    if phone_e164 is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid phone number format.",
        )

    phone_hash = hash_phone(phone_e164, token.tenant_id)
    redis = get_redis()
    ok = await verify_otp(redis, token.tenant_id, phone_hash, body.code)

    if not ok:
        logger.info(
            "verify.otp_failed",
            tenant_id=str(token.tenant_id),
            session_id=body.session_id,
        )
        return OTPConfirmResponse(status="invalid")

    await mark_session_verified(redis, body.session_id, token.tenant_id, phone_hash)
    logger.info(
        "verify.session_verified",
        tenant_id=str(token.tenant_id),
        session_id=body.session_id,
    )
    return OTPConfirmResponse(status="verified")
