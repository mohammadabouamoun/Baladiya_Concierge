"""Guardrails sidecar — FastAPI POST /validate.

Called by the API over HTTP before any resident message is processed.
Requires X-Service-Token header matching the Vault-issued service credential.

Response shape:
  GuardrailResponse {
      allowed: bool,
      modified_message: str | None,   # message with PII stripped
      triggered_rail: str | None,     # "injection" | "jailbreak" | "cross_tenant" | "pii" | "topic"
      refusal_text: str | None,
  }
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

import structlog
from fastapi import FastAPI, Header, HTTPException, Request, status
from pydantic import BaseModel

from rails.platform.injection import check_injection
from rails.platform.jailbreak import check_jailbreak
from rails.platform.cross_tenant import check_cross_tenant
from rails.tenant_overlay import TenantRailConfig, build_tenant_rail_config

# Lazy import: presidio_analyzer is only available inside the container image.
# At import time (e.g. in tests that don't call /validate), this is skipped.
try:
    from rails.platform.pii_detect import check_pii as _check_pii_impl
    _pii_available = True
except ImportError:
    _pii_available = False
    _check_pii_impl = None  # type: ignore[assignment]


def _check_pii(msg: str):
    if not _pii_available:
        return None  # PII detection unavailable — treat as no PII
    return _check_pii_impl(msg)  # type: ignore[misc]

logger = structlog.get_logger(__name__)

# ── Service token (loaded from env, which Vault populates) ─────────────────

_SERVICE_TOKEN: str = ""


def _load_service_token() -> str:
    token = os.environ.get("GUARDRAILS_SERVICE_TOKEN", "")
    if not token:
        logger.warning("guardrails.service_token_missing")
    return token


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    global _SERVICE_TOKEN
    _SERVICE_TOKEN = _load_service_token()
    logger.info("guardrails.ready")
    yield
    logger.info("guardrails.shutdown")


app = FastAPI(title="Baladiya Guardrails Sidecar", version="1.0.0", lifespan=lifespan)


# ── Schemas ────────────────────────────────────────────────────────────────

class GuardrailRequest(BaseModel):
    message: str
    tenant_id: str
    session_id: str
    tenant_rails: dict[str, Any] | None = None  # raw tenant.settings.guardrail_config


class GuardrailResponse(BaseModel):
    allowed: bool
    modified_message: str | None = None
    triggered_rail: str | None = None
    refusal_text: str | None = None


# ── Auth dependency ────────────────────────────────────────────────────────

def _verify_service_token(x_service_token: str = Header(default="")) -> None:
    if not _SERVICE_TOKEN:
        # Misconfiguration — fail closed
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service token not configured",
        )
    if x_service_token != _SERVICE_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid service token",
        )


# ── Routes ─────────────────────────────────────────────────────────────────

@app.get("/healthz", tags=["ops"])
async def healthz() -> dict:
    return {"status": "ok"}


@app.post("/validate", response_model=GuardrailResponse)
async def validate(
    body: GuardrailRequest,
    request: Request,
) -> GuardrailResponse:
    """Run all platform rails then tenant rails on the incoming message.

    Platform rails always run first and cannot be bypassed by tenant config.
    """
    _verify_service_token(request.headers.get("x-service-token", ""))

    msg = body.message
    log = logger.bind(tenant_id=body.tenant_id, session_id=body.session_id)

    # ── Platform rails (hardcoded, always on) ─────────────────────────────

    if check_injection(msg):
        log.warning("guardrails.injection_blocked")
        return GuardrailResponse(
            allowed=False,
            triggered_rail="injection",
            refusal_text="I'm unable to process that request.",
        )

    if check_jailbreak(msg):
        log.warning("guardrails.jailbreak_blocked")
        return GuardrailResponse(
            allowed=False,
            triggered_rail="jailbreak",
            refusal_text="I'm unable to process that request.",
        )

    if check_cross_tenant(msg):
        log.warning("guardrails.cross_tenant_blocked")
        return GuardrailResponse(
            allowed=False,
            triggered_rail="cross_tenant",
            refusal_text="I'm unable to process that request.",
        )

    # PII detection: flag but don't block — redaction happens in API middleware
    pii_result = _check_pii(msg)
    if pii_result is not None and pii_result.has_pii:
        log.info("guardrails.pii_detected", entity_types=pii_result.entity_types)

    # ── Tenant overlay rails ───────────────────────────────────────────────

    tenant_config: TenantRailConfig = build_tenant_rail_config(body.tenant_rails)

    if tenant_config.check_blocked_topic(msg):
        log.info("guardrails.topic_blocked", blocked_topics=tenant_config.blocked_topics)
        return GuardrailResponse(
            allowed=False,
            triggered_rail="topic",
            refusal_text=tenant_config.refusal_text(),
        )

    log.debug("guardrails.allowed")
    return GuardrailResponse(allowed=True)
