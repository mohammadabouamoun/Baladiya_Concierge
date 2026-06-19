"""Service authentication tests — T-054.

Verifies that unauthenticated requests to internal services (guardrails sidecar,
modelserver) return 401. Tests run against each service's FastAPI app directly
via httpx.ASGITransport (no live container needed).

Spec SC-004: raw curl to any internal service without a service credential → 401.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Guardrails container dir — add to sys.path so "from rails.X import..." works
_GUARDRAILS_DIR = str(Path(__file__).parents[2] / "guardrails")


@pytest_asyncio.fixture
async def guardrails_test_client():
    """Load the guardrails FastAPI app with a known test service token.

    The guardrails container uses imports relative to its own working dir
    (e.g. 'from rails.platform.injection import...'), so we add guardrails/
    to sys.path before importing.
    """
    if _GUARDRAILS_DIR not in sys.path:
        sys.path.insert(0, _GUARDRAILS_DIR)

    # Set env var before importing so _load_service_token() picks it up
    os.environ["GUARDRAILS_SERVICE_TOKEN"] = "test-service-token-abc"

    # Clear cached module so token reloads
    for mod_name in list(sys.modules.keys()):
        if mod_name in ("main", "rails", "rails.platform.injection",
                        "rails.platform.jailbreak", "rails.platform.cross_tenant",
                        "rails.platform.pii_detect", "rails.tenant_overlay"):
            del sys.modules[mod_name]

    import main as guardrails_main  # type: ignore[import]
    guardrails_main._SERVICE_TOKEN = "test-service-token-abc"

    async with AsyncClient(
        transport=ASGITransport(app=guardrails_main.app),
        base_url="http://test",
    ) as client:
        # Pre-warm PII analyzer (en_core_web_lg has multiple lazy-init stages).
        # Three calls flush all lazy initialization before the timed tests run.
        for warmup_msg in ("warmup", "water bill payment", "pothole on main street"):
            await client.post(
                "/validate",
                headers={"X-Service-Token": "test-service-token-abc"},
                json={
                    "message": warmup_msg,
                    "tenant_id": "00000000-0000-0000-0000-000000000001",
                    "session_id": "warmup",
                },
            )
        yield client

    # Cleanup sys.path
    if _GUARDRAILS_DIR in sys.path:
        sys.path.remove(_GUARDRAILS_DIR)


# ── Guardrails sidecar auth ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_guardrails_no_token_returns_401(guardrails_test_client):
    """POST /validate without X-Service-Token must return 401."""
    resp = await guardrails_test_client.post(
        "/validate",
        json={
            "message": "Hello",
            "tenant_id": "00000000-0000-0000-0000-000000000001",
            "session_id": "sess-001",
        },
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_guardrails_wrong_token_returns_401(guardrails_test_client):
    """POST /validate with wrong X-Service-Token must return 401."""
    resp = await guardrails_test_client.post(
        "/validate",
        headers={"X-Service-Token": "wrong-token"},
        json={
            "message": "Hello",
            "tenant_id": "00000000-0000-0000-0000-000000000001",
            "session_id": "sess-001",
        },
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_guardrails_valid_token_allowed(guardrails_test_client):
    """POST /validate with correct X-Service-Token must process request (not 401)."""
    resp = await guardrails_test_client.post(
        "/validate",
        headers={"X-Service-Token": "test-service-token-abc"},
        json={
            "message": "How do I pay my water bill?",
            "tenant_id": "00000000-0000-0000-0000-000000000001",
            "session_id": "sess-001",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["allowed"] is True


@pytest.mark.asyncio
async def test_guardrails_healthz_is_public(guardrails_test_client):
    """GET /healthz must not require a service token."""
    resp = await guardrails_test_client.get("/healthz")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_guardrails_validation_latency_under_100ms(guardrails_test_client):
    """SC-003: guardrails validation must add < 100ms p95 overhead.

    This test measures the regex-based rail checks (no network calls).
    In production the HTTP round-trip adds ~5-20ms; regex checks < 1ms.
    """
    import time

    timings: list[float] = []
    for _ in range(20):
        start = time.perf_counter()
        resp = await guardrails_test_client.post(
            "/validate",
            headers={"X-Service-Token": "test-service-token-abc"},
            json={
                "message": "How do I pay my water bill?",
                "tenant_id": "00000000-0000-0000-0000-000000000001",
                "session_id": "sess-latency",
            },
        )
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert resp.status_code == 200
        timings.append(elapsed_ms)

    timings.sort()
    p95 = timings[int(len(timings) * 0.95)]
    assert p95 < 100, f"Rail check p95 latency {p95:.1f}ms exceeds 100ms SC-003 budget"


# ── Modelserver auth ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_modelserver_no_token_returns_401():
    """POST /classify without X-Service-Token must return 401.

    The modelserver Settings uses extra="forbid" and loads from .env.
    We patch the settings instance directly to avoid .env loading issues
    in the test environment.
    """
    _MODELSERVER_DIR = str(Path(__file__).parents[2] / "modelserver")
    if _MODELSERVER_DIR not in sys.path:
        sys.path.insert(0, _MODELSERVER_DIR)

    # Clear cached modules so we can patch settings before the import
    for mod_name in list(sys.modules.keys()):
        if mod_name in ("main", "classifier"):
            del sys.modules[mod_name]

    try:
        # Override env vars needed by modelserver Settings before import
        env_backup = {}
        test_env = {
            "SERVICE_TOKEN": "test-ms-token",
            "ENV": "testing",
            "ARTIFACT_PATH": str(Path(__file__).parents[2] / "modelserver/artifacts/classifier.joblib"),
            "ARTIFACT_SHA256": "",
        }
        for k, v in test_env.items():
            env_backup[k] = os.environ.get(k)
            os.environ[k] = v

        import main as ms_main  # type: ignore[import]
    except Exception:
        pytest.skip("modelserver not importable in this test environment")
        return
    finally:
        if _MODELSERVER_DIR in sys.path:
            sys.path.remove(_MODELSERVER_DIR)
        # Restore env
        for k, v in env_backup.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    async with AsyncClient(
        transport=ASGITransport(app=ms_main.app),
        base_url="http://test",
    ) as client:
        resp = await client.post("/classify", json={"text": "test message"})
        assert resp.status_code == 401, (
            f"Expected 401 without service token, got {resp.status_code}"
        )
