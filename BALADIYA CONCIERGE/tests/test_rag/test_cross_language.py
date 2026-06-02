"""Cross-language retrieval test.

Verifies that an Arabic question retrieves the correct English chunk via the
multilingual Gemini embedding model.

Constitution §III: Arabic is additive — no separate Arabic RAG pipeline.
The multilingual embedding handles cross-language retrieval transparently.
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

ROOT = Path(__file__).parent.parent.parent
GOLDEN_PATH = ROOT / "evals" / "rag_golden.json"


def _load_xl_triples() -> list[dict]:
    """Return the 4 Arabic-question cross-language triples from the golden set."""
    data = json.loads(GOLDEN_PATH.read_text())
    return [t for t in data["triples"] if t.get("lang") == "ar" and "source_entry_ref" in t]


class TestCrossLanguageRetrieval:
    """Unit tests for cross-language retrieval behaviour."""

    def test_golden_set_has_arabic_triples(self):
        xl_triples = _load_xl_triples()
        assert len(xl_triples) >= 3, (
            f"Need ≥3 cross-language Arabic triples in golden set, got {len(xl_triples)}"
        )

    def test_xl_triples_reference_english_entries(self):
        """Each Arabic triple references an English source entry."""
        data = json.loads(GOLDEN_PATH.read_text())
        triples_by_id = {t["id"]: t for t in data["triples"]}

        xl_triples = _load_xl_triples()
        for triple in xl_triples:
            ref = triple["source_entry_ref"]
            assert ref in triples_by_id, f"{triple['id']} references unknown triple {ref}"
            source = triples_by_id[ref]
            assert source.get("source_entry", {}).get("lang") == "en", (
                f"{triple['id']} does not reference an English source entry"
            )

    @pytest.mark.asyncio
    async def test_arabic_query_returns_correct_chunk(self):
        """Arabic question → same English chunk as the paired English question.

        Uses mocked embeddings that simulate cross-language similarity
        (same embedding returned for both queries, which is what a multilingual
        model would do for semantically identical content).
        """
        from unittest.mock import MagicMock
        from api.services.rag_service import rag_search

        tenant_id = uuid.uuid4()
        entry_id = uuid.uuid4()
        chunk_text = "Water bill payment options: Residents may pay their water bills online at baladiya.gov"
        shared_embedding = [0.42] * 1536
        session = MagicMock()

        mock_chunk = {
            "chunk_id": uuid.uuid4(),
            "entry_id": entry_id,
            "chunk_text": chunk_text,
            "chunk_index": 0,
            "metadata": {},
            "similarity": 0.95,
        }

        mock_entry = MagicMock()
        mock_entry.id = entry_id
        mock_entry.title = "Water Bill Payment Options"
        mock_entry.lang = "en"
        mock_entry.category = "water"

        with patch("api.services.rag_service.emb.embed", new_callable=AsyncMock) as mock_embed, \
             patch("api.repositories.cms_repo.CmsChunkRepository.similarity_search", new_callable=AsyncMock) as mock_search, \
             patch("api.repositories.cms_repo.CmsEntryRepository.list_entries", new_callable=AsyncMock) as mock_entries:

            mock_embed.return_value = shared_embedding
            mock_search.return_value = [mock_chunk]
            mock_entries.return_value = [mock_entry]

            ar_results = await rag_search(
                query="كيف يمكنني دفع فاتورة المياه؟",
                tenant_id=tenant_id,
                session=session,
                top_k=5,
                rewrite=False,
            )

        assert len(ar_results) > 0, "Arabic question returned no results"
        assert ar_results[0].chunk_text == chunk_text, (
            "Arabic question did not retrieve the expected English chunk"
        )

    @pytest.mark.asyncio
    async def test_embedding_called_for_arabic_query(self):
        """The embedding client is called for Arabic queries — no Arabic bypass."""
        from unittest.mock import MagicMock
        from api.services.rag_service import rag_search

        tenant_id = uuid.uuid4()
        session = MagicMock()

        with patch("api.services.rag_service.emb.embed", new_callable=AsyncMock) as mock_embed, \
             patch("api.repositories.cms_repo.CmsChunkRepository.similarity_search", new_callable=AsyncMock) as mock_search, \
             patch("api.repositories.cms_repo.CmsEntryRepository.list_entries", new_callable=AsyncMock) as mock_entries:

            mock_embed.return_value = [0.1] * 1536
            mock_search.return_value = []
            mock_entries.return_value = []

            await rag_search(
                query="كيف أبلغ عن حفرة في الطريق؟",
                tenant_id=tenant_id,
                session=session,
                top_k=5,
                rewrite=False,
            )

        mock_embed.assert_called_once_with("كيف أبلغ عن حفرة في الطريق؟")

    def test_no_separate_arabic_pipeline(self):
        """Structural: rag_search does not branch on language — one pipeline for all."""
        import inspect
        from api.services.rag_service import rag_search

        source = inspect.getsource(rag_search)
        # There should be no lang-specific branching in the main search path
        assert "if lang ==" not in source, (
            "rag_search branches on language — violates constitution §III (Arabic is additive)"
        )
        assert "elif lang" not in source, (
            "rag_search has elif lang branch — violates constitution §III"
        )
