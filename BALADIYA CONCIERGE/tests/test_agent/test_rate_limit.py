"""T-044: Per-session capture_request rate limit.

Verifies that exceeding capture_requests_per_minute returns a 429-equivalent
ToolError and prevents any DB write.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from api.services.agent_service import AgentContext
from api.services.tools import capture_request as capture_tool
from api.services.tools.capture_request import _check_rate_limit


@pytest.mark.asyncio
async def test_rate_limit_blocks_after_limit_exceeded():
    """After limit is exceeded, capture_request returns a 429 error dict, no write."""
    session_id = "test-rate-limit-session"
    tenant_id = uuid.uuid4()

    context = AgentContext(
        tenant_id=tenant_id,
        session_id=session_id,
        db_session=AsyncMock(),
    )

    call_count = 0
    mock_repo_instance = AsyncMock()
    mock_repo_instance.create = AsyncMock(return_value=MagicMock(id=uuid.uuid4(), intent="report"))
    context.db_session.commit = AsyncMock()

    args = {"intent": "report", "description": "test report"}

    settings_obj = MagicMock()
    settings_obj.capture_requests_per_minute = 2

    # Simulate: first call increments to 1, second to 2, third to 3 (> limit=2)
    counter = [0]

    async def mock_incr(key):
        counter[0] += 1
        return counter[0]

    mock_redis = MagicMock()
    mock_redis.incr = AsyncMock(side_effect=mock_incr)
    mock_redis.expire = AsyncMock()

    # Report path now requires a verified phone (verify feature) — mock it as verified
    # and not blocked so the rate-limit behaviour is what's under test.
    mock_blocked = MagicMock()
    mock_blocked.is_blocked = AsyncMock(return_value=False)

    with (
        patch("api.services.tools.capture_request.CaptureRequestRepository", return_value=mock_repo_instance),
        patch("api.services.tools.capture_request.get_settings", return_value=settings_obj),
        patch("api.services.tools.capture_request.get_redis", return_value=mock_redis),
        patch("api.services.otp_service.get_session_phone_hash", new=AsyncMock(return_value="phh")),
        patch("api.repositories.blocked_reporter_repo.BlockedReporterRepository", return_value=mock_blocked),
    ):
        # First two succeed
        result1 = await capture_tool.run(args.copy(), context)
        result2 = await capture_tool.run(args.copy(), context)
        # Third exceeds limit
        result3 = await capture_tool.run(args.copy(), context)

    # First two should succeed
    assert "error" not in result1, f"First call should succeed: {result1}"
    assert "error" not in result2, f"Second call should succeed: {result2}"

    # Third should be rate-limited
    assert "error" in result3
    assert "429" in str(result3.get("status_code", "")) or "Rate limit" in str(result3.get("error", ""))

    # DB write was only called twice (not three times)
    assert mock_repo_instance.create.call_count == 2


@pytest.mark.asyncio
async def test_rate_limit_key_includes_session_and_tenant():
    """Rate-limit key must embed both session_id and tenant_id to prevent cross-session bleed."""
    session_id = "sess-rl-1"
    tenant_id = uuid.uuid4()

    used_keys: list[str] = []

    async def mock_incr(key):
        used_keys.append(key)
        return 1

    mock_redis = MagicMock()
    mock_redis.incr = AsyncMock(side_effect=mock_incr)
    mock_redis.expire = AsyncMock()

    settings_obj = MagicMock()
    settings_obj.capture_requests_per_minute = 100

    with (
        patch("api.services.tools.capture_request.get_redis", return_value=mock_redis),
        patch("api.services.tools.capture_request.get_settings", return_value=settings_obj),
    ):
        await _check_rate_limit(session_id, tenant_id)

    assert len(used_keys) == 1
    key = used_keys[0]
    assert session_id in key
    assert str(tenant_id) in key
