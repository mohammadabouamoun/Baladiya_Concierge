# Implementation Plan: Guardrails & Security

**Branch**: `005-guardrails-security` | **Date**: 2026-06-02 | **Spec**: [spec.md](./spec.md)

## Summary

Deploy NeMo Guardrails as a separate sidecar service called by the API over HTTP with a Vault service credential. Implement PII redaction middleware, two-layer rail architecture (platform locked + tenant configurable), and wire the CI red-team gate.

## Technical Context

**Language/Version**: Python 3.11 (sidecar + api middleware)

**Primary Dependencies**: nemo-guardrails, presidio-analyzer, presidio-anonymizer (for PII); fastapi, httpx

**Storage**: NeMo rail configs stored in the `guardrails` container filesystem; tenant rail overrides loaded from `tenant.settings.guardrail_config`

**Testing**: pytest; guardrails sidecar called via httpx in integration tests; red-team probes from `evals/redteam_probes.json`

**Target Platform**: `guardrails` Docker service (sidecar); PII middleware in `api` service

**Performance Goals**: Guardrail validation adds < 100ms overhead p95; fail-closed on sidecar unreachable

**Constraints**: Platform rails are hardcoded in sidecar config — not in DB, not tenant-configurable; sidecar requires `X-Service-Token` on every call; any sidecar outage → `api` returns 503 (never processes message unguarded)

## Constitution Check

- [x] Platform rails mandatory, identical for all tenants, not configurable via tenant settings
- [x] Sidecar fails closed — unreachable = 503, not passthrough
- [x] Service-to-service auth via Vault token (not "internal network" trust)
- [x] PII redaction before logging, before Redis write, before trace export
- [x] Red-team gate in CI — 100% probes must be refused

## Project Structure

```text
guardrails/
├── Dockerfile                  ← python:3.11-slim + nemo-guardrails + presidio
├── requirements.txt
├── main.py                     ← FastAPI: POST /validate + X-Service-Token auth
├── rails/
│   ├── platform/               ← locked rails: injection, jailbreak, cross-tenant, PII detect
│   │   ├── config.yml
│   │   └── prompts.yml
│   └── tenant_overlay.py       ← merge tenant rail config into NeMo at request time

api/
├── middleware/
│   └── redaction.py            ← Presidio-based PII redaction; applied before logging + Redis write
├── infra/
│   └── guardrails_client.py    ← httpx AsyncClient; Vault service token; fail-closed on 503

evals/
└── redteam_probes.json         ← ≥ 12 probes: injection x5, system-prompt x3, cross-tenant x2, jailbreak x2
```

## Two-Layer Rail Architecture

```
inbound message
  ↓
guardrails_client.validate(message, tenant_rails)
  ↓ (HTTP POST to guardrails sidecar)
  NeMo platform rails (HARDCODED — always on):
    - input_injection_rail: detect prompt injection patterns
    - jailbreak_rail: detect jailbreak attempts
    - cross_tenant_rail: detect requests for other tenants' data / system prompt
    - pii_detect_rail: flag PII in input (presidio)
  +
  NeMo tenant overlay (from tenant.settings.guardrail_config):
    - topic_rail: allowed/blocked topics
    - tone_rail: custom refusal wording
    - tool_rail: enabled tools filter
  ↓
GuardrailResponse { allowed, modified_message, triggered_rail, refusal_text }
  ↓ (back in api middleware)
  if not allowed → return refusal_text to resident (skip router/agent entirely)
  if allowed → strip any detected PII from message → log redacted → pass to router
```

## PII Redaction Patterns (Lebanese civic context)

| Pattern | Replacement |
|---|---|
| Lebanese national ID (6-digit numeric) | `[REDACTED_NID]` |
| Lebanese mobile `+961 X XXX XXXX`, `07X XXX XXX`, `03X XXX XXX` | `[REDACTED_PHONE]` |
| Email address | `[REDACTED_EMAIL]` |
| Exact address with building number adjacent to proper noun | `[REDACTED_ADDRESS]` |

Applied via Presidio custom recognizers on every message BEFORE structlog write and BEFORE Redis session write.
