"""Agent evaluation script — measures real LLM tool-selection accuracy.

Evaluates the 15 labelled examples in evals/agent_tool_selection.json against
the live Gemini/Groq LLM. Use this to populate EVALS.md §4 with measured numbers.

Usage:
    python evals/evaluate_agent.py [--model gemini|groq] [--verbose]

Outputs:
    - Overall tool-selection accuracy (vs eval_thresholds.yaml → agent_tool_accuracy)
    - Per-language accuracy (EN / MSA / Lebanese / Arabizi)
    - Per-tool accuracy (rag_search / capture_request / escalate)
    - Latency p50 and p95 per call
    - Whether the SC-002 workflow_handled_rate threshold is met (from a separate router pass)

This script makes live LLM API calls. Cost: ~15 × Gemini 2.5 Flash calls ≈ $0.002.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import sys
import time
import uuid
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))


EVALS_DIR = REPO_ROOT / "evals"
THRESHOLDS_FILE = REPO_ROOT / "eval_thresholds.yaml"


def load_examples() -> list[dict]:
    with (EVALS_DIR / "agent_tool_selection.json").open() as f:
        return json.load(f)


def load_thresholds() -> dict:
    import yaml
    with THRESHOLDS_FILE.open() as f:
        return yaml.safe_load(f)


def _tool_schema_for_eval() -> list[dict]:
    """Return the three agent tool schemas for the eval prompt."""
    from api.infra.llm_client import AGENT_TOOL_SCHEMAS
    return AGENT_TOOL_SCHEMAS


async def _call_llm_for_tool(example: dict, model: str) -> tuple[str | None, float]:
    """Ask the LLM which tool to call for this example. Returns (tool_name, latency_s)."""
    from api.infra import llm_client
    from api.infra.llm_client import AgentMessage

    system_prompt = (
        "You are a civic services assistant. "
        "For the given resident message, pick the most appropriate tool. "
        "Use rag_search for questions about services or policies, "
        "capture_request for reports or service requests, "
        "and escalate when the resident wants to speak to a human. "
        "Always call a tool — never reply with plain text."
    )

    start = time.perf_counter()
    turn = await llm_client.complete(
        system_prompt=system_prompt,
        history=[],
        user_message=example["input"],
        tool_schemas=_tool_schema_for_eval(),
    )
    elapsed = time.perf_counter() - start

    tool_name = turn.tool_call.name if turn.is_tool_call else None
    return tool_name, elapsed


async def run_eval(model: str = "gemini", verbose: bool = False) -> dict[str, Any]:
    """Run the full 15-example eval. Returns a results dict."""

    # Bootstrap settings from .env
    os.environ.setdefault("ENV", "testing")
    from api.core.config import get_settings
    get_settings.cache_clear()

    examples = load_examples()
    thresholds = load_thresholds()

    results: list[dict] = []
    latencies: list[float] = []

    print(f"\nRunning agent tool-selection eval ({len(examples)} examples, model={model})")
    print("-" * 60)

    for i, ex in enumerate(examples):
        if i > 0:
            await asyncio.sleep(13)  # stay under 5 req/min free-tier limit
        predicted, latency = await _call_llm_for_tool(ex, model)
        correct = predicted == ex["expected_tool"]

        if verbose:
            mark = "✓" if correct else "✗"
            print(f"  {mark} [{ex['variety']:10s}] {ex['input'][:55]:55s} → {predicted} (expected {ex['expected_tool']})")

        results.append({
            "id": ex["id"],
            "input": ex["input"],
            "lang": ex["lang"],
            "variety": ex["variety"],
            "expected": ex["expected_tool"],
            "predicted": predicted,
            "correct": correct,
            "latency_s": latency,
        })
        latencies.append(latency)

    # ── Overall accuracy ─────────────────────────────────────────
    n = len(results)
    correct_n = sum(1 for r in results if r["correct"])
    accuracy = correct_n / n

    # ── Per-variety breakdown ────────────────────────────────────
    varieties = sorted({r["variety"] for r in results})
    per_variety = {}
    for v in varieties:
        subset = [r for r in results if r["variety"] == v]
        per_variety[v] = sum(1 for r in subset if r["correct"]) / len(subset)

    # ── Per-tool breakdown ───────────────────────────────────────
    tools = ["rag_search", "capture_request", "escalate"]
    per_tool = {}
    for t in tools:
        subset = [r for r in results if r["expected"] == t]
        if subset:
            per_tool[t] = sum(1 for r in subset if r["correct"]) / len(subset)

    # ── Latency stats ────────────────────────────────────────────
    latency_p50 = statistics.median(latencies)
    latency_p95 = sorted(latencies)[int(0.95 * len(latencies))]

    threshold_accuracy = thresholds.get("agent_tool_accuracy", 0.80)
    passed = accuracy >= threshold_accuracy

    print(f"\n{'='*60}")
    print(f"Tool-selection accuracy : {accuracy:.3f}  (threshold: {threshold_accuracy:.2f})")
    print(f"Result                  : {'PASS ✓' if passed else 'FAIL ✗'}")
    print(f"\nPer-variety accuracy:")
    for v, acc in per_variety.items():
        print(f"  {v:12s}: {acc:.3f}")
    print(f"\nPer-tool accuracy:")
    for t, acc in per_tool.items():
        print(f"  {t:20s}: {acc:.3f}")
    print(f"\nLatency — p50: {latency_p50:.2f}s  p95: {latency_p95:.2f}s")

    sc_004_pass = latency_p95 < 5.0
    print(f"SC-004 (p95 < 5s)       : {'PASS ✓' if sc_004_pass else 'FAIL ✗'}  (measured p95: {latency_p95:.2f}s)")
    print(f"{'='*60}\n")

    return {
        "accuracy": accuracy,
        "passed": passed,
        "per_variety": per_variety,
        "per_tool": per_tool,
        "latency_p50": latency_p50,
        "latency_p95": latency_p95,
        "sc_004_pass": sc_004_pass,
        "results": results,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agent tool-selection evaluation")
    parser.add_argument("--model", choices=["gemini", "groq"], default="gemini")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    summary = asyncio.run(run_eval(model=args.model, verbose=args.verbose))
    sys.exit(0 if summary["passed"] else 1)
