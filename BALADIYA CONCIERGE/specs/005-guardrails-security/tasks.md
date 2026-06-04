# Tasks: Guardrails & Security

**Branch**: `005-guardrails-security` | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

---

## Phase 1: Setup

- [X] **T-001** `guardrails/Dockerfile` — python:3.11-slim + nemo-guardrails + presidio-analyzer + presidio-anonymizer; no torch
- [X] **T-002** `guardrails/rails/platform/config.yml` + `prompts.yml` — injection, jailbreak, cross-tenant, PII detection rails (hardcoded, not tenant-editable)
- [X] **T-003** `guardrails/main.py` — FastAPI `POST /validate`; validates `X-Service-Token` header → 401 if missing/invalid

---

## Phase 2: Foundational — Sidecar & Client

- [X] **T-010** `api/infra/guardrails_client.py` — async httpx client; Vault service token; `validate(message, tenant_rails)` → `GuardrailResponse`; raises `GuardrailUnavailable` on connection error
- [X] **T-011** `api/middleware/guardrails_middleware.py` — calls `guardrails_client.validate()`; on `GuardrailUnavailable` → return `503`; on `not allowed` → return refusal text; on allowed → pass through
- [X] **T-012** `api/middleware/redaction.py` — Presidio custom recognizers for Lebanese NID, phone formats, email, address; applied to message BEFORE structlog write and BEFORE Redis session write

---

## Phase 3: Platform Rails (US1)

- [X] **T-020** Implement NeMo injection rail: detect `ignore previous instructions`, system prompt extraction patterns
- [X] **T-021** Implement NeMo jailbreak rail: detect DAN, roleplay-as, hypothetical-override patterns
- [X] **T-022** Implement NeMo cross-tenant rail: detect requests for other tenants' data, `show all tenants`, `your system prompt`
- [X] **T-023** [P] Implement NeMo PII detect rail: flag Presidio-detected PII in input (complement to redaction middleware)

---

## Phase 4: Tenant Rails (US3)

- [X] **T-030** `guardrails/rails/tenant_overlay.py` — merge `tenant.settings.guardrail_config` (topics, tone, tools) into NeMo config at request time; platform rails are NOT in this overlay
- [X] **T-031** Streamlit admin: guardrail config page (allowed/blocked topics, custom refusal tone, enabled tools toggle)

---

## Phase 5: PII Redaction (US2)

- [X] **T-040** `tests/test_security/test_redaction.py` — paste fake Lebanese NID into simulated chat pipeline; assert zero unredacted occurrences in structlog output, Redis session dump, API response
- [X] **T-041** [P] `tests/test_security/test_pii_patterns.py` — unit tests for each Presidio custom recognizer pattern (NID, phone, email)

---

## Phase 6: Red-Team CI Gate (US1)

- [X] **T-050** Commit `evals/redteam_probes.json` — ≥ 12 probes with `{id, description, input, expected_outcome}`
- [X] **T-051** `tests/test_security/test_redteam.py` — load probes, send each to `POST /chat`, assert all refused; test fails if any probe succeeds
- [X] **T-052** CI gate: `redteam_pass_rate: 1.0` in `eval_thresholds.yaml`; gate blocks merge on failure
- [X] **T-053** [P] `tests/test_security/test_rail_separation.py` — tenant disables all tenant rails; verify platform rails still fire on injection probe
- [X] **T-054** [P] `tests/test_security/test_service_auth.py` — raw curl to `guardrails/validate` without token → 401; same for modelserver

---

## Dependencies & Execution Order

```
T-001 → T-002 → T-003
T-003 → T-010 → T-011 → T-012
T-012 → T-020 → T-021 → T-022 → T-023 [P]
T-011 → T-030 → T-031
T-012 → T-040 → T-041 [P]
T-022 → T-050 → T-051 → T-052
T-051 → T-053, T-054 [P]
```

**Gate**: Red-team gate: 0 failures. Redaction gate: 0 leaks. Service auth gate: 401 without token. Rail separation test passes.
