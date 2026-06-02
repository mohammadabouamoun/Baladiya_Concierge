"""CMS service: chunking, embedding, and vector lifecycle for CMS entries.

Chunking strategy: paragraph-boundary split with 512-token cap (≈2048 chars),
100-token min (≈400 chars), and 50-token overlap (≈200 chars).  Paragraph
boundaries preserve semantic units better than fixed-size splits for short
civic content.  Justified vs fixed-size baseline in DECISIONS.md §2.
"""
from __future__ import annotations

import re
import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.config import get_settings
from api.domain.cms import CmsEntry, CmsEntryCreate
from api.infra import embedding_client as emb
from api.repositories.cms_repo import CmsChunkRepository, CmsEntryRepository

logger = structlog.get_logger(__name__)


# ── Chunking (T-012) ──────────────────────────────────────────────────────

def _split_paragraphs(text: str) -> list[str]:
    """Split on blank lines; collapse whitespace within paragraphs."""
    paras = re.split(r"\n\s*\n", text.strip())
    return [p.strip() for p in paras if p.strip()]


def structural_chunk(text: str) -> list[str]:
    """Paragraph-boundary chunker with max/min char limits and overlap.

    Returns a list of chunk strings.  Each chunk is ≤ chunk_max_chars
    and ≥ chunk_min_chars (except possibly the last).  Adjacent chunks
    share chunk_overlap_chars of trailing/leading text.
    """
    settings = get_settings()
    max_c = settings.chunk_max_chars
    min_c = settings.chunk_min_chars
    overlap_c = settings.chunk_overlap_chars

    paragraphs = _split_paragraphs(text)
    if not paragraphs:
        return []

    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        # If single paragraph exceeds max, hard-split at word boundaries
        if len(para) > max_c:
            sub_chunks = _hard_split(para, max_c)
            for sub in sub_chunks:
                if len(current) + len(sub) + 1 <= max_c:
                    current = (current + "\n\n" + sub).strip() if current else sub
                else:
                    if len(current) >= min_c:
                        chunks.append(current)
                    current = sub
            continue

        proposed = (current + "\n\n" + para).strip() if current else para
        if len(proposed) <= max_c:
            current = proposed
        else:
            if len(current) >= min_c:
                chunks.append(current)
            # Carry overlap from the end of current into next chunk
            overlap = current[-overlap_c:] if len(current) >= overlap_c else current
            current = (overlap + "\n\n" + para).strip()

    if current:
        # Merge tiny trailing chunk into the last chunk if possible
        if chunks and len(current) < min_c:
            merged = chunks[-1] + "\n\n" + current
            if len(merged) <= max_c:
                chunks[-1] = merged
            else:
                chunks.append(current)
        else:
            chunks.append(current)

    return chunks


def _hard_split(text: str, max_c: int) -> list[str]:
    """Split oversized text at word boundaries."""
    words = text.split()
    parts: list[str] = []
    current = ""
    for word in words:
        if len(current) + len(word) + 1 <= max_c:
            current = (current + " " + word).strip() if current else word
        else:
            if current:
                parts.append(current)
            current = word
    if current:
        parts.append(current)
    return parts


# ── Embedding lifecycle (T-020, T-022, T-023) ─────────────────────────────

async def chunk_and_embed(
    entry: CmsEntry,
    session: AsyncSession,
    tenant_id: uuid.UUID,
) -> None:
    """Chunk entry body, embed each chunk, upsert into cms_chunks.

    Marks entry embedding_status='done' on success or 'failed' on error.
    Existing chunks for this entry are deleted first (re-index on edit).
    """
    entry_repo = CmsEntryRepository(session, tenant_id)
    chunk_repo = CmsChunkRepository(session, tenant_id)

    await chunk_repo.delete_by_entry(entry.id)

    chunks = structural_chunk(entry.body)
    if not chunks:
        logger.warning("cms.chunk_empty", entry_id=str(entry.id), tenant_id=str(tenant_id))
        await entry_repo.update_status(entry.id, "failed")
        await session.commit()
        return

    try:
        for idx, chunk_text in enumerate(chunks):
            embedding = await emb.embed(chunk_text)
            await chunk_repo.insert_chunk(
                entry_id=entry.id,
                chunk_text=chunk_text,
                embedding=embedding,
                chunk_index=idx,
                metadata={
                    "title": entry.title,
                    "category": entry.category,
                    "lang": entry.lang,
                    "entry_id": str(entry.id),
                },
            )
        await entry_repo.update_status(entry.id, "done")
        logger.info(
            "cms.embedded",
            entry_id=str(entry.id),
            tenant_id=str(tenant_id),
            chunks=len(chunks),
        )
    except Exception as exc:
        await entry_repo.update_status(entry.id, "failed")
        logger.error(
            "cms.embed_failed",
            entry_id=str(entry.id),
            tenant_id=str(tenant_id),
            error=str(exc),
        )
        raise

    await session.commit()


async def delete_entry_vectors(
    entry_id: uuid.UUID,
    tenant_id: uuid.UUID,
    session: AsyncSession,
) -> None:
    """Delete all pgvector chunks for an entry (on CMS delete or re-index)."""
    chunk_repo = CmsChunkRepository(session, tenant_id)
    await chunk_repo.delete_by_entry(entry_id)
    logger.info(
        "cms.vectors_deleted",
        entry_id=str(entry_id),
        tenant_id=str(tenant_id),
    )


async def create_entry(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    payload: CmsEntryCreate,
) -> CmsEntry:
    """Create a CMS entry and immediately attempt embedding.

    On embedding failure the entry is saved with status='failed'
    so the background retry can pick it up.
    """
    repo = CmsEntryRepository(session, tenant_id)
    entry = CmsEntry(
        tenant_id=tenant_id,
        title=payload.title,
        body=payload.body,
        category=payload.category,
        lang=payload.lang,
        embedding_status="pending",
    )
    entry = await repo.add(entry)
    await session.commit()
    await session.refresh(entry)

    try:
        await chunk_and_embed(entry, session, tenant_id)
    except Exception:
        # chunk_and_embed marks status=failed and re-raises; swallow here so
        # the HTTP response succeeds with the saved entry (status='failed').
        pass

    await session.refresh(entry)
    return entry


async def update_entry(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    entry_id: uuid.UUID,
    title: str | None = None,
    body: str | None = None,
    category: str | None = None,
    lang: str | None = None,
) -> CmsEntry | None:
    """Update a CMS entry; re-embeds if body/title/category/lang changed."""
    repo = CmsEntryRepository(session, tenant_id)
    entry = await repo.update_entry(entry_id, title=title, body=body, category=category, lang=lang)
    if entry is None:
        return None

    # Mark pending before re-embedding (T-022)
    await repo.update_status(entry_id, "pending")
    await session.commit()
    await session.refresh(entry)

    try:
        await chunk_and_embed(entry, session, tenant_id)
    except Exception:
        pass

    await session.refresh(entry)
    return entry


async def retry_pending_entries(
    session: AsyncSession,
    tenant_id: uuid.UUID,
) -> int:
    """Retry embedding for all pending/failed entries for a specific tenant.

    Called at startup (via retry_all_pending_entries) or periodically to
    recover from transient API failures (T-023).
    """
    repo = CmsEntryRepository(session, tenant_id)
    pending = await repo.get_pending()
    failed = await repo.get_failed()
    retried = 0
    for entry in pending + failed:
        try:
            await chunk_and_embed(entry, session, tenant_id)
            retried += 1
        except Exception as exc:
            logger.warning(
                "cms.retry_failed",
                entry_id=str(entry.id),
                error=str(exc),
            )
    return retried


async def retry_all_pending_entries() -> None:
    """Startup sweep: retry failed/pending embeddings across ALL tenants.

    Uses a platform-scoped session (no RLS) to discover affected tenant_ids,
    then opens a properly scoped session per tenant to do the actual re-embedding.
    Called once from api/main.py lifespan after DB and embedding client are ready.
    """
    from sqlalchemy import select as sa_select
    from api.infra.db import get_session_factory
    from api.domain.cms import CmsEntry

    factory = get_session_factory()

    # Platform-level scan — no RLS, read distinct tenant_ids with pending entries
    async with factory() as scan_session:
        result = await scan_session.execute(
            sa_select(CmsEntry.tenant_id).where(
                CmsEntry.embedding_status.in_(["pending", "failed"])
            ).distinct()
        )
        tenant_ids = [row[0] for row in result.all()]

    if not tenant_ids:
        return

    logger.info("cms.startup_retry", tenants_with_pending=len(tenant_ids))

    for tenant_id in tenant_ids:
        try:
            from sqlalchemy import text
            async with factory() as session:
                await session.execute(
                    text("SET LOCAL app.current_tenant = :tid"),
                    {"tid": str(tenant_id)},
                )
                try:
                    count = await retry_pending_entries(session, tenant_id)
                    if count:
                        logger.info("cms.startup_retry_done", tenant_id=str(tenant_id), retried=count)
                finally:
                    await session.execute(text("RESET app.current_tenant"))
        except Exception as exc:
            logger.warning("cms.startup_retry_error", tenant_id=str(tenant_id), error=str(exc))
