"""Agent tool: rag_search — wraps rag_service with ToolResult/ToolError contract."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from api.services.agent_service import AgentContext

logger = structlog.get_logger(__name__)


async def run(args: dict[str, Any], context: AgentContext) -> dict[str, Any]:
    """Search the tenant's knowledge base.

    Always tenant-filtered — constitution §I: an unfiltered search is a critical isolation bug.
    Returns structured results or a ToolError dict.
    """
    from api.services.rag_service import rag_search

    query = args.get("query", "").strip()
    if not query:
        return {"error": "query cannot be empty"}

    try:
        results = await rag_search(
            query=query,
            tenant_id=context.tenant_id,
            session=context.db_session,
            lang=context.lang,
        )
    except Exception as exc:
        logger.error(
            "tool.rag_search.failed",
            tenant_id=str(context.tenant_id),
            query=query[:60],
            error=str(exc),
        )
        return {"error": f"Search failed: {exc}"}

    if not results:
        return {"results": [], "message": "No relevant information found in the knowledge base."}

    # Relevance gate: only hand the LLM chunks close to the best match, so the model —
    # especially the weaker Groq fallback — can't dump unrelated categories into the
    # answer. The cutoff is relative to the top score and adapts to query type:
    #   • High top score (>= _CONFIDENT_TOP): a specific, well-answered question. Be
    #     strict so semantically-adjacent distractors (e.g. water-bill text bleeding
    #     into a property-tax answer) are dropped.
    #   • Lower top score: a broad/ambiguous question with clustered scores. Stay loose
    #     so legitimate breadth (e.g. "what services do you offer?") is preserved.
    # Always keep at least the top result. Agent path only; the RAG eval calls
    # rag_service.search directly and is unaffected.
    _CONFIDENT_TOP = 0.70
    _RATIO_STRICT = 0.93
    _RATIO_LOOSE = 0.85
    top_sim = results[0].similarity
    ratio = _RATIO_STRICT if top_sim >= _CONFIDENT_TOP else _RATIO_LOOSE
    cutoff = top_sim * ratio
    relevant = [r for r in results if r.similarity >= cutoff] or results[:1]

    formatted = [
        {
            "chunk": r.chunk_text[:800],
            "source": r.source_title,
            "category": r.category,
            "similarity": round(r.similarity, 3),
        }
        for r in relevant
    ]

    logger.info(
        "tool.rag_search.ok",
        tenant_id=str(context.tenant_id),
        query=query[:60],
        results=len(formatted),
        retrieved=len(results),
    )
    return {"results": formatted}
