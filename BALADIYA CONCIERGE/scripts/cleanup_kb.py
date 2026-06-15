"""Delete leftover eval/test KB entries from the Beirut tenant.

Removes entries whose title is a known eval-seed placeholder (and their chunks).
Idempotent: matches by exact title, skips anything already gone.

    docker compose exec -T api python - < scripts/cleanup_kb.py
"""
import asyncio
import os
import uuid

from sqlalchemy import text

from api.core.config import get_settings
from api.infra.db import init_db, get_session_factory
import api.domain.tenant  # noqa: F401
from api.repositories.cms_repo import CmsEntryRepository, CmsChunkRepository

TENANT_ID = "4667fd7f-944b-4ea8-bf07-657cf4b4b880"
JUNK_TITLES = {"Test Vector Entry", "Test Entry", "Fresh Test"}


async def main() -> None:
    settings = get_settings()
    db_url = getattr(settings, "database_url", None) or os.environ["DATABASE_URL"]
    await init_db(db_url)
    tenant = uuid.UUID(TENANT_ID)
    factory = get_session_factory()

    deleted = 0
    async with factory() as session:
        await session.execute(text(f"SET app.current_tenant = '{TENANT_ID}'"))
        entry_repo = CmsEntryRepository(session, tenant)
        chunk_repo = CmsChunkRepository(session, tenant)

        for entry in await entry_repo.list_entries():
            if entry.title in JUNK_TITLES:
                await chunk_repo.delete_by_entry(entry.id)
                await session.delete(entry)
                print(f"  deleted: {str(entry.id)[:8]} | {entry.lang} | {entry.category} | {entry.title}")
                deleted += 1

        await session.commit()
        remaining = len(await entry_repo.list_entries())
        await session.execute(text("RESET app.current_tenant"))

    print(f"\nDeleted {deleted} junk entries. {remaining} entries remain.")


asyncio.run(main())
