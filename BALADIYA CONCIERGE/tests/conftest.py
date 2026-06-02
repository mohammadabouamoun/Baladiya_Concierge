from __future__ import annotations

import asyncio
import uuid
from typing import AsyncGenerator

import bcrypt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from api.core.config import Settings, get_settings
from api.core.security import TokenClaims
from api.domain.audit import AuditLog
from api.domain.tenant import PlatformManager, Tenant, TenantAdmin
from api.infra.db import Base, get_session_factory
from api.main import app

TEST_DATABASE_URL = "postgresql+asyncpg://baladiya:baladiya_dev@localhost:5432/baladiya_test"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def engine():
    eng = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Apply RLS policies needed for tests
        await conn.execute(text("ALTER TABLE tenant_admins ENABLE ROW LEVEL SECURITY"))
        await conn.execute(text("ALTER TABLE tenant_admins FORCE ROW LEVEL SECURITY"))
        await conn.execute(
            text(
                """
                CREATE POLICY IF NOT EXISTS tenant_isolation ON tenant_admins
                    USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
                """
            )
        )
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest_asyncio.fixture
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def platform_manager(db_session: AsyncSession) -> PlatformManager:
    pm = PlatformManager(
        id=uuid.uuid4(),
        email=f"pm-{uuid.uuid4()}@test.local",
        hashed_password=bcrypt.hashpw(b"testpass", bcrypt.gensalt()).decode(),
    )
    db_session.add(pm)
    await db_session.commit()
    return pm


@pytest_asyncio.fixture
async def tenant_a(db_session: AsyncSession) -> tuple[Tenant, TenantAdmin]:
    tenant = Tenant(id=uuid.uuid4(), name="Municipality A", plan="standard", status="active")
    db_session.add(tenant)
    await db_session.flush()
    admin = TenantAdmin(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email=f"admin-a-{uuid.uuid4()}@test.local",
        hashed_password=bcrypt.hashpw(b"testpass", bcrypt.gensalt()).decode(),
    )
    db_session.add(admin)
    await db_session.commit()
    return tenant, admin


@pytest_asyncio.fixture
async def tenant_b(db_session: AsyncSession) -> tuple[Tenant, TenantAdmin]:
    tenant = Tenant(id=uuid.uuid4(), name="Municipality B", plan="standard", status="active")
    db_session.add(tenant)
    await db_session.flush()
    admin = TenantAdmin(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email=f"admin-b-{uuid.uuid4()}@test.local",
        hashed_password=bcrypt.hashpw(b"testpass", bcrypt.gensalt()).decode(),
    )
    db_session.add(admin)
    await db_session.commit()
    return tenant, admin


def make_token(user_id: uuid.UUID, role: str, tenant_id: uuid.UUID | None) -> TokenClaims:
    return TokenClaims(user_id=user_id, role=role, tenant_id=tenant_id)


@pytest_asyncio.fixture
async def http_client() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client
