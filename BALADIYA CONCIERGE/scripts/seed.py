#!/usr/bin/env python3
"""Seed script: create Platform Manager + 2 tenants from env vars.
Also seeds service tokens into Vault (idempotent).

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


def seed_vault_secrets():
    """Write service tokens into Vault KV so the API can read them at startup.

    Runs in local dev and CI where Vault is in dev mode.
    No-op if VAULT_ADDR is not reachable (e.g. unit-test environments).
    Returns the authenticated hvac client (for per-widget key seeding), or None.
    """
    vault_addr = os.environ.get("VAULT_ADDR", "http://localhost:8200")
    vault_token = os.environ.get("VAULT_TOKEN", "")
    guardrails_token = os.environ.get("GUARDRAILS_SERVICE_TOKEN", "dev-guardrails-token")
    widget_signing_key = os.environ.get("WIDGET_SIGNING_KEY", "dev-widget-signing-key-change-in-prod")
    database_url = os.environ.get("DATABASE_URL", "postgresql+asyncpg://baladiya:baladiya_dev@db:5432/baladiya")
    jwt_secret = os.environ.get("JWT_SECRET", "dev-jwt-secret-change-in-prod-2026")
    gemini_api_key = os.environ.get("GEMINI_API_KEY", "")
    groq_api_key = os.environ.get("GROQ_API_KEY", "")
    minio_access_key = os.environ.get("MINIO_ACCESS_KEY", "minioadmin")
    minio_secret_key = os.environ.get("MINIO_SECRET_KEY", "minioadmin")

    if not vault_token:
        print("[seed] VAULT_TOKEN not set — skipping Vault secret seeding")
        return None

    try:
        import hvac
        client = hvac.Client(url=vault_addr, token=vault_token)
        if not client.is_authenticated():
            print("[seed] Vault not authenticated — skipping secret seeding")
            return None

        client.secrets.kv.v2.create_or_update_secret(
            path="baladiya/db",
            secret={"url": database_url},
            mount_point="secret",
        )
        print("[seed] Seeded Vault secret: secret/baladiya/db")

        client.secrets.kv.v2.create_or_update_secret(
            path="baladiya/api",
            secret={"jwt_secret": jwt_secret},
            mount_point="secret",
        )
        print("[seed] Seeded Vault secret: secret/baladiya/api")

        # Only write LLM keys if they are non-empty — don't overwrite a real key
        # with an empty string when the migrate container lacks the env vars.
        if gemini_api_key or groq_api_key:
            client.secrets.kv.v2.create_or_update_secret(
                path="baladiya/llm",
                secret={"gemini_api_key": gemini_api_key, "groq_api_key": groq_api_key},
                mount_point="secret",
            )
            print("[seed] Seeded Vault secret: secret/baladiya/llm")
        else:
            print("[seed] Skipped secret/baladiya/llm — GEMINI_API_KEY/GROQ_API_KEY not set")

        client.secrets.kv.v2.create_or_update_secret(
            path="baladiya/minio",
            secret={"access_key": minio_access_key, "secret_key": minio_secret_key},
            mount_point="secret",
        )
        print("[seed] Seeded Vault secret: secret/baladiya/minio")

        client.secrets.kv.v2.create_or_update_secret(
            path="baladiya/guardrails",
            secret={"service_token": guardrails_token},
            mount_point="secret",
        )
        print("[seed] Seeded Vault secret: secret/baladiya/guardrails")

        client.secrets.kv.v2.create_or_update_secret(
            path="baladiya/widget",
            secret={"signing_key": widget_signing_key},
            mount_point="secret",
        )
        print("[seed] Seeded Vault secret: secret/baladiya/widget")

        # Per-widget key seeding (Phase 8 — FR-007) happens in main(), which is
        # already inside an event loop. Return the authenticated client so the
        # async step can reuse it.
        return client

    except Exception as exc:
        # Non-fatal: Vault may not be available in all environments
        print(f"[seed] Vault seeding skipped: {exc}")
        return None


async def _seed_per_widget_keys(client, default_key: str) -> None:
    """For each active widget in DB, seed Vault per-widget key if absent.

    Async — awaited from main()'s running event loop (no nested asyncio.run()).
    """
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from sqlalchemy import select, text
    from api.domain.widget import Widget

    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        print("[seed] DATABASE_URL not set — skipping per-widget key migration")
        return

    try:
        engine = create_async_engine(database_url)
        factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
        async with factory() as session:
            # Bypass RLS for seeding (no tenant context needed here)
            await session.execute(text("SET LOCAL app.current_tenant = ''"))
            result = await session.execute(select(Widget).where(Widget.is_active == True))  # noqa: E712
            widgets = list(result.scalars().all())
        await engine.dispose()

        for widget in widgets:
            vault_path = f"baladiya/widget/{widget.id}"
            try:
                client.secrets.kv.v2.read_secret_version(
                    path=vault_path, mount_point="secret"
                )
                # Already seeded — skip
            except Exception:
                client.secrets.kv.v2.create_or_update_secret(
                    path=vault_path,
                    secret={"signing_key": default_key},
                    mount_point="secret",
                )
                print(f"[seed] Seeded per-widget key: secret/{vault_path}")
    except Exception as exc:
        print(f"[seed] Per-widget key migration skipped: {exc}")


async def main() -> None:
    client = seed_vault_secrets()
    if client is not None:
        # Per-widget keys (Phase 8 — FR-007): seed baladiya/widget/{id}/signing_key
        # for each active widget, idempotently, using the global key as initial value.
        widget_signing_key = os.environ.get(
            "WIDGET_SIGNING_KEY", "dev-widget-signing-key-change-in-prod"
        )
        await _seed_per_widget_keys(client, widget_signing_key)
    database_url = os.environ["DATABASE_URL"]
    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        await seed(session)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
