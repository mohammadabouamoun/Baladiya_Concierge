# HANDOFF.md — Baladiya Concierge

> Snapshot of project state as of **2026-06-06**. Written for the next agent session or future self picking up this repo cold. Read this before touching any spec file or running any skill.
> **Updated**: Phase 8 (Hardening & Evals) complete — Arabic PII redaction, per-widget JWT key rotation, defense docs, real-text EN eval. Arabizi expansion and live eval runs deferred (need data work / docker stack).

---

## 1. Current Phase

| Field | Value |
|---|---|
| **Active feature** | `008` (complete) |
| **Status** | **Phases 1–8 complete — ready to start Phase 9** |
| **Last completed task** | Phase 8 — Arabic name PII redaction, per-widget JWT rotation, defense docs, real-text eval |
| **Last commit** | Phase 8 — hardening & evals |
| **Next task to start** | Define Phase 9 scope; run `/speckit-specify` |
| **How to start** | Update `feature.json` to `specs/009-...`; run `/speckit-specify` |

---

## 2. What Was Built

### Phase 1 — Foundation & Tenant Isolation (`001-foundation-isolation`) ✅

**All 28 tasks complete.**

| Area | Files Created |
|---|---|
| API scaffold | `api/main.py`, `api/core/config.py`, `api/core/logging.py`, `api/core/security.py` |
| Infra | `api/infra/db.py`, `api/infra/vault.py`, `api/infra/redis.py`, `api/infra/cost.py`, `api/infra/rate_limit.py` |
| Domain models | `api/domain/tenant.py`, `api/domain/audit.py` |
| Repositories | `api/repositories/base.py`, `api/repositories/tenant_repo.py` |
| Services | `api/services/platform_service.py` |
| Platform API | `api/api/platform/router.py`, `api/api/platform/deps.py` |
| DB migrations | `alembic/versions/001_baseline.py` (tenants + RLS), `alembic/env.py`, `alembic.ini` |
| Docker | `docker-compose.yml` (11 services), `docker/api.Dockerfile`, `docker/migrate.Dockerfile` |
| Seed | `scripts/seed.py` — Platform Manager + 2 tenants from env vars (idempotent) |
| Tests | `tests/conftest.py`, `tests/test_isolation/` (RLS + session reset + red-team + PM access), `tests/test_platform/` (provisioning + erasure + rate limiter) |
| Config | `.env.example`, `eval_thresholds.yaml`, `pytest.ini`, `requirements.txt`, `requirements-dev.txt` |

**Key architectural facts:**
- `get_db()` sets `SET LOCAL app.current_tenant` and resets in `finally` — always, even on exception
- `BaseRepository` enforces `.filter(tenant_id == ...)` on every query (second isolation layer)
- Platform Manager token has `tenant_id=None` — RLS is never set for PM routes by design
- Erasure order: Redis sessions → pgvector (future) → content tables → MinIO → TenantAdmin users → Tenant row → AuditLog write

---

### Phase 2 — Classifier & Model Server (`002-classifier`) ✅

**All 17 tasks complete.**

| Area | Files Created |
|---|---|
| Training notebook | `notebooks/train_classifier.ipynb` — executed; outputs committed |
| Model server | `modelserver/main.py`, `modelserver/classifier.py`, `modelserver/Dockerfile`, `modelserver/requirements.txt` |
| Artifact | `modelserver/artifacts/classifier.joblib` (0.53 MB) |
| Model card | `modelserver/model_card.md` — two-way comparison table (Classical ML vs LLM zero-shot) |
| API integration | `api/infra/modelserver_client.py`, `api/services/router_service.py` |
| Tests | `tests/test_classifier/test_classifier_gate.py`, `tests/test_classifier/test_modelserver.py` |
| CI | `.github/workflows/ci.yml` — unit tests, latency gate, image size gate, red-team gate |
| Dataset | `civic_intent_dataset.csv` — 12,731 rows (updated Phase 7); see §6 for breakdown |

**Trained model results — Phase 7 bilingual retrain (2026-06-06, 12,731-row dataset):**

| Approach | Macro-F1 | EN F1 | AR F1 | Arabizi F1 | p50 | p95 |
|---|---|---|---|---|---|---|
| **Classical ML (shipped)** | **0.9980** | **1.0000** | **0.9507** | **0.8322** | **1.48ms** | **3.97ms** |
| LLM zero-shot (Groq llama-3.3-70b) | 0.8291 | 0.7358 | 0.8512 | — | 2220ms | — |

*Phase 2 original results (547-row EN-only): Macro-F1=0.8983, EN F1=0.8784, AR F1=0.8117, p50=2.2ms*

**Artifact SHA-256**: `728a4bf1aee84c015ddd9d73d998573a179bd32085a9b39330a50306f177b041`
**Data SHA-256**: `5f3c9e954ee01981546584732da8f93e1cd957519e7cea3658c8224fa19bac17`

---

### Phase 3 — CMS & RAG (`003-cms-rag`) ✅

**All 17 tasks complete.**

| Area | Files Created |
|---|---|
| DB migration | `alembic/versions/002_cms_rag.py` — `cms_entries` + `cms_chunks` (vector(1536), HNSW), tenant RLS |
| Embedding client | `api/infra/embedding_client.py` — async httpx client for `gemini-embedding-001` (1536 dims) |
| Domain models | `api/domain/cms.py` — `CmsEntry`, `CmsChunk` SQLAlchemy + Pydantic schemas |
| Repository | `api/repositories/cms_repo.py` — `CmsRepository`, `CmsChunkRepository` inheriting `BaseRepository` |
| CMS service | `api/services/cms_service.py` — `chunk_and_embed`, `delete_entry_vectors`, background retry |
| RAG service | `api/services/rag_service.py` — query rewrite → embed → tenant-filtered pgvector cosine search |
| CMS API | `api/api/cms/router.py` — CRUD routes (tenant_admin only); `api/api/auth/router.py` — JWT login |
| RAG API | `api/api/rag/router.py` — `/rag/search` endpoint |
| Streamlit UI | `chatbot/pages/cms.py` — CMS list/create/edit/delete with embedding status badge |
| Eval golden set | `evals/rag_golden.json` — 15 hand-labelled triples (8 EN, 4 AR cross-language, 3 rephrases) |
| Eval scripts | `evals/evaluate_rag.py` — baseline vs query-rewrite comparison; `evals/seed_eval_content.py` |
| Tests | `tests/test_rag/test_rag_gate.py`, `test_tenant_isolation.py`, `test_cross_language.py` |
| Thresholds | `eval_thresholds.yaml` — `rag_hit_at_5: 0.73`, `rag_mrr: 0.60` (pre-measurement targets) |

**Key architectural facts:**
- Query rewrite via `gemini-2.5-flash` is the shipped strategy (fails-open to raw query on error)
- `cms_chunks` has `tenant_id` RLS + repository-layer filter — same dual-filter as all other tables
- Chunking: paragraph-boundary split, 512-token cap, 100-token min, 50-token overlap
- Embedding model is `gemini-embedding-001` with `outputDimensionality=1536` — never change, corpus is committed to this vector space

---

### Phase 4 — Router & Agent (`004-router-agent`) ✅

**All 22 tasks complete. `/speckit-analyze` remediation also applied (14 fixes).**

| Area | Files Created |
|---|---|
| DB migration | `alembic/versions/003_router_agent.py` — `capture_requests` + `escalation_tickets`, tenant RLS |
| Domain models | `api/domain/capture_request.py` — `CaptureRequest`, `EscalationTicket`, `CaptureRequestCreate` (strict Pydantic) |
| Session schema | `api/domain/session.py` — `SessionMemory`, `SessionTurn` Pydantic |
| Session service | `api/services/session_service.py` — Redis get/set/expire, `flush_tenant()` (SCAN-based) |
| Repositories | `api/repositories/capture_repo.py`, `api/repositories/escalation_repo.py` (both BaseRepository) |
| LLM client | `api/infra/llm_client.py` — Gemini-2.5-flash primary + Groq fallback; `asyncio.to_thread`; `_GeminiFailureTracker` class |
| Tools | `api/services/tools/rag_search.py`, `capture_request.py`, `escalate.py` |
| Agent service | `api/services/agent_service.py` — bounded loop (`max_tool_calls=3`), auto-escalate on cap |
| Router service | `api/services/router_service.py` — updated with `handle()` — full workflow dispatcher |
| Chat API | `api/api/chat/router.py` — `POST /chat` + `POST /chat/token` |
| Admin API | `api/api/admin/router.py` — capture_requests + escalation_tickets list for tenant admin |
| Prompts | `prompts/system_en.md`, `prompts/system_ar.md` — `{{persona}}` placeholder |
| Streamlit | `chatbot/pages/requests.py`, `chatbot/pages/escalations.py` |
| Eval set | `evals/agent_tool_selection.json` — 15 labelled examples (EN/MSA/Lebanese/Arabizi) |
| Eval script | `evals/evaluate_agent.py` — live LLM accuracy + SC-004 latency (p50/p95) |
| Tests | `tests/test_agent/` — 12 tests: tool_selection, capture_injection, session_scoping, rate_limit, latency, modelserver_down |

**Key architectural facts:**
- Workflow path (confident classifier): `spam→drop`, `report→capture_request`, `question→rag_search`, `human→escalate` — **no agent LLM call**
- Agent path (below threshold): bounded loop up to `max_tool_calls=3`, auto-escalates on cap
- `capture_request` tool: strips `tenant_id` from args before Pydantic validation — injection-proof by construction
- Per-session rate limit key: `capture_ratelimit:{session_id}:{tenant_id}`, window 60s
- Session key: `session:{session_id}:{tenant_id}`, TTL 1800s — justified in `DECISIONS.md §D10`
- LLM fallback: `_GeminiFailureTracker.count ≥ 3` → switches to Groq; resets on success
- Persona fetched from `tenant.settings["persona"]` at request time — never hardcoded

---

### Phase 5 — Guardrails & Security (`005-guardrails-security`) ✅

**All 22 tasks complete. `/speckit-analyze` remediation applied (11 fixes).**

| Area | Files Created/Modified |
|---|---|
| Guardrails sidecar | `guardrails/Dockerfile`, `guardrails/requirements.txt`, `guardrails/main.py` |
| Platform rails (hardcoded) | `guardrails/rails/platform/injection.py`, `jailbreak.py`, `cross_tenant.py`, `pii_detect.py` |
| Rail config | `guardrails/rails/platform/config.yml`, `prompts.yml` |
| Tenant overlay | `guardrails/rails/tenant_overlay.py` — blocked topics, refusal tone, tool filter |
| API client | `api/infra/guardrails_client.py` — fail-closed (`GuardrailUnavailable` → 503) |
| API middleware | `api/middleware/guardrails_middleware.py`, `api/middleware/redaction.py` |
| API wiring | `api/main.py`, `api/core/config.py`, `api/api/chat/router.py` |
| Admin UI | `chatbot/pages/guardrails.py` — guardrail config page |
| Admin API | `api/api/admin/router.py` — `GET/PATCH /admin/settings` for tenant guardrail config |
| Red-team probes | `evals/redteam_probes.json` — 14 probes (12 refused, 2 pass-through) |
| Tests | `tests/test_security/` — 56 tests (51 pass, 1 skipped, 0 fail) |
| CI gates | `.github/workflows/ci.yml` — 3 new jobs: guardrails-redteam, pii-redaction, service-auth |
| Vault seed | `scripts/seed.py` — seeds `baladiya/guardrails/service_token` at boot |

**Key architectural facts:**
- Platform rails implemented as **Python regex** (deterministic for CI, < 1ms — well within the 100ms SC-003 budget)
- `guardrails/` sidecar runs on **port 8002**; modelserver on 8001 — do NOT swap these
- `presidio_analyzer` lives only in the guardrails container; API middleware uses lightweight inline regex
- `pii_detect` import in `guardrails/main.py` is **lazy** — tests work without presidio installed in the dev venv
- PII redaction order in `redaction.py`: phone patterns run **before** NID to prevent digit sequences inside phone numbers from double-triggering the 6-digit NID pattern
- `TenantRepository` does NOT exist — use `PlatformTenantRepository` for cross-tenant reads
- Guardrails `X-Service-Token` is in Vault at `baladiya/guardrails/service_token`
- `POST /chat` flow: redact PII → check tenant status → fetch guardrail config → run guardrails → route to workflow/agent

---

### Phase 6 — Embeddable Widget (`006-widget`) ✅

**All 22 tasks complete. `/speckit-analyze` remediation applied. Widget UI redesigned.**

| Area | Files Created/Modified |
|---|---|
| DB migration | `alembic/versions/004_widget.py` — `widgets` table + RLS (`tenant_id`, `allowed_origins text[]`, `is_active`) |
| Domain model | `api/domain/widget.py` — `Widget` ORM, `WidgetCreate/Read/Update`, `WidgetConfig` (incl. `enabled_tools`, `persona`) |
| Repositories | `api/repositories/widget_repo.py` — `WidgetRepository` (BaseRepository) + `PlatformWidgetRepository` (unscoped, public lookup) |
| Service | `api/services/widget_service.py` — `create_widget()`, `update_widget()` (ORM ops out of router) |
| Token service | `api/api/widget/token_service.py` — origin validation → signed JWT (TTL 3600s) |
| Widget router | `api/api/widget/router.py` — `GET /widget.js`, `GET /widget/token`, `GET /widget/config`, widget CRUD |
| Config | `api/core/config.py` — added `widget_signing_key` field + Vault fetch |
| Security | `api/core/security.py` — `TokenClaims` now carries optional `widget_id` (parsed from JWT) |
| Chat router | `api/api/chat/router.py` — added tenant status check (suspended → 403) before guardrails |
| Main | `api/main.py` — widget router wired; CSP `frame-ancestors 'self'` baseline on all `/widget/` paths |
| Seed | `scripts/seed.py` — seeds `baladiya/widget/signing_key` in Vault |
| React widget | `widget/` — full React/Vite app: `App.tsx`, `ChatWidget.tsx`, `MessageList.tsx`, `LangToggle.tsx`, `useChat.ts` |
| Widget styles | `widget/src/index.css` — CSS custom properties, `Syne` + `DM Sans` fonts, geometric header pattern |
| Loader script | Embedded in router `_LOADER_JS`; served at `GET /widget.js`; handles 403 gracefully |
| Streamlit admin | `chatbot/pages/widget.py` — create/manage widgets, copy embed snippet |
| Demo site | `host/index.html` + `host/nginx.conf` — mock municipality site with `<script>` embed |
| Docker | `docker/widget.Dockerfile`, `docker/host.Dockerfile`, `docker/widget-nginx.conf` |
| docker-compose | `widget` + `host` services now have real Dockerfiles and ports (3000, 8080) |
| Tests | `tests/test_widget/test_widget_auth.py` (4 tests), `tests/test_widget/test_token_service.py` (5 tests) — all 9 pass |
| CI | `widget-auth` gate + `widget-bundle-size` gate added to `.github/workflows/ci.yml` |

**Key architectural facts:**
- Token flow: `GET /widget/token?widget_id=&origin=` (NOT POST) → validates origin → JWT signed with `jwt_secret`
- `tenant_id` comes from JWT claim only — never from body, URL param, or postMessage
- `widget_id` is in the JWT payload and parsed into `TokenClaims.widget_id`
- `GET /widget/config` uses `claims.widget_id` to look up `allowed_origins` and sets `Content-Security-Policy: frame-ancestors` dynamically (FR-009)
- Widget tokens signed with **`jwt_secret`** (not `widget_signing_key`) — `decode_token` uses `jwt_secret`; per-widget key rotation is deferred to Phase 8 (see `DECISIONS.md §D-Widget-001`)
- `PlatformWidgetRepository` is used for the public token exchange (no tenant context yet); `WidgetRepository` (BaseRepository) is used for tenant-admin CRUD
- Widget bundle: **48.5 KB gzipped** (SC-001 gate: < 100 KB)
- Widget UI aesthetic: dark navy header (`#172040`) with mashrabiya diamond-lattice SVG pattern; `Syne` display font + `DM Sans` body; tenant `theme_color` injected as `--accent` CSS custom property at runtime; bot bubbles have 2.5px left accent rail
- Preview mode: visit `http://localhost:5173/widget/?token=preview` with `npm run dev` in `widget/` — no backend needed

**SC-003 denial cases (all pass in CI):**

| Case | Status |
|---|---|
| Disallowed origin → 403 | ✅ |
| No Authorization header → 401 | ✅ |
| Expired JWT → 401 | ✅ |

**`/speckit-analyze` fixes applied (post-implementation):**
- F2: CSP `frame-ancestors` header — dynamic per `allowed_origins` in `/widget/config`; baseline `'self'` in middleware
- E1: Tenant suspended edge case — `POST /chat` now checks `tenant.status != "active"` → 403
- C1: Service layer — `widget_service.py` extracted; router no longer does direct DB ops
- Bug: Widget tokens were signed with `widget_signing_key` but decoded with `jwt_secret` — fixed to use `jwt_secret` throughout
- I3: `WidgetConfig` now includes `enabled_tools` and `persona` fields

---

### Phase 7 — Arabic Bilingual Expansion (`007-arabic`) ✅

**Bilingual classifier retrained. All Arabic cells ≥51 examples. `ar_macro_f1` threshold set.**

| Area | Files Modified |
|---|---|
| Dataset | `civic_intent_dataset.csv` — grown from 547 → **12,731 rows** |
| Build script | `build_dataset.md` — Arabic expansion (MSA/Lebanese/Arabizi × all intents) |
| English expansion | `dataset_english_large.md` — ~11,996 EN template rows (3K per intent) |
| Bilingual notebook | `notebooks/train_classifier_bilingual.ipynb` — retrained; outputs committed |
| Eval results | `evals/classifier_bilingual_results.json` — full per-variety F1 + SHA-256 |
| CI thresholds | `eval_thresholds.yaml` — `classifier_macro_f1: 0.97`, `en_macro_f1: 0.98`, `ar_macro_f1: 0.93` |
| Language detection | `api/services/lang_detect_service.py` (new) |
| Prompt routing | `api/services/prompt_service.py` (new) |
| Tests | `tests/test_arabic/` (new) |

**Bilingual classifier results (2026-06-06):**

| Variety | F1 | Test examples |
|---|---|---|
| en | 1.0000 | 2,412 |
| msa | 1.0000 | ~42 |
| lebanese | 1.0000 | ~43 |
| arabizi | 0.8322 | ~41 |
| **Overall macro-F1** | **0.9980** | **2,525** |

**Per-cell AR counts (all ≥51 — threshold met):**

| | report | question | human | spam |
|---|---|---|---|---|
| msa | 55 | 54 | 51 | 51 |
| lebanese | 55 | 55 | 51 | 51 |
| arabizi | 51 | 51 | 51 | 52 |

**Known limitations going into Phase 8:**
- Arabizi F1 = 0.8322 — still lowest variety (EN:AR ratio ~19:1 dilutes TF-IDF char n-gram space)
- EN F1 = 1.0 on template test set — may reflect template memorisation; evaluate on real resident text before defense
- Arabic rows are machine-seeded — hand-verify before citing per-variety F1 as reliable
- Name-pattern PII redaction (Arabic names) deferred — needs spacy NER or regex expansion in Phase 8

---

### Phase 8 — Hardening & Evals (`008-hardening-evals`) ✅

**Arabic PII redaction implemented. Per-widget JWT key rotation shipped. Defense docs updated. Real-text EN eval complete.**

| Area | Files Modified |
|---|---|
| Redaction | `api/middleware/redaction.py` — ARABIC_NAME recognizer with civic-term negative lookahead blocklist; fail-safe try/except per recognizer |
| Vault | `api/infra/vault.py` — `get_widget_signing_key()`, `invalidate_widget_key_cache()`, TTL-300s LRU cache (max 128 entries) |
| Security | `api/core/security.py` — two-pass JWT decode: peek `widget_id` unverified → fetch per-widget Vault key → verified decode |
| Widget token | `api/api/widget/token_service.py` — `issue_token()` signs with per-widget Vault key; falls back to `jwt_secret` on Vault miss |
| Admin API | `api/api/admin/router.py` — `POST /admin/widgets/{widget_id}/rotate-key` endpoint |
| Seed | `scripts/seed.py` — `_seed_per_widget_keys()` migrates existing widgets to per-widget Vault paths (idempotent) |
| Defense docs | `DECISIONS.md` §D-Arabic-001, `DATA.md` (12,731 rows, per-cell table, Arabizi caveat), `modelserver/model_card.md` (Phase 7 SHA-256, Phase 8 real-text eval) |
| Real-text eval | `evals/real_text_en_sample.json` (n=25: NYC 311 + manual), `evals/evaluate_real_text.py` |
| Tests | `tests/test_security/test_redaction.py` (5 Arabic name cases), `tests/test_widget/test_token_service.py` (3 rotation tests), `tests/test_platform/test_rate_limiter.py` (mock fix) |

**Phase 8 measured numbers:**

| Metric | Value | Notes |
|---|---|---|
| Real-text EN macro-F1 | **0.8420** | n=25: NYC 311 (acc=0.90) + manual (acc=0.80) |
| Template macro-F1 | 1.0000 | Confirms template memorisation — use 0.8420 for defense |
| Arabizi F1 | 0.8322 | Unchanged — data expansion deferred to Phase 9 |
| Per-widget JWT rotation | ✅ | Two-pass decode; Vault KV v2; 300s TTL LRU cache |
| Arabic PII redaction | ✅ | Two-word name pattern; 30+ civic-term blocklist; fail-safe |

**Deferred from Phase 8 (carry to Phase 9):**
- Arabizi data expansion (target F1 ≥ 0.90): add ≥49 rows/cell, rebuild CSV, retrain notebook, update CI gate
- Live eval runs (RAG + agent evals): require docker compose stack + seeded content; run `evaluate_rag.py --mode compare` and `evaluate_agent.py`

---

## 3. Completed Documentation

| File | Status | Notes |
|---|---|---|
| `BALADIYA_CONCIERGE.md` | Complete | Original product spec |
| `CLAUDE.md` | Complete | Tech stack, hard constraints |
| `DESIGN.md` | Complete | Architecture, component map, 7 key decisions |
| `DECISIONS.md` | Updated | §D-Widget-001 (shared JWT key rationale), §D-Arabic-001 (bilingual model defense) |
| `EVALS.md` | Updated | §8 Widget Evaluation (SC-001 measured, SC-002 3G template, SC-003 results, SC-004 RTL checklist) |
| `RUNBOOK.md` | Complete | Tenant lifecycle, incident runbook |
| `SECURITY.md` | Complete | Threat model, isolation enforcement |
| `DATA.md` | Updated | 12,731 rows, variety × intent table, Arabizi F1 caveat, EN memorisation warning |
| `modelserver/model_card.md` | Updated | Phase 7 SHA-256, real-text EN eval (n=25, macro-F1=0.8420), known limitations |
| `.specify/memory/constitution.md` | Complete | 7 non-negotiable governance rules |
| `specs/006-widget/spec.md` | Complete | Status updated to Implemented; FR-005 clarified |
| `specs/006-widget/plan.md` | Complete | HTTP method, loader location, dependency corrected |

---

## 4. Open Decisions / TBDs

### Resolved in Phase 6 ✅
- Widget JWT signing key strategy — use `jwt_secret`; per-widget rotation deferred to Phase 8 (`DECISIONS.md §D-Widget-001`)
- CSP frame-ancestors — dynamic per `allowed_origins` in `/widget/config`
- Tenant suspended edge case — enforced in `POST /chat`
- Widget service layer — `widget_service.py` created; router is thin

### Still Open

**Phase 3 (RAG) — needs live DB stack**
- `eval_thresholds.yaml → rag_hit_at_5`, `rag_mrr`, `rag_faithfulness` — pre-measurement placeholders
- Run `python evals/seed_eval_content.py` then `python evals/evaluate_rag.py --mode compare`; update thresholds to `measured − 2pp`

**Phase 4 (Agent) — needs live LLM API**
- `evals/evaluate_agent.py` not yet run — `agent_tool_accuracy` is a target, not a measured value
- `EVALS.md §4` (agent tool selection) — TBD rows not filled

**Phase 6 (Widget) — manual gate outstanding**
- SC-002: first message round-trip < 3s on 3G — measure with Chrome DevTools before defense demo (template in `EVALS.md §8`)
- SC-004: RTL manual checklist — 10-item checklist in `EVALS.md §8` — run before demo

**Phase 7 (Arabic) — complete ✅**
- All AR cells ≥51 examples; `ar_macro_f1` threshold set to 0.93 (measured **0.9507**) ✅
- Dataset: 12,731 rows total (10,206 train / 2,525 test); artifact SHA-256 updated ✅
- Arabizi F1 = **0.8322** — not gated, tracked; grow cells or split model in Phase 8
- Arabic rows are machine-seeded — hand-verify before defense, log corrections in model card
- Name-pattern PII redaction (deferred from Phase 5) — add to Phase 8 scope

---

## 5. CI Gate Status

| Gate | Threshold | Measured | Status |
|---|---|---|---|
| `classifier_macro_f1` | **0.97** | **0.9980** | ✅ Updated Phase 7 — bilingual retrain |
| `en_macro_f1` | **0.98** | **1.0000** | ✅ Updated Phase 7 (template test set, n=2412) |
| `ar_macro_f1` | **0.93** | **0.9507** | ✅ Set Phase 7 — hand-crafted AR test, n=113 |
| `arabizi_f1` | *(not gated)* | 0.8322 | ⚠️ Reported — grow Arabizi cells in Phase 8 |
| `agent_tool_accuracy` | 0.80 | — | ⚠️ Target set — run `evals/evaluate_agent.py` |
| `workflow_handled_rate` | 0.60 | — | ⚠️ Target set — measured via cost attribution logs |
| `rag_hit_at_5` | 0.73 | — | ⚠️ Pre-measurement target |
| `rag_mrr` | 0.60 | — | ⚠️ Pre-measurement target |
| `rag_faithfulness` | 0.60 | — | ⚠️ Pre-measurement target |
| `redteam_pass_rate` | 1.0 | 1.0 | ✅ Enforced — 12/12 probes refused in CI |
| `widget_bundle_kb` | < 100 KB | 48.5 KB | ✅ Real value — gate active |
| `widget_auth_denial` | 3/3 pass | 3/3 | ✅ All denial cases pass in CI |

**CI jobs (`.github/workflows/ci.yml`):**
- `test` — unit tests (no live services)
- `classifier-latency` — p95 < 50ms on real artifact
- `modelserver-image-size` — < 500 MB
- `redteam` — isolation probes (test_isolation/)
- `guardrails-redteam` — 100% red-team probes refused
- `pii-redaction` — zero PII leaks in redaction pipeline
- `service-auth` — 401 without service token
- `widget-auth` — **NEW Phase 6** — all 3 denial cases pass
- `widget-bundle-size` — **NEW Phase 6** — JS bundle < 100 KB gzipped

---

## 6. Dataset State

| Source | Rows | Intent | Notes |
|---|---|---|---|
| `build_dataset.md` | **628 AR + ~107 EN seed** | all 4, all varieties | Hand-crafted (EN seed + all MSA/Lebanese/Arabizi). **Rewrites CSV from scratch.** Edit here to add/fix rows. |
| `dataset_english_large.md` | **~11,996** | EN only, all 4 intents | Template-generated (3K per intent). **Re-run after `build_dataset.md`.** |
| `dataset_english.md` | ~79 | EN report + spam | Optional: NYC 311 Kaggle + enron_spam top-up. |
| **Total (CSV, confirmed)** | **12,731** | | 10,206 train / 2,525 test (~19.8% test) |

**Variety breakdown (confirmed from CSV):**

| Variety | Total | report | question | human | spam |
|---|---|---|---|---|---|
| en | 12,103 | 3,069 | 3,017 | 3,007 | 3,010 |
| msa | 211 | 55 | 54 | 51 | 51 |
| lebanese | 212 | 55 | 55 | 51 | 51 |
| arabizi | 205 | 51 | 51 | 51 | 52 |
| **total** | **12,731** | 3,230 | 3,177 | 3,160 | 3,164 |

**Category distribution (confirmed from CSV):**
`none` 6,324 · `roads` 1,502 · `environment` 898 · `electricity` 770 · `water` 766 · `waste` 730 · `permits` 710 · `general` 640 · `taxes` 391

**Full rebuild workflow** (run in this order every time you retrain):
```bash
python3 build_dataset.md          # 1. Rewrites CSV with 735 hand-crafted rows
python3 dataset_english_large.md  # 2. Appends ~12K EN template rows (3K per intent)
python3 dataset_english.md        # 3. Optional: top up from Kaggle 311 + enron_spam
# Then retrain: run notebooks/train_classifier_bilingual.ipynb
```

**Where to add/edit English data:**

| What you want to do | File to edit |
|---|---|
| Add hand-written English report/question/human/spam rows | `build_dataset.md` — find the relevant `# ENGLISH` section and add `add(...)` calls |
| Expand report templates (new civic scenarios) | `dataset_english_large.md` — `gen_report_*()` functions |
| Add question templates (new categories/topics) | `dataset_english_large.md` — `Q_*` lists inside `gen_questions()` |
| Add human escalation variants | `dataset_english_large.md` — `OPENERS`, `REASONS`, `CLOSERS` lists in `gen_human()` |
| Add spam template variants | `dataset_english_large.md` — `spam_sentence()` function, add new `elif category == N:` branches |

**Arabic dataset — where to add rows:**
All Arabic rows (MSA / Lebanese / Arabizi) live in `build_dataset.md` in clearly labelled sections:
- `# ARABIC — MODERN STANDARD ARABIC (MSA / فصحى)` — lines ~158–212
- `# ARABIC — LEBANESE DIALECT (عامية لبنانية)` — lines ~215–272
- `# ARABIC EXPANSION — target 55+ per (intent × variety) cell` — lines ~339–820

**Current per-cell AR counts (confirmed from `build_dataset.md` and CSV — all ≥51):**

| | report | question | human | spam |
|---|---|---|---|---|
| msa | 55 | 54 | 51 | 51 |
| lebanese | 55 | 55 | 51 | 51 |
| arabizi | 51 | 51 | 51 | 52 |

**Known issues (carry into Phase 8):**
- Arabizi F1 = 0.8322 — AR:EN ratio is ~1:19; TF-IDF char n-gram space dominated by English templates. Fix: grow Arabizi cells or split into per-language models.
- EN F1 = 1.0 on template test set — reflects template memorisation, not generalisation. Evaluate on real resident text before defense.
- Arabic cells are machine-seeded — hand-verify before citing per-variety F1 as reliable.

---

## 7. Environment Notes

| Tool | Location | Notes |
|---|---|---|
| Python venv | `/home/usermohammad/.venv` | Python 3.11; all project deps installed |
| Jupyter | `/home/usermohammad/.venv/bin/jupyter` | Kernel spec updated to use venv Python |
| Kaggle credentials | `/home/usermohammad/.kaggle/kaggle.json` | User: `mohammadabouamoun` |
| API keys | `BALADIYA CONCIERGE/.env` | `GEMINI_API_KEY`, `GROQ_API_KEY` — never commit |
| Git remote | `https://github.com/mohammadabouamoun/Baladiya_Concierge.git` | Pushed to `main` |
| NYC 311 dataset | `/tmp/311_data/nyc_311_2025.csv` | 68 MB; `/tmp` — not persisted across reboots |
| Widget dev server | `cd widget && npm run dev` | Visit `http://localhost:5173/widget/?token=preview` |
| Host demo site | `docker compose up host` | Serves mock municipality site on port 8080 |

**onnxruntime WSL locale issue**: ONNX inference fails with `en_US.UTF-8 locale not found`. Fix: `sudo apt-get install locales language-pack-en && sudo locale-gen en_US.UTF-8`. Does not affect `classifier.joblib`.

**uv pip**: Use `uv pip install <pkg>` for faster installs. For venv-specific: `uv pip install <pkg> --python /home/usermohammad/.venv/bin/python3`.

**presidio_analyzer is NOT installed in the dev venv** — guardrails-sidecar-only dependency. `pii_detect.py` import in `guardrails/main.py` is lazy (try/except).

---

## 8. Next Phase Prep — Phase 9

Update `feature.json` to `specs/009-...` and run `/speckit-specify` to define Phase 9.

**Recommended Phase 9 scope (deferred items from Phases 7–8):**
- **Arabizi quality** (deferred from Phase 8): grow Arabizi cells from 51–52 → 100 per intent; retrain; target Arabizi F1 ≥ 0.90; update `eval_thresholds.yaml` gate from not-gated to `arabizi_f1: 0.88`
- **Hand-verify Arabic rows**: sign off on machine-seeded MSA/Lebanese/Arabizi examples; log corrections in `modelserver/model_card.md §Data Corrections`
- **Live eval runs** (deferred from Phase 8, requires docker stack): run `evals/evaluate_rag.py --mode compare` and `evals/evaluate_agent.py` against live stack; update `eval_thresholds.yaml` with measured hit@k, MRR, faithfulness, answer-relevancy, tool-selection accuracy
- **SC-002 widget 3G latency**: measure first-message round-trip on 3G with Chrome DevTools (template in `EVALS.md §8`)
- **SC-004 RTL checklist**: run 10-item RTL checklist from `EVALS.md §8` before defense demo
- **Real EN data expansion**: collect 200+ real 311-style English messages per intent cell; retrain; close the template-memorisation gap (real-text macro-F1 = 0.8420 vs template 1.0000)

**Phase 8 items confirmed complete — no rework needed:**
- ✅ Arabic name PII redaction (`api/middleware/redaction.py`)
- ✅ Per-widget JWT key rotation (Vault KV v2 + two-pass decode)
- ✅ Defense docs: `DECISIONS.md §D-Arabic-001`, `DATA.md`, `modelserver/model_card.md`
- ✅ Real-text EN eval: n=25, macro-F1 = 0.8420, model card updated

---

## 9. Non-Obvious Facts

**`gemini-embedding-001` is 3072 dims natively, not 1536.** The embedding client passes `outputDimensionality: 1536` to truncate. The pgvector column is `vector(1536)`. Verified with a live API call on 2026-06-02. Do NOT change the column type or `outputDimensionality` — the entire corpus must stay in one vector space.

**`build_dataset.md` is a Python script.** `.md` extension is intentional. Run with `python3 build_dataset.md`.

**`Data.md` ≠ `DATA.md`.** `Data.md` is the user's original spec with model/API key decisions. `DATA.md` is the generated dataset documentation. Both exist at root.

**`feature.json` controls which phase is active.** The prerequisites script reads it. Already updated to `specs/008-hardening-evals`.

**Gemini free tier: 20 calls/day for `gemini-2.5-flash`.** Not enough to run the LLM eval on 98 test examples. The LLM zero-shot baseline uses **Groq llama-3.3-70b** (generous free tier).

**`classifier_confidence_thresholds` is in `Settings`.** Per-intent dict `{report: 0.75, question: 0.75, human: 0.65, spam: 0.90}`. Below threshold → agent path. Spam threshold intentionally high (0.90) to minimise false drops.

**Two-way comparison, not three-way.** DL/ONNX was dropped. Classical ML vs LLM zero-shot only.

**Session key structure: `session:{session_id}:{tenant_id}`** — SCAN pattern for erasure: `session:*:{tenant_id}`. Do NOT use `tenant:{tenant_id}:` prefix.

**`capture_request` never receives spam.** Spam is dropped by the classifier BEFORE any tool call.

**LLM fallback is request-count-based, not time-based.** `_GeminiFailureTracker.count ≥ 3` → Groq; resets to 0 on first successful Gemini call. To reset in tests: `from api.infra.llm_client import _gemini_tracker; _gemini_tracker.reset()`.

**`max_tool_calls` setting name (not `max_tool_iterations`).** Default is 3.

**Gemini SDK is synchronous.** `google-generativeai==0.7.2` has no native async. `llm_client.py` wraps in `asyncio.to_thread()`.

**Guardrails sidecar port is 8002, not 8001.** Port 8001 is modelserver.

**`PlatformTenantRepository` (not `TenantRepository`).** Use it for cross-tenant reads. `TenantAdminRepository` is for `TenantAdmin` entities. **`PlatformWidgetRepository`** (not `WidgetRepository`) is for the public token exchange lookup before tenant context is known.

**Per-widget JWT key rotation is live (Phase 8).** Each widget gets its own key at `baladiya/widget/{widget_id}/signing_key` in Vault KV v2. `decode_token` does a two-pass decode: peek `widget_id` without signature verification → fetch per-widget Vault key (TTL 300s LRU cache) → verified decode. Non-widget tokens (no `widget_id` claim) fall back to `jwt_secret`. Rotate via `POST /admin/widgets/{widget_id}/rotate-key` (Tenant Admin auth required).

**`TokenClaims.widget_id`** is now populated for widget-issued visitor tokens. Use it in routes that need to look up widget metadata (e.g., `allowed_origins` for dynamic CSP).

**`POST /chat` now checks `tenant.status`.** A resident with a valid JWT whose tenant was suspended mid-session gets 403 on the next message. The tenant fetch is reused for both the status check and guardrail config — no extra DB round-trip.

**`specs/004-agent-router/` is empty.** The actual Phase 4 specs live in `specs/004-router-agent/`. Safe to ignore the empty dir.

**Phase 8 docs already written.** `DESIGN.md`, `DECISIONS.md`, `RUNBOOK.md`, `SECURITY.md` are pre-written. Mark their Phase 8 tasks `[X]` without redoing the work.

---

## 10. Cross-Feature Dependency Map

```
P1 (Foundation) → ALL others
P2 (Classifier) → P4 (Router calls modelserver)
P3 (CMS/RAG)   → P4 (Router calls rag_search)
P4 (Router)    → P5 (Guardrails wraps POST /chat + redacts before session write)
P5 (Guardrails)→ P6 (Widget calls guarded API; tenant status checked)
P6 (Widget)    → P7 (RTL + Arabic end-to-end; widget enabled_tools/persona wired)
P7 (Arabic)    → P8 (Final evals include AR numbers)
```

---

*Last updated: 2026-06-06 | Phases 1–8 complete | Next: 009 (Arabizi expansion + live evals + RTL/latency checks)*
