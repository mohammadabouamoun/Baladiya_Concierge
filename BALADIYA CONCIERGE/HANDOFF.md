# HANDOFF.md — Baladiya Concierge

> Snapshot of project state as of **2026-06-06**. Written for the next agent session or future self picking up this repo cold. Read this before touching any spec file or running any skill.

---

## 1. Current Phase

| Field | Value |
|---|---|
| **Active feature** | `007-arabic` (next) |
| **Status** | **Phases 1–6 complete — ready to start Phase 7** |
| **Last completed task** | All 22 tasks in `006-widget` are `[X]` + `/speckit-analyze` remediation applied |
| **Last commit** | Phase 6 — embeddable React widget, JWT token exchange, widget redesign |
| **Next task to start** | Run `/speckit-implement` from `specs/007-arabic/` |
| **How to start** | `feature.json` already points to `specs/007-arabic` — run `/speckit-implement` |

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
| Dataset | `civic_intent_dataset.csv` — 547 rows; `dataset_english.md` for automated expansion |

**Trained model results (2026-06-02, 547-row dataset):**

| Approach | Macro-F1 | EN F1 | AR F1 | p50 |
|---|---|---|---|---|
| **Classical ML (shipped)** | **0.8983** | **0.8784** | **0.8117** | **2.2ms** |
| LLM zero-shot (Groq llama-3.3-70b) | 0.8291 | 0.7358 | 0.8512 | 2220ms |

**Artifact SHA-256**: `1ace7e21afd41ea78872a6ed262e75f3bac4b1fe10ef7e520c27117cbe26f9a9`
**Data SHA-256**: `afbb5e166f49102ac3618c35b690294efb6ef014982ee489c7d9a7af7ff2bfc1`

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

## 3. Completed Documentation

| File | Status | Notes |
|---|---|---|
| `BALADIYA_CONCIERGE.md` | Complete | Original product spec |
| `CLAUDE.md` | Complete | Tech stack, hard constraints |
| `DESIGN.md` | Complete | Architecture, component map, 7 key decisions |
| `DECISIONS.md` | Updated | §D-Widget-001 added (shared JWT signing key rationale + Phase 8 rotation path) |
| `EVALS.md` | Updated | §8 Widget Evaluation added (SC-001 measured, SC-002 3G template, SC-003 results, SC-004 RTL checklist) |
| `RUNBOOK.md` | Complete | Tenant lifecycle, incident runbook |
| `SECURITY.md` | Complete | Threat model, isolation enforcement |
| `DATA.md` | Complete | Dataset schema, labelling guidelines |
| `modelserver/model_card.md` | Complete | Two-way comparison, real F1 numbers, SHA-256 |
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

**Phase 7 (Arabic)**
- `eval_thresholds.yaml → ar_macro_f1` — `0.0`; set after Arabic dataset grows to ≥20 verified rows per cell
- Arabizi (F1=0.50) and Lebanese (F1=0.71) cells are thin — only 5 test rows each
- Name-pattern PII redaction (deferred from Phase 5) — needs spacy NER or regex expansion

---

## 5. CI Gate Status

| Gate | Threshold | Measured | Status |
|---|---|---|---|
| `classifier_macro_f1` | 0.88 | 0.8983 | ✅ Real value — gate active |
| `en_macro_f1` | 0.86 | 0.8784 | ✅ Real value — gate active |
| `ar_macro_f1` | 0.0 | 0.8117 | ⚠️ Placeholder — set in Phase 7 |
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
| `build_dataset.md` (hand-crafted) | 258 | all 4 | Run `python3 build_dataset.md` to regenerate |
| NYC 311 Kaggle (`nyc_311_2025.csv`) | ~229 | report only | Cached at `/tmp/311_data/nyc_311_2025.csv` |
| HuggingFace `enron_spam` | ~60 | spam only | Streamed — no download needed |
| **Total** | **547** | | |

**Workflow**: `python3 build_dataset.md` → `python3 dataset_english.md` → retrain notebook.

`build_dataset.md` **rewrites** the CSV from scratch. Always re-run `dataset_english.md` after it to re-append the 311/spam rows.

**Known thin cells** (need more data before quoting F1):
- `arabizi` × any intent: 5 test rows — F1 not reliable
- `lebanese` × any intent: 5 test rows — F1 not reliable
- `spam` × Arabic: scarce

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

## 8. Next Phase Prep — Phase 7 (Arabic)

`feature.json` already points to `specs/007-arabic` — run `/speckit-implement`.

**What Phase 7 builds:**
- Grow Arabic dataset cells: `arabizi × all intents` and `lebanese × all intents` from 5 → ≥20 verified rows each
- Retrain classifier and measure per-variety F1; set `ar_macro_f1` threshold in `eval_thresholds.yaml`
- Name-pattern PII redaction (deferred from Phase 5) — add spacy NER or regex patterns to `api/middleware/redaction.py`
- Arabic end-to-end test: widget RTL → Arabic message → classifier `ar` → RAG cross-language → response
- Phase 7 is the Arabic integration test phase, not a new backend phase

**Widget readiness for Phase 7:**
- RTL toggle (`LangToggle.tsx`) is already implemented and sets `document.documentElement.dir`
- `WidgetConfig.greeting_ar` is fetched and displayed
- `useChat.ts` sends messages to the same `/chat` endpoint; language detection happens server-side
- `WidgetConfig.enabled_tools` and `persona` are now returned by `/widget/config` — Phase 7 can filter tools per widget

**Critical dependencies:**
1. Classifier retrained with more Arabic data → `ar_macro_f1` threshold set
2. RAG cross-language retrieval already works (Phase 3) — no new work needed
3. PII redaction for Arabic names — needed before Phase 8 evals

---

## 9. Non-Obvious Facts

**`gemini-embedding-001` is 3072 dims natively, not 1536.** The embedding client passes `outputDimensionality: 1536` to truncate. The pgvector column is `vector(1536)`. Verified with a live API call on 2026-06-02. Do NOT change the column type or `outputDimensionality` — the entire corpus must stay in one vector space.

**`build_dataset.md` is a Python script.** `.md` extension is intentional. Run with `python3 build_dataset.md`.

**`Data.md` ≠ `DATA.md`.** `Data.md` is the user's original spec with model/API key decisions. `DATA.md` is the generated dataset documentation. Both exist at root.

**`feature.json` controls which phase is active.** The prerequisites script reads it. Already updated to `specs/007-arabic`.

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

**Widget tokens are signed with `jwt_secret`, not `widget_signing_key`.** `decode_token` uses `jwt_secret`; using a separate key would break validation. Per-widget key rotation is documented in `DECISIONS.md §D-Widget-001` and deferred to Phase 8.

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

*Last updated: 2026-06-06 | Phases 1–6 complete | Next: 007-arabic*
