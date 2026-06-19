# Implementation Plan: Phase 9 — Live Evals & Defense Readiness

**Branch**: `009-arabizi-liveeval` | **Date**: 2026-06-07 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/009-arabizi-liveeval/spec.md`

## Summary

Phase 9 closes all remaining open items before defense. Data expansion is deferred — Arabizi F1 = 0.8322 is accepted as-is. Three tracks:

1. **Hand-verify** — review all Arabic rows in `build_dataset.md` for correct labels and natural phrasing; log sign-off in `modelserver/model_card.md §Data Corrections`.
2. **Live evals** — bring up the docker compose stack; run `evaluate_rag.py --mode compare` and `evaluate_agent.py` against the real stack; replace pre-measurement placeholders in `eval_thresholds.yaml` and fill `EVALS.md §3–4`.
3. **Manual QA** — document and run SC-002 3G latency test; run SC-004 RTL checklist; record results in `EVALS.md §8`.

No new code is introduced. No retraining. All changes are to threshold files, evaluation results, and documentation.

## Technical Context

**Language/Version**: Python 3.11 (dataset scripts, eval scripts, modelserver), TypeScript/React (widget — no changes this phase)

**Primary Dependencies**: pytest (CI gate), docker compose (live eval stack), httpx (eval scripts calling live API)

**Storage**: `evals/*.json` (eval results written by eval scripts); no DB schema changes; no CSV rebuild

**Testing**: pytest + `eval_thresholds.yaml` for CI gates; manual Chrome DevTools for SC-002; manual visual inspection for SC-004 RTL

**Target Platform**: docker-compose stack (PostgreSQL 16, Redis 7, FastAPI, modelserver, guardrails, Vault, MinIO) for live eval runs; widget dev server (port 5173) + FastAPI (port 8000) for manual QA

**Project Type**: Multi-tenant civic SaaS (data expansion + evaluation phase only)

**Performance Goals**:
- First-message round-trip P50 ≤ 3 s under Slow 3G (SC-002, manual)
- All Arabic training rows reviewed and signed off (SC-001)

**Constraints**:
- No classifier retraining this phase — Arabizi F1 = 0.8322 accepted as-is
- Gemini free tier is 20 calls/day for `gemini-2.5-flash` — live eval runs must use Groq fallback for batch queries
- Manual SC-002 and SC-004 require Chrome and a running widget dev server — cannot be automated
- RAG thresholds set to `measured − 2pp`; agent threshold set to measured value (or `measured − 5pp` if variance is high)

**Scale/Scope**:
- RAG eval: 15 golden triples
- Agent eval: 15 golden examples
- Arabic rows to review: ~628 (MSA ~160, Lebanese ~161, Arabizi ~205 + expansion rows)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Rule | Phase 9 Status | Notes |
|---|---|---|
| I — Isolation is the grade | ✅ PASS | No new DB queries or API routes. No tenant data touched. Live eval seeding via `seed_eval_content.py` operates under Tenant Admin credentials, scoped to the test tenant. |
| II — No torch in containers | ✅ PASS | Classifier retrained in Jupyter notebook only. `modelserver` image unchanged. No new Python packages added to any Dockerfile. |
| III — Arabic is additive | ✅ PASS | Adding Arabizi rows is purely additive to the dataset. If Arabizi F1 regresses existing AR gates, the data is fixed, not the threshold. English paths are unaffected. |
| IV — CORS is not authentication | ✅ PASS | No widget auth changes in this phase. |
| V — Evals are the grade | ✅ PASS | This phase is entirely eval-focused: gating Arabizi F1, replacing pre-measurement RAG/agent placeholders with real numbers, and recording widget manual gates. |
| VI — Every decision backed by a number | ✅ PASS | All new thresholds are set to `measured − 2pp`. Model card updated with the new real-text eval sample size (≥800) and measured F1. Arabic row corrections logged with rationale. |
| VII — No fine-tuning, no scope creep | ✅ PASS | Data expansion only (classical TF-IDF + LogReg — same model architecture). No new features. No new architecture. |

**Engineering standards check**: No new async routes, no new Vault paths, no new structlog lines — not applicable for a pure data/eval phase.

## Project Structure

### Documentation (this feature)

```text
specs/009-arabizi-liveeval/
├── plan.md              ← this file
├── research.md          ← Phase 0 output (NYC 311 mining approach, Arabizi augmentation strategy)
├── data-model.md        ← Phase 1 output (dataset entity changes, eval result schemas)
├── contracts/
│   └── eval_results_schema.md  ← classifier_bilingual_results.json + real_text_en_sample.json schemas
└── tasks.md             ← Phase 2 output (speckit-tasks)
```

### Source Files Modified (no new top-level dirs)

```text
# Track 1 — Hand-verify Arabic rows (FR-001)
build_dataset.md                        ← correct any mislabelled/unnatural Arabic rows found during review
modelserver/model_card.md               ← §Data Corrections: table of corrections + dated sign-off line

# Track 2 — Live eval runs (FR-002–005)
evals/evaluate_rag.py                   ← run: docker compose up && python evals/seed_eval_content.py
                                                  && python evals/evaluate_rag.py --mode compare
evals/evaluate_agent.py                 ← run with live stack + GROQ_API_KEY; record per-example predictions
eval_thresholds.yaml                    ← replace pre-measurement placeholders:
                                            rag_hit_at_5: <measured − 2pp>
                                            rag_mrr: <measured − 2pp>
                                            rag_faithfulness: <measured − 2pp>
                                            rag_answer_relevancy: <measured>   (reported only, not gated)
                                            agent_tool_accuracy: <measured or measured − 5pp>

# Track 3 — EVALS.md fill-in (FR-003, FR-005, FR-006, FR-007)
EVALS.md                                ← §3 (RAG): fill TBD metric rows with real values + measurement date
                                        ← §4 (agent): fill per-example rows with predicted tools + pass/fail
                                        ← §8 SC-002: add procedure doc + measurement table (P50/P95/verdict, ≥5 runs)
                                        ← §8 SC-004: mark all 10 RTL checklist items pass/fail + date stamp

# HANDOFF.md update
HANDOFF.md                              ← update phase status to Phase 9 complete; update CI gate table
```

## Complexity Tracking

No constitution violations. Phase 9 adds no new architecture and no new data — it is a pure evaluation closeout and documentation phase.

---

## Phase 0: Research

**Research question 1 — Arabizi augmentation strategy**

The existing 51–52 Arabizi rows per intent cell use a mix of realistic Lebanese chat idioms with numeral substitutions (2=ء, 3=ع, etc.). Adding 49 more per cell requires:
- Staying within the same numeral substitution conventions
- Covering the same civic categories already represented (roads, water, electricity, waste, environment, permits, taxes, general)
- Avoiding synthetic-sounding duplication — varied vocabulary, varying category, varying urgency level

Decision: author new rows manually following the same `add(text, "ar", "arabizi", intent, category)` pattern. No template expansion — Arabizi templates would produce the same token patterns and defeat the purpose of variety expansion.

**Research question 2 — NYC 311 real EN mining**

The NYC 311 Kaggle dataset (`/tmp/311_data/nyc_311_2025.csv`) contains service request descriptions. Mapping strategy:
- `report` ← complaint descriptions (column: `Descriptor`) where `Agency` is relevant city service
- `question` ← cannot be reliably mined from 311 data (no question column); use manual curation for this intent
- `human` ← cannot be reliably mined; manually curated variants of "please connect me to a person / I need to speak to someone"
- `spam` ← cannot be mined from 311 data (civic service requests are by definition not spam); manually curate new spam variants

Preprocessing: strip addresses/PII before adding to dataset; apply a pre-screening pass using the existing classifier (confidence ≥ 0.70 for `report`) to filter noise.

**Research question 3 — Live eval run dependencies**

Minimum services required:
- `api` + `db` + `redis` + `vault` + `modelserver` — for agent eval
- All of the above + `guardrails` — for full chat path
- `embed` service is not a separate container; embedding calls go to Gemini API directly

Workaround for Gemini free tier during batch eval: set `GROQ_FALLBACK_FORCE=true` environment variable (or temporarily lower `_GeminiFailureTracker` threshold to 0) so all LLM eval calls route to Groq llama-3.3-70b — which has a generous free tier.

---

## Phase 1: Design & Contracts

### Data Model

See [`data-model.md`](data-model.md) for the full entity descriptions.

Key entities and their state after Phase 9:

| Entity | Current State | After Phase 9 |
|---|---|---|
| `build_dataset.md` Arabizi section | 51/51/51/52 rows per intent | 100/100/100/100 rows per intent |
| `civic_intent_dataset.csv` | 12,731 rows (10,206 train / 2,525 test) | ~13,731+ rows |
| `modelserver/artifacts/classifier.joblib` | Phase 7 artifact (SHA: `728a4bf1…`) | Phase 9 artifact (new SHA) |
| `evals/classifier_bilingual_results.json` | Phase 7 results (Arabizi F1=0.8322) | Phase 9 results (Arabizi F1 ≥ 0.88) |
| `evals/real_text_en_sample.json` | 25 records, macro-F1=0.8420 | ≥200 records, updated macro-F1 |
| `eval_thresholds.yaml` | No `arabizi_f1` gate; RAG/agent placeholders | `arabizi_f1: 0.88`; RAG/agent = measured − 2pp |
| `EVALS.md §3` | TBD rows | Filled with real values + measurement date |
| `EVALS.md §4` | TBD per-example rows | Filled with predicted tools + pass/fail |
| `EVALS.md §8 SC-002` | "⚠️ TBD" | ≥5 Slow 3G measurements, P50/P95, verdict |
| `EVALS.md §8 SC-004` | Checklist defined, not run | All 10 items marked pass/fail + date |
| `modelserver/model_card.md` | Phase 8 real-text eval (n=25); "machine-seeded" caveat open | n≥200 real-text eval; §Data Corrections signed off |

### Contracts

See [`contracts/eval_results_schema.md`](contracts/eval_results_schema.md).

- `classifier_bilingual_results.json` — unchanged schema; `arabizi_f1` key already present
- `real_text_en_sample.json` — each record: `{id, text, true_intent, predicted_intent, confidence, correct}`; expands from 25 → ≥200 records

### Rebuild Workflow (canonical order — must not be changed)

```bash
# Step 1: rebuild hand-crafted rows (overwrites CSV from scratch)
python3 build_dataset.md

# Step 2: append ~12K EN template rows
python3 dataset_english_large.md

# Step 3: append real EN + NYC 311 rows
python3 dataset_english.md

# Step 4: retrain bilingual notebook
# Run notebooks/train_classifier_bilingual.ipynb in Jupyter
# Commit outputs

# Step 5: run real-text eval
python3 evals/evaluate_real_text.py

# Step 6: update eval_thresholds.yaml + model card
```

### CI Gate Changes

| Gate | Before Phase 9 | After Phase 9 |
|---|---|---|
| `rag_hit_at_5` | 0.73 (placeholder) | `measured − 2pp` |
| `rag_mrr` | 0.60 (placeholder) | `measured − 2pp` |
| `rag_faithfulness` | 0.60 (placeholder) | `measured − 2pp` |
| `agent_tool_accuracy` | 0.80 (placeholder) | `measured (or measured − 5pp)` |
| `arabizi_f1` | not gated | not gated (deferred) |
| All other gates | unchanged | unchanged |

### Agent Context Update

The CLAUDE.md plan reference will be updated to point to this plan file.
