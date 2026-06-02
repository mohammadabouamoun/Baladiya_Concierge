# Implementation Plan: Foundation & Tenant Isolation

**Branch**: `001-foundation-isolation` | **Date**: 2026-06-02 | **Spec**: [spec.md](./spec.md)

## Summary

Stand up the full Compose stack skeleton, implement the three-role model, enforce Postgres RLS on all tenant tables, wire Vault secrets, and prove isolation with a CI red-team gate. This phase is a hard prerequisite for every other feature.

## Technical Context

**Language/Version**: Python 3.11

**Primary Dependencies**: FastAPI 0.111+, SQLAlchemy 2.x (async), asyncpg, fastapi-users, alembic, pydantic-settings, structlog, tenacity, httpx, redis (async), minio

**Storage**: PostgreSQL 16 + pgvector extension + RLS; Redis 7; MinIO; HashiCorp Vault

**Testing**: pytest + pytest-asyncio; real DB (no mocks for isolation tests); httpx AsyncClient for API tests

**Target Platform**: Linux containers via Docker Compose

**Performance Goals**: Provisioning p95 < 2s; per-request session variable set/reset adds < 1ms overhead

**Constraints**: No globals; async all the way; no torch; images < 500 MB; `.env` holds only Vault root token + ports

**Scale/Scope**: 2 seeded tenants for dev/CI; designed for 10–100 active tenants

## Constitution Check

- [x] No torch in any container
- [x] tenant_id from JWT only
- [x] RLS + repo-layer double filter
- [x] Platform Manager cannot read tenant content
- [x] Red-team gate in CI

## Project Structure

### Documentation

```text
specs/001-foundation-isolation/
├── spec.md          ← this spec
├── plan.md          ← this file
└── tasks.md         ← task breakdown
```

### Source Code

```text
api/
├── main.py                  ← lifespan: DB engine, Redis pool, LLM client singletons
├── core/
│   ├── config.py            ← pydantic-settings Settings (Vault-resolved)
│   ├── security.py          ← JWT decode, tenant_id extraction
│   └── logging.py           ← structlog setup with trace_id + tenant_id
├── domain/
│   ├── tenant.py            ← Tenant, TenantAdmin, PlatformManager models
│   └── audit.py             ← AuditLog model
├── infra/
│   ├── db.py                ← async engine, session factory, RLS middleware
│   ├── vault.py             ← Vault client, refuse-to-boot if unreachable
│   ├── redis.py             ← async Redis pool
│   └── minio.py             ← MinIO client
├── repositories/
│   ├── base.py              ← BaseRepository with tenant_id filter enforced
│   └── tenant_repo.py       ← TenantRepository
├── services/
│   └── platform_service.py  ← provision, suspend, erase tenant logic
└── api/
    └── platform/
        ├── router.py        ← /platform/tenants CRUD (Platform Manager only)
        └── deps.py          ← require_platform_manager dependency

alembic/
├── env.py
└── versions/
    └── 001_baseline.py      ← tenants, users, audit_log + RLS policies

tests/
├── conftest.py              ← two real tenant fixtures, platform manager fixture
├── test_isolation/
│   ├── test_rls.py          ← direct DB: Tenant A cannot see Tenant B rows
│   ├── test_session_reset.py ← mid-request exception → next request clean
│   └── test_redteam.py      ← CI red-team gate: injection + cross-tenant probes
└── test_platform/
    └── test_provisioning.py ← provision, suspend, erase, audit log
```

## Key Design Decisions

### RLS Implementation

```sql
-- Per-table policy (applied to every tenant-owned table)
ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON {table}
    USING (tenant_id = current_setting('app.current_tenant')::uuid);
```

The session variable is set in a FastAPI middleware (or the `get_db` dependency's `try/finally`):

```python
async def get_db(token: ...) -> AsyncGenerator[AsyncSession, None]:
    async with session_factory() as session:
        await session.execute(
            text("SET LOCAL app.current_tenant = :tid"),
            {"tid": str(token.tenant_id)}
        )
        try:
            yield session
        finally:
            await session.execute(text("RESET app.current_tenant"))
```

### Repository Base Class

Every repository inherits `BaseRepository` which appends `.filter(Model.tenant_id == self.tenant_id)` to every query. This is the second isolation layer — it catches queries on tables that may not have RLS yet (e.g., a new migration that forgot the policy).

### Platform Manager Isolation

Platform Manager routes live under `/platform/` and use a separate `require_platform_manager` dependency that never sets the RLS session variable (they have no tenant context). Any attempt to query a tenant table from a platform route triggers RLS denial.

### Erasure Order

To avoid FK violations during erasure:
1. Redis: `DEL tenant:{tenant_id}:*`
2. pgvector embeddings table (no FKs pointing to it)
3. Tenant content/conversation/request tables
4. MinIO: delete all objects under `tenants/{tenant_id}/`
5. Users table (tenant admin accounts)
6. Tenants table (the tenant row itself)
7. Write AuditLog (on a platform-scoped connection, not tenant-scoped)

### Per-Tenant Rate Limiting

Redis sorted-set sliding window per `(tenant_id, endpoint)`. Configurable `requests_per_minute` stored in `tenant.settings`. Applied as a FastAPI dependency on all chat/agent routes.

## Compose Stack (this phase)

Services needed for this phase: `db`, `migrate`, `api`, `vault`, `redis` (required for rate limiting in T-050/T-051)

All other services (`chatbot`, `widget`, `modelserver`, `guardrails`, `redis`, `minio`, `host`) are stubbed in `docker-compose.yml` but not started until their feature phase.
