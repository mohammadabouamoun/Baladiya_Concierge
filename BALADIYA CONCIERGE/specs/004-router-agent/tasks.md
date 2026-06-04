# Tasks: Router & Agent

**Branch**: `004-router-agent` | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

---

## Phase 1: Setup

- [X] **T-001** Alembic migration: `capture_requests` table with `tenant_id` RLS policy
- [X] **T-002** Alembic migration: `escalation_tickets` table with `tenant_id` RLS policy
- [X] **T-003** `api/domain/capture_request.py` — SQLAlchemy models + Pydantic schemas (`CaptureRequestCreate` with strict field validation)
- [X] **T-004** `api/domain/session.py` — `SessionMemory` Pydantic schema; `api/services/session_service.py` — `SessionService` (Redis get/set/expire with key `session:{session_id}:{tenant_id}`, TTL 1800s)

---

## Phase 2: Foundational — Repositories & LLM Client

- [X] **T-010** `api/repositories/capture_repo.py` — `CaptureRequestRepository` (BaseRepository, tenant-scoped)
- [X] **T-011** `api/repositories/escalation_repo.py` — `EscalationTicketRepository` (BaseRepository, tenant-scoped)
- [X] **T-012** `api/infra/llm_client.py` — async httpx client for hosted LLM API; API key from Vault; `tenacity` retry on transient errors

---

## Phase 3: Tools (US2)

- [X] **T-020** `api/services/tools/rag_search.py` — wraps `rag_service.rag_search()`; returns `ToolResult` or `ToolError`
- [X] **T-021** `api/services/tools/capture_request.py` — Pydantic validates payload; rate-limit check (Redis); `CaptureRequestRepository.create()`; `tenant_id` from session context ONLY (never payload)
- [X] **T-022** `api/services/tools/escalate.py` — `EscalationTicketRepository.create()`; links to `capture_request_id` if available
- [X] **T-023** Per-session `capture_request` rate limiter — implemented within T-021 (`tools/capture_request.py`); key pattern `capture_ratelimit:{session_id}:{tenant_id}`, window 60s, configurable `capture_requests_per_minute` in Settings

---

## Phase 4: Router & Agent (US1 + US2)

- [X] **T-030** `api/services/router_service.py` — classify via modelserver → confidence threshold check → route to workflow (spam/question/report/human) or agent
- [X] **T-031** `api/services/agent_service.py` — bounded tool-calling loop (`max_tool_calls`, `max_tokens_per_turn` from Settings); auto-escalate on cap exceeded; returns `ToolError` on any tool failure (never 500)
- [X] **T-032** `prompts/system_en.md` — English system prompt with `{{persona}}` placeholder injected at runtime
- [X] **T-033** `api/api/chat/router.py` — `POST /chat` endpoint; widget JWT required; calls guardrails passthrough stub → router → response (stub returns allowed=True always; full guardrails wired in phase 005)
- [X] **T-034** Log workflow-handled % vs agent-handled % per tenant via structlog (feeds cost attribution)

---

## Phase 5: Evals & CI Gate (US1 + US4)

- [X] **T-040** Hand-label 15 agent tool-selection examples → `evals/agent_tool_selection.json` (`{input, lang, expected_tool}`)
- [X] **T-041** `tests/test_agent/test_tool_selection.py` — evaluate agent on 15 examples; assert accuracy ≥ `eval_thresholds.yaml → agent_tool_accuracy`
- [X] **T-042** [P] `tests/test_agent/test_capture_injection.py` — inject fabricated `tenant_id` in tool payload → verify write uses JWT tenant_id
- [X] **T-043** [P] `tests/test_agent/test_session_scoping.py` — Tenant A session cannot bleed into Tenant B request
- [X] **T-044** [P] `tests/test_agent/test_rate_limit.py` — exceed per-session capture limit → 429, no write

---

## Phase 6: Streamlit Admin Views

- [X] **T-050** Streamlit page: `capture_requests` list (status, intent, created_at, description) for tenant admin
- [X] **T-051** Streamlit page: `escalation_tickets` list (status, reason, created_at) for tenant admin

---

## Dependencies & Execution Order

```
T-001 → T-002 → T-003 → T-004
T-004 → T-010 → T-011 → T-012
T-012 → T-020 → T-021 → T-022 → T-023
T-023 → T-030 → T-031 → T-032 → T-033 → T-034
T-033 → T-040 → T-041, T-042, T-043, T-044 [P]
T-041 → update eval_thresholds.yaml
T-034 → T-050 → T-051
```

**Gate**: Agent tool-selection CI gate passes; injection probe refused; session scoping test passes; ≥ 60% turns workflow-handled on eval set.
