"""T-042: capture_request injection defense.

Verifies that a fabricated tenant_id in the tool payload is silently stripped
and the write always uses the tenant_id from the JWT token (context).
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.services.agent_service import AgentContext
from api.services.tools import capture_request as capture_tool


@pytest.mark.asyncio
async def test_fabricated_tenant_id_is_stripped():
    """Injected tenant_id in args must be ignored — write uses context.tenant_id."""
    real_tenant_id = uuid.uuid4()
    attacker_tenant_id = uuid.uuid4()

    captured_tenant: list[uuid.UUID] = []

    async def mock_repo_create(payload, session_id, visitor_phone_hash=None):
        return MagicMock(id=uuid.uuid4(), intent="report")

    mock_repo = AsyncMock()
    mock_repo.create = mock_repo_create

    def make_mock_repo(session, tenant_id):
        captured_tenant.append(tenant_id)
        return mock_repo

    context = AgentContext(
        tenant_id=real_tenant_id,
        session_id="sess-inject-test",
        db_session=AsyncMock(),
    )
    # Inject commit
    context.db_session.commit = AsyncMock()

    # Args include a fabricated tenant_id — must be stripped by the tool
    args = {
        "intent": "report",
        "description": "pothole on main st",
        "tenant_id": str(attacker_tenant_id),  # injection attempt
    }

    # Report path now requires a verified, non-blocked phone (verify feature).
    mock_blocked = MagicMock()
    mock_blocked.is_blocked = AsyncMock(return_value=False)

    with (
        patch("api.services.tools.capture_request.CaptureRequestRepository", side_effect=make_mock_repo),
        patch("api.services.tools.capture_request._check_rate_limit", new_callable=AsyncMock),
        patch("api.services.tools.capture_request.get_redis", return_value=MagicMock()),
        patch("api.services.otp_service.get_session_phone_hash", new=AsyncMock(return_value="phh")),
        patch("api.repositories.blocked_reporter_repo.BlockedReporterRepository", return_value=mock_blocked),
    ):
        result = await capture_tool.run(args, context)

    assert "error" not in result, f"Unexpected error: {result}"
    # The repo must have been constructed with real_tenant_id, not attacker_tenant_id
    assert len(captured_tenant) == 1
    assert captured_tenant[0] == real_tenant_id
    assert captured_tenant[0] != attacker_tenant_id


@pytest.mark.asyncio
async def test_malformed_payload_returns_tool_error():
    """A payload that fails Pydantic validation returns ToolError — no write."""
    real_tenant_id = uuid.uuid4()

    context = AgentContext(
        tenant_id=real_tenant_id,
        session_id="sess-invalid",
        db_session=AsyncMock(),
    )

    # Missing required 'description' field
    args = {"intent": "report"}

    with patch("api.services.tools.capture_request._check_rate_limit", new_callable=AsyncMock):
        result = await capture_tool.run(args, context)

    assert "error" in result
    # DB must NOT have been called
    context.db_session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_invalid_intent_returns_tool_error():
    """An invalid intent value fails Pydantic validation — no write."""
    context = AgentContext(
        tenant_id=uuid.uuid4(),
        session_id="sess-bad-intent",
        db_session=AsyncMock(),
    )

    args = {"intent": "delete_all_data", "description": "crafted payload"}

    with patch("api.services.tools.capture_request._check_rate_limit", new_callable=AsyncMock):
        result = await capture_tool.run(args, context)

    assert "error" in result
