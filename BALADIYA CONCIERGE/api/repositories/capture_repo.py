"""Repositories for CaptureRequest and EscalationTicket — both tenant-scoped."""
from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from api.domain.capture_request import CaptureRequest, CaptureRequestCreate, EscalationTicket
from api.repositories.base import BaseRepository


class CaptureRequestRepository(BaseRepository[CaptureRequest]):
    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID) -> None:
        super().__init__(session, tenant_id, CaptureRequest)

    async def create(self, payload: CaptureRequestCreate, session_id: str) -> CaptureRequest:
        """Create a capture request. tenant_id always comes from self._tenant_id."""
        record = CaptureRequest(
            tenant_id=self._tenant_id,
            session_id=session_id,
            intent=payload.intent,
            description=payload.description,
            name=payload.name,
            contact=payload.contact,
            location=payload.location,
        )
        return await self.add(record)

    async def list_by_session(self, session_id: str) -> list[CaptureRequest]:
        return await self.list(session_id=session_id)

    async def update_status(self, record_id: uuid.UUID, status: str) -> CaptureRequest | None:
        record = await self.get(record_id)
        if record is None:
            return None
        record.status = status
        await self._session.flush()
        return record
