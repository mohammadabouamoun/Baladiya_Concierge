"""CMS repository — tenant-scoped CRUD for CmsEntry and CmsChunk."""
from __future__ import annotations

import uuid

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from api.domain.cms import CmsChunk, CmsEntry
from api.repositories.base import BaseRepository


class CmsEntryRepository(BaseRepository[CmsEntry]):
    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID) -> None:
        super().__init__(session, tenant_id, CmsEntry)

    async def get_by_id(self, entry_id: uuid.UUID) -> CmsEntry | None:
        return await self.get(entry_id)

    async def list_entries(self, category: str | None = None) -> list[CmsEntry]:
        if category:
            return await self.list(category=category)
        return await self.list()

    async def get_pending(self) -> list[CmsEntry]:
        return await self.list(embedding_status="pending")

    async def get_failed(self) -> list[CmsEntry]:
        return await self.list(embedding_status="failed")

    async def update_status(
        self, entry_id: uuid.UUID, status: str
    ) -> CmsEntry | None:
        entry = await self.get(entry_id)
        if entry is None:
            return None
        entry.embedding_status = status
        await self._session.flush()
        return entry

    async def update_entry(
        self,
        entry_id: uuid.UUID,
        title: str | None = None,
        body: str | None = None,
        category: str | None = None,
        lang: str | None = None,
    ) -> CmsEntry | None:
        entry = await self.get(entry_id)
        if entry is None:
            return None
        if title is not None:
            entry.title = title
        if body is not None:
            entry.body = body
        if category is not None:
            entry.category = category
        if lang is not None:
            entry.lang = lang
        await self._session.flush()
        return entry


class CmsChunkRepository:
    """Direct chunk operations — not via BaseRepository because pgvector
    search requires raw SQL; this repo handles both CRUD and vector queries."""

    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID) -> None:
        if tenant_id is None:
            raise ValueError("CmsChunkRepository requires a tenant_id")
        self._session = session
        self._tenant_id = tenant_id

    async def delete_by_entry(self, entry_id: uuid.UUID) -> None:
        """Delete all chunks for an entry.  RLS enforces tenant boundary."""
        stmt = (
            delete(CmsChunk)
            .where(CmsChunk.entry_id == entry_id)
            .where(CmsChunk.tenant_id == self._tenant_id)
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def delete_by_tenant(self) -> None:
        """Purge all chunks for this repo's tenant (right-to-erasure path).

        Uses self._tenant_id exclusively — caller must construct the repo with
        the target tenant_id.  Called from platform_service.erase_tenant on a
        platform-scoped session (no RLS), so the explicit WHERE is the only guard.
        """
        stmt = delete(CmsChunk).where(CmsChunk.tenant_id == self._tenant_id)
        await self._session.execute(stmt)
        await self._session.flush()

    async def insert_chunk(
        self,
        entry_id: uuid.UUID,
        chunk_text: str,
        embedding: list[float],
        chunk_index: int,
        metadata: dict,
    ) -> uuid.UUID:
        """Insert a single chunk with its embedding vector.

        Uses raw SQL because SQLAlchemy does not know the vector type from
        the ORM model definition (column added by migration via ALTER TABLE).
        """
        chunk_id = uuid.uuid4()
        await self._session.execute(
            text(
                """
                INSERT INTO cms_chunks
                    (id, entry_id, tenant_id, chunk_text, embedding, chunk_index, metadata)
                VALUES
                    (:id, :entry_id, :tenant_id, :chunk_text, :embedding::vector, :chunk_index, :metadata::jsonb)
                """
            ),
            {
                "id": str(chunk_id),
                "entry_id": str(entry_id),
                "tenant_id": str(self._tenant_id),
                "chunk_text": chunk_text,
                "embedding": "[" + ",".join(str(v) for v in embedding) + "]",
                "chunk_index": chunk_index,
                "metadata": __import__("json").dumps(metadata),
            },
        )
        return chunk_id

    async def similarity_search(
        self,
        query_embedding: list[float],
        top_k: int,
    ) -> list[dict]:
        """Cosine similarity search — ALWAYS filters by tenant_id.

        Returns list of dicts with chunk_id, entry_id, chunk_text,
        chunk_index, metadata, and cosine similarity score (1 - distance).
        """
        embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"
        result = await self._session.execute(
            text(
                """
                SELECT
                    c.id            AS chunk_id,
                    c.entry_id,
                    c.chunk_text,
                    c.chunk_index,
                    c.metadata,
                    1 - (c.embedding <=> :embedding::vector) AS similarity
                FROM cms_chunks c
                WHERE c.tenant_id = :tenant_id
                ORDER BY c.embedding <=> :embedding::vector
                LIMIT :top_k
                """
            ),
            {
                "embedding": embedding_str,
                "tenant_id": str(self._tenant_id),
                "top_k": top_k,
            },
        )
        rows = result.mappings().all()
        return [dict(row) for row in rows]
