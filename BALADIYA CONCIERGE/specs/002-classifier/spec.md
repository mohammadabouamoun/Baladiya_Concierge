# Feature Specification: Classifier & Model Server (Design C)

**Feature Branch**: `002-classifier`

**Created**: 2026-06-02

**Status**: Draft

**Covers**: Design C — Your Own Model: ML vs DL, Trained Offline, Served Lean

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Classical Classifier Baseline (Priority: P1)

A developer trains a TF-IDF + LogReg (or linear SVM) classifier on `civic_intent_dataset.csv` in a Colab notebook, exports a `joblib` artifact, and starts the `modelserver`. The model server classifies an inbound resident message by intent in under 50ms.

**Why this priority**: The classifier is the router's brain. The English baseline must work before Arabic or DL approaches are layered in.

**Independent Test**: POST `{"text": "There is a pothole on Main Street"}` to `modelserver/classify` → `{"intent": "report", "category": "roads", "confidence": 0.92, "lang": "en", "variety": "en"}` in < 50ms.

**Acceptance Scenarios**:

1. **Given** the `modelserver` starts with a valid `joblib` artifact whose SHA-256 matches the model card, **When** it receives `POST /classify` with an English text, **Then** it returns `intent`, `category`, `confidence`, `lang`, `variety` in < 50ms.
2. **Given** the artifact SHA-256 does NOT match the model card, **When** `modelserver` starts, **Then** it refuses to boot with a clear error message.
3. **Given** the `modelserver` is called from the FastAPI `api` service, **When** the call is made, **Then** it uses a service credential (resolved from Vault) — not an open unauthenticated endpoint.

---

### User Story 2 — Three-Way Comparison (Priority: P1)

A developer trains all three approaches on the held-out test set and commits the comparison table before choosing one to ship.

**Why this priority**: The spec and defense require a committed comparison — shipping without the table is a grade violation.

**Independent Test**: `EVALS.md` contains a table with macro-F1, per-class F1, per-variety F1, p95 latency, and estimated cost-per-call for all three approaches. The shipped model is identified with a justification.

**Acceptance Scenarios**:

1. **Given** the training notebook runs on the CSV, **When** it completes, **Then** it outputs a comparison table: Classical (TF-IDF+LogReg) vs Optional DL (ONNX) vs LLM zero-shot — macro-F1, per-class F1, per-variety F1 (EN/MSA/Lebanese/Arabizi), p95 latency, cost/call.
2. **Given** the comparison table is committed to `EVALS.md`, **When** a new training run updates the artifact, **Then** the CI gate checks that macro-F1 on the held-out test does not fall below `eval_thresholds.yaml` → `classifier_macro_f1`.
3. **Given** the shipped model artifact, **When** its SHA-256 is computed, **Then** it matches the hash in `model_card.md`.

---

### User Story 3 — Arabic & Arabizi Classification (Priority: P2)

The classifier correctly classifies Lebanese dialect and Arabizi messages without any English-path code changes.

**Why this priority**: Arabic is additive. If Arabic data is missing, the classifier still works in English. If present, it must not degrade English F1.

**Independent Test**: POST `{"text": "fi 7afra kbire bel tari2"}` (Arabizi for "there's a big pothole") → `{"intent": "report", "category": "roads", ...}` without error.

**Acceptance Scenarios**:

1. **Given** the classifier is trained on the full bilingual dataset, **When** an Arabic (MSA, Lebanese, or Arabizi) message is classified, **Then** intent and category are returned; per-variety F1 is reported alongside English F1.
2. **Given** the Arabic dataset rows are removed from `civic_intent_dataset.csv`, **When** the classifier is retrained and `modelserver` is restarted, **Then** English classification still works identically — no Arabic dependency in the code path.
3. **Given** a message with mixed Arabic and Latin characters (Arabizi), **When** classified, **Then** language detection returns `ar`/`arabizi` and the char n-gram features handle it correctly.

---

### Edge Cases

- What if `confidence` is below the threshold? The model server returns the full result; the router decides whether to fall through to the agent (see `004-router-agent`).
- What if the model artifact is corrupted mid-run? The model is loaded once at startup; corruption mid-run is not possible unless the `modelserver` restarts.
- What if a message is in a completely unrecognized language? Language detection fails → defaults to `en`; the classifier runs on the raw text; the `confidence` will be low and the router will fall through to the agent.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The `modelserver` MUST load the classifier artifact at startup and refuse to boot if the artifact SHA-256 does not match `model_card.md`.
- **FR-002**: The `modelserver` MUST expose `POST /classify` returning `{intent, category, confidence, lang, variety}`.
- **FR-003**: Classification latency MUST be < 50ms p95 for the classical sklearn model.
- **FR-004**: The `modelserver` container MUST NOT contain torch, transformers, or any ML training code. Only `onnxruntime`, `scikit-learn`, `numpy`, `joblib`.
- **FR-005**: The `modelserver` MUST authenticate incoming requests with a service credential from Vault — it is not an open endpoint.
- **FR-006**: Three approaches MUST be trained, evaluated, and compared before shipping any one of them. The comparison table MUST be committed to `EVALS.md`.
- **FR-007**: The CI classifier gate MUST check macro-F1 on the held-out test against `eval_thresholds.yaml → classifier_macro_f1`. A regression blocks merge.
- **FR-008**: The classifier MUST report per-language F1 (EN and AR) and per-variety F1 (en, msa, lebanese, arabizi) in the CI gate output.
- **FR-009**: Char n-grams (3–5) MUST be included in the TF-IDF features to handle Arabizi and Lebanese spelling variation.
- **FR-010**: A confidence threshold MUST be configurable per intent in `eval_thresholds.yaml`. Messages below the threshold fall through to the agent rather than being handled by the workflow.

### Key Entities

- **ClassifyRequest**: `{text: str}`
- **ClassifyResponse**: `{intent: str, category: str, confidence: float, lang: str, variety: str}`
- **ModelCard** (`model_card.md`): task, data source + SHA-256, three-way comparison results, deployment choice + justification, artifact SHA-256
- **ModelArtifact**: either `classifier.joblib` (sklearn) or `classifier.onnx` (ONNX)

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Classical baseline macro-F1 ≥ threshold in `eval_thresholds.yaml` (placeholder: 0.80) on held-out test.
- **SC-002**: Classification latency < 50ms p95 for the shipped model (measured in the `modelserver` CI smoke test).
- **SC-003**: Per-variety F1 reported for all four varieties (en, msa, lebanese, arabizi) — absolute numbers committed in `EVALS.md`.
- **SC-004**: `modelserver` image size < 500 MB (verified in CI build step).
- **SC-005**: Artifact SHA-256 in `model_card.md` matches the loaded file — verified at startup.
- **SC-006**: Arabic classification works with the bilingual dataset; English F1 does not degrade when Arabic rows are added.

---

## Assumptions

- Training is done in a Colab/Jupyter notebook outside the repo. The notebook is committed under `notebooks/` for reproducibility but is never run in a container.
- The `civic_intent_dataset.csv` in the repo is the training/test data. The held-out test split is deterministic (`sha1(text) % 5 == 0 → test`).
- Language detection uses `langdetect` or `langid` as a lightweight library call (no model weights).
- The LLM zero-shot baseline uses the same hosted API as the agent — evaluated offline with API calls, not served in `modelserver`.
- `model_card.md` is committed alongside the artifact in `modelserver/` (or referenced from MinIO if the artifact is large).
