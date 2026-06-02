"""RAG evaluation script — baseline vs query-rewrite comparison.

Usage:
    python evals/evaluate_rag.py --mode baseline  # naive dense retrieval
    python evals/evaluate_rag.py --mode improved  # with query rewrite
    python evals/evaluate_rag.py --mode compare   # both + comparison table

Prerequisites:
    1. Run the full stack: docker-compose up db vault migrate api
    2. Seed eval content:  python evals/seed_eval_content.py
    3. Set EVAL_TENANT_ID env var to the tenant used by seed_eval_content.py

Results are committed to DECISIONS.md §2 and EVALS.md §5.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import uuid
from pathlib import Path

import httpx

ROOT = Path(__file__).parent.parent
GOLDEN_PATH = ROOT / "evals" / "rag_golden.json"
API_BASE = os.environ.get("API_BASE_URL", "http://localhost:8000")
EVAL_TOKEN = os.environ.get("EVAL_TOKEN", "")
TENANT_ID = os.environ.get("EVAL_TENANT_ID", "")
TOP_K = 5


def _load_golden() -> list[dict]:
    data = json.loads(GOLDEN_PATH.read_text())
    direct = [t for t in data["triples"] if "source_entry" in t]
    return direct


def _hit_at_k(retrieved_texts: list[str], expected_keywords: list[str], k: int) -> float:
    """1 if any of the top-k chunks contains ALL expected keywords, else 0."""
    for text in retrieved_texts[:k]:
        text_lower = text.lower()
        if all(kw.lower() in text_lower for kw in expected_keywords):
            return 1.0
    return 0.0


def _reciprocal_rank(retrieved_texts: list[str], expected_keywords: list[str]) -> float:
    """Reciprocal rank of the first chunk containing ALL expected keywords."""
    for rank, text in enumerate(retrieved_texts, start=1):
        text_lower = text.lower()
        if all(kw.lower() in text_lower for kw in expected_keywords):
            return 1.0 / rank
    return 0.0


async def _search(query: str, rewrite: bool) -> list[str]:
    """Call the API RAG search endpoint and return chunk texts."""
    headers = {"Authorization": f"Bearer {EVAL_TOKEN}"}
    params = {"query": query, "top_k": TOP_K, "rewrite": str(rewrite).lower()}
    async with httpx.AsyncClient(base_url=API_BASE, timeout=30.0) as client:
        resp = await client.get("/rag/search", headers=headers, params=params)
        resp.raise_for_status()
        return [r["chunk_text"] for r in resp.json()]


async def evaluate(mode: str) -> dict:
    """Evaluate on the golden set.  Returns metrics dict."""
    triples = _load_golden()
    rewrite = mode == "improved"

    hits = []
    rr_scores = []

    for triple in triples:
        try:
            chunks = await _search(triple["question"], rewrite=rewrite)
            hits.append(_hit_at_k(chunks, triple["expected_keywords"], k=5))
            rr_scores.append(_reciprocal_rank(chunks, triple["expected_keywords"]))
        except Exception as exc:
            print(f"ERROR on {triple['id']}: {exc}", file=sys.stderr)
            hits.append(0.0)
            rr_scores.append(0.0)

    hit_at_5 = sum(hits) / len(hits) if hits else 0.0
    mrr = sum(rr_scores) / len(rr_scores) if rr_scores else 0.0

    # Cross-language triples (G-009 to G-012)
    xl_ids = {"G-009", "G-010", "G-011", "G-012"}
    xl_hits = [h for t, h in zip(triples, hits) if t["id"] in xl_ids]
    xl_hit_at_5 = sum(xl_hits) / len(xl_hits) if xl_hits else 0.0

    return {
        "mode": mode,
        "n_triples": len(triples),
        "hit_at_5": round(hit_at_5, 4),
        "mrr": round(mrr, 4),
        "xl_hit_at_5": round(xl_hit_at_5, 4),
        "per_triple": [
            {
                "id": t["id"],
                "hit": h,
                "rr": rr,
                "question": t["question"][:60],
            }
            for t, h, rr in zip(triples, hits, rr_scores)
        ],
    }


def _print_table(baseline: dict, improved: dict) -> None:
    print("\n=== RAG Evaluation: Baseline vs Query-Rewrite Improvement ===\n")
    print(f"{'Metric':<25} {'Baseline':>10} {'Improved':>10} {'Delta':>10}")
    print("-" * 60)
    for key in ("hit_at_5", "mrr", "xl_hit_at_5"):
        b = baseline[key]
        i = improved[key]
        delta = i - b
        sign = "+" if delta >= 0 else ""
        print(f"{key:<25} {b:>10.4f} {i:>10.4f} {sign+f'{delta:.4f}':>10}")
    print()
    print("Per-triple results (improved mode):")
    print(f"  {'ID':<8} {'Hit':>5} {'RR':>7}  Question")
    for r in improved["per_triple"]:
        print(f"  {r['id']:<8} {r['hit']:>5.1f} {r['rr']:>7.4f}  {r['question']}")


async def _main() -> None:
    parser = argparse.ArgumentParser(description="RAG golden-set evaluation")
    parser.add_argument("--mode", choices=["baseline", "improved", "compare"], default="compare")
    args = parser.parse_args()

    if not EVAL_TOKEN:
        print("ERROR: Set EVAL_TOKEN env var to a valid tenant_admin JWT.", file=sys.stderr)
        sys.exit(1)

    if args.mode == "compare":
        print("Evaluating baseline (naive dense retrieval)...")
        baseline = await evaluate("baseline")
        print("Evaluating improved (query rewrite)...")
        improved = await evaluate("improved")
        _print_table(baseline, improved)
        gain = improved["hit_at_5"] - baseline["hit_at_5"]
        if gain >= 0.02:
            print(f"\n✅ Query rewrite gain: +{gain:.4f} hit@5 — USE query rewrite improvement")
        else:
            print(f"\n⚠️  Query rewrite gain: {gain:+.4f} hit@5 — Consider metadata filtering instead")
    else:
        result = await evaluate(args.mode)
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(_main())
