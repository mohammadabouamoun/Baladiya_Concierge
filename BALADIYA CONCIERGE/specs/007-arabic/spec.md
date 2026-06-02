# Feature Specification: Arabic Bilingual Layer (Phase 2)

**Feature Branch**: `007-arabic`

**Created**: 2026-06-02

**Status**: Draft

**Covers**: Arabic CMS content, language detection, RTL widget toggle, per-language metrics

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Arabic Resident Uses the Widget (Priority: P1)

An Arabic-speaking resident opens the widget, switches to Arabic, and sends a question in Lebanese dialect. The agent retrieves relevant content and responds in Arabic.

**Why this priority**: This is the core deliverable of Phase 2. The widget RTL toggle exists from `006-widget`; this story ensures the full pipeline (classify → retrieve → respond) works in Arabic.

**Independent Test**: Widget in Arabic mode → resident types "كيف بقدر دفع فاتورة المي؟" (Lebanese: "how can I pay the water bill?") → classifier returns `{intent: question, lang: ar, variety: lebanese}` → `rag_search` retrieves Arabic or multilingual chunk → agent responds in Arabic.

**Acceptance Scenarios**:

1. **Given** the widget is in Arabic mode and the resident types in Arabic, **When** the classifier processes the message, **Then** it returns `lang=ar` and the appropriate `variety` (msa, lebanese, arabizi) with a confidence score.
2. **Given** language detection returns `ar`, **When** the agent builds its prompt, **Then** the Arabic system prompt variant from `prompts/system_ar.md` is used (not the English variant).
3. **Given** the tenant's CMS has Arabic entries, **When** `rag_search` runs for an Arabic query, **Then** the multilingual embedding retrieves Arabic-tagged chunks preferentially, with cross-language fallback to English chunks.

---

### User Story 2 — English Product Unaffected by Arabic Data Absence (Priority: P1)

The Arabic dataset is empty (not yet collected). The English product classifies, retrieves, acts, and ships unchanged.

**Why this priority**: Additive guarantee. The defense requires proving this. It is a constitution requirement.

**Independent Test**: Remove all `lang=ar` rows from `civic_intent_dataset.csv`. Retrain. English macro-F1 is unchanged. The widget, router, and agent all function normally with only English content.

**Acceptance Scenarios**:

1. **Given** the Arabic rows are removed from the training CSV, **When** the classifier is retrained and the modelserver restarts, **Then** English classification F1 does not degrade; no code error occurs; language detection simply always returns `en`.
2. **Given** the tenant has no Arabic CMS entries, **When** a resident asks in Arabic, **Then** the multilingual embedding retrieves English chunks as fallback; the agent responds in English (or politely in Arabic noting limited Arabic content).
3. **Given** language detection fails on an unrecognized input, **When** the classifier runs, **Then** it defaults to `lang=en` and processes the message through the English path — no exception, no empty response.

---

### User Story 3 — Per-Language & Per-Variety Metrics Reported (Priority: P2)

After training with bilingual data, the model card and `EVALS.md` report F1 broken down by language and variety.

**Why this priority**: The spec requires per-language F1 committed alongside the overall macro-F1. Quoting a single number without per-language breakdown is a grade violation.

**Independent Test**: `EVALS.md` contains a table with EN macro-F1, AR macro-F1, and per-variety F1 (msa, lebanese, arabizi) — all from the held-out test set.

**Acceptance Scenarios**:

1. **Given** the bilingual classifier is evaluated on the held-out test, **When** metrics are computed, **Then** macro-F1 is broken down by `lang` (en, ar) and by `variety` (en, msa, lebanese, arabizi) in the evaluation output.
2. **Given** the per-variety numbers show arabizi F1 is significantly lower than MSA F1, **When** the model card is written, **Then** this gap is acknowledged and a justification is given (data scarcity, char n-gram vs word n-gram tradeoff).
3. **Given** the CI classifier gate runs, **When** per-language F1 is computed, **Then** both `en_macro_f1` and `ar_macro_f1` are checked against thresholds in `eval_thresholds.yaml` (Arabic threshold may be lower, but must exist).

---

### Edge Cases

- Arabizi uses number substitutions (3=ع, 7=ح, 2=ء). A TF-IDF word tokenizer will split on spaces and treat numbers as part of words. Char n-grams (3–5) handle this; word n-grams do not. This must be verified in the training notebook.
- Mixed Arabic-English messages (code-switching, e.g., "fi pothole kbir on Main Street") — language detection may return either. The classifier should handle both; the router falls through to the agent if confidence is below threshold.
- MSA and Lebanese dialect can have very different word forms for the same intent. The dataset must have sufficient variety per intent × variety cell (target: 50+ verified examples per cell).

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Language detection MUST run on every inbound message before classification. On failure, default to `lang=en`.
- **FR-002**: The prompt builder MUST select the Arabic system prompt variant (`prompts/system_ar.md`) when `lang=ar`, and the English variant otherwise. No hardcoded language assumptions in prompt code.
- **FR-003**: The CMS admin MUST allow Tenant Admin to tag each entry with a `lang` field (`ar` or `en`) — both languages can coexist in the same tenant's CMS.
- **FR-004**: RAG retrieval MUST prefer same-language chunks via metadata filtering when `lang=ar`, with cross-language fallback to English. The preference is a soft boost, not a hard filter (multilingual embedding handles both).
- **FR-005**: The CI classifier gate MUST separately check `en_macro_f1` and `ar_macro_f1` against thresholds in `eval_thresholds.yaml`. Both must pass; a regression in either blocks merge.
- **FR-006**: The Arabic dataset in `civic_intent_dataset.csv` MUST be hand-verified before the per-variety F1 numbers are committed. The model card MUST log: "Drafted N rows, hand-corrected M, relabelled K."
- **FR-007**: No English code path may import, reference, or depend on an Arabic resource. Language detection is the only gate between the two paths.

### Key Entities

- **Prompt variants**: `prompts/system_en.md`, `prompts/system_ar.md` — version-controlled; tenant persona injected at runtime
- **LangDetectResult**: `{lang: str, variety: str, confidence: float}` — returned by the language detection step before classification

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Arabic macro-F1 ≥ threshold in `eval_thresholds.yaml` → `ar_macro_f1` (placeholder: 0.70 — lower than English baseline, justified by data size).
- **SC-002**: Per-variety F1 reported and committed for msa, lebanese, arabizi in `EVALS.md`.
- **SC-003**: English macro-F1 does not degrade when Arabic rows are added to the training set (compared to the English-only baseline).
- **SC-004**: Arabic end-to-end pipeline verified: widget RTL → classify `ar` → prompt_ar → rag retrieve → respond in Arabic — demonstrated in the defense demo.
- **SC-005**: Additive guarantee verified: with empty Arabic dataset, all CI gates pass in English and no code exception occurs.

---

## Assumptions

- The Arabic dataset in `civic_intent_dataset.csv` is the training data. It is machine-seeded and must be hand-verified before any Arabic F1 numbers are claimed as valid.
- `langdetect` or `langid` is used for language detection — lightweight, no model weights, fast.
- The Arabic system prompt (`prompts/system_ar.md`) is written in MSA but instructs the LLM to respond naturally in the language/dialect the resident used.
- Arabizi hand-verification requires a Lebanese Arabic speaker. If unavailable, the Arabizi rows are flagged as "unverified" in the model card and excluded from the reported per-variety F1.
- The RTL widget toggle is implemented in `006-widget`; this spec only covers the backend language routing and prompt selection.
