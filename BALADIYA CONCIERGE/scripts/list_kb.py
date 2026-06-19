"""List all KB entries for the Beirut tenant (dry-run inspection before cleanup)."""
import asyncio
import os
import uuid

from sqlalchemy import text

from api.core.config import get_settings
from api.infra.db import init_db, get_session_factory
import api.domain.tenant  # noqa: F401
from api.repositories.cms_repo import CmsEntryRepository

TENANT_ID = "4667fd7f-944b-4ea8-bf07-657cf4b4b880"


async def main() -> None:
    settings = get_settings()
    db_url = getattr(settings, "database_url", None) or os.environ["DATABASE_URL"]
    await init_db(db_url)
    tenant = uuid.UUID(TENANT_ID)
    factory = get_session_factory()
    async with factory() as session:
        await session.execute(text(f"SET app.current_tenant = '{TENANT_ID}'"))
        repo = CmsEntryRepository(session, tenant)
        entries = await repo.list_entries()
        await session.execute(text("RESET app.current_tenant"))

    print(f"\n{len(entries)} entries\n" + "-" * 80)
    for e in sorted(entries, key=lambda x: (x.lang, x.category)):
        print(f"  {str(e.id)[:8]} | {e.lang} | {e.category:<12} | {e.title[:40]:<40} | {e.body[:50]!r}")


asyncio.run(main())
