"""T-040: CI classifier gate.

Loads held-out test rows from civic_intent_dataset.csv,
classifies each via the modelserver HTTP endpoint,
and asserts macro-F1 >= eval_thresholds.yaml → classifier_macro_f1.

Requires a running modelserver — marked 'integration'.
Run with: pytest tests/test_classifier/test_classifier_gate.py -m integration
"""
from __future__ import annotations

import csv
import hashlib
import os
from pathlib import Path

import pytest
import yaml
from sklearn.metrics import f1_score

REPO_ROOT = Path(__file__).parents[2]
CSV_PATH = REPO_ROOT / "civic_intent_dataset.csv"
THRESHOLDS_PATH = REPO_ROOT / "eval_thresholds.yaml"
MODELSERVER_URL = os.getenv("MODELSERVER_URL", "http://localhost:8001")
SERVICE_TOKEN = os.getenv("MODELSERVER_SERVICE_TOKEN", "")


def _load_thresholds() -> dict:
    with open(THRESHOLDS_PATH) as f:
        return yaml.safe_load(f)


def _load_test_split() -> list[dict]:
    rows = []
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["split"] == "test":
                rows.append(row)
    return rows


@pytest.fixture(scope="module")
def test_rows():
    return _load_test_split()


@pytest.fixture(scope="module")
def thresholds():
    return _load_thresholds()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_classifier_macro_f1(test_rows, thresholds):
    """Macro-F1 on held-out test must meet the threshold in eval_thresholds.yaml."""
    import httpx

    if not test_rows:
        pytest.skip("No test rows found in CSV")

    threshold = thresholds.get("classifier_macro_f1", 0.0)
    if threshold == 0.0:
        pytest.skip("classifier_macro_f1 threshold is 0.0 (placeholder) — set a real value after training")

    y_true = []
    y_pred = []
    headers = {"X-Service-Token": SERVICE_TOKEN} if SERVICE_TOKEN else {}

    async with httpx.AsyncClient(base_url=MODELSERVER_URL, headers=headers, timeout=10.0) as client:
        for row in test_rows:
            resp = await client.post("/classify", json={"text": row["text"]})
            assert resp.status_code == 200, f"modelserver returned {resp.status_code} for: {row['text'][:60]}"
            y_pred.append(resp.json()["intent"])
            y_true.append(row["intent"])

    macro_f1 = f1_score(y_true, y_pred, average="macro")

    # Per-language F1
    en_indices = [i for i, r in enumerate(test_rows) if r["lang"] == "en"]
    ar_indices  = [i for i, r in enumerate(test_rows) if r["lang"] == "ar"]

    en_f1 = f1_score(
        [y_true[i] for i in en_indices], [y_pred[i] for i in en_indices], average="macro"
    ) if en_indices else None
    ar_f1 = f1_score(
        [y_true[i] for i in ar_indices], [y_pred[i] for i in ar_indices], average="macro"
    ) if ar_indices else None

    print(f"\nClassifier CI Gate Results:")
    print(f"  Macro-F1: {macro_f1:.4f}  (threshold: {threshold})")
    print(f"  EN F1:    {en_f1:.4f}" if en_f1 is not None else "  EN F1: N/A")
    print(f"  AR F1:    {ar_f1:.4f}" if ar_f1 is not None else "  AR F1: N/A (no AR test rows)")

    # Per-variety F1
    for variety in ["en", "msa", "lebanese", "arabizi"]:
        idx = [i for i, r in enumerate(test_rows) if r.get("variety") == variety]
        if len(idx) >= 2:
            vf1 = f1_score([y_true[i] for i in idx], [y_pred[i] for i in idx], average="macro")
            print(f"  {variety} F1: {vf1:.4f}")

    assert macro_f1 >= threshold, (
        f"Classifier macro-F1 {macro_f1:.4f} is below threshold {threshold}. "
        "Retrain or lower the threshold in eval_thresholds.yaml with justification."
    )

    en_threshold = thresholds.get("en_macro_f1", 0.0)
    if en_threshold > 0.0 and en_f1 is not None:
        assert en_f1 >= en_threshold, f"EN macro-F1 {en_f1:.4f} < threshold {en_threshold}"
