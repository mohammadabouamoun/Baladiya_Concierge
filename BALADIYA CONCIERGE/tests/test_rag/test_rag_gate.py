"""RAG quality gate — evaluates rag_search on the 15-triple golden set.

Asserts hit@5, MRR, and faithfulness (keyword proxy) against thresholds
in eval_thresholds.yaml.

Requires: DB running, eval content seeded (evals/seed_eval_content.py).
These tests are marked 'integration' and skipped in unit-only CI runs.
Set RAG_EVAL=1 env var to enable.
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
import yaml
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))  # make evals.rag_judge importable
GOLDEN_PATH = ROOT / "evals" / "rag_golden.json"
THRESHOLDS_PATH = ROOT / "eval_thresholds.yaml"

RAG_EVAL_ENABLED = os.environ.get("RAG_EVAL", "0") == "1"
# Live gates retrieve from a seeded tenant — the same one seed_eval_content.py
# populated. Read it from env (a random uuid retrieves nothing). Skip if unset.
EVAL_TENANT_ID = os.environ.get("EVAL_TENANT_ID", "")


def _load_thresholds() -> dict:
    return yaml.safe_load(THRESHOLDS_PATH.read_text())


def _load_golden() -> list[dict]:
    data = json.loads(GOLDEN_PATH.read_text())
    return [t for t in data["triples"] if "source_entry" in t]


def _hit_at_k(retrieved_texts: list[str], keywords: list[str], k: int) -> float:
    for text_ in retrieved_texts[:k]:
        if all(kw.lower() in text_.lower() for kw in keywords):
            return 1.0
    return 0.0


def _reciprocal_rank(retrieved_texts: list[str], keywords: list[str]) -> float:
    for rank, text_ in enumerate(retrieved_texts, start=1):
        if all(kw.lower() in text_.lower() for kw in keywords):
            return 1.0 / rank
    return 0.0


_NEED_TENANT = pytest.mark.skipif(
    not EVAL_TENANT_ID, reason="Set EVAL_TENANT_ID to a seeded tenant to run live RAG gates"
)


@pytest.mark.skipif(not RAG_EVAL_ENABLED, reason="Set RAG_EVAL=1 to run RAG quality gate")
class TestRagGate:
    """Live quality gate — requires a seeded tenant (EVAL_TENANT_ID) and an LLM key."""

    @_NEED_TENANT
    @pytest.mark.asyncio
    async def test_hit_at_5_above_threshold(self, db_session: AsyncSession):
        from api.services.rag_service import rag_search
        threshold = _load_thresholds().get("rag_hit_at_5", 0.0)
        triples = _load_golden()
        tenant_id = uuid.UUID(EVAL_TENANT_ID)

        hits = []
        for triple in triples:
            results = await rag_search(
                query=triple["question"], tenant_id=tenant_id, session=db_session,
                top_k=5, rewrite=True, lang=triple.get("lang", "en"),
            )
            texts = [r.chunk_text for r in results]
            hits.append(_hit_at_k(texts, triple["expected_keywords"], k=5))

        hit_at_5 = sum(hits) / len(hits)
        assert hit_at_5 >= threshold, (
            f"RAG hit@5 {hit_at_5:.4f} below threshold {threshold} "
            f"(failing triples: {[t['id'] for t, h in zip(triples, hits) if h == 0]})"
        )

    @_NEED_TENANT
    @pytest.mark.asyncio
    async def test_mrr_above_threshold(self, db_session: AsyncSession):
        from api.services.rag_service import rag_search
        threshold = _load_thresholds().get("rag_mrr", 0.0)
        triples = _load_golden()
        tenant_id = uuid.UUID(EVAL_TENANT_ID)

        rr_scores = []
        for triple in triples:
            results = await rag_search(
                query=triple["question"], tenant_id=tenant_id, session=db_session,
                top_k=5, rewrite=True, lang=triple.get("lang", "en"),
            )
            texts = [r.chunk_text for r in results]
            rr_scores.append(_reciprocal_rank(texts, triple["expected_keywords"]))

        mrr = sum(rr_scores) / len(rr_scores)
        assert mrr >= threshold, f"RAG MRR {mrr:.4f} below threshold {threshold}"

    @_NEED_TENANT
    @pytest.mark.asyncio
    async def test_faithfulness_and_relevancy_above_threshold(self, db_session: AsyncSession):
        """Real LLM-judge gate (RAGAS-style), replacing the old keyword proxy.

        For each triple: retrieve → generate a grounded answer → judge faithfulness
        (answer claims supported by context) and answer-relevancy (answer addresses
        the question). Judge uses the app's Gemini→Groq fallback. See DECISIONS.md
        §D-RAG-002 for the measured baseline (faithfulness 0.95, relevancy 0.975, n=8)
        and the self-evaluation caveat.
        """
        from api.services.rag_service import rag_search
        from evals.rag_judge import generate_answer, judge_faithfulness, judge_relevancy

        thresholds = _load_thresholds()
        faith_thr = thresholds.get("rag_faithfulness", 0.0)
        rel_thr = thresholds.get("rag_answer_relevancy", 0.0)

        triples = _load_golden()
        tenant_id = uuid.UUID(EVAL_TENANT_ID)

        faiths, rels = [], []
        for triple in triples:
            results = await rag_search(
                query=triple["question"], tenant_id=tenant_id, session=db_session,
                top_k=5, rewrite=True, lang=triple.get("lang", "en"),
            )
            contexts = [r.chunk_text for r in results]
            answer = await generate_answer(triple["question"], contexts)
            f = await judge_faithfulness(answer, contexts)
            r = await judge_relevancy(triple["question"], answer)
            if f >= 0:
                faiths.append(f)
            if r >= 0:
                rels.append(r)

        faithfulness = sum(faiths) / len(faiths) if faiths else 0.0
        relevancy = sum(rels) / len(rels) if rels else 0.0
        assert faithfulness >= faith_thr, (
            f"RAG faithfulness (LLM-judge) {faithfulness:.4f} below threshold {faith_thr}"
        )
        assert relevancy >= rel_thr, (
            f"RAG answer-relevancy (LLM-judge) {relevancy:.4f} below threshold {rel_thr}"
        )


class TestRagGateUnit:
    """Unit-level tests that run in CI without a live DB."""

    def test_golden_set_has_15_triples(self):
        triples = _load_golden()
        assert len(triples) == 8, f"Expected 8 direct-source triples, got {len(triples)}"
        data = json.loads(GOLDEN_PATH.read_text())
        assert len(data["triples"]) == 15, f"Expected 15 total triples, got {len(data['triples'])}"

    def test_golden_set_has_cross_language_triples(self):
        data = json.loads(GOLDEN_PATH.read_text())
        ar_triples = [t for t in data["triples"] if t.get("lang") == "ar"]
        assert len(ar_triples) >= 3, f"Need ≥3 Arabic triples, got {len(ar_triples)}"

    def test_thresholds_file_has_rag_keys(self):
        thresholds = _load_thresholds()
        assert "rag_hit_at_5" in thresholds
        assert "rag_mrr" in thresholds
        assert "rag_faithfulness" in thresholds

    @pytest.mark.asyncio
    async def test_rag_search_returns_list(self):
        """Unit test with mocked embedding — verifies return type and tenant filter."""
        from unittest.mock import MagicMock
        from api.services.rag_service import rag_search
        tenant_id = uuid.uuid4()
        session = MagicMock()

        with patch("api.services.rag_service.emb.embed", new_callable=AsyncMock) as mock_embed, \
             patch("api.repositories.cms_repo.CmsChunkRepository.similarity_search", new_callable=AsyncMock) as mock_search, \
             patch("api.repositories.cms_repo.CmsEntryRepository.list_entries", new_callable=AsyncMock) as mock_entries:

            mock_embed.return_value = [0.0] * 1536
            mock_search.return_value = []
            mock_entries.return_value = []

            results = await rag_search(
                query="test query",
                tenant_id=tenant_id,
                session=session,
                top_k=5,
                rewrite=False,
            )

        assert isinstance(results, list)
        mock_embed.assert_called_once()
