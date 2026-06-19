# Data Model: Phase 9 — Arabizi Uplift, Live Evals & Defense Readiness

**Date**: 2026-06-07 | **Plan**: [plan.md](plan.md)

## Overview

Phase 9 introduces no new database tables or API schema changes. All data entities are existing files whose contents are expanded or updated. This document describes the expected structure and state of each entity after Phase 9.

---

## Entity 1 — Arabizi Training Rows (`build_dataset.md`)

**What it represents**: Intent-labelled chat messages in Arabizi script (Lebanese Arabic written with Latin letters and numerals).

**Location**: `build_dataset.md` → section `# ARABIC — ARABIZI (Lebanese written in Latin letters + numbers)` (lines ~283–338) and the expansion rows appended after line 338.

**Schema** (same as all `add()` calls):
```
add(text: str, lang: "ar", variety: "arabizi", intent: "report"|"question"|"human"|"spam", category: str)
```

**State after Phase 9**:

| intent | Before Phase 9 | After Phase 9 | Delta |
|---|---|---|---|
| report | 51 | ≥100 | +49 |
| question | 51 | ≥100 | +49 |
| human | 51 | ≥100 | +49 |
| spam | 52 | ≥100 | +48 |
| **total** | **205** | **≥400** | **+195** |

**Validation rules**:
- Each row MUST use the numeral substitution conventions defined in the comment header (2=ء/ق, 3=ع, 5=خ, 6=ط, 7=ح, 8=غ, 9=ص)
- Each row MUST cover a civic topic (roads, water, electricity, waste, environment, permits, taxes, general) or `none` for human/spam
- No row may duplicate an existing row (Jaccard similarity > 0.8 threshold)
- Label MUST match the content — a question phrased as "kif...?" MUST be `question`, not `report`

---

## Entity 2 — Real English Training Rows (`dataset_english.md`)

**What it represents**: Intent-labelled real 311-style civic chat messages in English.

**Location**: `dataset_english.md` → appended rows from NYC 311 mining and manual curation.

**Schema** (same pattern as existing rows in `dataset_english.md`):
```python
add(text: str, lang: "en", variety: "en", intent: str, category: str)
```

**State after Phase 9**:

| intent | Source | New rows target |
|---|---|---|
| report | NYC 311 `Descriptor` column (filtered, PII-stripped, pre-screened) | ≥200 |
| question | Manual curation (311 data has no questions) | ≥200 |
| human | Manual curation | ≥200 |
| spam | Manual curation (varied civic-domain spam) | ≥200 |
| **total** | | **≥800** |

**Mining filters**:
- Agency relevance: DSNY, DEP, DOT, DOB, DPR (discard non-civic agencies)
- PII strip: remove street numbers + addresses before inserting
- Pre-screening: classifier `confidence ≥ 0.70` for `report` label
- Deduplication: discard if Jaccard similarity > 0.8 with any existing dataset row

---

## Entity 3 — Classifier Artifact (`modelserver/artifacts/classifier.joblib`)

**What it represents**: The trained TF-IDF + LogisticRegression pipeline serialised with joblib.

**State after Phase 9**:

| Field | Before Phase 9 | After Phase 9 |
|---|---|---|
| SHA-256 | `728a4bf1aee84c015ddd9d73d998573a179bd32085a9b39330a50306f177b041` | New SHA (TBD after retrain) |
| Training rows | 10,206 | ~11,000+ |
| Arabizi F1 | 0.8322 | ≥ 0.88 (target ≥ 0.90) |
| EN template F1 | 1.0000 | ≥ 0.98 (must not regress) |
| AR macro-F1 | 0.9507 | ≥ 0.93 (must not regress) |

**Where SHA is recorded**: `modelserver/model_card.md §Artifact Provenance`

---

## Entity 4 — Evaluation Results (`evals/classifier_bilingual_results.json`)

**What it represents**: Per-variety and per-class F1 scores from the last classifier evaluation run.

**Schema** (existing — no change):
```json
{
  "evaluation_date": "YYYY-MM-DD",
  "dataset_sha256": "<sha>",
  "artifact_sha256": "<sha>",
  "macro_f1": 0.0,
  "per_class": {"report": 0.0, "question": 0.0, "human": 0.0, "spam": 0.0},
  "per_variety": {"en": 0.0, "msa": 0.0, "lebanese": 0.0, "arabizi": 0.0},
  "latency_p50_ms": 0.0,
  "latency_p95_ms": 0.0
}
```

**State after Phase 9**: `arabizi_f1` ≥ 0.88; all other values updated to Phase 9 retrain numbers.

---

## Entity 5 — Real-Text Eval Set (`evals/real_text_en_sample.json`)

**What it represents**: A held-out set of real (not template) English messages used to measure the gap between template test-set performance and real-world performance.

**Schema** (per record — existing):
```json
{"id": 1, "text": "...", "true_intent": "report", "predicted_intent": "report", "confidence": 0.95, "correct": true}
```

**State after Phase 9**:

| Field | Before Phase 9 | After Phase 9 |
|---|---|---|
| Record count | 25 | ≥ 200 |
| Macro-F1 | 0.8420 | Updated (target > 0.8420) |
| Source note | "NYC 311 (n=20) + manual (n=5)" | "NYC 311 (n≥160) + manual (n≥40)" |

---

## Entity 6 — CI Thresholds (`eval_thresholds.yaml`)

**What it represents**: The single source of truth for all CI gates. CI fails if any gate's measured value is below its threshold.

**State after Phase 9** (showing changed fields only):

```yaml
# ← NEW gate
arabizi_f1: 0.88   # measured <value> (Phase 9 retrain, YYYY-MM-DD); gate = measured − 2pp

# ← UPDATED from pre-measurement placeholders
rag_hit_at_5: <measured − 2pp>       # measured <value> (Phase 9 live eval, YYYY-MM-DD)
rag_mrr: <measured − 2pp>            # measured <value>
rag_faithfulness: <measured − 2pp>   # measured <value>
rag_answer_relevancy: <measured>     # reported only, not gated

agent_tool_accuracy: <measured>      # measured <value> (Phase 9 live eval, YYYY-MM-DD)
```

---

## Entity 7 — Model Card (`modelserver/model_card.md`)

**What it represents**: The authoritative record of model lineage, evaluation results, data provenance, and known limitations.

**Sections added/updated in Phase 9**:

- **§Data Corrections**: New section. Table with columns: `Row text (first 40 chars) | Original label | Corrected label | Correction type | Rationale`. Sign-off line: `Reviewed YYYY-MM-DD by [reviewer]. [N] corrections made.`
- **§Known Limitations → Real-text EN performance**: Update n=25 → n≥200; update macro-F1 from 0.8420 to the new measured value; update or close the "template memorisation" caveat.
- **§Artifact Provenance**: New row for Phase 9 retrain with date, new SHA-256, and training-set row count.
- **§Evaluation Results**: New row for Arabizi F1 (Phase 9) and real-text macro-F1 (Phase 9).

---

## Entity 8 — EVALS.md Sections

**What it represents**: The project-level evaluation document. Sections 3, 4, and 8 contain TBD rows that must be filled.

**§3 — RAG Quality Evaluation** (fill TBD rows):

| Metric | Placeholder | After Phase 9 |
|---|---|---|
| hit@5 (raw query) | TBD | Measured value |
| hit@5 (query-rewrite) | TBD | Measured value |
| MRR (raw query) | TBD | Measured value |
| MRR (query-rewrite) | TBD | Measured value |
| Faithfulness | TBD | Measured value |
| Answer relevancy | TBD | Measured value |
| Measurement date | TBD | YYYY-MM-DD |

**§4 — Agent Tool-Selection** (fill per-example rows):

Each of the 15 golden examples gets: `predicted_tool`, `correct` (Y/N), `notes`.

**§8 SC-002 — 3G Latency** (fill measurement table):

| Run | Throttle preset | P50 (s) | P95 (s) | Verdict |
|---|---|---|---|---|
| 1–5 | Slow 3G | TBD | TBD | TBD |

**§8 SC-004 — RTL Checklist** (mark all 10 items):

Each item gets `[x]` (pass) or `[ ] FAIL — see issue #N` plus a date stamp.
