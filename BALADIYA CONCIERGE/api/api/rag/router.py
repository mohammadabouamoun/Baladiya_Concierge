"""RAG search endpoint — used by the agent tool and evaluation scripts."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import HTTPException
from api.core.security import TokenClaims, get_current_user
from api.domain.cms import RagSearchResult
from api.infra.db import get_db
from api.services import rag_service

router = APIRouter()


async def _require_tenant_scoped(
    token: Annotated[TokenClaims, Depends(get_current_user)],
) -> TokenClaims:
    """Enforce that the caller has a tenant-scoped token (tenant_id is not None).

    Platform Manager tokens have tenant_id=None and must not reach RAG search —
    they have no tenant corpus to search against, and passing None to
    CmsChunkRepository would violate the isolation contract.
    """
    if token.tenant_id is None:
        raise HTTPException(
            status_code=403,
            detail="RAG search requires a tenant-scoped token",
        )
    return token


async def _get_rag_db(
    token: Annotated[TokenClaims, Depends(_require_tenant_scoped)],
) -> AsyncSession:
    async for session in get_db(token):
        yield session


@router.get("/search", response_model=list[RagSearchResult])
async def rag_search(
    token: Annotated[TokenClaims, Depends(_require_tenant_scoped)],
    session: Annotated[AsyncSession, Depends(_get_rag_db)],
    query: str = Query(..., min_length=1, max_length=1000),
    top_k: int = Query(default=5, ge=1, le=20),
    rewrite: bool = Query(default=True),
) -> list[RagSearchResult]:
    """Tenant-filtered cosine similarity search over CMS chunks.

    tenant_id is derived from the verified JWT — never from the request body.
    Platform Manager tokens are rejected at the route boundary (403).
    """
    return await rag_service.rag_search(
        query=query,
        tenant_id=token.tenant_id,
        session=session,
        top_k=top_k,
        rewrite=rewrite,
    )
