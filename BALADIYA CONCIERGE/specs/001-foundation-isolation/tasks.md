# Tasks: Foundation & Tenant Isolation

**Branch**: `001-foundation-isolation` | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

---

## Phase 1: Setup & Scaffold

- [X] **T-001** Initialize repo structure: `api/`, `alembic/`, `tests/`, `specs/`, `prompts/`, `notebooks/`, `evals/`, `docker-compose.yml`, `.env.example`
- [X] **T-001a** Create `eval_thresholds.yaml` with all required keys at placeholder values (0.0); keys: `classifier_macro_f1`, `en_macro_f1`, `ar_macro_f1`, `classifier_confidence_thresholds` (report:0.75 / question:0.75 / human:0.65 / spam:0.90), `agent_tool_accuracy`, `rag_hit_at_5`, `rag_mrr`, `rag_faithfulness`, `redteam_pass_rate: 1.0`
- [X] **T-001b** Create `evals/.gitkeep` — directory holds `rag_golden.json`, `agent_tool_selection.json`, `redteam_probes.json` (populated in later phases)
- [X] **T-002** Write `docker-compose.yml` with all 11 services stubbed; active in this phase: `db`, `vault`, `migrate`, `api`, `redis` (redis required for rate limiting)
- [X] **T-003** Configure `api/core/config.py` — `pydantic-settings` `Settings` class, `extra="forbid"`, all secrets resolve from Vault env vars; service refuses to boot if Vault is unreachable
- [X] **T-004** Configure `api/core/logging.py` — `structlog` with `trace_id` + `tenant_id` processors; JSON output in prod, colored in dev
- [X] **T-005** Wire `api/main.py` lifespan: DB engine, Redis pool, MinIO client, LLM/embedding HTTP clients loaded once at startup

---

## Phase 2: Foundational — DB, RLS, Auth

*No feature work can start until this phase is complete.*

- [X] **T-010** Write Alembic baseline migration: `tenants`, `platform_managers`, `tenant_admins`, `audit_log` tables with correct FK relations and `tenant_id` columns on all tenant-owned tables
- [X] **T-011** Apply RLS policies in migration: `ENABLE ROW LEVEL SECURITY` + `CREATE POLICY tenant_isolation` on every tenant-owned table using `current_setting('app.current_tenant')::uuid`
- [X] **T-012** Implement `api/infra/db.py` — async SQLAlchemy engine, `get_db` dependency that sets `SET LOCAL app.current_tenant` and resets in `finally`
- [X] **T-013** Implement `api/infra/vault.py` — Vault client wrapper; `load_secrets()` called at lifespan startup; raises `StartupError` if Vault unreachable
- [X] **T-014** Implement `api/infra/redis.py` — async Redis pool (aioredis/redis-py async)
- [X] **T-015** Implement `fastapi-users` JWT auth: `tenant_id` + `role` embedded in JWT payload at issuance; `get_current_user` dependency validates and extracts both
- [X] **T-016** Implement `api/repositories/base.py` — `BaseRepository` that enforces `.filter(Model.tenant_id == self.tenant_id)` on every query; raises `TenantScopeError` if `tenant_id` is missing
- [X] **T-017** Implement domain models: `Tenant`, `TenantAdmin`, `PlatformManager`, `AuditLog` (SQLAlchemy mapped classes + Pydantic schemas)

---

## Phase 3: Provisioning (US1)

- [X] **T-020** Implement `require_platform_manager` dependency — validates JWT role=platform_manager; never sets tenant RLS variable
- [X] **T-021** Implement `platform_service.provision_tenant()` — creates tenant row, creates tenant_admin user, writes audit log; idempotent on duplicate email
- [X] **T-022** Implement `POST /platform/tenants` route using `platform_service.provision_tenant()`
- [X] **T-023** Implement `GET /platform/tenants` — list all tenants with status; Platform Manager only
- [X] **T-024** Seed script (run by `migrate` container after Alembic): create Platform Manager account + 2 tenants (Municipality A, Municipality B) from `.env` values
- [X] **T-025** [P] Write `tests/test_platform/test_provisioning.py` — provision two tenants, verify isolation, verify idempotency

---

## Phase 4: Isolation Proof (US2 + US3)

- [X] **T-030** Write `tests/test_isolation/test_rls.py` — direct asyncpg connection: set session variable to Tenant A, query returns only Tenant A rows; same for Tenant B
- [X] **T-031** Write `tests/test_isolation/test_session_reset.py` — simulate mid-request exception for Tenant A; verify next request on same connection returns Tenant B data correctly (not Tenant A's)
- [X] **T-032** Write `tests/test_isolation/test_redteam.py` — isolation-only probes (NOT the full CI red-team gate, which is owned by phase 005):
  - Probe 1: POST with Tenant A token but Tenant B `tenant_id` in body → response scoped to Tenant A
  - Probe 2: POST with Tenant A token and `tenant_id` in query param → ignored, scoped to Tenant A
  - These tests verify DB isolation only; prompt injection probes are in `005-guardrails-security/tests/test_security/test_redteam.py`
- [X] **T-033** Add red-team test to `eval_thresholds.yaml`: `redteam_pass_rate: 1.0` (all probes must be refused)
- [X] **T-034** [P] Write `tests/test_isolation/test_platform_manager_access.py` — Platform Manager cannot SELECT from tenant conversation, request, or content tables via any API route

---

## Phase 5: Suspension & Erasure (US4)

- [X] **T-040** Implement `platform_service.suspend_tenant()` — sets `tenant.status = suspended`; JWT issuance for that tenant returns `403`
- [X] **T-041** Implement `platform_service.erase_tenant()` — ordered deletion: Redis sessions → pgvector embeddings → tenant content tables → MinIO blobs → tenant admin users → tenant row → AuditLog write
- [X] **T-042** Implement `POST /platform/tenants/{id}/suspend` and `DELETE /platform/tenants/{id}` routes
- [X] **T-043** Write `tests/test_platform/test_erasure.py` — erase Tenant B, run post-delete sweep confirming zero orphan rows/vectors/blobs/sessions

---

## Phase 6: Rate Limiting & Cost Attribution

- [X] **T-050** Implement Redis sliding-window rate limiter as a FastAPI dependency; reads `tenant.settings.requests_per_minute`; returns `429` when exceeded
- [X] **T-051** Implement cost attribution middleware — wraps LLM/embedding calls with a `tenant_id` tag; logs to `structlog` with `cost_tokens` field
- [X] **T-052** [P] Write unit tests for rate limiter (mock Redis)

---

## Dependencies & Execution Order

```
T-001 → T-002 → T-003 → T-004 → T-005
T-005 → T-010 → T-011 → T-012 → T-013 → T-014 → T-015 → T-016 → T-017
T-017 → T-020 → T-021 → T-022 → T-023 → T-024
T-024 → T-030, T-031, T-032 (can run in parallel [P])
T-017 → T-040 → T-041 → T-042 → T-043
T-012 → T-050 → T-051
```

**Gate**: All tests in `tests/test_isolation/` must pass (including red-team) before moving to feature `002-classifier`. This gate is enforced in CI.
