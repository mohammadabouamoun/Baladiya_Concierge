"""Async HTTP client for the Guardrails sidecar.

Fails closed on connection error — the API must never process a message
without guardrail validation (constitution requirement).
"""
from __future__ import annotations

from typing import Any

import structlog
from httpx import AsyncClient, HTTPStatusError, RequestError

from api.core.config import get_settings

logger = structlog.get_logger(__name__)

_client: AsyncClient | None = None


class GuardrailUnavailable(Exception):
    """Raised when the guardrails sidecar is unreachable."""


class GuardrailResponse:
    __slots__ = ("allowed", "modified_message", "triggered_rail", "refusal_text")

    def __init__(
        self,
        allowed: bool,
        modified_message: str | None = None,
        triggered_rail: str | None = None,
        refusal_text: str | None = None,
    ) -> None:
        self.allowed = allowed
        self.modified_message = modified_message
        self.triggered_rail = triggered_rail
        self.refusal_text = refusal_text


async def init_guardrails_client() -> None:
    global _client
    settings = get_settings()
    _client = AsyncClient(
        base_url=settings.guardrails_url,
        headers={"X-Service-Token": settings.guardrails_service_token},
        timeout=10.0,
    )
    logger.info("guardrails_client.ready", url=settings.guardrails_url)


async def close_guardrails_client() -> None:
    if _client:
        await _client.aclose()


def get_client() -> AsyncClient:
    if _client is None:
        raise RuntimeError("guardrails client not initialised — call init_guardrails_client() at startup")
    return _client


async def validate(
    message: str,
    tenant_id: str,
    session_id: str,
    tenant_rails: dict[str, Any] | None = None,
) -> GuardrailResponse:
    """Validate a message through the guardrails sidecar.

    Raises GuardrailUnavailable on connection error (caller must return 503).
    """
    client = get_client()
    payload = {
        "message": message,
        "tenant_id": tenant_id,
        "session_id": session_id,
        "tenant_rails": tenant_rails,
    }
    try:
        resp = await client.post("/validate", json=payload)
        resp.raise_for_status()
    except RequestError as exc:
        logger.error("guardrails_client.connection_error", error=str(exc))
        raise GuardrailUnavailable(f"Guardrails sidecar unreachable: {exc}") from exc
    except HTTPStatusError as exc:
        logger.error("guardrails_client.http_error", status=exc.response.status_code)
        raise GuardrailUnavailable(f"Guardrails sidecar returned {exc.response.status_code}") from exc

    data = resp.json()
    return GuardrailResponse(
        allowed=data["allowed"],
        modified_message=data.get("modified_message"),
        triggered_rail=data.get("triggered_rail"),
        refusal_text=data.get("refusal_text"),
    )
