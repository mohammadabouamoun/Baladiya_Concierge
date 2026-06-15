"""CMS CRUD routes — tenant admin only.

All routes derive tenant_id from the verified JWT token, never from the request body.
"""
from __future__ import annotations

import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.api.cms.deps import require_tenant_admin
from api.core.security import TokenClaims
from api.domain.cms import CmsEntryCreate, CmsEntryRead, CmsEntryUpdate
from api.infra.db import get_db
from api.services import cms_service

logger = structlog.get_logger(__name__)

router = APIRouter()


async def _get_tenant_db(
    token: Annotated[TokenClaims, Depends(require_tenant_admin)],
) -> AsyncSession:
    async for session in get_db(token):
        yield session


@router.get("/entries", response_model=list[CmsEntryRead])
async def list_entries(
    token: Annotated[TokenClaims, Depends(require_tenant_admin)],
    session: Annotated[AsyncSession, Depends(_get_tenant_db)],
    category: str | None = None,
) -> list[CmsEntryRead]:
    from api.repositories.cms_repo import CmsEntryRepository
    repo = CmsEntryRepository(session, token.tenant_id)
    entries = await repo.list_entries(category=category)
    return [CmsEntryRead.model_validate(e) for e in entries]


@router.post("/entries", response_model=CmsEntryRead, status_code=status.HTTP_201_CREATED)
async def create_entry(
    payload: CmsEntryCreate,
    token: Annotated[TokenClaims, Depends(require_tenant_admin)],
    session: Annotated[AsyncSession, Depends(_get_tenant_db)],
) -> CmsEntryRead:
    entry = await cms_service.create_entry(session, token.tenant_id, payload)
    logger.info(
        "cms.entry_created",
        entry_id=str(entry.id),
        tenant_id=str(token.tenant_id),
        status=entry.embedding_status,
    )
    return CmsEntryRead.model_validate(entry)


@router.put("/entries/{entry_id}", response_model=CmsEntryRead)
async def update_entry(
    entry_id: uuid.UUID,
    payload: CmsEntryUpdate,
    token: Annotated[TokenClaims, Depends(require_tenant_admin)],
    session: Annotated[AsyncSession, Depends(_get_tenant_db)],
) -> CmsEntryRead:
    entry = await cms_service.update_entry(
        session,
        token.tenant_id,
        entry_id,
        title=payload.title,
        body=payload.body,
        category=payload.category,
        lang=payload.lang,
    )
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")
    logger.info(
        "cms.entry_updated",
        entry_id=str(entry_id),
        tenant_id=str(token.tenant_id),
        status=entry.embedding_status,
    )
    return CmsEntryRead.model_validate(entry)


@router.delete("/entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_entry(
    entry_id: uuid.UUID,
    token: Annotated[TokenClaims, Depends(require_tenant_admin)],
    session: Annotated[AsyncSession, Depends(_get_tenant_db)],
) -> None:
    from api.repositories.cms_repo import CmsEntryRepository
    repo = CmsEntryRepository(session, token.tenant_id)
    entry = await repo.get_by_id(entry_id)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")
    await cms_service.delete_entry_vectors(entry_id, token.tenant_id, session)
    await repo.delete(entry)
    await session.commit()
    logger.info(
        "cms.entry_deleted",
        entry_id=str(entry_id),
        tenant_id=str(token.tenant_id),
    )
