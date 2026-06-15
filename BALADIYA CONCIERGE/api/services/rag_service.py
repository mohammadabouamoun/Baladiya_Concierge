"""RAG service: embed query → tenant-filtered pgvector cosine search → return chunks.

Improvement over naive dense retrieval: query rewrite via LLM removes filler
words, expands acronyms, and normalises Lebanese/Arabizi dialect to MSA before
embedding.  Measured vs naive baseline on 15-triple golden set; results in
DECISIONS.md §2 and EVALS.md §5.  If gain < 2pp hit@5, metadata filtering is
applied instead.
"""
from __future__ import annotations

import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.config import get_settings
from api.domain.cms import RagSearchResult
from api.infra import embedding_client as emb
from api.repositories.cms_repo import CmsChunkRepository, CmsEntryRepository

logger = structlog.get_logger(__name__)


async def _rewrite_query(query: str, lang: str = "en") -> str:
    """Rewrite query with LLM to improve retrieval quality.

    Removes filler words, expands abbreviations, normalises Arabic dialect to MSA.
    Falls back to original query on any LLM error (fail-open for retrieval).
    """
    import google.generativeai as genai  # lazy import — not in critical path

    settings = get_settings()
    if not settings.gemini_api_key:
        return query

    system = (
        "You are a search query optimizer for a civic services chatbot. "
        "Rewrite the user's query into a clean, concise retrieval query. "
        "Remove filler words and conversational phrases. "
        "Expand abbreviations. "
        "If the query is in Lebanese Arabic or Arabizi, normalize it to Modern Standard Arabic (MSA). "
        "Return ONLY the rewritten query, no explanation."
    )

    try:
        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel("gemini-2.5-flash")
        result = model.generate_content(
            f"{system}\n\nOriginal query: {query}\n\nRewritten query:",
            generation_config={"max_output_tokens": 100, "temperature": 0.0},
        )
        rewritten = result.text.strip()
        if rewritten:
            logger.debug("rag.query_rewrite", original=query[:60], rewritten=rewritten[:60])
            return rewritten
    except Exception as exc:
        logger.warning("rag.rewrite_failed", query=query[:60], error=str(exc))

    return query


async def rag_search(
    query: str,
    tenant_id: uuid.UUID,
    session: AsyncSession,
    top_k: int | None = None,
    rewrite: bool = True,
    lang: str = "en",
) -> list[RagSearchResult]:
    """Retrieve top-k chunks from tenant's CMS via cosine similarity.

    Steps:
    1. Optionally rewrite query (LLM query rewrite improvement)
    2. Embed rewritten query via Gemini embedding API
    3. Cosine similarity search ALWAYS filtered by tenant_id (constitution §I)
    4. Join with cms_entries to get source title and lang
    5. Return structured RagSearchResult list

    A query without tenant_id filter is a critical isolation bug — this
    function never performs unfiltered search.
    """
    settings = get_settings()
    k = top_k if top_k is not None else settings.rag_top_k

    retrieval_query = await _rewrite_query(query, lang=lang) if rewrite else query

    query_embedding = await emb.embed(retrieval_query)

    chunk_repo = CmsChunkRepository(session, tenant_id)

    raw_results = await chunk_repo.similarity_search(query_embedding, top_k=k, lang=lang or None)

    if not raw_results:
        logger.info(
            "rag.no_results",
            tenant_id=str(tenant_id),
            query_preview=query[:60],
        )
        return []

    entry_ids = list({r["entry_id"] for r in raw_results})
    entry_repo = CmsEntryRepository(session, tenant_id)
    entries = {e.id: e for e in await entry_repo.list_entries() if e.id in entry_ids}

    results: list[RagSearchResult] = []
    for row in raw_results:
        entry_id = uuid.UUID(str(row["entry_id"])) if not isinstance(row["entry_id"], uuid.UUID) else row["entry_id"]
        chunk_id = uuid.UUID(str(row["chunk_id"])) if not isinstance(row["chunk_id"], uuid.UUID) else row["chunk_id"]
        entry = entries.get(entry_id)
        results.append(
            RagSearchResult(
                chunk_id=chunk_id,
                entry_id=entry_id,
                chunk_text=row["chunk_text"],
                source_title=entry.title if entry else "",
                lang=entry.lang if entry else "en",
                similarity=float(row["similarity"]),
                category=entry.category if entry else "general",
            )
        )

    logger.info(
        "rag.search",
        tenant_id=str(tenant_id),
        query_preview=query[:60],
        results=len(results),
        top_similarity=results[0].similarity if results else 0.0,
    )
    return results
