# Feature Specification: Phase 8 — Hardening & Evals

**Feature Branch**: `008-hardening-evals`

**Created**: 2026-06-06

**Status**: Draft

**Input**: User description: "Phase 8 — Hardening & Evals. Scope from HANDOFF.md §8: Arabizi quality, Arabic PII redaction, per-widget JWT key rotation, live eval runs, defense documentation, real resident text eval."

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Arabizi Quality Improvement (Priority: P1)

A data scientist growing the training set needs to push Arabizi F1 above 0.90 so the project can be defended with reliable multilingual numbers. They add verified Arabizi examples (targeting ≥100 per intent cell), rebuild the dataset, retrain the bilingual classifier, and confirm the new threshold passes CI.

**Why this priority**: Arabizi F1 = 0.8322 is the weakest reported metric and the most likely question at defense. Fixing it before the other documentation work ensures the numbers cited in DECISIONS.md and the model card are defensible.

**Independent Test**: Run the retrained classifier against the held-out test set; verify `arabizi_f1 ≥ 0.90` reported in `evals/classifier_bilingual_results.json` and `eval_thresholds.yaml` gated in CI.

**Acceptance Scenarios**:

1. **Given** `build_dataset.md` has been updated with ≥100 verified Arabizi examples per intent cell, **When** the bilingual notebook is retrained, **Then** the reported Arabizi macro-F1 on the held-out test set is ≥ 0.90.
2. **Given** a new threshold `arabizi_f1: 0.90` is set in `eval_thresholds.yaml`, **When** CI runs the classifier gate, **Then** the gate passes with the retrained artifact.
3. **Given** the retrained artifact is in place, **When** the classifier is queried with Arabizi inputs (e.g., "shu fi shi msh mzbout bel kahraba"), **Then** the correct intent is returned with confidence ≥ 0.70.

---

### User Story 2 — Arabic Name PII Redaction (Priority: P1)

A visitor chatting in Arabic types their full name while describing a problem. The redaction middleware must strip or mask that name before the text is stored in Redis session memory or written to the database — the same guarantee already provided for phone numbers and national IDs.

**Why this priority**: PII redaction is a constitution-level requirement ("PII redaction — zero PII leaks in redaction pipeline"). Arabic names were explicitly deferred from Phase 5; shipping Phase 8 without them leaves a known gap.

**Independent Test**: Send a POST /chat request containing an Arabic name (e.g., "أنا محمد علي من بيروت"); verify the stored session turn and any DB write contain a redacted placeholder, not the original name.

**Acceptance Scenarios**:

1. **Given** a chat message contains an Arabic given name + family name, **When** the redaction middleware processes it, **Then** the name is replaced with a `[NAME]` placeholder before any downstream write.
2. **Given** a message with only an English name (already covered), **When** the redaction middleware runs, **Then** existing English name redaction is unchanged.
3. **Given** the PII redaction CI gate runs, **When** test cases include Arabic name patterns, **Then** zero Arabic names appear unredacted in session or DB outputs.

---

### User Story 3 — Per-Widget JWT Key Rotation (Priority: P2)

A tenant admin rotates the signing key for one of their widgets (e.g., after suspected key exposure) without affecting other widgets or tenants. The old key is invalidated; new tokens issued for that widget use the new key; existing sessions with old tokens expire naturally.

**Why this priority**: The shared `jwt_secret` is documented as a temporary shortcut in `DECISIONS.md §D-Widget-001`; per-widget keys are the correct security posture. This closes the deferred item before defense.

**Independent Test**: Create two widgets for the same tenant; rotate the key for widget A; confirm tokens issued before rotation for widget A are rejected, tokens for widget B are unaffected, and new tokens for widget A validate correctly.

**Acceptance Scenarios**:

1. **Given** a widget has an active signing key stored in Vault, **When** the tenant admin triggers key rotation via the admin API, **Then** a new key is generated, stored in Vault, and the `widgets` table updated with the new key reference.
2. **Given** a visitor token was issued with the old key, **When** that token is presented after rotation, **Then** the API returns 401 Unauthorized.
3. **Given** two widgets share the same tenant but different signing keys, **When** one widget's key is rotated, **Then** the other widget's tokens remain valid.

---

### User Story 4 — Live Eval Runs (Priority: P2)

A developer runs the RAG and agent evaluation scripts against the live stack for the first time and replaces the placeholder thresholds in `eval_thresholds.yaml` with the actual measured values (measured − 2pp safety margin). These become the gated CI values.

**Why this priority**: Several thresholds (`rag_hit_at_5`, `rag_mrr`, `rag_faithfulness`, `agent_tool_accuracy`, `workflow_handled_rate`) are pre-measurement placeholders. CI cannot enforce what hasn't been measured.

**Independent Test**: Run `evals/evaluate_rag.py --mode compare` and `evals/evaluate_agent.py` end-to-end; verify `eval_thresholds.yaml` is updated with non-placeholder values and CI gates pass.

**Acceptance Scenarios**:

1. **Given** the live stack is running (API + modelserver + guardrails + DB + Redis), **When** `evals/evaluate_rag.py --mode compare` is executed against the 15-triple golden set, **Then** `rag_hit_at_5`, `rag_mrr`, and `rag_faithfulness` are recorded in `EVALS.md §3` and thresholds set to measured − 2pp.
2. **Given** the agent eval script runs against the 15 labelled examples, **When** results are collected, **Then** `agent_tool_accuracy` and `workflow_handled_rate` are recorded and `eval_thresholds.yaml` updated.
3. **Given** updated thresholds, **When** CI runs, **Then** all previously-placeholder gates pass.

---

### User Story 5 — Defense Documentation (Priority: P2)

A project owner prepares for the final defense review. They need `DECISIONS.md`, `DATA.md`, and `modelserver/model_card.md` to reflect the bilingual retrain results from Phase 7 (SHA-256, per-variety F1, rationale for choosing Classical ML over a separate-language-model approach), so every architectural claim is backed by a measured number.

**Why this priority**: Constitution Rule VI states every architectural choice must be backed by a measured number. These documents are evaluated at defense.

**Independent Test**: Verify `DECISIONS.md` contains a §D-Arabic-001 entry with measured F1 numbers; `DATA.md` has the 12,731-row breakdown with Arabizi F1 caveat; `modelserver/model_card.md` has Phase 7 SHA-256 and per-variety results.

**Acceptance Scenarios**:

1. **Given** Phase 7 bilingual retrain results (macro-F1=0.9980, ar_macro_f1=0.9507, arabizi_f1=0.8322, SHA-256 committed), **When** `DECISIONS.md` is updated, **Then** it contains a §D-Arabic-001 defending Classical ML vs per-language-model with the measured numbers.
2. **Given** the 12,731-row dataset, **When** `DATA.md` is reviewed, **Then** it shows the full per-cell breakdown (msa/lebanese/arabizi × report/question/human/spam) and an explicit caveat that Arabizi rows are machine-seeded.
3. **Given** the Phase 7 model artifact, **When** `modelserver/model_card.md` is reviewed, **Then** it shows the Phase 7 SHA-256, per-variety F1, and a comparison row vs Phase 2 baseline.

---

### User Story 6 — Real Resident Text Evaluation (Priority: P3)

A project owner wants to verify that the EN classifier generalises beyond the template test set. They evaluate the classifier on a small set of real (non-template) resident messages, document the results, and add a caveat to the model card if generalisation drops below the template F1.

**Why this priority**: EN F1 = 1.0 on the template test set is likely template memorisation. Knowing the real-world F1 is required before the defense claim "our classifier achieves F1=0.998" can be made honestly.

**Independent Test**: Collect ≥20 real or manually paraphrased resident messages (not from the template generators), run the classifier, record the F1, and update the model card with the real-text result.

**Acceptance Scenarios**:

1. **Given** ≥20 non-template English resident messages (real 311-style texts), **When** the classifier is evaluated, **Then** the real-text F1 is recorded in `modelserver/model_card.md` as a separate row from the template-test F1.
2. **Given** a real-text F1 below template-test F1, **When** the model card is updated, **Then** a caveat note is added explaining the gap and recommending further data collection.

---

### Edge Cases

- What if Arabizi F1 does not reach 0.90 even after expanding cells? Document the gap in the model card and update `eval_thresholds.yaml` to the best measured value with a note; do not gate on an unachievable threshold.
- What if the live stack is unavailable for eval runs? Document the blocker in `EVALS.md`; thresholds remain as pre-measurement targets with a timestamp note.
- What if rotating a widget's JWT key breaks in-flight visitor sessions? The token TTL is 3600s; document that active sessions expire naturally; no forced logout mechanism is required.
- What if an Arabic name regex overlaps with a known city name or common noun? Use a conservative pattern (proper-noun capitalization indicator or name-list approach); prefer false negatives over redacting civic information.

## Requirements *(mandatory)*

### Functional Requirements

**Arabizi Quality**
- **FR-001**: The dataset (`build_dataset.md`) MUST be expanded to ≥100 verified Arabizi examples per intent cell (report, question, human, spam).
- **FR-002**: The bilingual classifier MUST be retrained on the expanded dataset; the retrained artifact MUST be committed to `modelserver/artifacts/`.
- **FR-003**: `eval_thresholds.yaml` MUST include an `arabizi_f1` gate with threshold ≥ 0.90 once the measured value reaches that level.

**Arabic PII Redaction**
- **FR-004**: `api/middleware/redaction.py` MUST redact Arabic full names (given + family name patterns) before any downstream write (session, DB, logs).
- **FR-005**: The PII redaction CI gate MUST include at least 5 Arabic name test cases; all MUST pass with zero leaked names.
- **FR-006**: Existing English redaction (phone, NID, email) MUST remain unmodified and continue passing all existing tests.

**Per-Widget JWT Key Rotation**
- **FR-007**: Each widget row MUST have its own signing key stored in Vault (path: `baladiya/widgets/<widget_id>/signing_key`).
- **FR-008**: The token service MUST sign visitor tokens with the per-widget key fetched from Vault, not the shared `jwt_secret`.
- **FR-009**: `decode_token` for widget-origin tokens MUST validate against the widget's per-widget key (looked up by `widget_id` claim).
- **FR-010**: The admin API MUST expose a `POST /admin/widgets/{widget_id}/rotate-key` endpoint that generates a new key, writes it to Vault, and invalidates the previous key reference.
- **FR-011**: Existing widget tokens signed with the old key MUST be rejected (401) after rotation.

**Live Eval Runs**
- **FR-012**: `evals/evaluate_rag.py --mode compare` MUST be run against the live stack and results recorded in `EVALS.md §3`.
- **FR-013**: `evals/evaluate_agent.py` MUST be run against the live stack and results recorded in `EVALS.md §4`.
- **FR-014**: `eval_thresholds.yaml` thresholds for `rag_hit_at_5`, `rag_mrr`, `rag_faithfulness`, `agent_tool_accuracy`, and `workflow_handled_rate` MUST be updated from pre-measurement placeholders to measured − 2pp.

**Defense Documentation**
- **FR-015**: `DECISIONS.md` MUST contain a `§D-Arabic-001` entry defending the choice of a single bilingual Classical ML model over per-language models, backed by measured F1 numbers.
- **FR-016**: `DATA.md` MUST show the full 12,731-row breakdown (per-variety, per-intent cell counts) and include a caveat that Arabizi rows are machine-seeded.
- **FR-017**: `modelserver/model_card.md` MUST include the Phase 7 retrained artifact SHA-256, per-variety F1 table, and a baseline comparison row vs Phase 2.

**Real Resident Text Eval**
- **FR-018**: ≥20 non-template English resident messages MUST be collected and evaluated against the classifier.
- **FR-019**: The real-text F1 result MUST be added to `modelserver/model_card.md` as a separate row from the template-test result, with an honest caveat if F1 drops.

### Key Entities

- **Widget Signing Key**: Per-widget secret stored in Vault; referenced by `widget_id`; rotatable without affecting other widgets or the shared `jwt_secret`.
- **Arabic Name Pattern**: Regex or name-list rule applied in `redaction.py`; covers Arabic script proper names; produces `[NAME]` placeholder.
- **Arabizi Training Example**: A verified (human-reviewed) text message in Arabizi script with a labelled intent; stored in `build_dataset.md`.
- **Eval Result Record**: A measured metric value (F1, hit@k, MRR) tied to a dataset SHA-256 and run timestamp; stored in `EVALS.md` and `eval_thresholds.yaml`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Arabizi F1 on the held-out test set reaches ≥ 0.90; the `arabizi_f1` CI gate passes.
- **SC-002**: Zero Arabic names appear unredacted in session memory, database writes, or log output during the PII redaction CI gate (5 Arabic name test cases, 0 leaks).
- **SC-003**: Widget token issued with a rotated-away key is rejected (401) within one API call; a freshly issued token with the new key is accepted (200).
- **SC-004**: All five previously-placeholder eval thresholds (`rag_hit_at_5`, `rag_mrr`, `rag_faithfulness`, `agent_tool_accuracy`, `workflow_handled_rate`) are replaced with measured values in `eval_thresholds.yaml` and CI gates pass.
- **SC-005**: `DECISIONS.md`, `DATA.md`, and `modelserver/model_card.md` each contain the Phase 7 measured numbers (macro-F1, per-variety F1, SHA-256); no "TBD" or placeholder rows remain in those files.
- **SC-006**: Real-text EN classifier F1 is recorded in the model card (any value acceptable; the gate is documentation completeness, not a specific F1 floor).

## Assumptions

- The bilingual classifier notebook (`notebooks/train_classifier_bilingual.ipynb`) can be re-executed in the existing Colab/local environment with the expanded dataset without requiring torch or GPU (scikit-learn TF-IDF + LogReg only).
- Vault is running and the seed script (`scripts/seed.py`) can be extended to seed per-widget signing keys at `baladiya/widgets/<widget_id>/signing_key`.
- The live stack (API + modelserver + guardrails + DB + Redis) can be started locally via `docker-compose up` for eval runs.
- Arabic name PII patterns will use regex (Arabic Unicode block proper-noun heuristics); full spacy NER is out of scope unless regex coverage is demonstrably insufficient.
- Per-widget key rotation does not require a UI change in this phase — the admin API endpoint is sufficient; Streamlit UI update is future work.
- "Real resident text" for FR-018 may include manually paraphrased examples if a labelled real-world dataset is unavailable.
- Arabizi expansion rows added to `build_dataset.md` must be hand-verified (or clearly marked as machine-seeded) before the model card can cite Arabizi F1 as a reliable defense number.
