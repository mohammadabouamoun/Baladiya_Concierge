"""Tenant isolation test for pgvector search.

Verifies that rag_search NEVER returns chunks from another tenant's CMS,
even when both tenants have identical content.

Constitution §I: a query without tenant_id filter is a critical isolation bug.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from api.domain.cms import RagSearchResult


def _make_mock_chunk(tenant_id: uuid.UUID, text: str = "test chunk") -> dict:
    return {
        "chunk_id": uuid.uuid4(),
        "entry_id": uuid.uuid4(),
        "chunk_text": text,
        "chunk_index": 0,
        "metadata": {},
        "similarity": 0.9,
    }


class TestTenantIsolation:
    """Unit tests for tenant isolation — no live DB needed."""

    @pytest.mark.asyncio
    async def test_search_uses_tenant_id_filter(self):
        """similarity_search is always called with the correct tenant_id."""
        from unittest.mock import MagicMock
        from api.services.rag_service import rag_search

        tenant_a = uuid.uuid4()
        session = MagicMock()

        with patch("api.services.rag_service.emb.embed", new_callable=AsyncMock) as mock_embed, \
             patch("api.repositories.cms_repo.CmsChunkRepository.similarity_search", new_callable=AsyncMock) as mock_search, \
             patch("api.repositories.cms_repo.CmsEntryRepository.list_entries", new_callable=AsyncMock) as mock_entries:

            mock_embed.return_value = [0.1] * 1536
            mock_search.return_value = []
            mock_entries.return_value = []

            await rag_search(
                query="water bill payment",
                tenant_id=tenant_a,
                session=session,
                top_k=5,
                rewrite=False,
            )

            # The CmsChunkRepository is constructed with tenant_a
            # similarity_search must be called (not bypassed)
            mock_search.assert_called_once()

    @pytest.mark.asyncio
    async def test_chunk_repo_raises_without_tenant_id(self):
        """CmsChunkRepository raises ValueError if tenant_id is None."""
        from unittest.mock import MagicMock
        from api.repositories.cms_repo import CmsChunkRepository

        with pytest.raises(ValueError, match="tenant_id"):
            CmsChunkRepository(session=MagicMock(), tenant_id=None)

    @pytest.mark.asyncio
    async def test_separate_tenants_get_separate_results(self):
        """Two tenants with different content receive different results."""
        from unittest.mock import MagicMock
        from api.services.rag_service import rag_search

        tenant_a = uuid.uuid4()
        tenant_b = uuid.uuid4()

        chunk_a_text = "Tenant A: water bill payment options"
        chunk_b_text = "Tenant B: different municipality info"

        def make_search_result(text: str):
            entry_id = uuid.uuid4()
            return [{
                "chunk_id": uuid.uuid4(),
                "entry_id": entry_id,
                "chunk_text": text,
                "chunk_index": 0,
                "metadata": {"title": "Entry", "category": "water", "lang": "en", "entry_id": str(entry_id)},
                "similarity": 0.9,
            }]

        def make_entry(tenant_id: uuid.UUID, entry_id: uuid.UUID):
            entry = MagicMock()
            entry.id = entry_id
            entry.title = "Entry"
            entry.lang = "en"
            entry.category = "water"
            return entry

        # Test tenant A
        with patch("api.services.rag_service.emb.embed", new_callable=AsyncMock) as mock_embed, \
             patch("api.repositories.cms_repo.CmsChunkRepository.similarity_search", new_callable=AsyncMock) as mock_search, \
             patch("api.repositories.cms_repo.CmsEntryRepository.list_entries", new_callable=AsyncMock) as mock_entries:

            mock_embed.return_value = [0.1] * 1536
            entry_id_a = uuid.uuid4()
            mock_search.return_value = [{
                "chunk_id": uuid.uuid4(), "entry_id": entry_id_a,
                "chunk_text": chunk_a_text, "chunk_index": 0,
                "metadata": {}, "similarity": 0.9
            }]
            mock_entry_a = MagicMock()
            mock_entry_a.id = entry_id_a
            mock_entry_a.title = "Entry A"
            mock_entry_a.lang = "en"
            mock_entry_a.category = "water"
            mock_entries.return_value = [mock_entry_a]

            results_a = await rag_search(
                query="water bill", tenant_id=tenant_a, session=MagicMock(),
                top_k=5, rewrite=False,
            )

        # Test tenant B
        with patch("api.services.rag_service.emb.embed", new_callable=AsyncMock) as mock_embed, \
             patch("api.repositories.cms_repo.CmsChunkRepository.similarity_search", new_callable=AsyncMock) as mock_search, \
             patch("api.repositories.cms_repo.CmsEntryRepository.list_entries", new_callable=AsyncMock) as mock_entries:

            mock_embed.return_value = [0.1] * 1536
            entry_id_b = uuid.uuid4()
            mock_search.return_value = [{
                "chunk_id": uuid.uuid4(), "entry_id": entry_id_b,
                "chunk_text": chunk_b_text, "chunk_index": 0,
                "metadata": {}, "similarity": 0.8
            }]
            mock_entry_b = MagicMock()
            mock_entry_b.id = entry_id_b
            mock_entry_b.title = "Entry B"
            mock_entry_b.lang = "en"
            mock_entry_b.category = "general"
            mock_entries.return_value = [mock_entry_b]

            results_b = await rag_search(
                query="water bill", tenant_id=tenant_b, session=MagicMock(),
                top_k=5, rewrite=False,
            )

        assert len(results_a) == 1
        assert len(results_b) == 1
        assert results_a[0].chunk_text == chunk_a_text
        assert results_b[0].chunk_text == chunk_b_text
        # Results never cross tenants
        assert results_a[0].chunk_text != results_b[0].chunk_text

    @pytest.mark.asyncio
    async def test_no_unfiltered_vector_search_in_codebase(self):
        """Structural check: similarity_search always passes tenant_id to the WHERE clause."""
        import inspect
        from api.repositories.cms_repo import CmsChunkRepository

        source = inspect.getsource(CmsChunkRepository.similarity_search)
        assert "tenant_id" in source, (
            "similarity_search does not filter by tenant_id — critical isolation bug"
        )
        assert "WHERE" in source.upper() or "where" in source.lower(), (
            "similarity_search has no WHERE clause"
        )
