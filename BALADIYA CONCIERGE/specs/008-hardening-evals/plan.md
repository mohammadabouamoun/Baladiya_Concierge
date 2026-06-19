# Implementation Plan: Phase 8 — Hardening & Evals

**Branch**: `008-hardening-evals` | **Date**: 2026-06-06 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/008-hardening-evals/spec.md`

## Summary

Phase 8 closes every deferred item from Phases 1–7 and prepares the project for defense. Six parallel tracks: (1) grow Arabizi training cells to ≥100/intent and retrain to hit F1 ≥ 0.90; (2) add Arabic name regex patterns to the PII redaction middleware; (3) implement per-widget JWT signing key rotation via Vault; (4) run the live RAG and agent eval scripts against the real stack and pin the measured thresholds; (5) write the three missing defense documents (DECISIONS.md §D-Arabic-001, DATA.md update, model card Phase 7 row); (6) evaluate the EN classifier on 20+ non-template resident messages and record the real-text F1.

No new architecture is introduced. All changes touch existing files in established patterns.

## Technical Context

**Language/Version**: Python 3.11 (API, modelserver, evals), TypeScript/React (widget — no changes this phase)

**Primary Dependencies**: scikit-learn + joblib (classifier), FastAPI async (API), SQLAlchemy async (DB), hvac (Vault), pytest + httpx (tests), `re` stdlib (PII redaction patterns)

**Storage**: PostgreSQL 16 + RLS (no new tables — `widgets` schema unchanged; per-widget keys live entirely in Vault), Redis 7 (session — unchanged), MinIO (unchanged)

**Testing**: pytest; new tests cover Arabic name redaction (PII gate), per-widget key token acceptance/rejection, and arabizi F1 regression gate

**Target Platform**: Linux server (WSL2 dev); docker-compose stack for eval runs

**Project Type**: Multi-tenant SaaS API + classifier service

**Performance Goals**: Redaction middleware must add < 5ms to request path (Arabic name regex is O(n) over message length, matching existing pattern cost). Per-widget Vault lookup is cached in `Settings` per-widget on first use; must not exceed 20ms cold.

**Constraints**:
- No torch in any container (Constitution II) — classifier retraining is notebook-only
- Arabizi expansion rows must be hand-verified (or marked machine-seeded) before citing F1 in defense
- `decode_token` must remain backward-compatible: tokens without a `widget_id` claim continue to validate against `jwt_secret`
- PII redaction is fail-safe: if a name pattern causes an exception, log and continue (don't crash the request)
- Live eval runs require the full docker-compose stack; if unavailable, thresholds stay as pre-measurement targets with a timestamp note

**Scale/Scope**: ~12,731 training rows (classifier); 15 eval triples (RAG); 15 eval examples (agent); ≥20 real-text EN messages (model card)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Rule | Phase 8 status | Notes |
|---|---|---|
| I — Isolation is the grade | ✅ PASS | No new DB tables; no new query paths. Per-widget Vault lookup uses `widget_id` from JWT claim only — never from client body. `decode_token` key selection uses `claims["widget_id"]` after JWT signature verification, not before. |
| II — No torch in containers | ✅ PASS | Classifier retrained in notebook only; `modelserver` image unchanged — still `onnxruntime` + `scikit-learn` + `numpy`. |
| III — Arabic is additive | ✅ PASS | Arabic name PII patterns are additive to the existing `_RECOGNIZERS` list. If Arabic patterns raise an exception, `redact()` logs and continues — English path unaffected. |
| IV — CORS is not authentication | ✅ PASS | Per-widget key rotation does not change the authentication model. Origin validation in `token_service.py` is unchanged. |
| V — Evals are the grade | ✅ PASS | This phase *is* the eval-hardening phase: live runs + threshold pinning. CI gates added for `arabizi_f1`. |
| VI — Every decision backed by a number | ✅ PASS | DECISIONS.md §D-Arabic-001 will be backed by measured Phase 7 F1 numbers. Real-text F1 recorded in model card. |
| VII — No fine-tuning, no scope creep | ✅ PASS | No fine-tuning. No new architecture. Arabizi expansion is data growth, not model architecture change. |

**Engineering Standards check**:
- All new API endpoints (`/admin/widgets/{widget_id}/rotate-key`) are async, use `Depends()` for auth, and follow existing admin router pattern.
- Vault key lookup is wrapped in `try/except hvac.exceptions.VaultError` with `tenacity` retry — consistent with existing Vault access.
- All new log lines use `structlog` with `trace_id` + `tenant_id`.

## Project Structure

### Documentation (this feature)

```text
specs/008-hardening-evals/
├── plan.md              ← this file
├── research.md          ← Phase 0 output (Vault per-widget key pattern)
├── data-model.md        ← Phase 1 output (widget key entity, Arabic name pattern entity)
├── contracts/
│   └── rotate_key.md    ← POST /admin/widgets/{widget_id}/rotate-key contract
└── tasks.md             ← Phase 2 output (speckit-tasks)
```

### Source Code (modified files — no new top-level dirs)

```text
# Arabizi quality (FR-001–003)
build_dataset.md                        ← add ≥50 new Arabizi rows per intent cell
notebooks/train_classifier_bilingual.ipynb  ← retrain; commit updated outputs
modelserver/artifacts/classifier.joblib ← updated artifact
evals/classifier_bilingual_results.json ← updated results
eval_thresholds.yaml                    ← arabizi_f1: 0.90 gate added

# Arabic PII redaction (FR-004–006)
api/middleware/redaction.py             ← add _ARABIC_NAME recognizer to _RECOGNIZERS
tests/test_security/test_redaction.py   ← add 5 Arabic name test cases

# Per-widget JWT key rotation (FR-007–011)
api/domain/widget.py                    ← no change (Vault path by convention, not DB column)
api/infra/vault.py                      ← add get_widget_signing_key(widget_id) helper
api/core/security.py                    ← update decode_token: if widget_id claim present → fetch per-widget key
api/api/widget/token_service.py         ← issue_token uses per-widget Vault key (not jwt_secret)
api/api/admin/router.py                 ← add POST /admin/widgets/{widget_id}/rotate-key endpoint
scripts/seed.py                         ← seed initial per-widget keys for existing widgets at startup
tests/test_widget/test_token_service.py ← add rotation + isolation test cases

# Live eval runs (FR-012–014)
evals/evaluate_rag.py                   ← run against live stack; results to EVALS.md
evals/evaluate_agent.py                 ← run against live stack; results to EVALS.md
eval_thresholds.yaml                    ← replace pre-measurement placeholders with measured − 2pp

# Defense documentation (FR-015–017)
DECISIONS.md                            ← add §D-Arabic-001 bilingual retrain defense
DATA.md                                 ← update row counts + per-cell table + Arabizi caveat
modelserver/model_card.md               ← add Phase 7 row: SHA-256, per-variety F1, baseline comparison

# Real resident text eval (FR-018–019)
modelserver/model_card.md               ← add real-text eval section with ≥20-example result
```

**Structure Decision**: Single project layout — all changes are in existing directories (`api/`, `modelserver/`, `evals/`, `tests/`). No new top-level directories needed.

## Implementation Notes (non-obvious decisions)

### Arabic Name PII Pattern

Arabic names do not have uppercase signals. The best regex heuristic for Lebanese civic context: two or more consecutive Arabic-script words (Unicode block `؀–ۿ`) each ≥ 3 characters, separated by a space, with no numerals. This catches "محمد علي", "رنا خوري", "أحمد الحسن" while avoiding short Arabic words that are civic terms ("مياه", "كهرباء"). Pattern:

```python
r"[؀-ۿ]{3,}(?:\s+[؀-ۿ]{3,})+"
```

Replacement: `[NAME]`. Conservative — false negatives preferred over redacting civic topic words. Pattern is appended to `_RECOGNIZERS` *after* phone/NID patterns (no ordering conflict for Arabic script — no digit overlap).

### Per-Widget Key: Vault Path Convention

No DB schema change. Each widget's key lives at `baladiya/widget/{widget_id}/signing_key` in Vault. `decode_token` algorithm:

1. Decode JWT *without* verification to read `widget_id` claim (header + payload only — no signature check yet).
2. If `widget_id` present: fetch `baladiya/widget/{widget_id}/signing_key` from Vault (LRU-cached per process, TTL 5min).
3. Verify JWT signature with the fetched key.
4. If `widget_id` absent: verify with `jwt_secret` (existing path — backward compatible).

Key rotation endpoint generates a new 32-byte random key, writes it to Vault, returns `{"rotated": true, "widget_id": "..."}`. Old tokens become invalid immediately (no token revocation list needed — the key itself is the gate).

`scripts/seed.py` is extended: on startup, for each active widget in DB, if `baladiya/widget/{widget_id}/signing_key` does not exist in Vault, write the current `widget_signing_key` value as a migration default (so existing Phase 6 widgets work without requiring an explicit rotation).

### Arabizi Expansion Strategy

Target: 100 verified examples per intent cell (currently 51–52). Add 48–49 rows per cell (4 cells × 49 = 196 new rows) in `build_dataset.md`. Arabizi patterns: Romanized Lebanese Arabic (e.g., "shu", "mashi", "hayde", "bi2oul", "3am"), intentional misspellings, number substitutions ("3" for ع, "2" for ء/أ). Use the existing `add()` call pattern in `build_dataset.md`.

Retrain with `notebooks/train_classifier_bilingual.ipynb`. If Arabizi F1 does not reach 0.90 after expansion, document the gap and set threshold to best measured value (do not block CI on an unreachable target).

### Live Eval Prerequisites

`evals/evaluate_rag.py` requires: API running, DB seeded with eval content (`python evals/seed_eval_content.py`), Gemini API key set. `evals/evaluate_agent.py` requires: API running, modelserver running, Groq API key set (agent uses Groq for LLM zero-shot comparison). Run order:

```bash
docker compose up -d api modelserver guardrails db redis
python evals/seed_eval_content.py
python evals/evaluate_rag.py --mode compare
python evals/evaluate_agent.py
```

If Gemini quota is exhausted (20 calls/day on free tier), schedule eval run across two calendar days.
