from __future__ import annotations

from collections.abc import AsyncGenerator

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from api.core.security import TokenClaims

logger = structlog.get_logger(__name__)

_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


class Base(DeclarativeBase):
    pass


async def init_db(database_url: str) -> None:
    global _engine, _session_factory
    _engine = create_async_engine(
        database_url,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )
    _session_factory = async_sessionmaker(
        _engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )
    logger.info("db.connected", url=database_url.split("@")[-1])


async def close_db() -> None:
    if _engine:
        await _engine.dispose()
        logger.info("db.disconnected")


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    if _session_factory is None:
        raise RuntimeError("DB not initialised — call init_db() at startup")
    return _session_factory


async def get_db(token: TokenClaims) -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yields a session with the RLS tenant variable set.

    The variable is always reset in the finally block — even on exception —
    so pooled connections never carry a previous tenant's context.
    """
    factory = get_session_factory()
    async with factory() as session:
        if token.tenant_id is not None:
            await session.execute(
                text("SET LOCAL app.current_tenant = :tid"),
                {"tid": str(token.tenant_id)},
            )
        try:
            yield session
        finally:
            # Reset unconditionally — guards against exception paths
            await session.execute(text("RESET app.current_tenant"))
