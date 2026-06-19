"""T-052: Unit tests for Redis sliding-window rate limiter (mock Redis)."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from api.core.security import TokenClaims
from api.infra.rate_limit import rate_limit


def _make_request(path: str = "/test") -> MagicMock:
    req = MagicMock()
    req.url.path = path
    return req


def _make_token(tenant_id: uuid.UUID | None = None) -> TokenClaims:
    return TokenClaims(
        user_id=uuid.uuid4(),
        role="tenant_admin" if tenant_id else "platform_manager",
        tenant_id=tenant_id,
    )


@pytest.mark.asyncio
async def test_rate_limit_platform_manager_not_limited():
    """Platform Manager requests bypass rate limiting."""
    token = _make_token(tenant_id=None)
    req = _make_request()
    # Should not raise — no Redis calls needed
    with patch("api.infra.rate_limit.get_redis") as mock_get_redis:
        await rate_limit(req, token)
        mock_get_redis.assert_not_called()


@pytest.mark.asyncio
async def test_rate_limit_allows_under_limit():
    """Requests under the limit pass through."""
    tenant_id = uuid.uuid4()
    token = _make_token(tenant_id=tenant_id)
    req = _make_request()

    # pipeline() is called synchronously; only execute() is awaited
    mock_pipeline = MagicMock()
    mock_pipeline.execute = AsyncMock(return_value=[None, None, 10, None])
    mock_redis = MagicMock()
    mock_redis.pipeline.return_value = mock_pipeline

    with patch("api.infra.rate_limit.get_redis", return_value=mock_redis):
        await rate_limit(req, token)  # must not raise


@pytest.mark.asyncio
async def test_rate_limit_blocks_over_limit():
    """Requests over the limit get a 429."""
    tenant_id = uuid.uuid4()
    token = _make_token(tenant_id=tenant_id)
    req = _make_request()

    mock_pipeline = MagicMock()
    mock_pipeline.execute = AsyncMock(return_value=[None, None, 61, None])
    mock_redis = MagicMock()
    mock_redis.pipeline.return_value = mock_pipeline

    with patch("api.infra.rate_limit.get_redis", return_value=mock_redis):
        with pytest.raises(HTTPException) as exc_info:
            await rate_limit(req, token)
        assert exc_info.value.status_code == 429
