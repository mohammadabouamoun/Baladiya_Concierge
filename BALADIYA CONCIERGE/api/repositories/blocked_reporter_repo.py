"""Repository for BlockedReporter — tracks phone hashes flagged for false reports."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.domain.verification import BlockedReporter

logger = structlog.get_logger(__name__)


class BlockedReporterRepository:
    """Not a BaseRepository — blocked_reporters is admin-scoped, not chat-scoped.

    Reads use the platform-level DB session (RLS off for platform manager or
    set to the correct tenant for tenant admin).
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def is_blocked(self, tenant_id: uuid.UUID, phone_hash: str) -> bool:
        """Return True if this phone is blocked from submitting reports in this tenant."""
        result = await self._session.execute(
            select(BlockedReporter).where(
                BlockedReporter.tenant_id == tenant_id,
                BlockedReporter.phone_hash == phone_hash,
                BlockedReporter.blocked == True,  # noqa: E712
            )
        )
        return result.scalar_one_or_none() is not None

    async def record_false_report(self, tenant_id: uuid.UUID, phone_hash: str) -> BlockedReporter:
        """Increment false_report_count; create the row if it doesn't exist.

        After first false flag the reporter is blocked.
        """
        result = await self._session.execute(
            select(BlockedReporter).where(
                BlockedReporter.tenant_id == tenant_id,
                BlockedReporter.phone_hash == phone_hash,
            )
        )
        row = result.scalar_one_or_none()

        if row is None:
            row = BlockedReporter(
                tenant_id=tenant_id,
                phone_hash=phone_hash,
                false_report_count=1,
                blocked=True,
            )
            self._session.add(row)
        else:
            row.false_report_count += 1
            row.blocked = True
            row.updated_at = datetime.now(timezone.utc)

        await self._session.flush()
        logger.warning(
            "blocked_reporter.flagged",
            tenant_id=str(tenant_id),
            phone_hash=phone_hash[:8] + "****",
            count=row.false_report_count,
        )
        return row
