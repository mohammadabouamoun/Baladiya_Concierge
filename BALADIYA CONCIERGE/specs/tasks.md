# Master Task Breakdown — Baladiya Concierge

This is the top-level task index across all features. Each feature has its own detailed `tasks.md`. This file tracks the phase gates and cross-feature dependencies.

**Format**: `[ID] [P?] Description` — `[P]` = can run in parallel with other P-tagged tasks in the same phase.

---

## Phase 1: Foundation & Isolation (`001-foundation-isolation`)

**Gate**: All isolation tests + red-team suite pass in CI before Phase 2.

See [specs/001-foundation-isolation/tasks.md](./001-foundation-isolation/tasks.md) for full breakdown.

- [ ] **P1-001** Repo scaffold, Compose stack (all 11 services stubbed, 5 active: db, vault, migrate, api, redis — redis needed for rate limiting in P1)
- [ ] **P1-002** Pydantic settings + Vault integration + refuse-to-boot
- [ ] **P1-003** structlog with trace_id + tenant_id
- [ ] **P1-004** Alembic baseline migration: all tables + RLS policies
- [ ] **P1-005** Async SQLAlchemy get_db with SET/RESET session variable in finally block
- [ ] **P1-006** fastapi-users JWT auth: tenant_id + role in token payload
- [ ] **P1-007** BaseRepository with mandatory tenant_id filter
- [ ] **P1-008** Platform Manager provisioning API (provision / suspend / erase)
- [ ] **P1-009** Seed script: Platform Manager + 2 tenants
- [ ] **P1-010** [P] RLS integration tests (direct DB, no HTTP)
- [ ] **P1-011** [P] Session variable reset test (exception mid-request)
- [ ] **P1-012** [P] Red-team isolation probes in CI
- [ ] **P1-013** Per-tenant rate limiting (Redis sliding window)
- [ ] **P1-014** Cost attribution middleware (tag LLM/embedding calls with tenant_id)
- [ ] **P1-015** eval_thresholds.yaml with placeholder values for all 4 CI gates

**Phase 1 Gate**: `pytest tests/test_isolation/ -v` all green. `docker-compose up db vault migrate api` seeds 2 tenants cleanly.

---

## Phase 2: Classifier & Model Server (`002-classifier`)

**Gate**: Classifier macro-F1 CI gate passes; modelserver boots with SHA-256 verification; 3-way comparison committed.

- [ ] **P2-001** [P] Training notebook: TF-IDF + LogReg/SVM classical baseline — evaluate on held-out test
- [ ] **P2-002** [P] Training notebook: optional DL model → ONNX (if pursued)
- [ ] **P2-003** [P] LLM zero-shot baseline evaluation (API calls, offline)
- [ ] **P2-004** Commit 3-way comparison table to EVALS.md; choose model; write model_card.md with artifact SHA-256
- [ ] **P2-005** modelserver Dockerfile (no torch; < 500 MB)
- [ ] **P2-006** modelserver FastAPI: lifespan SHA-256 check + /classify endpoint + service-token auth
- [ ] **P2-007** api/infra/modelserver_client.py: httpx async client with Vault service credential
- [ ] **P2-008** CI classifier gate: macro-F1 + per-language F1 vs eval_thresholds.yaml
- [ ] **P2-009** [P] Integration test: POST /classify returns correct schema, < 50ms, rejects no-token

**Phase 2 Gate**: `classifier_macro_f1` CI gate passes; `modelserver` image < 500 MB; model_card.md SHA-256 matches artifact.

---

## Phase 3: CMS & RAG (`003-cms-rag`)

**Gate**: RAG CI gate passes (hit@5, MRR, faithfulness on 15 golden triples); CMS CRUD works in Streamlit admin.

- [ ] **P3-001** Alembic migration: cms_entries, cms_chunks (pgvector with tenant_id RLS)
- [ ] **P3-002** CmsRepository: CRUD + chunking on save + embedding via hosted API + pgvector upsert
- [ ] **P3-003** Tenant-filtered pgvector similarity search (MUST include tenant_id filter)
- [ ] **P3-004** rag_search tool implementation (called by router workflow and agent)
- [ ] **P3-005** RAG improvement: query rewrite (primary choice) — measure vs baseline on golden set; if gain < 2pp hit@5, fall back to metadata filtering and re-evaluate; commit the chosen approach + number to DECISIONS.md
- [ ] **P3-006** Streamlit admin: CMS CRUD page (title, body, category, lang; embedding status indicator)
- [ ] **P3-007** Hand-label 15 RAG golden triples (question / ideal-answer / ground-truth-chunk) → evals/rag_golden.json
- [ ] **P3-008** CI RAG gate: hit@5, MRR, faithfulness, answer relevancy vs eval_thresholds.yaml
- [ ] **P3-009** [P] Background re-embed on edit; delete vectors on cms_entry delete
- [ ] **P3-010** Document chunking strategy + improvement choice in DECISIONS.md with measured numbers

**Phase 3 Gate**: `rag_hit_at_5` CI gate passes; Arabic question retrieves English chunk (cross-language test).

---

## Phase 4: Router & Agent (`004-router-agent`)

**Gate**: Agent tool-selection CI gate passes; capture_request injection probe refused; session memory scoped correctly.

- [ ] **P4-001** Alembic migration: capture_requests, escalation_tickets
- [ ] **P4-002** Router: classify via modelserver → route to workflow (spam/question/report/human) or agent
- [ ] **P4-003** capture_request tool: Pydantic payload validation + tenant-scoped write + per-session rate limit
- [ ] **P4-004** escalate tool: write escalation_ticket scoped to tenant
- [ ] **P4-005** Bounded agent loop: max_tool_calls + max_tokens_per_turn from config
- [ ] **P4-006** Redis session memory: get/set/expire per session:{session_id}:{tenant_id}
- [ ] **P4-007** Prompts: prompts/system_en.md + prompts/system_ar.md (tenant persona injected at runtime)
- [ ] **P4-008** Streamlit admin: view capture_requests and escalation_tickets for the tenant
- [ ] **P4-009** Hand-label 15 agent tool-selection examples → evals/agent_tool_selection.json
- [ ] **P4-010** CI agent tool-selection gate vs eval_thresholds.yaml
- [ ] **P4-011** [P] Capture_request injection red-team probe (extends Phase 1 red-team suite)
- [ ] **P4-012** [P] Session memory scoping test (Tenant A session cannot bleed into Tenant B)
- [ ] **P4-013** Log workflow-handled % vs agent-handled % per tenant (cost attribution)

**Phase 4 Gate**: Agent tool-selection CI gate passes; injection probe refuses fabricated tenant_id; ≥ 60% turns handled by workflow.

---

## Phase 5: Guardrails & Security (`005-guardrails-security`)

**Gate**: Red-team CI gate passes (100% probes refused); redaction CI test passes; sidecar rejects calls without service token.

- [ ] **P5-001** NeMo Guardrails sidecar Dockerfile + platform rails config (injection, jailbreak, cross-tenant, PII)
- [ ] **P5-002** Guardrails sidecar /validate endpoint + service-token auth (401 without token)
- [ ] **P5-003** api → guardrails HTTP call with Vault service credential; fail-closed on sidecar down (503)
- [ ] **P5-004** PII redaction middleware: Lebanese national ID, phone formats, email → [REDACTED_*] before logs/Redis/traces
- [ ] **P5-005** Tenant rails: configurable topics/tone/persona in tenant.settings.guardrail_config; wired into sidecar call
- [ ] **P5-006** Commit evals/redteam_probes.json (≥ 12 probes: injection x5, system-prompt x3, cross-tenant x2, jailbreak x2)
- [ ] **P5-007** CI red-team gate: all probes refused; gate blocks merge on any failure
- [ ] **P5-008** CI redaction test: fake national ID in chat → zero unredacted occurrences in all outputs
- [ ] **P5-009** [P] Test: tenant disabling all tenant rails does not affect platform rail outcomes
- [ ] **P5-010** [P] Test: raw curl to guardrails/modelserver without token → 401
- [ ] **P5-011** Document rail separation in SECURITY.md

**Phase 5 Gate**: Red-team gate: 0 failures. Redaction gate: 0 leaks. Internal services: 401 without token.

---

## Phase 6: Widget (`006-widget`)

**Gate**: Widget bundle < 100 KB gzipped; all 3 denial cases pass in CI; embed snippet works on allowed host.

- [ ] **P6-001** React (Vite) widget: chat UI, message input, conversation display
- [ ] **P6-002** widget.js loader: inject iframe, exchange widget_id + origin for signed JWT
- [ ] **P6-003** API: GET /widget/token (validates origin vs allowed_origins, returns signed JWT)
- [ ] **P6-004** API: GET /widget/config (returns greeting, theme from tenant.settings using token)
- [ ] **P6-005** RTL toggle: CSS dir="rtl" on language switch; Arabic greeting fallback
- [ ] **P6-006** per-tenant CORS headers + CSP: frame-ancestors on widget responses
- [ ] **P6-007** Streamlit admin: widget management (create widget, set allowed_origins, copy embed snippet)
- [ ] **P6-008** host nginx container: mock municipality demo site with embedded widget script tag
- [ ] **P6-009** [P] CI: disallowed origin → 403; no token → 401; expired token → 401
- [ ] **P6-010** [P] CI: widget bundle size check < 100 KB gzipped

**Phase 6 Gate**: Embed snippet works on `host` container; 3 denial cases all pass.

---

## Phase 7: Arabic & Polish (`007-arabic`)

**Gate**: AR macro-F1 CI gate passes; additive guarantee test passes; RTL demo works end-to-end.

- [ ] **P7-001** Hand-verify Arabic rows in civic_intent_dataset.csv; log corrections in model card
- [ ] **P7-002** Retrain classifier with bilingual data; update model card with per-variety F1
- [ ] **P7-003** Language detection integration in router (langdetect/langid → lang + variety)
- [ ] **P7-004** Prompt router: use system_ar.md when lang=ar, system_en.md otherwise
- [ ] **P7-005** RAG: prefer same-language chunks via metadata filter (soft boost)
- [ ] **P7-006** CMS admin: lang field for CMS entries (en / ar toggle)
- [ ] **P7-007** CI: ar_macro_f1 gate vs eval_thresholds.yaml
- [ ] **P7-008** [P] Additive guarantee test: remove Arabic rows → English CI gates still pass, no code exception
- [ ] **P7-009** [P] Per-variety F1 table committed in EVALS.md

**Phase 7 Gate**: Both `en_macro_f1` and `ar_macro_f1` CI gates pass; additive guarantee test passes.

---

## Phase 8: CI, Evals & Final Polish

- [ ] **P8-001** Finalize eval_thresholds.yaml with real numbers (not placeholders) after Phases 2–7
- [ ] **P8-002** Stack smoke test in CI: `docker-compose up` from fresh clone → 2 tenants seeded, all services healthy
- [ ] **P8-003** Write DESIGN.md (isolation strategy, cost model, scale story for 10 vs 1000 tenants)
- [ ] **P8-004** Write DECISIONS.md (every architectural choice backed by a number)
- [ ] **P8-005** Write RUNBOOK.md (how to provision a tenant, reset a secret, recover from sidecar outage)
- [ ] **P8-006** Write SECURITY.md (rail architecture, red-team results, PII redaction coverage)
- [ ] **P8-007** Tag `v0.1.0-final`; verify `docker-compose up` from a fresh clone with `cp .env.example .env`
- [ ] **P8-008** Practice defense demo: widget embed → report → question → escalate → erase tenant

---

## Cross-Feature Dependency Map

```
P1 (Foundation) ──────────────────────────────> ALL other phases depend on P1
P2 (Classifier) → P4 (Router uses classifier)
P3 (CMS/RAG)    → P4 (Router uses rag_search tool)
P4 (Router)     → P5 (Guardrails wraps the router/agent)
P5 (Guardrails) → P6 (Widget calls the guarded API)
P6 (Widget)     → P7 (RTL toggle + Arabic end-to-end)
P7 (Arabic)     → P8 (Final evals include Arabic numbers)
```
