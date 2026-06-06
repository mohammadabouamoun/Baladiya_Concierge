# Data Model: Phase 8 — Hardening & Evals

**Date**: 2026-06-06

## Changes Summary

Phase 8 introduces **no new database tables**. All changes are to: (a) Vault key storage conventions, (b) in-memory regex recognizer list, (c) classifier artifact and training data.

---

## 1. Widget Signing Key (Vault — per-widget)

**Not a DB entity.** Key material lives entirely in Vault.

| Field | Value |
|---|---|
| Vault path | `baladiya/widget/{widget_id}/signing_key` |
| Type | Random 32-byte hex string (256 bits) |
| Scope | One entry per widget UUID |
| Set at | Widget creation (seed script) or explicit rotation |
| Rotation | `POST /admin/widgets/{widget_id}/rotate-key` writes a new random key to the same path |
| Cache | LRU, max 128 entries, TTL 300s in API process (per `decode_token`) |
| Fallback | None — if Vault is unreachable, token validation fails (fail-closed) |

**`widgets` table**: unchanged. No new columns. The `id` column (widget UUID) is the Vault path key.

**Migration note**: `scripts/seed.py` extended — at startup, for each active `widgets` row, if `baladiya/widget/{widget_id}/signing_key` is absent in Vault, write the global `widget_signing_key` value as the initial per-widget key. This makes the migration zero-downtime: existing tokens issued with `jwt_secret` will fail validation (they have no `widget_id` claim), but new tokens issued after migration will validate against the per-widget key.

---

## 2. Arabic Name Pattern (In-Memory — `redaction.py`)

**Not a DB entity.** Added to the `_RECOGNIZERS` list in `api/middleware/redaction.py`.

| Field | Value |
|---|---|
| Entity type | `ARABIC_NAME` |
| Pattern | `[؀-ۿ]{3,}(?:\s+[؀-ۿ]{3,})+` |
| Replacement | `[NAME]` |
| Ordering | Appended last (after phone, NID, email, address patterns — no ordering conflict) |
| Scope | Applies to all messages, all tenants, all languages (pattern only matches Arabic script) |
| False positive policy | Acceptable — prefer false positives over false negatives for PII |

---

## 3. Arabizi Training Examples (Dataset)

**Not a DB entity.** Rows in `build_dataset.md` and `civic_intent_dataset.csv`.

| Field | Value |
|---|---|
| Schema | Same as existing: `id | text | lang | variety | intent | category | split` |
| New rows | ~196 new Arabizi rows (49 per intent cell × 4 cells: report, question, human, spam) |
| `variety` | `arabizi` |
| `lang` | `ar` |
| Target per-cell count | ≥100 (up from 51–52) |
| Verification status | Machine-seeded (must be hand-verified before citing F1 as reliable) |
| Split | Deterministic `sha1(text) % 5 == 0 → test` (~20%) |

---

## 4. Classifier Artifact (Updated)

**Not a DB entity.** File at `modelserver/artifacts/classifier.joblib`.

| Field | Phase 2 | Phase 7 | Phase 8 (target) |
|---|---|---|---|
| Training rows | 547 | 12,731 | ~12,927 (+196 Arabizi) |
| Macro-F1 | 0.8983 | 0.9980 | ≥ 0.9980 (held) |
| Arabizi F1 | 0.50 | 0.8322 | ≥ 0.90 (target) |
| SHA-256 | `1ace7e...` | `728a4b...` | TBD after retrain |

---

## 5. `decode_token` Logic Change (Behavioral — not a new entity)

`api/core/security.py` — `decode_token()` updated to support per-widget key selection:

```
Input: raw JWT string
Step 1: jwt.decode(token, verify_signature=False) → read claims (unverified)
Step 2: if "widget_id" in claims:
           key = vault.get_widget_signing_key(claims["widget_id"])  ← Vault LRU cache
        else:
           key = settings.jwt_secret
Step 3: jwt.decode(token, key, algorithms=[settings.jwt_algorithm]) → verified claims
Step 4: return TokenClaims(**verified_claims)
```

**Backward compatibility**: Tokens without a `widget_id` claim (admin, tenant admin, platform manager) continue to use `jwt_secret`. No change to existing auth flow.

---

## 6. Eval Threshold State (after Phase 8)

| Threshold | Before Phase 8 | After Phase 8 |
|---|---|---|
| `arabizi_f1` | not gated | measured value (gate if ≥ 0.90) |
| `rag_hit_at_5` | 0.73 (pre-measurement) | measured − 2pp |
| `rag_mrr` | 0.60 (pre-measurement) | measured − 2pp |
| `rag_faithfulness` | 0.60 (pre-measurement) | measured − 2pp |
| `agent_tool_accuracy` | 0.80 (pre-measurement) | measured − 2pp |
| `workflow_handled_rate` | 0.60 (pre-measurement) | measured − 2pp |
