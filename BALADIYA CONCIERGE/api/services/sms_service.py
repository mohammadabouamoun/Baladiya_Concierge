"""SMS backend abstraction for OTP delivery.

Default: ConsoleSMSBackend — logs the OTP (dev / demo).
Swap for a real provider (Twilio, AWS SNS, etc.) by setting sms_backend in config.
"""
from __future__ import annotations

import structlog

logger = structlog.get_logger(__name__)


class ConsoleSMSBackend:
    """Logs the OTP code instead of sending a real SMS. Suitable for dev and demo."""

    async def send(self, phone_e164: str, code: str) -> None:
        masked = phone_e164[:5] + "****" + phone_e164[-2:]
        logger.info(
            "sms.otp_console",
            phone=masked,
            code=code,
            note="Replace ConsoleSMSBackend with a real SMS provider for production",
        )


_backend: ConsoleSMSBackend | None = None


def get_sms_backend() -> ConsoleSMSBackend:
    global _backend
    if _backend is None:
        _backend = ConsoleSMSBackend()
    return _backend


async def send_otp(phone_e164: str, code: str) -> None:
    """Send OTP via the configured backend."""
    await get_sms_backend().send(phone_e164, code)
