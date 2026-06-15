# Research: Phase 9 — Arabizi Uplift, Live Evals & Defense Readiness

**Date**: 2026-06-07 | **Plan**: [plan.md](plan.md)

## R-001 — Arabizi Augmentation Strategy

**Decision**: Author new Arabizi rows manually following the existing `add(text, "ar", "arabizi", intent, category)` pattern in `build_dataset.md`. No template expansion.

**Rationale**: The existing Arabizi rows use realistic Lebanese chat idioms with numeral substitution (2=ء/ق, 3=ع, 5=خ, 6=ط, 7=ح, 8=غ, 9=ص). Template generation would produce repeated token patterns that TF-IDF char n-grams would memorise rather than generalise from. Hand-authored variety is the same approach used for the initial Phase 7 MSA and Lebanese expansion, which achieved F1 = 1.0000 for those varieties.

**Alternatives considered**:
- Back-translation (MSA → Lebanese → Arabizi): rejected — introduces translation artefacts and requires a reliable Arabic NLP pipeline not available in the project venv.
- Synonym substitution on existing rows: rejected — produces surface variety but not semantic variety; char n-grams would still memorise the substitution pattern.
- Crowdsourcing: out of scope for this phase.

**How to apply**: Need 49 new rows per intent cell (report: 49, question: 49, human: 49, spam: 48 to reach 100 each). Cover all civic categories represented in existing rows. Vary urgency markers, category mix, and sentence structure.

---

## R-002 — Real EN Data Mining from NYC 311

**Decision**: Mine `report` intent rows from `Descriptor` column of `/tmp/311_data/nyc_311_2025.csv`; manually curate `question`, `human`, and `spam` rows.

**Rationale**:
- 311 service requests are by definition civic reports — direct mapping to `report` intent.
- The dataset has no question-format entries (service requests are statements, not questions) — `question` must be curated manually.
- `human` (escalation requests) and `spam` do not appear in 311 data — must be curated manually.

**Mining procedure**:
1. Filter rows where `Agency` is a relevant city service (DSNY, DEP, DOT, DOB, DPR, etc.)
2. Extract `Descriptor` column; strip addresses (remove anything matching `\d+ [A-Z].+(?:ST|AVE|BLVD|RD|DR|LN|CT)` and NYC-specific PII patterns)
3. Pre-screen with existing classifier: keep rows where `intent == "report"` AND `confidence ≥ 0.70`
4. Sample at most ≥200 rows per `report` cell; deduplicate by Jaccard similarity (discard if Jaccard > 0.8 with existing dataset rows)

**Alternatives considered**:
- Using the enron_spam Kaggle dataset for spam rows: rejected — the enron dataset is email spam, not chat/civic spam; style is too different from the target domain.
- Using CommonCrawl civic queries for `question` intent: out of scope.

---

## R-003 — Live Eval Stack Minimum Requirements

**Decision**: Bring up the following docker compose services for Phase 9 eval runs:
- `db`, `redis`, `vault`, `api`, `modelserver` — required for agent eval (tool calls need DB + session)
- `guardrails` — required if testing the full chat path through `POST /chat`
- `host`, `widget` — not required for eval scripts (evals call API directly)

**Rationale**: `evaluate_rag.py` calls the `/rag/search` endpoint directly (not via the chat path), so guardrails are not required for the RAG eval. `evaluate_agent.py` dispatches tool calls; it needs `db` for `capture_request` writes and `redis` for session, but does not need the widget or host containers.

**Gemini rate limit workaround**: The `evaluate_agent.py` script makes one Gemini call per golden example (15 examples = 15 calls). The Gemini free-tier limit is 20 calls/day for `gemini-2.5-flash`. If any calls fail with 429, the script should catch and route to Groq fallback automatically (the existing `_GeminiFailureTracker` handles this after 3 failures). No code change needed — just run with `GROQ_API_KEY` configured in `.env`.

For RAG eval, `evaluate_rag.py --mode compare` makes embedding calls (Gemini embedding API, separate quota) and optionally LLM-judge calls for faithfulness. The embedding quota is more generous. If LLM-judge calls are rate-limited, run with `--no-llm-judge` flag to skip faithfulness LLM scoring and use the keyword-overlap proxy instead.

**Alternatives considered**:
- Running evals against a mock/stub stack: rejected — pre-measurement placeholder thresholds already in place; the only reason for live eval is to replace them with real numbers. A mock eval would just reproduce the placeholder.

---

## R-004 — Arabizi CI Gate Threshold Setting

**Decision**: Set `arabizi_f1: 0.88` in `eval_thresholds.yaml` (not 0.90).

**Rationale**: The project convention is to set CI gates at `measured − 2pp` to absorb run-to-run variance from dataset split randomness and minor sklearn non-determinism. If Arabizi macro-F1 is measured at 0.90, the gate is 0.88. If it comes in at 0.91, the gate would be 0.89 — still set at target minus buffer. The spec targets ≥ 0.90; the gate is the enforcement floor, not the target.

**How to apply**: After retraining, read the `arabizi_f1` value from `evals/classifier_bilingual_results.json`. If ≥ 0.90: set gate to `measured − 2pp`. If between 0.88 and 0.90: set gate to 0.88 (the minimum acceptable floor). If below 0.88: do not commit; investigate data quality and retrain.

---

## R-005 — Hand-Verification Scope

**Decision**: Review all 628 Arabic rows in `build_dataset.md` (MSA: ~160, Lebanese: ~161, Arabizi: ~205 + new rows added this phase). Mark any correction in `modelserver/model_card.md §Data Corrections` as a table row with columns: `| Row text (first 40 chars) | Original label | Corrected label | Correction type | Rationale |`.

**Correction types**:
- `intent_label` — wrong intent (e.g., a question labelled as report)
- `variety_label` — wrong variety (e.g., MSA labelled as Lebanese)
- `phrasing` — grammatically unnatural or code-switched in a way that distorts the variety label
- `no_change` — reviewed and confirmed correct

**How to apply**: Focus on cells flagged in Phase 7 as "machine-seeded": all Arabizi rows (lines ~283–338 in `build_dataset.md`) and the ARABIC EXPANSION section (lines ~340–860). Original MSA/Lebanese seed rows (~lines 158–282) were more carefully authored and are lower-risk.
