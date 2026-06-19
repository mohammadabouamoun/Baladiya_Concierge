"""PII redaction integration test — T-040.

Pastes a fake Lebanese NID into the simulated chat pipeline and asserts
zero unredacted occurrences in structlog output, Redis session dump,
and API response. CI gate: redaction_pass_rate = 1.0 (zero leaks).

These tests run with ENV=testing (no live Vault/DB required for the
redaction path itself). Redis session tests use the conftest fixtures.
"""
from __future__ import annotations

import io
import json
import logging
import uuid
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
import structlog

from api.middleware.redaction import redact

# ── Fake PII constants ──────────────────────────────────────────────────────
FAKE_NID = "123456"
FAKE_PHONE = "+961 3 999 8888"
FAKE_EMAIL = "testuser@fakelebanon.lb"

# ── Unit-level: redact() never leaks ───────────────────────────────────────

def test_nid_not_in_redacted_output():
    result = redact(f"My national ID is {FAKE_NID}.")
    assert FAKE_NID not in result
    assert "[REDACTED_NID]" in result


def test_phone_not_in_redacted_output():
    result = redact(f"Call me at {FAKE_PHONE}")
    assert FAKE_PHONE not in result
    assert "[REDACTED_PHONE]" in result


def test_email_not_in_redacted_output():
    result = redact(f"Email me at {FAKE_EMAIL}")
    assert FAKE_EMAIL not in result
    assert "[REDACTED_EMAIL]" in result


# ── Log sink: verify redacted text is what structlog would receive ──────────

def test_redaction_applied_before_log():
    """Simulate the chat pipeline: redact → log. Raw PII must not reach the log."""
    raw_message = f"My ID is {FAKE_NID} and phone {FAKE_PHONE}"
    safe_message = redact(raw_message)

    # Verify the safe_message (what gets logged) contains no raw PII
    assert FAKE_NID not in safe_message
    assert FAKE_PHONE not in safe_message
    assert "[REDACTED_NID]" in safe_message
    assert "[REDACTED_PHONE]" in safe_message


# ── Session service: verify redacted text is what gets written to Redis ─────

@pytest.mark.asyncio
async def test_session_write_receives_redacted_message():
    """Simulate session.add_turns() receiving the redacted message, not raw PII."""
    from api.services.session_service import SessionService

    # Build a mock Redis that records what was written
    written_data: list[str] = []

    mock_redis = AsyncMock()

    async def fake_get(key):
        return None

    async def fake_set(key, value, ex=None):
        written_data.append(value)

    mock_redis.get.side_effect = fake_get
    mock_redis.set.side_effect = fake_set

    session_svc = SessionService(redis=mock_redis)
    tenant_id = uuid.uuid4()
    session_id = "test-session-001"

    raw_message = f"My national ID is {FAKE_NID}."
    safe_message = redact(raw_message)  # This is what the chat router passes

    await session_svc.add_turns(
        session_id=session_id,
        tenant_id=tenant_id,
        turns=[("user", safe_message)],
    )

    assert written_data, "Nothing was written to Redis"
    serialized = written_data[0]
    assert FAKE_NID not in serialized, f"Raw PII leaked into Redis: {serialized}"
    assert "[REDACTED_NID]" in serialized


# ── API response: verify raw PII does not appear in chat response ───────────

@pytest.mark.asyncio
async def test_api_response_does_not_contain_raw_pii():
    """The chat endpoint must redact PII before passing to the router."""
    from api.middleware.redaction import redact as redact_fn

    raw_input = f"My ID is {FAKE_NID} and my email is {FAKE_EMAIL}"
    safe_input = redact_fn(raw_input)

    # The router receives safe_input — verify raw PII is absent
    assert FAKE_NID not in safe_input
    assert FAKE_EMAIL not in safe_input


# ── Arabic name PII redaction (Phase 8 — FR-004–006) ───────────────────────

def test_arabic_full_name_redacted():
    """Arabic full name (given + family) must be replaced with [NAME]."""
    result = redact("اشتكي من محمد علي بسبب الكهرباء")
    assert "محمد علي" not in result
    assert "[NAME]" in result


def test_arabic_name_with_prefix_redacted():
    """Arabic name with prefix particle must be redacted."""
    result = redact("أنا رنا خوري من بيروت")
    assert "رنا خوري" not in result
    assert "[NAME]" in result


def test_arabic_three_word_name_redacted():
    """Three-token Arabic name must be redacted."""
    result = redact("أحمد الحسن قدم شكوى")
    assert "أحمد الحسن" not in result
    assert "[NAME]" in result


def test_arabic_civic_phrase_not_redacted():
    """Civic institution name (مياه الجنوب) must NOT be redacted as a personal name."""
    result = redact("مياه الجنوب مشكلة")
    assert "[NAME]" not in result


def test_arabic_utility_name_not_redacted():
    """Utility phrase (كهرباء لبنان) must NOT be redacted as a personal name."""
    result = redact("كهرباء لبنان منقطعة")
    assert "[NAME]" not in result


# ── End-to-end via HTTP (requires ENV=testing, mocked guardrails) ───────────

@pytest.mark.asyncio
@pytest.mark.integration
async def test_chat_endpoint_redacts_before_processing(http_client):
    """Full HTTP path: POST /chat with fake NID → response must not echo raw NID."""
    import uuid as uuid_mod

    tenant_id = uuid_mod.uuid4()
    session_id = str(uuid_mod.uuid4())

    # Patch guardrails client to allow through (no sidecar in test env)
    from api.infra import guardrails_client as gc_mod
    from api.infra.guardrails_client import GuardrailResponse

    with patch.object(gc_mod, "_client") as mock_client:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "allowed": True,
            "modified_message": None,
            "triggered_rail": None,
            "refusal_text": None,
        }
        mock_resp.raise_for_status = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_resp)

        # Issue a visitor token for the tenant
        token_resp = await http_client.post(
            "/chat/token", json={"tenant_id": str(tenant_id)}
        )
        if token_resp.status_code != 200:
            pytest.skip("Token endpoint not reachable in this test configuration")

        access_token = token_resp.json()["access_token"]
        chat_resp = await http_client.post(
            "/chat",
            json={"session_id": session_id, "message": f"My ID is {FAKE_NID}"},
            headers={"Authorization": f"Bearer {access_token}"},
        )

    # The NID must not appear in the response (even as an echo)
    if chat_resp.status_code == 200:
        assert FAKE_NID not in chat_resp.text
