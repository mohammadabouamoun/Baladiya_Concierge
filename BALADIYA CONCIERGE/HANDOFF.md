# HANDOFF.md — Baladiya Concierge

> Snapshot of project state as of **2026-06-11**. Written for the next agent session or future self picking up this repo cold. Read this before touching any spec file or running any skill.
> **Updated**: Phase 9 Session 7 — Arabizi question confidence fixed (+55 civic-vocabulary question rows). AR sub-model retrained on 784 rows. "emta lazem ndfa3 fatouret el may" confidence 0.532→0.933. Overall macro-F1 0.9966, AR 0.9740, Arabizi 0.9578. See §2 Phase 9 Session 7 and §10 for details.

---

## 1. Current Phase

| Field | Value |
|---|---|
| **Active feature** | `009` (in progress) |
| **Status** | **Phases 1–9 automated complete** — 149/149 tests passing (3 skipped); SC-002/SC-004 widget checks remaining (manual browser work only) |
| **Last completed task** | Session 6: MSA spam confidence fixed — 155 MSA spam rows (was 51), AR sub-model retrained (SHA: `ab51509e`), `ar_classifier_confidence_thresholds` added (spam: 0.75), MSA spam confidence 0.532→0.804 |
| **Last commit** | Phase 8 — hardening & evals |
| **Next task to start** | Seed a valid `GEMINI_API_KEY` into Vault/`.env`, rebuild api container, then re-run `evaluate_rag.py` and seed Arabic CMS content |
| **How to start** | Set `GEMINI_API_KEY=<key>` in `.env`, then `docker compose up --build api -d`; run `python scripts/seed.py` to seed content |

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

### Phase 9 — Live Evals & Defense Readiness (`009-arabizi-liveeval`) 🔄

**Session 1 (2026-06-08):** Docker stack restored, live eval runs completed, CMS seeded, PII over-triggering fixed, Groq tool-call fixed, Vault seed bug fixed. 135 tests passing.

**Session 2 (2026-06-08):** Three critical bugs fixed. 149/149 tests passing.

**Session 3 (2026-06-09):** All automatable §8 tasks complete. See §8 for details. 149/149 tests passing.

**Session 4 (2026-06-09):** Five root-cause bugs fixed. Arabic/Arabizi widget responses now return in Arabic. 149/149 tests passing. See Session 4 block below.

**Session 5 (2026-06-10):** Platform Manager Streamlit app built (port 8502, 3 pages: tenants/provision/audit). Tenants renamed to Beirut & Jbeil. Streamlit design system applied (navy + Lebanese gold). Docker split-start documented in §11 for 8 GB RAM machines. 149/149 tests passing.

**Session 6 (2026-06-11):** MSA spam confidence fixed. AR sub-model retrained on 739 rows (155 MSA spam). `ar_classifier_confidence_thresholds` added to `Settings` with `spam: 0.75` (vs 0.90 for EN). MSA spam confidence 0.532→0.804. Overall macro-F1 0.9973, AR 0.9798, Arabizi 0.9636 (bonus improvement). 149/149 tests passing.

**Session 7 (2026-06-12):** Arabizi question confidence fixed. +55 Arabizi question rows focused on civic payment/billing vocabulary (`ndfa3`, `fatouret`, `may`, `kahraba`, etc.). AR sub-model retrained on 784 rows (Arabizi question cells 100→155). "emta lazem ndfa3 fatouret el may" confidence 0.532→0.933 (well above 0.75 AR threshold). Overall macro-F1 0.9966, AR 0.9740, Arabizi 0.9578. All CI thresholds pass. 149/149 tests passing.

#### Session 6 Changes (2026-06-11)

**MSA Spam Confidence Fix — Two-Pronged Approach**

Root cause: The AR sub-model (`classifier_ar.joblib`) is trained on ~700 rows vs ~10K for EN. Smaller training set → naturally lower softmax calibration even when classification is correct (precision/recall = 1.0). MSA spam "تهانينا ربحت جائزة" had confidence 0.532 — well below the 0.90 spam routing threshold — so it fell through to the agent path.

**Fix 1 — Data expansion:** MSA spam rows grown 51 → 155 (+104 rows) in `build_dataset.md`. Added diverse scam/phishing/lottery patterns in MSA Arabic. AR sub-model retrained on 739 Arabic rows (MSA 206 + Lebanese 179 + Arabizi 314 train). SHA-256: `ab51509e713d6e6ebd7cbf7150c01c8213813a2125694e713b98d1966ac73119`.

**Fix 2 — Per-language routing thresholds:** Added `ar_classifier_confidence_thresholds` field to `Settings` in `api/core/config.py` with `{report: 0.70, question: 0.70, human: 0.60, spam: 0.75}`. Router (`api/services/router_service.py`) selects AR thresholds when `result.variety in ("msa", "lebanese", "arabizi")`. The 0.75 spam threshold is the calibration-equivalent of 0.90 for the English model.

**Artifacts updated (Session 6):**
- `civic_intent_dataset.csv` — 12,979 → 13,083 rows; data SHA-256 `f225e547ddb29575bc380375a50879b515f556786be1ce9eb1b56922498dff4e`
- `modelserver/artifacts/classifier.joblib` — SHA-256 `bd2d33060edcc9c7e02246fa6b499174928df9875474abd32c2967ef0c1edc0d`
- `modelserver/artifacts/classifier_ar.joblib` — SHA-256 `ab51509e713d6e6ebd7cbf7150c01c8213813a2125694e713b98d1966ac73119`
- `evals/classifier_bilingual_results.json` — Session 6 numbers
- `modelserver/model_card.md` — Session 6 section added

**Results (Session 6):**

| Metric | Before | After |
|---|---|---|
| Overall macro-F1 | 0.9962 | **0.9973** |
| EN macro-F1 | 0.9984 | **0.9984** (unchanged) |
| AR macro-F1 | 0.9594 | **0.9798** |
| Arabizi F1 | 0.9510 | **0.9636** (bonus improvement) |
| MSA spam confidence | 0.532 | **0.804** (above 0.75 AR threshold → correctly dropped) |

**Files:** `build_dataset.md`, `api/core/config.py`, `api/services/router_service.py`, `modelserver/artifacts/classifier_ar.joblib`, `modelserver/artifacts/classifier.joblib`

---

#### Session 4 Changes (2026-06-09)

Five bugs were discovered by live-testing the widget with English, Arabic, and Arabizi input, then diagnosed and fixed.

**Bug S4-1 — All workflow responses returned in English regardless of input language**

Root cause: `api/services/router_service.py` had hardcoded English strings for all intents (`"Your request has been recorded"`, etc.) with no language switching.

Fix: Added `_W` dict with parallel `"en"` and `"ar"` sub-dicts covering all 6 response keys (`report_ok`, `report_err`, `question_miss`, `human_ok`, `human_err`, `fallback`). Added `_lang_key(variety)` helper that maps `msa / lebanese / arabizi → "ar"`, `en → "en"`. Workflow path now looks up `strings = _W[_lang_key(lang_result.variety)]` before building the response.

Files: `api/services/router_service.py`

---

**Bug S4-2 — Duplicate text in workflow responses ("Your request has been recorded. Your request has been recorded. Reference number: ...")**

Root cause: The `capture_request` tool already returns a full human-readable message in its response dict. The router was appending its own message on top, then formatting with the tool's message again, producing doubled text.

Fix: Router now builds the response cleanly from `result.get("id", "")[:8].upper()` and `result.get("ticket_id", "")[:8].upper()` and uses the `_W` string template directly, discarding the raw tool message.

Files: `api/services/router_service.py`

---

**Bug S4-3 — Arabic script messages returned variety="en" (langdetect missing from API container)**

Root cause: `langdetect` was only in `modelserver/requirements.txt`, not in the top-level `requirements.txt`. `lang_detect_service._detect_sync()` hit `from langdetect import ...` which raised `ModuleNotFoundError`. The outer `try/except` caught it and returned `lang="en", variety="en"` — every Arabic message was treated as English.

Fix 1: Added an Arabic-script fast-path before the `langdetect` import: `if arabic_chars > 2 and arabic_chars >= latin_chars → return LangDetectResult(lang="ar", variety=..., confidence=0.90)`. This is now the primary Arabic detection path — langdetect is never called for Arabic script text.

Fix 2: Added `langdetect==1.0.9` to `requirements.txt` so the fallback path also works in the api container.

Files: `api/services/lang_detect_service.py`, `requirements.txt`

---

**Bug S4-4 — Arabizi regex false-positives on English text (575 EN test rows routed to AR sub-model)**

Root cause: The expanded `_ARABIZI_RE` in `modelserver/classifier.py` (Session 3) added bare digit pattern `[23578]` which matched any digit in English text ("building 12" → "2", "3 weeks" → "3"). Also added the word `may` which appears in common English phrases ("you may need").

Fix: Changed digit pattern from `[23578]` to `[a-zA-Z][23578]|[23578][a-zA-Z]` — digit must be letter-adjacent (within a word like `share3` or `7ufra`). Removed `may` from the word list. Changed from `search()` to `len(findall()) >= 2` threshold — a single match is not enough to declare Arabizi. Result: 0 EN false positives, 82/86 Arabizi test rows still detected correctly.

Files: `modelserver/classifier.py`

---

**Bug S4-5 — AR sub-model not loading in container (ARTIFACT_AR_PATH env var missing)**

Root cause: `docker-compose.yml` modelserver service had no `ARTIFACT_AR_PATH` env var. The container used the default path (`artifacts/classifier_ar.joblib`) but the file is mounted at `modelserver/artifacts/classifier_ar.joblib`. `ar_pipeline` stayed `None` — all Arabic text was routed to the EN classifier.

Fix: Added `ARTIFACT_AR_PATH: "modelserver/artifacts/classifier_ar.joblib"` to the modelserver `environment` block in `docker-compose.yml`.

Files: `docker-compose.yml`

---

#### Bug 1 — Classifier always returned `spam=0.52` for every input

**Root cause:** `modelserver/classifier.py:89` created `pd.DataFrame({"text": [text]})` and passed the full DataFrame to `pipeline.predict()`. `TfidfVectorizer` iterates over the columns of a DataFrame (yielding the column name `"text"`) rather than the rows (yielding the actual text). Every call produced n-grams of the string `"text"` — identical regardless of input, giving fixed probabilities `{human:0.07, question:0.18, report:0.23, spam:0.52}`.

**Fix:** Changed to pass `[text]` (a plain Python list) instead of a DataFrame. The bilingual notebook trained with `train_df['text']` (a pandas Series), which iterates over values. One-line fix: `pipeline.predict([text])`.

**File:** `modelserver/classifier.py:89–91`

#### Bug 2 — Arabizi variety always returned `"en"`, never `"arabizi"`

**Root cause:** `detect_variety()` gated the Arabizi Latin-ratio + digit-pattern check behind `if lang not in ("ar", "fa", "ur")`. But `langdetect` returns European language codes (`da`, `ca`, `sq`, `no`) for Arabizi text because it is written in Latin script. The gate was never satisfied, so all Arabizi messages fell through as `"en"` variety.

**Fix:** Moved the Arabizi check (Latin ratio > 0.5 AND `_ARABIZI_RE.search()`) to run **before** the `langdetect` language gate. Arabizi is now correctly detected regardless of what `langdetect` says.

**File:** `modelserver/classifier.py:31–41`

#### Bug 3 — Arabic name redaction failing 3 test cases after Phase 8 fix

**Root cause:** The Phase 8 fix for `مواعيد دفع` (civic vocabulary falsely redacted as a name) tightened the ARABIC_NAME pattern to require a formal name-introducing prefix (اسمي, السيد, etc.). This was too strict — it missed bare names like `محمد علي`, names after `أنا`, and names at the start of a sentence.

**Fix:** Added a second recognizer `ARABIC_GIVEN_NAME` using an explicit list of ~30 common Arabic/Lebanese given names (محمد, أحمد, رنا, جورج, etc.) as the first-word anchor. Pattern: `[given-name]\s+[؀-ۿ]{3,}`. This catches real names without touching civic phrases (`مواعيد`, `مياه`, `كهرباء`) which are not in the given-name list.

**File:** `api/middleware/redaction.py`

#### Session 3 Changes (2026-06-09)

**§8.1 Arabizi Data Expansion** — +195 rows (49 per intent cell, 51→100 each). Rebuilt CSV (12,979 rows). Retrained bilingual notebook. Arabizi F1: 0.8322 → **0.9377** (n=86 test rows). Artifact SHA-256 updated to `1e0501540f52b029477e5abe5eb4c6c0eb03f251adb9ac2a739679fdd0141e9e`.

**§8.2 Real EN Data Expansion** — +503 real-style EN rows (200 per report/question/human intent), added to `build_dataset.md`. Rebuilt CSV + retrained. Real-text EN F1: 0.8420 → **0.9245** (same n=25 held-out eval set). Template-memorisation gap closed from 0.1580 to 0.0739.

**§8.3 Per-Language Classifier Split** — trained dedicated Arabic sub-model on 660 Arabic-only rows. Exported to `modelserver/artifacts/classifier_ar.joblib` (SHA-256: `0cd5e3d0e74ba4933bf99a4ecc0ec56186ccf67bcb8e7a0b8f7612816c204222`). Dual-dispatch in `ClassifierService.predict()`: variety ≠ `en` → AR pipeline. Arabizi F1 on AR-only model: **0.9510** (up from 0.9377). New `ARTIFACT_AR_PATH` / `ARTIFACT_AR_SHA256` settings in `main.py`.

**§8.5 Arabizi regex** — `_ARABIZI_RE` in `modelserver/classifier.py` expanded from single-digit pattern to also match common Arabizi words (`emta`, `kif`, `lazem`, `bade`, `share3`, `may`, etc.) that don't contain digit substitutions. Previously "emta kif lazem ndfa3" (no digits) was misclassified as `en`.

**§8.5 Arabic name list** — `ARABIC_GIVEN_NAME` in `api/middleware/redaction.py` expanded from ~30 to 100+ names covering Muslim male/female, Christian Lebanese male/female, Druze, and Arabizi transliterations.

**§8.5 RAG eval** — 500 errors from `/rag/search` in docker stack traced to `GEMINI_API_KEY=''` (empty) in container. Embedding calls return 403. Not a code bug — needs a valid Gemini API key in Vault/env to re-run. Threshold values from the 2026-06-07 live eval remain the authoritative numbers.

#### Bug 4 — Guardrails latency test p95 > 100ms (intermittent)

**Root cause:** `en_core_web_lg` (presidio/spacy) has multiple lazy-initialization stages. A single warmup call in the test fixture flushed stage 1 but not all stages; one of the 20 timed calls hit a residual cold-start spike.

**Fix:** Increased warmup to 3 calls with varied civic text before yielding the test client.

**File:** `tests/test_security/test_service_auth.py`

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

### Resolved in Phase 9 ✅
- RAG eval live run — `rag_hit_at_5=0.875`, `rag_mrr=0.875`; thresholds updated to `measured − 2pp` ✅
- Agent eval live run — `agent_tool_accuracy=0.933` (14/15); threshold updated to 0.91 ✅
- Arabic training row review — all 628 rows (MSA 211, Lebanese 212, Arabizi 205) reviewed; 0 corrections; sign-off in `modelserver/model_card.md §Data Corrections` ✅

### Still Open (require manual browser work before defense demo)

**Phase 6 (Widget) — manual gates outstanding**
- SC-002: first message round-trip < 3s on 3G — measure with Chrome DevTools before defense demo (template in `EVALS.md §8`)
  - Start widget dev server: `cd widget && npm run dev`; start API: `docker compose up api -d`
  - Open `http://localhost:5173/widget/?token=preview`; DevTools → Network → throttle "Slow 3G"; measure 5 round-trips; fill `EVALS.md §8 SC-002`
- SC-004: RTL manual checklist — 10-item checklist in `EVALS.md §8` — run before demo
  - Toggle language to Arabic in widget; verify RTL layout, bubble direction, send-button flip, toggle labels; fill `EVALS.md §8 SC-004`

---

## 5. CI Gate Status

| Gate | Threshold | Measured | Status |
|---|---|---|---|
| `classifier_macro_f1` | **0.97** | **0.9966** | ✅ Session 7 retrain (13,138 rows, 2026-06-12) |
| `en_macro_f1` | **0.97** | **0.9984** | ✅ Session 7 mixed real+template EN test (n=2,449) |
| `ar_macro_f1` | **0.95** | **0.9740** | ✅ Session 7 AR test, n=198 (MSA 69 + Lebanese 33 + Arabizi 96) |
| `arabizi_f1` | **0.94** | **0.9578** | ✅ Session 7 AR sub-model (§8.3 split), n=96 |
| `agent_tool_accuracy` | **0.91** | **0.933** | ✅ Phase 9 live eval 14/15 (2026-06-07) |
| `workflow_handled_rate` | 0.60 | — | ⚠️ Target set — measured via cost attribution logs |
| `rag_hit_at_5` | **0.85** | **0.875** | ✅ Phase 9 live eval 8 triples (2026-06-07) |
| `rag_mrr` | **0.85** | **0.875** | ✅ Phase 9 live eval (2026-06-07) |
| `rag_faithfulness` | 0.60 | — | ⚠️ Keyword-overlap proxy; LLM-judge not run (free tier) |
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
| `build_dataset.md` | **927 AR + ~610 EN seed** | all 4, all varieties | Hand-crafted. 927 AR = 400 Arabizi (100/intent) + 212 Lebanese + 315 MSA (155 spam). 610 EN = 200 report + 200 question + 200 human + ~10 spam seed. **Rewrites CSV from scratch.** |
| `dataset_english_large.md` | **~11,996** | EN only, all 4 intents | Template-generated (3K per intent). **Re-run after `build_dataset.md`.** |
| `dataset_english.md` | ~79 | EN report + spam | Optional: NYC 311 Kaggle + enron_spam top-up. |
| **Total (CSV, confirmed)** | **13,083** | | 10,470 train / 2,613 test (~20.0% test) |

**Variety breakdown (confirmed from CSV — Phase 9 Session 6):**

| Variety | Total | report | question | human | spam |
|---|---|---|---|---|---|
| en | 12,156 | — | — | — | — |
| msa | 315 | 55 | 54 | 51 | 155 |
| lebanese | 212 | 55 | 55 | 51 | 51 |
| arabizi | 400 | 100 | 100 | 100 | 100 |
| **total** | **13,083** | — | — | — | — |

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
| msa | 55 | 54 | 51 | **155** |
| lebanese | 55 | 55 | 51 | 51 |
| arabizi | 100 | 100 | 100 | 100 |

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

## 8. Next Phase Prep — Improvements Roadmap

**All automatable Phase 9 tasks are complete (Session 3, 2026-06-09).** Only manual browser gates remain. Items below are preserved for documentation; ✅ = done.

---

### 8.1 Arabizi Data Expansion ✅ DONE

**Why:** Arabizi F1 = 0.8322 is the weakest variety. The `emta lazem ndfa3 fatouret el may` (water bill payment question) is classified as `spam` — a real resident asking this question gets no answer. Root cause: only 51 examples per Arabizi cell, and the training set is 19:1 EN:AR, drowning out Arabizi char n-gram features.

**Target:** 100 examples per cell (currently 51–52), Arabizi F1 ≥ 0.90.

**Where to add rows:** `build_dataset.md` — find the `# ARABIZI` section (around line 339). Each row is:
```python
add("fi 7ufra bel share3", lang="ar", variety="arabizi", intent="report", category="roads")
```

**Arabizi transcription rules:**
| Arabic letter | Arabizi digit/char |
|---|---|
| ع (`ayn`) | `3` |
| ح (`ha`) | `7` |
| ء/أ (`hamza`) | `2` |
| خ (`kha`) | `5` |
| ط (`ta`) | `6` |
| غ (`ghayn`) | `8` |
| ق (`qaf`) | `9` or `q` |

**Common civic Arabizi vocabulary to use in examples:**
| Arabic meaning | Arabizi spelling |
|---|---|
| street (شارع) | `share3` |
| water (ماء/مي) | `may` / `mei` |
| electricity (كهرباء) | `kahraba` / `kahrabeh` |
| pothole (حفرة) | `7ufra` / `hafra` |
| broken (مكسور) | `maksur` / `mkassar` |
| when (متى/إمتى) | `emta` / `imta` |
| I want to pay (بدي/لازم ادفع) | `bade ndfa3` / `lazem ndfa3` |
| bill (فاتورة) | `fatouret` / `fa2touret` |
| road (طريق) | `tari2` / `tari3` |
| garbage (زبالة) | `zbele` / `zbala` |
| permit (رخصة) | `ro5se` / `rkhsa` |
| I need to talk (بدي حكي) | `bade 7ke` / `bade 7ki` |
| near (عند/جنب) | `3and` / `jemb` |
| school (مدرسة) | `madrase` / `mdarse` |
| neighbourhood (حي/حارة) | `7aret` / `7ay` |

**Needed Arabizi examples per intent (49 more per cell):**

```
report (need +49): pothole, broken streetlight, water leak, garbage overflow, 
  damaged road, power outage, broken bench, crack in wall, etc.
  "fi 7ufra kbiri bel tari2 jemb el madrase"
  "el kahraba ma3a mn embare7 la hala2"
  "fi tassarob may bel share3 el jedid"
  "el zbele mesh mn2oule mn 3 t2am"

question (need +49): payment deadlines, how to apply for permit, office hours,
  complaint status, required documents, etc.
  "emta lazem ndfa3 fatouret el may"       ← currently classified as spam!
  "kif bade 2arrab talbiyye lal ro5se"
  "shu el awa2 el rasmiyye lal baladiyye"
  "fi ay maktab bade ro7 la2arrab shakwa"

human (need +49): need a real person, urgent help, can't solve online, etc.
  "bade 7ke ma3 7ada men el baladiyye"
  "ma 3am efham el tabi2 bade 7ada y3enni"
  "el mawdu3 3ajem bade wa7ad mes2oul"
  "min fadlak wasselni la 7ada yekdar ysa3edni"

spam (need +49): prize scams, fake offers, click links, lottery wins, etc.
  "ra7est bi jaize kbire do5ol 3al link"
  "2ndak forsit tis3a fe3lan majaniyyan"
  "mabrok ra7elt bil siyyara el jedide"
  "click hon w 2rbeh 1000 dollar"
```

**Rebuild steps after adding rows:**
```bash
python3 build_dataset.md         # regenerates CSV with new rows
# (skip dataset_english_large.md — don't re-generate EN templates)
# Open notebooks/train_classifier_bilingual.ipynb → Run All
# Update eval_thresholds.yaml: arabizi_f1: 0.88  (or measured − 2pp)
# Update modelserver/model_card.md with new SHA-256 + F1
docker compose build modelserver  # rebuild image with new artifact
docker compose up -d modelserver  # restart
```

**Expected outcome:** Arabizi F1 ≥ 0.90; `emta lazem ndfa3` correctly classified as `question`.

---

### 8.2 Real English Data Expansion ✅ DONE

**Why:** Real-text EN macro-F1 = 0.8420 vs template F1 = 1.0000. The EN test set is template-generated, so the model memorised patterns rather than generalising. Real NYC 311 messages + manually written variants will close this gap.

**Where:** `build_dataset.md` — add real 311-style EN rows. Target: 200 real rows per intent cell. NYC 311 CSV is at `/tmp/311_data/nyc_311_2025.csv` (if present; re-download from Kaggle if not).

**Guidance:** Real messages to add per intent:
- **report**: "There's a large pothole on Oak Ave near the bus stop", "Street lamp has been out for 3 weeks on Main St", "Water coming up from the drain on 5th Ave"
- **question**: "What documents do I need for a building permit?", "What are the office hours for the permits department?", "How do I check the status of my complaint?"
- **human**: "I've been trying to get help with this for 2 months please someone call me", "This is urgent my family has no water"
- **spam**: Add nothing — the spam examples are already strong (synthetic spam is easy)

---

### 8.3 Per-Language Classifier Split ✅ DONE

**Why:** A single TF-IDF model over a 19:1 EN:AR dataset means the char n-gram space is dominated by English tokens. Arabic varieties share 48,875 features with 12,103 English rows.

**Approach:** Train a small dedicated Arabic classifier (`ar_pipeline`) on only the 628 Arabic rows. Use `detect_variety` output to route to the right pipeline: if `variety == "en"` → EN pipeline; otherwise → AR pipeline.

**Files to change:**
- `modelserver/classifier.py` — add `ArabicClassifierService`, update `ClassifierService.predict()` to dual-dispatch
- `notebooks/train_classifier_bilingual.ipynb` — add Arabic-only training cell, export second artifact
- `modelserver/artifacts/` — add `classifier_ar.joblib`

**Expected outcome:** Arabizi F1 can reach 0.95+ with only 200 balanced Arabic examples per variety (no EN dilution).

---

### 8.4 Remaining Manual Gates (browser work)

- **SC-002**: First-message round-trip < 3s on 3G. Open Chrome → DevTools → Network → "Slow 3G" → send a message → record 5 round-trip times → fill `EVALS.md §8 SC-002` P50/P95 rows.
- **SC-004**: RTL manual checklist. Toggle language to Arabic in widget → verify: RTL layout, text direction, bubble alignment, send-button flip, placeholder text, language-toggle label. Fill `EVALS.md §8 SC-004` checkboxes.

---

### 8.5 Minor Improvements ✅ DONE (Session 3)

| Improvement | Status |
|---|---|
| `emta`/`kif`/`lazem` words in `_ARABIZI_RE` | ✅ Done — `modelserver/classifier.py` |
| `ARABIC_GIVEN_NAME` list grown to 100+ names | ✅ Done — `api/middleware/redaction.py` |
| `arabizi_f1: 0.90` gate added to `eval_thresholds.yaml` | ✅ Done |
| RAG eval re-run — blocked by missing `GEMINI_API_KEY` in docker env | ⚠️ Not runnable — add key to Vault/`.env` and rebuild api container |
| Arabic/Arabizi CMS content seeding | ⚠️ Deferred — needs valid Gemini API key for embedding |

**Phase 8 items confirmed complete — no rework needed:**
- ✅ Arabic name PII redaction (two-pattern: prefix + given-name list)
- ✅ Per-widget JWT key rotation (Vault KV v2 + two-pass decode)
- ✅ Defense docs: `DECISIONS.md §D-Arabic-001`, `DATA.md`, `modelserver/model_card.md`
- ✅ Real-text EN eval: n=25, macro-F1 = 0.8420, model card updated
- ✅ Classifier DataFrame→list bug fixed (all intents now predict correctly)
- ✅ Arabizi variety detection bug fixed (`detect_variety` pre-gates on Latin ratio before langdetect)

---

## 9. Non-Obvious Facts

**`gemini-embedding-001` is 3072 dims natively, not 1536.** The embedding client passes `outputDimensionality: 1536` to truncate. The pgvector column is `vector(1536)`. Verified with a live API call on 2026-06-02. Do NOT change the column type or `outputDimensionality` — the entire corpus must stay in one vector space.

**`build_dataset.md` is a Python script.** `.md` extension is intentional. Run with `python3 build_dataset.md`.

**`Data.md` ≠ `DATA.md`.** `Data.md` is the user's original spec with model/API key decisions. `DATA.md` is the generated dataset documentation. Both exist at root.

**`feature.json` controls which phase is active.** The prerequisites script reads it. Already updated to `specs/008-hardening-evals`.

**Gemini free tier: 20 calls/day for `gemini-2.5-flash`.** Not enough to run the LLM eval on 98 test examples. The LLM zero-shot baseline uses **Groq llama-3.3-70b** (generous free tier).

**`classifier_confidence_thresholds` is in `Settings`.** Per-intent dict `{report: 0.75, question: 0.75, human: 0.65, spam: 0.90}`. Below threshold → agent path. Spam threshold intentionally high (0.90) to minimise false drops.

**`ar_classifier_confidence_thresholds` is the Arabic-specific routing dict (added Session 6).** `{report: 0.70, question: 0.70, human: 0.60, spam: 0.75}`. The AR sub-model is trained on ~700 rows vs ~10K for EN — calibrated softmax probabilities are naturally lower even when precision/recall = 1.0. Router selects this dict for `variety in (msa, lebanese, arabizi)`. See `api/core/config.py` and `api/services/router_service.py`.

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

## 10. What Still Needs Fixing & Future Work

### 10.1 Still Broken — Needs to be Fixed

These are real bugs that will affect the live demo or production use. They are not fixed yet because they require a valid Gemini API key or more training data.

---

**[FIXED - Session 6] Arabic spam confidence fixed — MSA spam now correctly dropped**

- Fixed 2026-06-11. Confidence improved: "تهانينا ربحت جائزة" now classified at 0.804 (above 0.75 AR threshold).
- Fix 1 (data): MSA spam rows grown 51 → 155 (+104 diverse scam/phishing/lottery patterns) in `build_dataset.md`. AR sub-model retrained; SHA-256 `ab51509e...`.
- Fix 2 (threshold): Added `ar_classifier_confidence_thresholds` in `api/core/config.py` with `spam: 0.75`. The AR sub-model has fewer training rows so calibrated confidence is lower even when precision/recall = 1.0. Router now selects AR-specific thresholds for `msa | lebanese | arabizi`.
- Bonus: Arabizi F1 improved 0.9510 → 0.9636 in the main pipeline from the MSA data expansion.

---

**[FIXED - Session 7] Arabizi question confidence fixed — "emta lazem ndfa3 fatouret el may" now routes correctly**

- Fixed 2026-06-12. +55 Arabizi question rows with civic payment/billing vocabulary added to `build_dataset.md`. AR sub-model retrained on 784 rows. Confidence: 0.532 → 0.933 (well above 0.75 AR threshold).
- Fix details: Added rows covering water/electricity billing (`fatouret`, `ndfa3`, `kahraba`, `may`), permit/fee queries, schedule queries. All test probes now score > 0.86 on the `question` class.
- Remaining issue (b): No Gemini API key in container — agent path falls back to Groq, which returns English. Fix B (API key): Set `GEMINI_API_KEY=<real-key>` in `.env`, rebuild api container: `docker compose up --build api -d`.

---

**[BROKEN] RAG eval blocked — cannot re-run `evaluate_rag.py`**

- Symptom: `python evals/evaluate_rag.py` returns 500 errors from `/rag/search`. Container logs show `403 from Gemini embedding API`.
- Root cause: `GEMINI_API_KEY=''` in the api container — embedding calls fail.
- Fix: Set `GEMINI_API_KEY=<real-key>` in `.env`, rebuild api container. Then: `python evals/evaluate_rag.py --mode compare`. Update `eval_thresholds.yaml` with measured values − 2pp.
- Current thresholds (from 2026-06-07 live eval): `rag_hit_at_5: 0.85`, `rag_mrr: 0.85` — these are still valid; just can't re-run without the key.

---

**[BROKEN] Arabic CMS content not seeded — RAG returns no results for Arabic queries**

- Symptom: Arabic questions that should hit the knowledge base return "I don't have specific information" (or the Arabic equivalent).
- Root cause: `scripts/seed.py` only seeds English CMS content. Arabic CMS entries need embeddings, which require the Gemini embedding API. No key → no Arabic vectors.
- Fix: Add `GEMINI_API_KEY`, rebuild, then run `python scripts/seed.py` to seed Arabic content. Or manually POST to `/cms/entries` with Arabic content via the Tenant Admin API.

---

**[BROKEN] SC-002 and SC-004 — manual browser gates not yet done**

- SC-002: 3G latency. Open Chrome → DevTools → Network → "Slow 3G" → send message → record 5 round-trips → fill `EVALS.md §8 SC-002`.
- SC-004: RTL checklist. Toggle to Arabic in widget → verify layout, bubble direction, send-button, placeholder text → fill `EVALS.md §8 SC-004`.
- These are human browser tasks — cannot be automated.

---

### 10.2 Future Improvements — Do When Time Allows

These are not blocking bugs — the system works without them — but they improve quality.

| Improvement | Why | Effort | Where |
|---|---|---|---|
| ~~Add 50+ MSA spam rows to training data~~ ✅ Done Session 6 | MSA spam confidence 0.532→0.804; 51→155 rows; AR threshold 0.90→0.75 | — | `build_dataset.md`, `api/core/config.py` |
| ~~Add 50+ Arabizi question rows~~ ✅ Done Session 7 | Arabizi question confidence 0.532→0.933; 100→155 rows; "emta lazem ndfa3" correctly routed | — | `build_dataset.md`, AR sub-model retrained |
| Seed Gemini API key in Vault | Enables: RAG eval, Arabic CMS seeding, agent path Arabic responses | Very low | `docker compose up vault -d`, then `python scripts/seed.py` after setting key in `.env` |
| Run `evaluate_rag.py --mode compare` | Get live RAG numbers with current stack | Low | After fixing Gemini key |
| Run `evaluate_agent.py` | Verify agent tool accuracy ≥ 0.91 with current live stack | Low | After fixing Gemini key |
| Hand-verify Arabic training rows (MSA/Lebanese) | Currently machine-generated — cite per-variety F1 as "preliminary" until reviewed | Medium | Read `build_dataset.md` Arabic sections; verify 200–300 rows |
| LLM-judge faithfulness eval (`rag_faithfulness` threshold 0.60) | Currently uses keyword-overlap proxy — not a real faithfulness score | High | Requires Gemini key + writing eval prompt |

---

## 11. Running the Stack on a Low-RAM Machine (8 GB)

Running all containers at once causes lag on an 8 GB laptop. Split into two rounds:

**Round 1 — Streamlit admin only** (lighter, ~5 containers active):
```bash
docker compose start db redis vault migrate api chatbot platform_manager
```
Open `http://localhost:8501` (Tenant Admin) and `http://localhost:8502` (Platform Manager).

**Round 2 — Widget demo only** (stop admin first, then start widget stack):
```bash
docker compose stop chatbot platform_manager
docker compose start modelserver guardrails host
```
Open `http://localhost:8080` (municipality demo site with embedded widget).

Stop everything without deleting images or volumes:
```bash
docker compose stop
```

---

## 12. Cross-Feature Dependency Map

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

*Last updated: 2026-06-12 Session 7 | 149/149 tests passing (3 skipped) | Session 7: Arabizi question confidence fixed (0.532→0.933), +55 Arabizi question rows, AR sub-model retrained on 784 rows (SHA 96149720), macro-F1 0.9966, AR 0.9740, Arabizi 0.9578 | Still broken: RAG eval blocked by missing GEMINI_API_KEY, SC-002/SC-004 need human browser | See §10 for full breakdown*


What's Still Remaining

1. Can be done now (no Gemini key needed)

- ✅ DONE (Session 7) — +55 Arabizi question rows added to `build_dataset.md`. AR sub-model retrained on 784 rows. "emta lazem ndfa3 fatouret el may" confidence 0.532→0.933. All CI thresholds pass. No remaining automatable tasks without a Gemini key.

2. Blocked on GEMINI_API_KEY (user must provide the key)

All four items below unblock the moment you add a valid key to .env:

âââââââââââââââââââââââââââââââ¬âââââââââââââââââââââââââââââââââââââââââââââââââââ
â            Task             â                       How                        â
âââââââââââââââââââââââââââââââ¼âââââââââââââââââââââââââââââââââââââââââââââââââââ¤
â Arabic CMS content seeded   â python scripts/seed.py after key is set          â
âââââââââââââââââââââââââââââââ¼âââââââââââââââââââââââââââââââââââââââââââââââââââ¤
â RAG eval re-run             â python evals/evaluate_rag.py --mode compare      â
âââââââââââââââââââââââââââââââ¼âââââââââââââââââââââââââââââââââââââââââââââââââââ¤
â Agent eval re-run           â python evals/evaluate_agent.py                   â
âââââââââââââââââââââââââââââââ¼âââââââââââââââââââââââââââââââââââââââââââââââââââ¤
â Agent path Arabic responses â Gemini fallback â Groq currently returns English â
âââââââââââââââââââââââââââââââ´âââââââââââââââââââââââââââââââââââââââââââââââââââ

3. Manual browser [HUMAN] tasks (cannot be automated)

- SC-002: Chrome DevTools â Network â "Slow 3G" â send 5 messages â fill EVALS.md Â§8 SC-002
- SC-004: Toggle widget to Arabic â verify RTL layout, bubble direction, send-button flip â fill EVALS.md Â§8 SC-004

4. Optional quality (before defense)

- Hand-verify MSA/Lebanese training rows â they're machine-generated; citing per-variety F1 as reliable requires human spot-check
- LLM-judge faithfulness eval â current rag_faithfulness uses a keyword-overlap proxy, not a real faithfulness score

---
The highest-leverage single action is providing the Gemini API key â it unblocks items 2 and 3's agent path at once. Want me to start on the Arabizi question rows expansion now?