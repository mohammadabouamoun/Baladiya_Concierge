"""Repository for EscalationTicket — tenant-scoped."""
from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from api.domain.capture_request import EscalationTicket
from api.repositories.base import BaseRepository


class EscalationTicketRepository(BaseRepository[EscalationTicket]):
    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID) -> None:
        super().__init__(session, tenant_id, EscalationTicket)

    async def create(
        self,
        reason: str,
        capture_request_id: uuid.UUID | None = None,
    ) -> EscalationTicket:
        """Create an escalation ticket. tenant_id always comes from self._tenant_id."""
        ticket = EscalationTicket(
            tenant_id=self._tenant_id,
            capture_request_id=capture_request_id,
            reason=reason,
        )
        return await self.add(ticket)

    async def update_status(self, ticket_id: uuid.UUID, status: str) -> EscalationTicket | None:
        ticket = await self.get(ticket_id)
        if ticket is None:
            return None
        ticket.status = status
        await self._session.flush()
        return ticket
