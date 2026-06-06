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


# ── Per-widget key rotation tests (Phase 8 — FR-007–011) ───────────────────

_WIDGET_A_KEY = "widget-a-signing-key-32-chars-xx"
_WIDGET_B_KEY = "widget-b-signing-key-32-chars-yy"
_WIDGET_B_ID = uuid.uuid4()


def _issue_raw_token(widget_id: uuid.UUID, tenant_id: uuid.UUID, key: str) -> str:
    """Helper: mint a widget JWT signed with the given key."""
    import time
    now = int(time.time())
    return jwt.encode(
        {"sub": str(uuid.uuid4()), "jti": str(uuid.uuid4()),
         "tenant_id": str(tenant_id), "widget_id": str(widget_id),
         "role": "visitor", "iat": now, "exp": now + 3600},
        key, algorithm="HS256",
    )


def test_rotate_key_invalidates_old_token():
    """A token signed with the old key must be rejected after key rotation."""
    from api.core.security import decode_token
    import api.infra.vault as vault_mod

    old_key = _WIDGET_A_KEY
    new_key = "new-widget-a-key-32-chars-replace"

    old_token = _issue_raw_token(_WIDGET_ID, _TENANT_ID, old_key)

    with patch("api.core.security.get_settings", return_value=_fake_settings()):
        # Before rotation: cache returns old key → decode succeeds
        vault_mod._widget_key_cache[str(_WIDGET_ID)] = (old_key, float("inf"))
        claims = decode_token(old_token)
        assert str(claims.widget_id) == str(_WIDGET_ID)

        # Rotation: cache now holds new key
        vault_mod._widget_key_cache[str(_WIDGET_ID)] = (new_key, float("inf"))

        # Old token should now be rejected (wrong signature for new key)
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            decode_token(old_token)
        assert exc_info.value.status_code == 401


def test_rotate_key_does_not_affect_other_widget():
    """Rotating widget A's key must not invalidate widget B's tokens."""
    from api.core.security import decode_token
    import api.infra.vault as vault_mod

    token_b = _issue_raw_token(_WIDGET_B_ID, _TENANT_ID, _WIDGET_B_KEY)

    with patch("api.core.security.get_settings", return_value=_fake_settings()):
        # Seed both caches
        vault_mod._widget_key_cache[str(_WIDGET_ID)] = (_WIDGET_A_KEY, float("inf"))
        vault_mod._widget_key_cache[str(_WIDGET_B_ID)] = (_WIDGET_B_KEY, float("inf"))

        # Rotate widget A: update its cache entry
        vault_mod._widget_key_cache[str(_WIDGET_ID)] = ("rotated-key-for-a-32-chars-xxxxx", float("inf"))

        # Widget B's token must still decode successfully
        claims_b = decode_token(token_b)
        assert str(claims_b.widget_id) == str(_WIDGET_B_ID)


def test_non_widget_token_unaffected():
    """A tenant_admin JWT (no widget_id claim) must validate via jwt_secret after rotation."""
    from api.core.security import decode_token
    import api.infra.vault as vault_mod
    import time

    now = int(time.time())
    admin_token = jwt.encode(
        {"sub": str(uuid.uuid4()), "jti": str(uuid.uuid4()),
         "tenant_id": str(_TENANT_ID), "role": "tenant_admin",
         "iat": now, "exp": now + 3600},
        _JWT_SECRET, algorithm="HS256",
    )

    with patch("api.core.security.get_settings", return_value=_fake_settings()):
        # Rotate a widget key (should not affect admin token)
        vault_mod._widget_key_cache[str(_WIDGET_ID)] = ("some-rotated-key-32-chars-xxxxxx", float("inf"))

        # Admin token must still decode with jwt_secret
        claims = decode_token(admin_token)
        assert claims.role == "tenant_admin"
        assert claims.widget_id is None
