# Tasks: Classifier & Model Server

**Branch**: `002-classifier` | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

---

## Phase 1: Setup

- [X] **T-001** Create `notebooks/` directory; scaffold `notebooks/train_classifier.ipynb` with sections: data loading, dedup, split verification, classical pipeline, evaluation, export
- [X] **T-002** Create `modelserver/` directory with `Dockerfile`, `requirements.txt` (scikit-learn, numpy, joblib, onnxruntime, langdetect, fastapi, uvicorn, httpx — NO torch), `main.py` skeleton

---

## Phase 2: Training — Three-Way Comparison (US2)

*Run in Colab/notebook, never in a container.*

- [X] **T-010** Load `civic_intent_dataset.csv`; de-duplicate; verify train/test split (deterministic sha1 hash, ~20% test); print per-cell counts
- [X] **T-011** [P] Classical baseline: `Pipeline([LanguageDetectTransformer, ColumnTransformer([char_ngram(3-5), word_ngram(1-2)]), LogisticRegression(class_weight='balanced')])` → evaluate macro-F1, per-class F1, per-variety F1, p95 latency on held-out test → `joblib.dump` → record SHA-256
- [X] **T-012** [P] Optional DL approach: small MLP or distilbert encoder (CPU-only torch in notebook only) → export to ONNX → evaluate same metrics → record SHA-256
- [X] **T-013** [P] LLM zero-shot baseline: batch the held-out test through the hosted API → evaluate macro-F1, cost-per-call, latency (no artifact — eval only)
- [X] **T-014** Commit three-way comparison table to `EVALS.md`; choose one model to ship; write `modelserver/model_card.md` (task, data SHA-256, comparison table, shipping choice + one-line justification, artifact SHA-256)

---

## Phase 3: Model Server (US1)

- [X] **T-020** `modelserver/classifier.py` — `ClassifierService`: `load(path)`, `predict(text)` → `ClassifyResponse`, `lang_detect(text)` → `(lang, variety)`
- [X] **T-021** `modelserver/main.py` — FastAPI lifespan: compute `sha256(artifact_path)`, compare to `settings.artifact_sha256` (from Vault/env), raise `StartupError` on mismatch; load `ClassifierService`
- [X] **T-022** `POST /classify` endpoint — validates `X-Service-Token` header → 401 if missing/invalid; returns `ClassifyResponse{intent, category, confidence, lang, variety}`
- [X] **T-023** `modelserver/Dockerfile` — verify final image size < 500 MB; CI build step asserts this

---

## Phase 4: API Integration (US1)

- [X] **T-030** `api/infra/modelserver_client.py` — async httpx client; Vault service credential in `X-Service-Token`; `classify(text)` → `ClassifyResponse`; `tenacity` retry on transient errors
- [X] **T-031** Wire confidence thresholds into `api/services/router_service.py`: load `classifier_confidence_thresholds` from `Settings`; below threshold → fall through to agent

---

## Phase 5: CI Gate (US2)

- [X] **T-040** `tests/test_classifier/test_classifier_gate.py` — load held-out test from CSV; classify each via modelserver HTTP call; assert macro-F1 ≥ `eval_thresholds.yaml → classifier_macro_f1`; assert per-language F1 reported
- [X] **T-041** [P] `tests/test_classifier/test_modelserver.py` — POST /classify returns correct schema in < 50ms; POST without token → 401; invalid SHA-256 at boot → StartupError
- [X] **T-042** [P] CI build step: `docker build modelserver/ && docker image inspect ... | jq '.[].Size'` → assert < 524288000 bytes (500 MB)
- [X] **T-043** Update `eval_thresholds.yaml`: set real values for `classifier_macro_f1`, `en_macro_f1` after training

---

## Dependencies & Execution Order

```
T-001 → T-002
T-002 → T-010 → T-011, T-012, T-013 [P]
T-011 → T-014   (classical must complete; DL/LLM results folded in)
T-014 → T-020 → T-021 → T-022 → T-023
T-023 → T-030 → T-031
T-031 → T-040, T-041, T-042 [P]
T-040 → T-043
```

**Gate**: `classifier_macro_f1` CI gate passes; `modelserver` image < 500 MB; artifact SHA-256 matches model card; three-way comparison table committed in EVALS.md.
