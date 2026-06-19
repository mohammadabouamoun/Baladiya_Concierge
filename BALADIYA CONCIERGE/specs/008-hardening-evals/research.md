# Research: Phase 8 — Hardening & Evals

**Date**: 2026-06-06

## 1. Arabic Name Regex — Best Approach for Lebanese Context

**Decision**: Unicode Arabic block range regex — `[؀-ۿ]{3,}(?:\s+[؀-ۿ]{3,})+`

**Rationale**: Arabic names in Lebanese civic messages appear as two or more consecutive Arabic-script words (given name + family name). The Unicode Arabic block (`U+0600`–`U+06FF`) covers all Arabic script including Lebanese dialect characters. A 3-character minimum per token excludes common prepositions and Arabic particles (لل، في، من — 2 chars) that appear in civic descriptions. Two-token minimum excludes single isolated Arabic words used as civic terms (مياه، كهرباء، طريق).

**Alternatives considered**:
- spaCy Arabic NER (`ar_core_news_sm`): accurate but adds ~500 MB to the container image (Constitution II violation) and requires GPU or slow CPU inference. Rejected.
- Static name list (top Lebanese surnames/given names): brittle, requires maintenance, misses transliteration variants. Rejected for primary pattern; acceptable as future enhancement.
- Presidio `SpacyRecognizer`: depends on spaCy NER — same rejection reason.

**False positive rate**: Acceptable. Short civic phrases (مياه الجنوب = "Southern Water") have 4+ chars per token but are 2-word institutional names, not personal names. The pattern may redact them. False negatives (missing a name) are unacceptable per PII policy; false positives (redacting a civic phrase) are acceptable (resident can rephrase).

---

## 2. Per-Widget JWT Key Rotation — Vault Pattern

**Decision**: Convention-based Vault paths (`baladiya/widget/{widget_id}/signing_key`); no DB column; LRU cache with 5-minute TTL in-process.

**Rationale**: Vault is already the secrets store (Phase 1). Adding a DB column for the key reference would create a second source of truth and require a migration. The `widget_id` is already in the JWT payload (`TokenClaims.widget_id`), so `decode_token` can derive the Vault path deterministically. LRU cache (max 128 entries, 300s TTL) avoids per-request Vault round-trips while keeping rotation latency < 5 minutes (old key remains cacheable for ≤300s after rotation — acceptable, as token TTL is 3600s).

**Alternatives considered**:
- Store key inline in `widgets.signing_key` (DB column): simpler lookup but key material in DB — violates defense-in-depth. Rejected.
- Store key as a Vault dynamic secret with auto-rotation: requires Vault PKI/database engine setup not in scope. Rejected.
- JWT revocation list in Redis: would allow instant invalidation but adds complexity and a new data dependency. Not needed — key rotation achieves the same effect at the cost of ≤300s cache window. Rejected.

**Decode flow** (two-pass JWT read):
1. `jwt.decode(token, options={"verify_signature": False})` — reads `widget_id` from payload without verifying.
2. If `widget_id` present: fetch `baladiya/widget/{widget_id}/signing_key` from Vault (LRU cached).
3. `jwt.decode(token, key, algorithms=[algorithm])` — full verification with the correct key.
4. If `widget_id` absent: fall through to existing `jwt_secret` path.

Security note: step 1 reads claims before verification. This is safe because the `widget_id` claim is only used to *select* the key for step 3 verification — no authorization decision is made on unverified claims.

---

## 3. Arabizi F1 Improvement — Data vs Architecture

**Decision**: Grow Arabizi cells to ≥100 examples per intent first; measure F1; if still below 0.90, document and set threshold to best measured value.

**Rationale**: Current Arabizi F1 = 0.8322 on 41 test rows. The EN:AR ratio is ~19:1 (12,103 EN vs 628 AR). TF-IDF char n-gram space is heavily English-weighted. Adding ~200 more Arabizi rows (49 per intent cell × 4 cells) brings the ratio to ~37:1 — still heavily EN-dominated. Gains are expected but 0.90 is not guaranteed without further balancing.

**Alternatives considered**:
- Per-language models (separate EN and AR classifiers): eliminates cross-language TF-IDF dilution, likely achieves higher AR F1. Increases complexity (two artifacts, two modelserver endpoints, language-detection routing). Deferred — too much architectural change for Phase 8.
- Class-weighted TF-IDF with upsampling of AR rows: could be tried in the notebook without changing the model architecture. Worth attempting as a secondary experiment if simple expansion doesn't reach 0.90.
- Separate Arabizi model: extreme — Arabizi has 4 intent classes and ~200 examples. Not enough data for a standalone classifier.

**Gate strategy**: Add `arabizi_f1` to `eval_thresholds.yaml` *after* measuring. If measured F1 ≥ 0.90, gate at 0.90. If below, gate at measured − 2pp (same safety margin convention) and document the gap in the model card.

---

## 4. Live Eval Prerequisites

**Decision**: Run evals against docker-compose stack locally; record results; update thresholds.

**Rationale**: No CI job currently runs the full live eval (requires live API + DB + Gemini API key). Running locally is the pragmatic path for Phase 8. Results are committed to `EVALS.md` and `eval_thresholds.yaml`; future CI can pick these up.

**Gemini quota constraint**: Free tier allows 20 calls/day for `gemini-2.5-flash`. The RAG eval (`evaluate_rag.py --mode compare`) uses Gemini for query rewrite (1 call per triple × 15 triples = 15 calls minimum). The agent eval may use Gemini for LLM calls. Run on separate days or use Groq fallback path for agent eval.

---

## 5. Defense Documentation — What's Missing

| Document | Current state | Required addition |
|---|---|---|
| `DECISIONS.md` | Has D1–D10, D-Widget-001 | Add §D-Arabic-001: bilingual retrain defense (Classical ML vs per-language-model, with measured Phase 7 F1 numbers) |
| `DATA.md` | Unknown — needs read | Add 12,731-row breakdown table, per-cell Arabizi counts, machine-seeded caveat |
| `modelserver/model_card.md` | Phase 2 numbers only (547 rows, 0.8983 macro-F1, SHA-256: `1ace7e...`) | Add Phase 7 row: 12,731 rows, macro-F1=0.9980, ar_macro_f1=0.9507, arabizi_f1=0.8322, SHA-256: `728a4b...` |
