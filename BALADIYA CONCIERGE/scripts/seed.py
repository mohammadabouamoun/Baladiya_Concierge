#!/usr/bin/env python3
"""Seed script: create Platform Manager + 2 tenants from env vars.

Run by the `migrate` container after Alembic finishes.
Idempotent — safe to run multiple times.
"""
from __future__ import annotations

import asyncio
import os
import uuid

import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.domain.tenant import Tenant, TenantAdmin
from api.domain.audit import AuditLog
from api.infra.db import Base

# Import models so metadata is registered
import api.domain.tenant  # noqa: F401
import api.domain.audit   # noqa: F401

from sqlalchemy.dialects.postgresql import insert as pg_insert
from api.domain.tenant import PlatformManager


def _hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


async def seed(session: AsyncSession) -> None:
    # ── Platform Manager ──────────────────────────────────────────────────
    pm_email = os.environ["PLATFORM_MANAGER_EMAIL"]
    pm_password = os.environ["PLATFORM_MANAGER_PASSWORD"]

    existing_pm = (
        await session.execute(
            select(PlatformManager).where(PlatformManager.email == pm_email)
        )
    ).scalar_one_or_none()

    if not existing_pm:
        pm = PlatformManager(
            id=uuid.uuid4(),
            email=pm_email,
            hashed_password=_hash(pm_password),
        )
        session.add(pm)
        await session.flush()
        print(f"[seed] Created platform manager: {pm_email}")
    else:
        pm = existing_pm
        print(f"[seed] Platform manager already exists: {pm_email}")

    # ── Tenants ───────────────────────────────────────────────────────────
    tenant_configs = [
        {
            "name": os.environ["TENANT_A_NAME"],
            "admin_email": os.environ["TENANT_A_ADMIN_EMAIL"],
            "admin_password": os.environ["TENANT_A_ADMIN_PASSWORD"],
        },
        {
            "name": os.environ["TENANT_B_NAME"],
            "admin_email": os.environ["TENANT_B_ADMIN_EMAIL"],
            "admin_password": os.environ["TENANT_B_ADMIN_PASSWORD"],
        },
    ]

    for cfg in tenant_configs:
        existing_admin = (
            await session.execute(
                select(TenantAdmin).where(TenantAdmin.email == cfg["admin_email"])
            )
        ).scalar_one_or_none()

        if existing_admin:
            print(f"[seed] Tenant already exists for admin: {cfg['admin_email']}")
            continue

        tenant = Tenant(
            id=uuid.uuid4(),
            name=cfg["name"],
            plan="standard",
            status="active",
            settings={"requests_per_minute": 60},
        )
        session.add(tenant)
        await session.flush()

        admin = TenantAdmin(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            email=cfg["admin_email"],
            hashed_password=_hash(cfg["admin_password"]),
            role="tenant_admin",
        )
        session.add(admin)

        audit = AuditLog(
            actor_id=pm.id,
            actor_role="platform_manager",
            action="provision_tenant",
            tenant_id=tenant.id,
            metadata_={"source": "seed", "tenant_name": cfg["name"]},
        )
        session.add(audit)
        print(f"[seed] Created tenant '{cfg['name']}' with admin {cfg['admin_email']}")

    await session.commit()
    print("[seed] Done.")


async def main() -> None:
    database_url = os.environ["DATABASE_URL"]
    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        await seed(session)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
