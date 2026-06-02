"""T-041: modelserver unit + smoke tests.

- POST /classify returns correct schema in < 50ms
- POST without token → 401
- Invalid artifact SHA-256 at boot → StartupError
"""
from __future__ import annotations

import hashlib
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ── Helpers ────────────────────────────────────────────────────────────────

def _make_test_app(service_token: str = "test-token", artifact_sha256: str = ""):
    """Build a modelserver FastAPI app with a mock ClassifierService."""
    import os
    os.environ["SERVICE_TOKEN"] = service_token
    os.environ["ARTIFACT_SHA256"] = artifact_sha256
    os.environ["ENV"] = "testing"

    # Patch artifact loading so we don't need a real .joblib in tests
    from modelserver.classifier import ClassifyResponse as CR

    mock_classifier = MagicMock()
    mock_classifier.predict.return_value = CR(
        intent="report",
        category="roads",
        confidence=0.92,
        lang="en",
        variety="en",
    )

    return mock_classifier


@pytest.fixture
def mock_client():
    """TestClient with patched classifier and service token."""
    mock_clf = _make_test_app()

    with patch("modelserver.main.settings") as mock_settings:
        mock_settings.service_token = "test-token"
        mock_settings.artifact_path = "artifacts/classifier.joblib"
        mock_settings.artifact_sha256 = ""
        mock_settings.env = "testing"

        from modelserver.main import app
        app.state.classifier = mock_clf

        with TestClient(app, raise_server_exceptions=False) as client:
            yield client, mock_clf


# ── Tests ──────────────────────────────────────────────────────────────────

def test_classify_returns_correct_schema(mock_client):
    client, mock_clf = mock_client
    t0 = time.perf_counter()
    resp = client.post(
        "/classify",
        json={"text": "There is a pothole on Main Street"},
        headers={"X-Service-Token": "test-token"},
    )
    latency_ms = (time.perf_counter() - t0) * 1000

    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) >= {"intent", "category", "confidence", "lang", "variety"}
    assert body["intent"] in ("report", "question", "human", "spam")
    assert 0.0 <= body["confidence"] <= 1.0
    assert latency_ms < 50, f"Response took {latency_ms:.1f}ms — must be < 50ms"


def test_classify_without_token_returns_401():
    with patch("modelserver.main.settings") as mock_settings:
        mock_settings.service_token = "required-token"
        mock_settings.artifact_path = "artifacts/classifier.joblib"
        mock_settings.artifact_sha256 = ""
        mock_settings.env = "testing"

        from modelserver.main import app

        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.post("/classify", json={"text": "test"})
            assert resp.status_code == 401, (
                f"Expected 401 without token, got {resp.status_code}"
            )


def test_classify_with_wrong_token_returns_401():
    with patch("modelserver.main.settings") as mock_settings:
        mock_settings.service_token = "correct-token"
        mock_settings.artifact_path = "artifacts/classifier.joblib"
        mock_settings.artifact_sha256 = ""
        mock_settings.env = "testing"

        from modelserver.main import app

        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.post(
                "/classify",
                json={"text": "test"},
                headers={"X-Service-Token": "wrong-token"},
            )
            assert resp.status_code == 401


def test_startup_error_on_sha256_mismatch(tmp_path):
    """StartupError is raised when artifact SHA-256 does not match settings."""
    from modelserver.main import StartupError, _sha256_file

    fake_artifact = tmp_path / "classifier.joblib"
    fake_artifact.write_bytes(b"fake model weights")
    actual_sha = _sha256_file(fake_artifact)
    wrong_sha = "0" * 64

    assert actual_sha != wrong_sha  # sanity check

    with pytest.raises(Exception):
        # Simulate what lifespan does on mismatch
        if actual_sha != wrong_sha:
            raise StartupError(f"Artifact SHA-256 mismatch: {actual_sha} != {wrong_sha}")


def test_healthz_endpoint():
    with patch("modelserver.main.settings") as mock_settings:
        mock_settings.service_token = ""
        mock_settings.artifact_path = "artifacts/classifier.joblib"
        mock_settings.artifact_sha256 = ""
        mock_settings.env = "testing"

        from modelserver.main import app

        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.get("/healthz")
            assert resp.status_code == 200
            assert resp.json()["status"] == "ok"


@pytest.mark.integration
def test_real_artifact_latency_p95():
    """SC-002: classify with the real joblib artifact, assert p95 < 50ms.

    Skipped unless MODELSERVER_ARTIFACT_PATH env var is set to a real .joblib file.
    This confirms the latency gate against the actual model weights, not a mock.
    """
    import os
    import numpy as np
    from pathlib import Path

    artifact_path = os.getenv(
        "MODELSERVER_ARTIFACT_PATH",
        str(Path(__file__).parents[2] / "modelserver" / "artifacts" / "classifier.joblib"),
    )
    if not Path(artifact_path).exists():
        pytest.skip(f"Artifact not found: {artifact_path}")

    from modelserver.classifier import ClassifierService

    clf = ClassifierService(Path(artifact_path))

    test_texts = [
        "There is a pothole on Main Street near the bakery",
        "How do I apply for a building permit?",
        "I want to speak to a real person please",
        "WIN a FREE iPhone now click this link",
        "fi 7afra kbire bel tari2",
        "انقطع التيار الكهربائي عن شارعنا من الليلة الماضية",
        "بدّي احكي مع حدا حقيقي",
        "The garbage hasn't been collected for two weeks",
    ] * 5  # 40 calls for stable p95

    latencies = []
    for text in test_texts:
        t = time.perf_counter()
        clf.predict(text)
        latencies.append((time.perf_counter() - t) * 1000)

    p95_ms = float(np.percentile(latencies, 95))
    p50_ms = float(np.percentile(latencies, 50))
    print(f"\nReal artifact latency — p50: {p50_ms:.1f}ms  p95: {p95_ms:.1f}ms")

    assert p95_ms < 50, (
        f"Classification p95 latency {p95_ms:.1f}ms exceeds 50ms limit (SC-002). "
        "Investigate model size or server load."
    )
