# Implementation Plan: Classifier & Model Server

**Branch**: `002-classifier` | **Date**: 2026-06-02 | **Spec**: [spec.md](./spec.md)

## Summary

Train a civic intent classifier offline (three approaches), export the winning model to `joblib`/`ONNX`, and serve it from a lean `modelserver` FastAPI service. Wire the `api` to call `modelserver` over HTTP using a Vault service credential.

## Technical Context

**Language/Version**: Python 3.11 (training notebook + modelserver)

**Training dependencies** (notebook/Colab only, never in containers): scikit-learn, numpy, pandas, langdetect, optionally cpu-only torch + onnx for DL approach

**Modelserver dependencies** (container): scikit-learn, numpy, joblib, onnxruntime (optional), langdetect, fastapi, httpx

**Testing**: pytest; modelserver called via httpx in integration tests; training evaluated in notebook

**Target Platform**: `modelserver` Docker container on Linux

**Performance Goals**: < 50ms p95 classification latency; < 500 MB image

**Constraints**: No torch in container; no training code in container; SHA-256 gate at startup

## Constitution Check

- [x] No torch in modelserver container
- [x] Artifact SHA-256 verified at boot
- [x] Service-to-service auth via Vault credential
- [x] Three-way comparison committed before shipping
- [x] Per-variety F1 reported

## Project Structure

### Documentation

```text
specs/002-classifier/
├── spec.md     ← this spec
├── plan.md     ← this file
notebooks/
└── train_classifier.ipynb  ← offline training (committed, never run in container)
```

### Source Code

```text
modelserver/
├── Dockerfile               ← python:3.11-slim; no torch; < 500 MB
├── requirements.txt         ← scikit-learn, numpy, joblib, onnxruntime, langdetect, fastapi, uvicorn, httpx
├── main.py                  ← FastAPI app: lifespan loads artifact + verifies SHA-256
├── classifier.py            ← ClassifierService: load(), predict(), lang_detect()
├── model_card.md            ← task, data hash, three-way results, shipping choice + reason, artifact SHA-256
└── artifacts/
    └── classifier.joblib    ← (or classifier.onnx) — committed if < 50 MB, else referenced from MinIO

api/
├── infra/
│   └── modelserver_client.py  ← httpx AsyncClient; uses Vault service credential; classify()
└── services/
    └── router_service.py       ← calls modelserver_client.classify(); applies confidence threshold
```

## Feature Pipeline

### Classical ML Approach (Primary — must ship)

```
civic_intent_dataset.csv
  → de-duplicate + near-duplicate scan
  → train/test split (deterministic sha1 hash)
  → Pipeline([
       LanguageDetectTransformer(),        # adds lang/variety as feature
       ColumnTransformer([
         ('char_ngram', TfidfVectorizer(analyzer='char_wb', ngram_range=(3,5)), 'text'),
         ('word_ngram', TfidfVectorizer(analyzer='word', ngram_range=(1,2)), 'text'),
       ]),
       LogisticRegression(max_iter=1000, class_weight='balanced')
     ])
  → evaluate: macro-F1, per-class F1, per-variety F1 on held-out test
  → joblib.dump(pipeline, 'classifier.joblib')
  → sha256(classifier.joblib) → model_card.md
```

### Optional DL Approach (for comparison table, may not ship)

```
  → Small 2-layer MLP or distilbert-like encoder (CPU-only torch in Colab only)
  → Export to ONNX via torch.onnx.export
  → Evaluate same metrics
  → Compare: if DL macro-F1 > classical + 3pp AND latency still < 50ms → consider shipping
```

### LLM Zero-Shot Approach (for comparison table, never serves live traffic)

```
  → Prompt: "Classify this message by intent (report/question/human/spam) and category."
  → Run on held-out test via API (offline, batched)
  → Record F1, cost-per-call, latency
```

## Confidence Threshold Design

The confidence threshold is configured per-intent in `eval_thresholds.yaml`:

```yaml
classifier_confidence_thresholds:
  report: 0.75
  question: 0.75
  human: 0.65    # err toward escalation
  spam: 0.90     # high bar before dropping
```

Below threshold → falls through to the agent (fail safe, not fail cheap).

## Modelserver Boot Sequence

```python
@asynccontextmanager
async def lifespan(app):
    artifact_path = settings.artifact_path
    expected_sha = settings.artifact_sha256  # from model_card.md / Vault
    actual_sha = sha256(artifact_path)
    if actual_sha != expected_sha:
        raise StartupError(f"Artifact SHA-256 mismatch: {actual_sha} != {expected_sha}")
    app.state.classifier = ClassifierService(artifact_path)
    yield
```

## Service-to-Service Auth

`modelserver` validates an `X-Service-Token` header (a shared secret from Vault). The `api` resolves this token at startup via Vault and passes it on every `/classify` call. `modelserver` returns `401` if the token is missing or wrong.
