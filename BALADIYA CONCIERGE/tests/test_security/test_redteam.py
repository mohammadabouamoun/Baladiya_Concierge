"""Red-team CI gate — T-051.

Loads all probes from evals/redteam_probes.json and tests them against
the guardrails rail logic. All probes with expected_outcome="refused" must
be refused. Any passing probe fails the build.

CI gate: redteam_pass_rate: 1.0 (eval_thresholds.yaml)
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from guardrails.rails.platform.injection import check_injection
from guardrails.rails.platform.jailbreak import check_jailbreak
from guardrails.rails.platform.cross_tenant import check_cross_tenant

PROBES_PATH = Path(__file__).parents[2] / "evals" / "redteam_probes.json"


def _load_probes():
    with open(PROBES_PATH) as f:
        return json.load(f)


def _is_refused(message: str) -> tuple[bool, str | None]:
    """Run platform rails and return (refused, triggered_rail)."""
    if check_injection(message):
        return True, "injection"
    if check_jailbreak(message):
        return True, "jailbreak"
    if check_cross_tenant(message):
        return True, "cross_tenant"
    return False, None


# Parametrize over all probes — each probe is a separate test case
_probes = _load_probes()


@pytest.mark.parametrize(
    "probe",
    [p for p in _probes if p["expected_outcome"] == "refused"],
    ids=[p["id"] for p in _probes if p["expected_outcome"] == "refused"],
)
def test_probe_is_refused(probe):
    """Every red-team probe must be refused by the platform rails."""
    refused, triggered = _is_refused(probe["input"])
    assert refused, (
        f"PROBE {probe['id']} PASSED — build must fail.\n"
        f"Description: {probe['description']}\n"
        f"Input: {probe['input']!r}\n"
        f"Expected: refused by {probe.get('triggered_rail', 'any rail')}"
    )


@pytest.mark.parametrize(
    "probe",
    [p for p in _probes if p["expected_outcome"] == "allowed"],
    ids=[p["id"] for p in _probes if p["expected_outcome"] == "allowed"],
)
def test_legitimate_probe_passes(probe):
    """Legitimate civic requests must NOT be refused by platform rails."""
    refused, triggered = _is_refused(probe["input"])
    assert not refused, (
        f"PROBE {probe['id']} FALSELY REFUSED — false positive.\n"
        f"Description: {probe['description']}\n"
        f"Input: {probe['input']!r}\n"
        f"Triggered rail: {triggered}"
    )


def test_all_refused_probes_covered():
    """Verify the probe set has at least 12 refused probes (spec minimum)."""
    refused_probes = [p for p in _probes if p["expected_outcome"] == "refused"]
    assert len(refused_probes) >= 12, (
        f"Only {len(refused_probes)} refused probes — spec requires ≥ 12. "
        "Add more to evals/redteam_probes.json."
    )
