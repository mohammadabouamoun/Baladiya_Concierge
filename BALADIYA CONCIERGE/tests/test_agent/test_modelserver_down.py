"""E3: Modelserver-down graceful degradation — spec edge case.

When the modelserver is unreachable, POST /chat must return 503 with a
user-friendly message and no raw stack trace.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient, RequestError

from api.main import app


@pytest.mark.asyncio
async def test_chat_returns_503_when_modelserver_down(monkeypatch):
    """modelserver RequestError → 503 Service Unavailable (no 500, no traceback)."""
    from api.core.config import get_settings

    # Use testing env to skip Vault
    monkeypatch.setenv("ENV", "testing")
    get_settings.cache_clear()

    async def mock_classify(_text):
        raise RequestError("Connection refused")

    with (
        patch("api.infra.modelserver_client.classify", side_effect=mock_classify),
        patch("api.infra.db.get_session_factory") as mock_factory,
        patch("api.infra.redis.get_redis") as mock_redis,
    ):
        mock_session = AsyncMock()
        mock_factory.return_value = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_session),
            __aexit__=AsyncMock(return_value=None),
        ))
        mock_redis.return_value = AsyncMock()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            import jwt as pyjwt
            from datetime import datetime, timedelta, timezone
            settings = get_settings()
            token = pyjwt.encode(
                {
                    "sub": str(uuid.uuid4()),
                    "role": "visitor",
                    "tenant_id": str(uuid.uuid4()),
                    "exp": datetime.now(timezone.utc) + timedelta(hours=1),
                },
                settings.jwt_secret,
                algorithm=settings.jwt_algorithm,
            )

            resp = await client.post(
                "/chat",
                json={"session_id": "test-session", "message": "pothole on main st"},
                headers={"Authorization": f"Bearer {token}"},
            )

    assert resp.status_code == 503
    body = resp.json()
    assert "temporarily unavailable" in body.get("detail", "").lower()

    # Cleanup
    get_settings.cache_clear()
