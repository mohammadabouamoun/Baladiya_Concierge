# Contract: Evaluation Result Schemas

**Feature**: Phase 9 — Arabizi Uplift, Live Evals & Defense Readiness
**Date**: 2026-06-07

These schemas define the expected structure of evaluation result files. Any script writing to these files must conform to the schema; any script reading from them may rely on these fields being present.

---

## classifier_bilingual_results.json

**Location**: `evals/classifier_bilingual_results.json`
**Written by**: `notebooks/train_classifier_bilingual.ipynb` (eval cell)
**Read by**: `eval_thresholds.yaml` gate check in CI, `modelserver/model_card.md` update step

```json
{
  "evaluation_date": "YYYY-MM-DD",
  "dataset_sha256": "<hex string>",
  "artifact_sha256": "<hex string>",
  "training_rows": 0,
  "test_rows": 0,
  "macro_f1": 0.0,
  "per_class": {
    "report": 0.0,
    "question": 0.0,
    "human": 0.0,
    "spam": 0.0
  },
  "per_variety": {
    "en": 0.0,
    "msa": 0.0,
    "lebanese": 0.0,
    "arabizi": 0.0
  },
  "latency_p50_ms": 0.0,
  "latency_p95_ms": 0.0
}
```

**Phase 9 constraint**: `per_variety.arabizi ≥ 0.88` and `per_variety.en ≥ 0.98` and `macro_f1 ≥ 0.97`. CI gate reads these fields directly; schema changes that rename these keys will break CI.

---

## real_text_en_sample.json

**Location**: `evals/real_text_en_sample.json`
**Written by**: `evals/evaluate_real_text.py`
**Read by**: `modelserver/model_card.md` update step

**Top-level structure**:
```json
{
  "evaluation_date": "YYYY-MM-DD",
  "artifact_sha256": "<hex string>",
  "sample_size": 0,
  "macro_f1": 0.0,
  "per_intent_f1": {
    "report": 0.0,
    "question": 0.0,
    "human": 0.0,
    "spam": 0.0
  },
  "sources": ["nyc_311", "manual"],
  "records": [
    {
      "id": 1,
      "text": "<message text>",
      "true_intent": "report",
      "predicted_intent": "report",
      "confidence": 0.95,
      "correct": true,
      "source": "nyc_311"
    }
  ]
}
```

**Phase 9 constraint**: `sample_size ≥ 200` (up from 25 in Phase 8). The `source` field on each record disambiguates NYC 311 mined rows from manually curated rows.

---

## evaluate_rag.py output format

**Location**: Written to stdout and optionally to `evals/rag_results_latest.json` (created by the script).

```json
{
  "evaluation_date": "YYYY-MM-DD",
  "mode": "compare",
  "golden_set_size": 15,
  "raw_query": {
    "hit_at_5": 0.0,
    "mrr": 0.0,
    "faithfulness": 0.0,
    "answer_relevancy": 0.0
  },
  "query_rewrite": {
    "hit_at_5": 0.0,
    "mrr": 0.0,
    "faithfulness": 0.0,
    "answer_relevancy": 0.0
  }
}
```

**Phase 9 use**: The `query_rewrite` strategy values are used to set `eval_thresholds.yaml` RAG gates (minus 2pp). The `raw_query` values are reported for comparison only.

---

## evaluate_agent.py output format

**Location**: Written to stdout; per-example results are also reported.

```json
{
  "evaluation_date": "YYYY-MM-DD",
  "golden_set_size": 15,
  "accuracy": 0.0,
  "per_example": [
    {
      "id": 1,
      "input": "<message>",
      "expected_tool": "rag_search",
      "predicted_tool": "rag_search",
      "correct": true,
      "notes": ""
    }
  ]
}
```

**Phase 9 use**: `accuracy` is used to set `agent_tool_accuracy` in `eval_thresholds.yaml`. `per_example` rows populate `EVALS.md §4`.
