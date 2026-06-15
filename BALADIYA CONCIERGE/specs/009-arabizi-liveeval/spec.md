# Feature Specification: Phase 9 — Live Evals & Defense Readiness

**Feature Branch**: `009-arabizi-liveeval`

**Created**: 2026-06-07

**Status**: Draft — scope reduced 2026-06-07 (data expansion deferred; Arabizi F1 = 0.8322 accepted)

**Input**: User description: "Phase 9 — Live Eval Runs, Arabic row hand-verification, and RTL/Latency Checks. Data expansion deferred."

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Hand-Verification of Arabic Training Rows (Priority: P1)

A data steward reviewing the training set needs to confirm that the machine-seeded MSA, Lebanese, and Arabizi rows in `build_dataset.md` are linguistically correct and correctly labelled. Any errors found are corrected in `build_dataset.md` and logged in `modelserver/model_card.md §Data Corrections` with the original text, correction, and rationale.

**Why this priority**: The model card explicitly states Arabic rows are machine-seeded and "should be hand-verified before citing per-variety F1 as reliable." This sign-off is the minimum required before defense. It is P1 because all other eval work cites the current artifact — the sign-off confirms that artifact is trustworthy.

**Independent Test**: Review each Arabic row in `build_dataset.md` for correct intent label and plausible phrasing; record every finding (correction or explicit "no change") in `modelserver/model_card.md §Data Corrections` with a dated sign-off line.

**Acceptance Scenarios**:

1. **Given** the MSA/Lebanese/Arabizi sections of `build_dataset.md` are reviewed row-by-row, **When** any row has a wrong intent label or unnatural phrasing, **Then** it is corrected in `build_dataset.md` and logged with original text + correction + rationale in `modelserver/model_card.md §Data Corrections`.
2. **Given** the review is complete, **When** `modelserver/model_card.md` is checked, **Then** a `§Data Corrections` section exists with a dated sign-off line confirming all rows were reviewed (even if no corrections were needed).
3. **Given** any corrections are made to `build_dataset.md`, **When** the model card is updated, **Then** the correction log entries reference the specific row text and the reason for the change.

---

### User Story 2 — Live RAG Evaluation (Priority: P1)

A developer running the full stack needs to replace the placeholder RAG thresholds in `eval_thresholds.yaml` (`rag_hit_at_5: 0.73`, `rag_mrr: 0.60`) with values measured against a live PostgreSQL + pgvector instance seeded with `evals/seed_eval_content.py`. Results fill the TBD rows in `EVALS.md §3`.

**Why this priority**: The RAG evaluation section is the most visibly incomplete part of the project documentation. Pre-measurement placeholder thresholds that have never been validated cannot be cited in a defense.

**Independent Test**: Bring up the docker compose stack, run `python evals/seed_eval_content.py`, then `python evals/evaluate_rag.py --mode compare`; confirm it outputs hit@5, MRR, faithfulness, and answer-relevancy numbers; update `eval_thresholds.yaml` to `measured − 2pp`.

**Acceptance Scenarios**:

1. **Given** the docker compose stack is running and CMS content is seeded via `seed_eval_content.py`, **When** `evaluate_rag.py --mode compare` is executed against the 15-triple golden set, **Then** it reports hit@5, MRR, faithfulness, and answer-relevancy for both raw-query and query-rewrite strategies.
2. **Given** measured values are available, **When** `eval_thresholds.yaml` is updated, **Then** `rag_hit_at_5`, `rag_mrr`, and `rag_faithfulness` are set to `measured − 2pp` — no longer pre-measurement placeholders.
3. **Given** the updated thresholds, **When** CI runs the RAG gate, **Then** it passes.
4. **Given** `EVALS.md §3`, **When** TBD rows are filled, **Then** every metric column contains a real value with its sample size and measurement date.

---

### User Story 3 — Live Agent Tool-Selection Evaluation (Priority: P1)

A developer needs to replace the placeholder `agent_tool_accuracy` threshold in `eval_thresholds.yaml` with a value measured by running `evals/evaluate_agent.py` against a live LLM-backed stack. Results fill the TBD rows in `EVALS.md §4`.

**Why this priority**: The agent eval section has never been run end-to-end. The 15-labelled golden set exists; the only missing step is executing the script and recording the number.

**Independent Test**: With a live API key and the docker compose stack running, execute `python evals/evaluate_agent.py`; confirm reported tool-selection accuracy; update `eval_thresholds.yaml` and `EVALS.md §4`.

**Acceptance Scenarios**:

1. **Given** the API key is configured and the live stack is running, **When** `evaluate_agent.py` is executed, **Then** it reports tool-selection accuracy per example and a macro accuracy on the 15-example set.
2. **Given** measured tool-selection accuracy is available, **When** `eval_thresholds.yaml` is updated, **Then** `agent_tool_accuracy` is set to the measured value (or `measured − 5pp` if variance is high) and CI passes.
3. **Given** `EVALS.md §4`, **When** TBD rows are filled, **Then** every example row contains the model's predicted tool and a pass/fail annotation.

---

### User Story 4 — Widget 3G Latency Measurement (Priority: P2)

A QA engineer validating the widget against EVALS.md §8 SC-002 (first message round-trip < 3 s on 3G) needs a documented, reproducible measurement procedure using Chrome DevTools Network throttling. Results are recorded in `EVALS.md §8 SC-002` with P50 and P95 values.

**Why this priority**: SC-002 is a committed success criterion. It remains the only unverified performance gate before defense. It cannot be automated — it requires a real browser + DevTools session.

**Independent Test**: With the widget dev server and FastAPI backend running, open Chrome DevTools → Network → throttle to "Slow 3G"; submit a message; record first-response time; repeat 5 times; report P50 and P95.

**Acceptance Scenarios**:

1. **Given** the widget is loaded at `http://localhost:5173/widget/?token=preview` and the network is throttled to Slow 3G in Chrome DevTools, **When** a resident submits a first message, **Then** the first response token is rendered within 3 seconds (P50).
2. **Given** five independent measurements are taken, **When** P50 and P95 are recorded in `EVALS.md §8 SC-002`, **Then** the table contains the measurement date, preset used, P50, P95, and a pass/fail verdict.
3. **Given** SC-002 fails (P50 > 3 s), **When** the result is recorded, **Then** the cause is noted and a remediation is proposed.

---

### User Story 5 — RTL Checklist Sign-Off (Priority: P2)

A QA engineer verifying the widget's Arabic RTL layout needs to run the 10-item RTL checklist from `EVALS.md §8 SC-004` against the widget in Arabic mode and record each item as pass or fail.

**Why this priority**: The RTL checklist is the only remaining manual UI gate before the product can claim bilingual readiness.

**Independent Test**: Open the widget in Arabic mode, step through each checklist item, mark pass/fail. All 10 items must pass for a clean sign-off.

**Acceptance Scenarios**:

1. **Given** the widget is running in Arabic mode and RTL layout is active, **When** each of the 10 RTL checklist items in `EVALS.md §8 SC-004` is evaluated, **Then** a pass/fail result is recorded for every item.
2. **Given** all 10 items pass, **When** `EVALS.md §8 SC-004` is updated, **Then** the table contains every item marked `[x]` with a date stamp.
3. **Given** any item fails, **When** the result is recorded, **Then** a GitHub issue is opened and the checklist item is marked `[ ] FAIL — see issue #N`.

---

### Edge Cases

- What if the docker compose stack fails to start (missing API keys, port conflicts)? — Document the exact error in `RUNBOOK.md §Troubleshooting`; live evals are not marked complete until the stack runs.
- What if widget latency exceeds 3 s on the first cold measurement but meets it on warm requests? — Record both cold and warm P50/P95; document the cold-start overhead source.
- What if Arabic corrections reduce per-variety F1 below the current `ar_macro_f1: 0.93` gate? — Do not lower the threshold; correct the data and retrain before signing off.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Every Arabic row (MSA/Lebanese/Arabizi) in `build_dataset.md` MUST be reviewed by a human; `modelserver/model_card.md §Data Corrections` MUST record a dated sign-off and any corrections made.
- **FR-002**: With the docker compose stack running and CMS content seeded, `evals/evaluate_rag.py --mode compare` MUST complete; `eval_thresholds.yaml` RAG gates (`rag_hit_at_5`, `rag_mrr`, `rag_faithfulness`) MUST be updated from placeholder values to `measured − 2pp`.
- **FR-003**: `EVALS.md §5` TBD rows MUST be filled with real measured values, sample size, and measurement date.
- **FR-004**: With the live stack and API keys configured, `evals/evaluate_agent.py` MUST complete against the 15-example golden set; `eval_thresholds.yaml` `agent_tool_accuracy` MUST be updated from placeholder to a measured value.
- **FR-005**: `EVALS.md §4` TBD rows MUST be filled with per-example predicted tools and pass/fail annotations.
- **FR-006**: `EVALS.md §8 SC-002` MUST contain a documented measurement procedure and a table of ≥5 P50/P95 measurements from a Chrome DevTools Slow 3G throttled session.
- **FR-007**: `EVALS.md §8 SC-004` MUST contain completed pass/fail results for all 10 RTL checklist items with a date stamp.

### Key Entities

- **RAG golden set**: `evals/rag_golden.json` — 15 hand-labelled triples for hit@5, MRR, faithfulness, answer-relevancy measurement.
- **Agent golden set**: `evals/agent_tool_selection.json` — 15 labelled examples for tool-selection accuracy measurement.
- **CI thresholds**: `eval_thresholds.yaml` — source of truth for all gated metrics; CI fails if measured value falls below threshold.
- **Model card**: `modelserver/model_card.md` — records the Arabic row review sign-off in `§Data Corrections`.
- **EVALS.md**: Project-level evaluation document; §5 = RAG results, §4 = agent results, §8 = widget SC-002 / SC-004.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All Arabic training rows have a human-reviewed sign-off in `modelserver/model_card.md §Data Corrections`; dated sign-off line is present.
- **SC-002**: RAG evaluation completes on the live stack; `eval_thresholds.yaml` RAG gates are set to measured values (not placeholders); CI passes.
- **SC-003**: Agent tool-selection evaluation completes on the live stack; `eval_thresholds.yaml` `agent_tool_accuracy` is updated to a measured value; CI passes.
- **SC-004**: `EVALS.md §8 SC-002` records ≥5 first-message round-trip measurements under Slow 3G; P50 ≤ 3 s (or shortfall documented with root cause).
- **SC-005**: All 10 RTL checklist items in `EVALS.md §8 SC-004` have a recorded pass/fail result with a date stamp.

## Assumptions

- The docker compose stack can be brought up locally; API keys (`GEMINI_API_KEY`, `GROQ_API_KEY`) are in `.env` and the Vault root token is available.
- The widget dev server runs on port 5173 and the FastAPI backend on port 8000 for the 3G latency (EVALS.md §8 SC-002) and RTL checklist (EVALS.md §8 SC-004) tests; Chrome is available.
- `evals/evaluate_rag.py` and `evals/evaluate_agent.py` require live API calls; Gemini free-tier limit (20 calls/day) may require routing through Groq fallback for batch queries.
- RTL checklist items require visual inspection; they are complete only when a human signs off in `EVALS.md`.
- No new code features are added in this phase — all changes are to threshold files, evaluation results, and documentation.
- Arabizi F1 = 0.8322 is accepted as-is; no classifier retraining is planned for this phase.
