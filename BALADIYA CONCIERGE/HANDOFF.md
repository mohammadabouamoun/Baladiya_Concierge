# HANDOFF.md — Baladiya Concierge

> Snapshot of project state as of **2026-06-04**. Written for the next agent session or future self picking up this repo cold. Read this before touching any spec file or running any skill.

---

## 1. Current Phase

| Field | Value |
|---|---|
| **Active feature** | `005-guardrails-security` (next) |
| **Status** | **Phases 1–4 complete — ready to start Phase 5** |
| **Last completed task** | All 22 tasks in `004-router-agent` are `[X]` + analyze fixes applied |
| **Next task to start** | Run `/speckit-implement` from `specs/005-guardrails-security/` |
| **How to start** | `feature.json` already updated → `"feature_directory": "specs/005-guardrails-security"` — run `/speckit-implement` |

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

**All 22 tasks complete. `/speckit-analyze` remediation also applied (14 fixes). Committed `a83ed7a`.**

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
| Chat API | `api/api/chat/router.py` — `POST /chat` + `POST /chat/token`; guardrails passthrough stub |
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
- Guardrails stub in `POST /chat`: returns `True` always — **Phase 5 replaces this** with the real sidecar call
- `POST /chat/token` issues visitor JWTs (no origin check) — **Phase 6 adds origin verification**
- 503 returned on `httpx.RequestError` from modelserver — no raw tracebacks

---

## 3. Completed Documentation

| File | Status | Notes |
|---|---|---|
| `BALADIYA_CONCIERGE.md` | Complete | Original product spec |
| `CLAUDE.md` | Complete | Tech stack, hard constraints |
| `DESIGN.md` | Complete | Architecture, component map, 7 key decisions |
| `DECISIONS.md` | Updated | §1 classifier, §2 RAG, §3 chunking, §D10 session TTL filled; agent/evals TBD |
| `EVALS.md` | Partial | Classifier results filled; RAG/agent/red-team sections TBD |
| `RUNBOOK.md` | Complete | Tenant lifecycle, incident runbook |
| `SECURITY.md` | Complete | Threat model, isolation enforcement |
| `DATA.md` | Complete | Dataset schema, labelling guidelines |
| `modelserver/model_card.md` | Complete | Two-way comparison, real F1 numbers, SHA-256 |
| `.specify/memory/constitution.md` | Complete | 7 non-negotiable governance rules |

---

## 4. Open Decisions / TBDs

### Resolved in Phase 4 ✅
- `eval_thresholds.yaml → agent_tool_accuracy` = **0.80** (target; run `evals/evaluate_agent.py` for measured value)
- `eval_thresholds.yaml → workflow_handled_rate` = **0.60** (target; measured via cost attribution logs)
- `max_tool_calls = 3` — config setting, default per FR-003
- `evals/agent_tool_selection.json` — 15 examples committed
- Session TTL 1800s — justified in `DECISIONS.md §D10`
- `DECISIONS.md §D10` — Session Memory TTL added

### Still Open

**Phase 3 (RAG) — needs live DB stack**
- `eval_thresholds.yaml → rag_hit_at_5`, `rag_mrr`, `rag_faithfulness` — `0.0` placeholder
- Run `python evals/seed_eval_content.py` then `python evals/evaluate_rag.py --mode compare` to get measured values; update thresholds to `measured − 2pp`
- Arabic chunk density — single char-limit confirmed as hypothesis; Phase 7 will re-evaluate

**Phase 4 (Agent) — needs live LLM API**
- `evals/evaluate_agent.py` not yet run — `agent_tool_accuracy` is a target, not a measured value
- `EVALS.md §4` (agent tool selection) — TBD rows not filled
- `EVALS.md §5` (SC-002 workflow %) — not filled
- `DECISIONS.md §2` and `§3` RAG eval rows — `[run eval]` placeholders

**Phase 5 (Security)**
- `evals/redteam_probes.json` — does not exist; 12+ probes in Phase 5
- Red-team gate rows in `EVALS.md §6` — all `[TBD — Phase 5]`
- Guardrails sidecar p99 under load — must validate in Phase 5
- `guardrails_url: "http://guardrails:8002"` already in Settings — sidecar not yet built

**Phase 7 (Arabic)**
- `eval_thresholds.yaml → ar_macro_f1` — `0.0`; set after Arabic dataset grows to ≥20 verified rows per cell
- Arabizi (F1=0.50) and Lebanese (F1=0.71) cells are thin — only 5 test rows each

---

## 5. CI Gate Status

| Gate | Threshold | Measured | Status |
|---|---|---|---|
| `classifier_macro_f1` | 0.88 | 0.8983 | ✅ Real value — gate active |
| `en_macro_f1` | 0.86 | 0.8784 | ✅ Real value — gate active |
| `ar_macro_f1` | 0.0 | 0.8117 | ⚠️ Placeholder — set in Phase 7 |
| `agent_tool_accuracy` | 0.80 | — | ⚠️ Target set — run `evals/evaluate_agent.py` for measured value |
| `workflow_handled_rate` | 0.60 | — | ⚠️ Target set — measured via cost attribution logs |
| `rag_hit_at_5` | 0.73 | — | ⚠️ Pre-measurement target — run `evals/evaluate_rag.py` |
| `rag_mrr` | 0.60 | — | ⚠️ Pre-measurement target — run `evals/evaluate_rag.py` |
| `rag_faithfulness` | 0.60 | — | ⚠️ Pre-measurement target — Phase 5 LLM-judge eval |
| `redteam_pass_rate` | 1.0 | — | ✅ Non-negotiable — never lower |

**CI workflow**: `.github/workflows/ci.yml` — runs on every push. Gates: unit tests, latency p95 < 50ms (real artifact), modelserver image < 500 MB, red-team isolation probes.

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

**onnxruntime WSL locale issue**: ONNX inference fails with `en_US.UTF-8 locale not found`. Fix: `sudo apt-get install locales language-pack-en && sudo locale-gen en_US.UTF-8`. This does not affect the shipped `classifier.joblib`.

**uv pip**: Use `uv pip install <pkg>` for faster installs. For venv-specific: `uv pip install <pkg> --python /home/usermohammad/.venv/bin/python3`.

---

## 8. Next Phase Prep — Phase 5 (Guardrails & Security)

`feature.json` already points to `specs/005-guardrails-security`. The spec, plan, and tasks are fully written. Run `/speckit-implement` to start.

**What Phase 5 builds:**
- `guardrails/` — NeMo Guardrails sidecar Docker service (FastAPI `POST /validate`, platform rails)
- `api/infra/guardrails_client.py` — async httpx client; replaces the passthrough stub in `POST /chat`
- `api/middleware/redaction.py` — Presidio PII redaction (Lebanese NID, phone, email) applied before logging and before Redis writes
- `evals/redteam_probes.json` — 12+ red-team probes committed; CI gate refuses all of them
- Right-to-erasure compliance verification

**Critical wiring point:** `api/api/chat/router.py` has `_guardrails_check()` stub that returns `True` always. Phase 5 replaces it with a real call to `guardrails_client.validate()`. The function signature is already in place — only the implementation changes.

**Service auth:** The guardrails sidecar validates `X-Service-Token` header. This token lives in Vault at `baladiya/guardrails/service_token` — the Vault seed script needs a new entry. `guardrails_url` is already in `Settings` (`"http://guardrails:8002"`).

**docker-compose.yml**: The guardrails service needs to be added as a new container (port 8002). The `guardrails_url` setting is already wired in `api/core/config.py`.

**Dependencies:**
1. Phase 4's `agent_service.run()` output is the thing being guarded — guardrails wraps it
2. Phase 4's `POST /chat` guardrails stub is the exact integration point
3. Redaction must run BEFORE structlog write AND before Redis session write in `session_service.add_turns()`

**DB must be running for integration tests:** `docker-compose up db vault migrate api redis guardrails`

---

## 9. Non-Obvious Facts

**`gemini-embedding-001` is 3072 dims natively, not 1536.** The embedding client passes `outputDimensionality: 1536` to truncate. The pgvector column is `vector(1536)`. This was verified with a live API call on 2026-06-02. Do NOT change the column type or the `outputDimensionality` — the entire corpus must stay in one vector space.

**`build_dataset.md` is a Python script.** `.md` extension is intentional. Run with `python3 build_dataset.md`.

**`Data.md` ≠ `DATA.md`.** `Data.md` is the user's original spec with model/API key decisions. `DATA.md` is the generated dataset documentation. Both exist at root.

**`feature.json` controls which phase is active.** The prerequisites script reads it. Update manually at each phase boundary.

**Gemini free tier: 20 calls/day for `gemini-2.5-flash`.** Not enough to run the LLM eval on 98 test examples. The LLM zero-shot baseline uses **Groq llama-3.3-70b** (generous free tier). See `notebooks/train_classifier.ipynb` cell-17/18.

**`classifier_confidence_thresholds` is in `Settings`.** Per-intent dict `{report: 0.75, question: 0.75, human: 0.65, spam: 0.90}`. Below threshold → agent path. Spam threshold intentionally high (0.90) to minimise false drops.

**Two-way comparison, not three-way.** The spec originally said "three approaches" but DL/ONNX was dropped. The comparison is Classical ML vs LLM zero-shot only.

**Session key structure: `session:{session_id}:{tenant_id}`** — SCAN pattern for erasure: `session:*:{tenant_id}`. Do NOT use `tenant:{tenant_id}:` prefix (spec.md had this wrong before the Phase 4 analyze fix — corrected in commit `a83ed7a`).

**`capture_request` never receives spam.** Spam is dropped by the classifier BEFORE any tool call. The router's `SPAM` branch returns `("", "spam")` immediately.

**LLM fallback is request-count-based, not time-based.** `_GeminiFailureTracker.count ≥ 3` → Groq; resets to 0 on the first successful Gemini call. It's a module-level singleton class, not a bare global. To reset in tests: `from api.infra.llm_client import _gemini_tracker; _gemini_tracker.reset()`.

**`max_tool_calls` setting name (not `max_tool_iterations`).** Was renamed in Phase 4 analyze pass. The default is 3 (spec FR-003). Do not confuse with `max_tokens_per_turn` (4096).

**Gemini SDK is synchronous.** `google-generativeai==0.7.2` has no native async. The `llm_client.py` wraps `model.generate_content()` in `asyncio.to_thread()`. This is acceptable since the thread-pool offloads the blocking call.

**Phase 8 docs already written.** `DESIGN.md`, `DECISIONS.md`, `RUNBOOK.md`, `SECURITY.md` are pre-written. Mark their Phase 8 tasks `[X]` without redoing the work.

**`specs/004-agent-router/` is empty.** The actual Phase 4 specs live in `specs/004-router-agent/` (note the different ordering). The empty directory is a leftover from the initial `feature.json` pointer — safe to ignore.

---

## 10. Cross-Feature Dependency Map

```
P1 (Foundation) → ALL others
P2 (Classifier) → P4 (Router calls modelserver)
P3 (CMS/RAG)   → P4 (Router calls rag_search)
P4 (Router)    → P5 (Guardrails wraps POST /chat + redacts before session write)
P5 (Guardrails)→ P6 (Widget calls guarded API)
P6 (Widget)    → P7 (RTL + Arabic end-to-end)
P7 (Arabic)    → P8 (Final evals include AR numbers)
```

---

*Last updated: 2026-06-04 | Phases 1–4 complete | Next: 005-guardrails-security*
