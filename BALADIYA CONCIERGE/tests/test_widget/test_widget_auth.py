"""Widget auth CI gate tests — T-051, T-052, T-053.

All three denial cases required by SC-003:
  1. GET /widget/token with disallowed origin → 403
  2. POST /chat with no Authorization header → 401
  3. POST /chat with expired JWT → 401
"""
from __future__ import annotations

import time
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from api.core.config import Settings
from api.main import app

_WIDGET_SIGNING_KEY = "test-widget-signing-key-32chars!!"
_JWT_SECRET = "test-jwt-secret-for-widget-tests!"
_TENANT_ID = uuid.uuid4()
_WIDGET_ID = uuid.uuid4()


@pytest.fixture(autouse=True)
def patch_settings():
    fake = Settings.model_construct(
        env="testing",
        vault_addr="http://localhost:8200",
        vault_token="dev-root-token",
        jwt_secret=_JWT_SECRET,
        jwt_algorithm="HS256",
        jwt_expire_minutes=60,
        widget_token_expire_minutes=60,
        widget_signing_key=_WIDGET_SIGNING_KEY,
        database_url="postgresql+asyncpg://baladiya:baladiya_dev@localhost:5432/baladiya_test",
        redis_url="redis://localhost:6379/0",
        minio_endpoint="localhost:9000",
        minio_access_key="",
        minio_secret_key="",
        gemini_api_key="",
        groq_api_key="",
        guardrails_url="http://guardrails:8002",
        modelserver_url="http://modelserver:8001",
        guardrails_service_token="",
        modelserver_service_token="",
        default_requests_per_minute=60,
        capture_requests_per_minute=5,
        classifier_confidence_thresholds={"report": 0.75, "question": 0.75, "human": 0.65, "spam": 0.90},
        max_tool_calls=3,
        max_tokens_per_turn=4096,
        chunk_max_chars=2048,
        chunk_min_chars=400,
        chunk_overlap_chars=200,
        rag_top_k=5,
        embedding_model="gemini-embedding-001",
        embedding_dimensions=1536,
    )
    from api.core.config import get_settings
    get_settings.cache_clear()
    with patch("api.core.config.get_settings", return_value=fake), \
         patch("api.core.security.get_settings", return_value=fake), \
         patch("api.api.widget.token_service.get_settings", return_value=fake):
        yield fake
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


def _make_visitor_jwt(*, expired: bool = False) -> str:
    now = int(time.time())
    exp = now - 10 if expired else now + 3600
    claims = {
        "sub": str(uuid.uuid4()),
        "role": "visitor",
        "tenant_id": str(_TENANT_ID),
        "widget_id": str(_WIDGET_ID),
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": exp,
    }
    return jwt.encode(claims, _JWT_SECRET, algorithm="HS256")


# ── T-051: disallowed origin → 403 ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_widget_token_disallowed_origin_returns_403():
    """SC-003 case 1: GET /widget/token with origin not in allowed_origins → 403.

    Uses FastAPI dependency override to inject a mock session (no live DB).
    """
    from api.api.widget.router import _unscoped_db

    fake_widget = MagicMock()
    fake_widget.id = _WIDGET_ID
    fake_widget.tenant_id = _TENANT_ID
    fake_widget.allowed_origins = ["https://allowed.gov"]
    fake_widget.is_active = True

    mock_session = MagicMock()

    async def _mock_db():
        yield mock_session

    app.dependency_overrides[_unscoped_db] = _mock_db

    try:
        with patch(
            "api.api.widget.token_service.PlatformWidgetRepository"
        ) as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_by_widget_id = AsyncMock(return_value=fake_widget)

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as c:
                resp = await c.get(
                    "/widget/token",
                    params={
                        "widget_id": str(_WIDGET_ID),
                        "origin": "https://evil.com",
                    },
                )
    finally:
        app.dependency_overrides.pop(_unscoped_db, None)

    assert resp.status_code == 403, (
        f"Expected 403 for disallowed origin, got {resp.status_code}: {resp.text}"
    )


# ── T-052: no Authorization header → 401 ───────────────────────────────────

@pytest.mark.asyncio
async def test_chat_no_token_returns_401(client):
    """SC-003 case 2: POST /chat without Authorization header → 401."""
    resp = await client.post(
        "/chat",
        json={"session_id": "sess-test", "message": "Hello"},
    )
    assert resp.status_code == 401, (
        f"Expected 401 for missing token, got {resp.status_code}: {resp.text}"
    )


# ── T-053: expired JWT → 401 ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_chat_expired_token_returns_401(client):
    """SC-003 case 3: POST /chat with expired JWT → 401."""
    expired_token = _make_visitor_jwt(expired=True)
    resp = await client.post(
        "/chat",
        headers={"Authorization": f"Bearer {expired_token}"},
        json={"session_id": "sess-test", "message": "Hello"},
    )
    assert resp.status_code == 401, (
        f"Expected 401 for expired token, got {resp.status_code}: {resp.text}"
    )


# ── Extra: malformed token → 401 ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_chat_malformed_token_returns_401(client):
    """POST /chat with a garbage token → 401."""
    resp = await client.post(
        "/chat",
        headers={"Authorization": "Bearer not.a.real.jwt"},
        json={"session_id": "sess-test", "message": "Hello"},
    )
    assert resp.status_code == 401, (
        f"Expected 401 for malformed token, got {resp.status_code}: {resp.text}"
    )
