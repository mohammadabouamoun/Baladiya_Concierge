"""Unit tests for the widget token service — origin validation + JWT signing."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest

# Widget tokens are signed with jwt_secret (same key decode_token uses) so the
# standard auth middleware validates them without a second key lookup.
_JWT_SECRET = "test-jwt-secret-32-chars-for-tests"
_TENANT_ID = uuid.uuid4()
_WIDGET_ID = uuid.uuid4()


def _fake_settings():
    s = MagicMock()
    s.jwt_secret = _JWT_SECRET
    s.jwt_algorithm = "HS256"
    s.widget_signing_key = "reserved-for-future-per-widget-rotation"
    return s


def _fake_widget(allowed_origins: list[str]):
    w = MagicMock()
    w.id = _WIDGET_ID
    w.tenant_id = _TENANT_ID
    w.allowed_origins = allowed_origins
    w.is_active = True
    return w


@pytest.mark.asyncio
async def test_issue_token_allowed_origin_succeeds():
    """issue_token returns a JWT signed with jwt_secret when origin is allowed."""
    fake_session = MagicMock()
    widget = _fake_widget(["https://municipality.gov", "https://www.municipality.gov"])

    with patch("api.api.widget.token_service.PlatformWidgetRepository") as MockRepo, \
         patch("api.api.widget.token_service.get_settings", return_value=_fake_settings()):
        MockRepo.return_value.get_by_widget_id = AsyncMock(return_value=widget)

        from api.api.widget.token_service import issue_token
        token = await issue_token(_WIDGET_ID, "https://municipality.gov", fake_session)

    assert isinstance(token, str)
    payload = jwt.decode(token, _JWT_SECRET, algorithms=["HS256"])
    assert payload["tenant_id"] == str(_TENANT_ID)
    assert payload["widget_id"] == str(_WIDGET_ID)
    assert payload["role"] == "visitor"
    assert "jti" in payload
    assert payload["exp"] > payload["iat"]


@pytest.mark.asyncio
async def test_issue_token_disallowed_origin_raises_403():
    """issue_token raises HTTPException 403 when origin is not allowed."""
    from fastapi import HTTPException
    fake_session = MagicMock()
    widget = _fake_widget(["https://allowed.gov"])

    with patch("api.api.widget.token_service.PlatformWidgetRepository") as MockRepo, \
         patch("api.api.widget.token_service.get_settings", return_value=_fake_settings()):
        MockRepo.return_value.get_by_widget_id = AsyncMock(return_value=widget)

        from api.api.widget.token_service import issue_token
        with pytest.raises(HTTPException) as exc_info:
            await issue_token(_WIDGET_ID, "https://evil.com", fake_session)

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_issue_token_origin_trailing_slash_normalized():
    """Trailing slash in origin is normalized before comparison."""
    fake_session = MagicMock()
    widget = _fake_widget(["https://municipality.gov"])

    with patch("api.api.widget.token_service.PlatformWidgetRepository") as MockRepo, \
         patch("api.api.widget.token_service.get_settings", return_value=_fake_settings()):
        MockRepo.return_value.get_by_widget_id = AsyncMock(return_value=widget)

        from api.api.widget.token_service import issue_token
        token = await issue_token(_WIDGET_ID, "https://municipality.gov/", fake_session)

    assert token is not None


@pytest.mark.asyncio
async def test_issue_token_widget_not_found_raises_404():
    """issue_token raises 404 when widget_id doesn't match any active widget."""
    from fastapi import HTTPException
    fake_session = MagicMock()

    with patch("api.api.widget.token_service.PlatformWidgetRepository") as MockRepo, \
         patch("api.api.widget.token_service.get_settings", return_value=_fake_settings()):
        MockRepo.return_value.get_by_widget_id = AsyncMock(return_value=None)

        from api.api.widget.token_service import issue_token
        with pytest.raises(HTTPException) as exc_info:
            await issue_token(uuid.uuid4(), "https://somewhere.gov", fake_session)

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_token_ttl_is_3600_seconds():
    """Widget tokens must expire in exactly 3600 seconds (1 hour) — FR-008."""
    fake_session = MagicMock()
    widget = _fake_widget(["https://municipality.gov"])

    with patch("api.api.widget.token_service.PlatformWidgetRepository") as MockRepo, \
         patch("api.api.widget.token_service.get_settings", return_value=_fake_settings()):
        MockRepo.return_value.get_by_widget_id = AsyncMock(return_value=widget)

        from api.api.widget.token_service import issue_token
        token = await issue_token(_WIDGET_ID, "https://municipality.gov", fake_session)

    payload = jwt.decode(token, _JWT_SECRET, algorithms=["HS256"])
    ttl = payload["exp"] - payload["iat"]
    assert ttl == 3600, f"Expected TTL 3600s, got {ttl}s"
