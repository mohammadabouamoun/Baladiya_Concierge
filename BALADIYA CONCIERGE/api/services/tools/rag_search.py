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

    formatted = [
        {
            "chunk": r.chunk_text[:800],
            "source": r.source_title,
            "category": r.category,
            "similarity": round(r.similarity, 3),
        }
        for r in results
    ]

    logger.info(
        "tool.rag_search.ok",
        tenant_id=str(context.tenant_id),
        query=query[:60],
        results=len(formatted),
    )
    return {"results": formatted}
