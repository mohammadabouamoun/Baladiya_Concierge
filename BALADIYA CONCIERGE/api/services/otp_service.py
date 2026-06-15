"""Redis-backed OTP generation and verification for phone-verified report filing.

Key layout:
  otp:{tenant_id}:{phone_hash}          → 6-digit code (TTL: OTP_TTL_SECONDS)
  otp_rate:{tenant_id}:{phone_hash}     → request count (TTL: OTP_RATE_WINDOW_SECONDS)
  session_phone:{session_id}:{tenant_id} → verified phone_hash (TTL: SESSION_TTL_SECONDS)
"""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import uuid

import structlog
from redis.asyncio import Redis

from api.core.config import get_settings

logger = structlog.get_logger(__name__)

OTP_DIGITS = 6
SESSION_TTL_SECONDS = 1800  # matches session TTL in session_service


def hash_phone(phone_e164: str, tenant_id: uuid.UUID) -> str:
    """Tenant-scoped HMAC-SHA256 of phone number. One-way; tenant_id prevents cross-tenant collisions."""
    settings = get_settings()
    msg = f"{tenant_id}:{phone_e164}".encode()
    return hmac.new(settings.jwt_secret.encode(), msg, hashlib.sha256).hexdigest()


_LB_MOBILE_PREFIXES = frozenset({"03", "70", "71", "76", "78", "79", "81", "82", "83", "86", "88"})


def _is_valid_lb_local(local8: str) -> bool:
    """Return True if `local8` is a valid 8-digit Lebanese mobile number (no country code)."""
    return len(local8) == 8 and local8[:2] in _LB_MOBILE_PREFIXES and local8.isdigit()


def normalize_phone(raw: str) -> str | None:
    """Normalize a phone number to E.164 (+XXXXXXXXXXX).

    Lebanese numbers (country code 961):
      - E.164:   +96170123456 or 0096170123456
      - Local:   70123456 or 070123456 (8 digits, leading 0 optional)
    Valid Lebanese mobile prefixes: 03, 70, 71, 76, 78, 79, 81, 82, 83, 86, 88
    Local number is exactly 8 digits (prefix 2 + subscriber 6).

    Returns None if the number can't be parsed or fails Lebanese mobile validation
    when the country code is 961.
    """
    # Strip everything except digits and a leading +
    digits = re.sub(r"[^\d+]", "", raw.strip())
    if digits.startswith("+"):
        digits = digits[1:]
    elif digits.startswith("00"):
        digits = digits[2:]

    # ── Lebanese E.164: 961 + 8 local digits ──────────────────────────────
    if digits.startswith("961"):
        local = digits[3:]
        if not _is_valid_lb_local(local):
            return None
        return "+961" + local

    # ── Local Lebanese: 8 digits or 9 digits with exactly one leading 0 ────
    if len(digits) == 9 and digits[0] == "0":
        local = digits[1:]   # strip one leading 0 (070... → 70..., 003... → 03...)
    elif len(digits) == 8:
        local = digits
    else:
        return None
    if _is_valid_lb_local(local):
        return "+961" + local

    return None


async def generate_otp(redis: Redis, tenant_id: uuid.UUID, phone_hash: str) -> tuple[str, bool]:
    """Generate and store a 6-digit OTP.  Returns (code, rate_limited).

    Rate-limited to settings.otp_rate_limit requests per settings.otp_rate_window_seconds.
    """
    settings = get_settings()
    rate_key = f"otp_rate:{tenant_id}:{phone_hash}"
    count = await redis.incr(rate_key)
    if count == 1:
        await redis.expire(rate_key, settings.otp_rate_window_seconds)
    if count > settings.otp_rate_limit:
        logger.warning("otp.rate_limited", tenant_id=str(tenant_id))
        return "", True

    code = str(secrets.randbelow(10 ** OTP_DIGITS)).zfill(OTP_DIGITS)
    otp_key = f"otp:{tenant_id}:{phone_hash}"
    await redis.set(otp_key, code, ex=settings.otp_ttl_seconds)
    logger.info("otp.generated", tenant_id=str(tenant_id), phone_hash=phone_hash[:8] + "****")
    return code, False


async def verify_otp(redis: Redis, tenant_id: uuid.UUID, phone_hash: str, code: str) -> bool:
    """Verify a 6-digit OTP. Returns True on match (and deletes it — single use)."""
    otp_key = f"otp:{tenant_id}:{phone_hash}"
    stored = await redis.get(otp_key)
    if stored is None:
        logger.info("otp.expired_or_missing", tenant_id=str(tenant_id))
        return False
    if not secrets.compare_digest(stored, code.strip()):
        logger.info("otp.wrong_code", tenant_id=str(tenant_id))
        return False
    await redis.delete(otp_key)
    logger.info("otp.verified", tenant_id=str(tenant_id))
    return True


async def mark_session_verified(
    redis: Redis, session_id: str, tenant_id: uuid.UUID, phone_hash: str
) -> None:
    """Mark a chat session as phone-verified. Expires with the session TTL."""
    key = f"session_phone:{session_id}:{tenant_id}"
    await redis.set(key, phone_hash, ex=SESSION_TTL_SECONDS)
    logger.info("otp.session_marked_verified", session_id=session_id, tenant_id=str(tenant_id))


async def get_session_phone_hash(
    redis: Redis, session_id: str, tenant_id: uuid.UUID
) -> str | None:
    """Return the verified phone_hash for this session, or None if not verified."""
    key = f"session_phone:{session_id}:{tenant_id}"
    return await redis.get(key)
