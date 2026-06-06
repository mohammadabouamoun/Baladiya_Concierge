# Tasks: Phase 8 — Hardening & Evals

**Input**: Design documents from `specs/008-hardening-evals/`

**Prerequisites**: plan.md ✅ | spec.md ✅ | research.md ✅ | data-model.md ✅ | contracts/rotate_key.md ✅

**Tests**: Included for US2 (PII gate — safety-critical) and US3 (security-critical key rotation). Skipped for US1 (CI gate is the test), US4 (eval scripts are the test), US5/US6 (documentation).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to
- Exact file paths are included in every task description

---

## Phase 1: Setup (Verify Prerequisites)

**Purpose**: Confirm the development environment is ready before touching any code.

- [x] T001 Confirm venv is active and all deps installed: `source /home/usermohammad/.venv/bin/activate && python -c "import sklearn, joblib, jwt, structlog"`
- [x] T002 [P] Confirm `notebooks/train_classifier_bilingual.ipynb` kernel is set to the project venv Python (`/home/usermohammad/.venv/bin/python3`)
- [x] T003 [P] Confirm `modelserver/artifacts/classifier.joblib` SHA-256 matches `728a4bf1...` (Phase 7 artifact) in `eval_thresholds.yaml` comments

**Checkpoint**: Dev environment verified — all six user story tracks can begin.

---

## Phase 2: Foundational (Shared — No Story Dependencies)

**Purpose**: No shared foundational changes needed — all Phase 8 work is in isolated tracks. This phase is intentionally empty; all user stories can start immediately after Phase 1.

**⚠️ Note**: US1 and US2 are both P1 and fully independent — start both in parallel after Phase 1.

---

## Phase 3: User Story 1 — Arabizi Quality (Priority: P1) 🎯 MVP Track A

**Goal**: Grow Arabizi training cells to ≥100 examples per intent, retrain the bilingual classifier, and gate Arabizi F1 in CI.

**Independent Test**: Run retrained classifier on held-out Arabizi test rows; confirm `arabizi_f1 ≥ 0.90` reported in `evals/classifier_bilingual_results.json`. CI gate passes.

### Implementation for User Story 1

- [ ] T004 [US1] Add ≥49 new verified Arabizi `report` examples to `build_dataset.md` in the `# ARABIC EXPANSION` section (target: 100 total report/arabizi rows); use patterns: "fi shi msh mzbout", "hayde l-masale", "bi2oul l-kahraba"
- [ ] T005 [US1] Add ≥49 new verified Arabizi `question` examples to `build_dataset.md` (target: 100 total question/arabizi rows); use patterns: "kifeh b2adder", "shu lazem a3mel", "wayn l-maktab"
- [ ] T006 [US1] Add ≥49 new verified Arabizi `human` examples to `build_dataset.md` (target: 100 total human/arabizi rows); use patterns: "bde 7ada y2arrebne", "fi mas2ale mush 3arif kifeh", "bedde 7ke ma3 shi msou2al"
- [ ] T007 [US1] Add ≥48 new verified Arabizi `spam` examples to `build_dataset.md` (target: 100 total spam/arabizi rows); use patterns: "rb7 jayeze", "click hon", "free dollar", "ta3a khod jaye"
- [ ] T008 [US1] Rebuild dataset: `python3 build_dataset.md && python3 dataset_english_large.md` from repo root; confirm CSV row count increases by ~196 and Arabizi per-cell counts are ≥100 (run `python3 -c "import pandas as pd; df=pd.read_csv('civic_intent_dataset.csv'); print(df[df.variety=='arabizi'].groupby('intent').size())"`)
- [ ] T009 [US1] Retrain bilingual classifier by running all cells in `notebooks/train_classifier_bilingual.ipynb`; commit updated notebook outputs (including the new Arabizi F1 metric)
- [ ] T010 [US1] Copy retrained artifact to `modelserver/artifacts/classifier.joblib`; record new SHA-256 in a comment in `eval_thresholds.yaml`
- [ ] T011 [US1] Update `evals/classifier_bilingual_results.json` with Phase 8 results (per-variety F1, artifact SHA-256, row counts, timestamp)
- [ ] T012 [US1] Update `eval_thresholds.yaml`: if measured `arabizi_f1 ≥ 0.90`, add gate `arabizi_f1: 0.90`; if below 0.90, add gate at `measured_value − 0.02` with a comment documenting the gap and reason
- [ ] T013 [US1] Verify CI classifier gate still passes with the retrained artifact: `python -m pytest tests/test_classifier/ -v`

**Checkpoint**: Arabizi F1 measured and gated; retrained artifact committed; US1 complete.

---

## Phase 4: User Story 2 — Arabic Name PII Redaction (Priority: P1) 🎯 MVP Track B

**Goal**: Add Arabic name regex to the PII redaction middleware; 5 Arabic name test cases pass with zero leaks in CI.

**Independent Test**: POST /chat with a message containing an Arabic full name; verify stored session turn contains `[NAME]` placeholder, not the original name.

### Tests for User Story 2 (safety-critical — write before implementation)

- [x] T014 [US2] In `tests/test_security/test_redaction.py`, add 5 Arabic name test cases:
  - `"اشتكي من محمد علي بسبب الكهرباء"` → must contain `[NAME]`, not `محمد علي`
  - `"أنا رنا خوري من بيروت"` → must contain `[NAME]`, not `رنا خوري`
  - `"أحمد الحسن قدم شكوى"` → must contain `[NAME]`, not `أحمد الحسن`
  - `"مياه الجنوب مشكلة"` → must NOT have `[NAME]` (civic phrase, not a name — verify no false positive)
  - `"كهرباء لبنان منقطعة"` → must NOT have `[NAME]` (institutional name — verify no false positive)
  - Confirm these tests FAIL before implementation
- [x] T015 [US2] Verify that existing English redaction test cases in `tests/test_security/test_redaction.py` still pass (no regression): run `python -m pytest tests/test_security/test_redaction.py -v` and confirm all pre-existing cases green

### Implementation for User Story 2

- [x] T016 [US2] In `api/middleware/redaction.py`, add the Arabic name pattern as a new `_PatternRecognizer` entry appended to the `_RECOGNIZERS` list (after the existing STREET_ADDRESS entry):
  ```python
  _PatternRecognizer(
      "ARABIC_NAME",
      r"[؀-ۿ]{3,}(?:\s+[؀-ۿ]{3,})+",
      "[NAME]",
  )
  ```
  Wrap the `recognizer.redact(result)` call in a `try/except Exception` that logs at DEBUG and continues — fail-safe per plan.md constraint
- [x] T017 [US2] Run `python -m pytest tests/test_security/test_redaction.py -v` and confirm all 5 new Arabic name cases pass and all existing cases still pass
- [x] T018 [US2] Run the full PII redaction CI gate: `python -m pytest tests/test_security/ -v -k "redaction"` — confirm zero failures

**Checkpoint**: Arabic names redacted from all downstream writes; PII CI gate passes; US2 complete.

---

## Phase 5: User Story 3 — Per-Widget JWT Key Rotation (Priority: P2)

**Goal**: Each widget has its own Vault-stored signing key; the rotate-key endpoint invalidates old tokens immediately; existing non-widget tokens are unaffected.

**Independent Test**: Issue token for widget A; rotate widget A's key; confirm old token returns 401; issue new token for widget A; confirm 200. Issue token for widget B; confirm still 200 after widget A rotation.

### Tests for User Story 3 (security-critical — write before implementation)

- [x] T019 [US3] In `tests/test_widget/test_token_service.py`, add test `test_rotate_key_invalidates_old_token`: issue token for a test widget; call rotate-key endpoint; attempt to use old token on an authenticated endpoint; assert 401
- [x] T020 [US3] In `tests/test_widget/test_token_service.py`, add test `test_rotate_key_does_not_affect_other_widget`: create two test widgets; rotate widget A key; confirm widget B's pre-rotation token still returns 200
- [x] T021 [US3] In `tests/test_widget/test_token_service.py`, add test `test_non_widget_token_unaffected`: issue a `tenant_admin` JWT (no `widget_id` claim); confirm it still validates correctly after a widget key rotation (uses `jwt_secret` path)
- [x] T022 [US3] Confirm the three new tests FAIL before implementation

### Implementation for User Story 3

- [x] T023 [US3] In `api/infra/vault.py`, add async helper `get_widget_signing_key(widget_id: uuid.UUID) -> str` that fetches `baladiya/widget/{widget_id}/signing_key` from Vault; wrap in `functools.lru_cache` (keyed on widget_id string, 128 entries); add `invalidate_widget_key_cache(widget_id)` to bust the cache on rotation
- [x] T024 [US3] In `api/core/security.py`, update `decode_token()` to implement the two-pass flow from `data-model.md §5`:
  - Step 1: `jwt.decode(token, options={"verify_signature": False})` to read `widget_id` from payload
  - Step 2: if `widget_id` present, call `vault.get_widget_signing_key(widget_id)` to fetch per-widget key; else use `settings.jwt_secret`
  - Step 3: `jwt.decode(token, key, algorithms=[...])` for full verified decode
  - Maintain full backward compatibility — tokens without `widget_id` claim use `jwt_secret` as before
- [x] T025 [US3] In `api/api/widget/token_service.py`, update `issue_token()` to sign with the per-widget Vault key instead of `settings.jwt_secret`: call `await vault.get_widget_signing_key(widget_id)` and use that key in `jwt.encode(claims, per_widget_key, ...)`
- [x] T026 [US3] In `api/api/admin/router.py`, add `POST /admin/widgets/{widget_id}/rotate-key` endpoint per `contracts/rotate_key.md`:
  - Auth: `Depends(require_tenant_admin)` — reject if caller's `tenant_id` ≠ widget's `tenant_id` (404 if not found, 403 if tenant mismatch)
  - Generate 32-byte random key: `secrets.token_hex(32)`
  - Write to Vault at `baladiya/widget/{widget_id}/signing_key`
  - Call `vault.invalidate_widget_key_cache(widget_id)` to immediately invalidate LRU cache
  - Emit `structlog` audit line: `widget.key.rotated` with `widget_id`, `tenant_id`, `actor_id`, `trace_id`
  - Return `{"rotated": True, "widget_id": str(widget_id)}`
- [x] T027 [US3] In `scripts/seed.py`, extend the startup seeding: for each active row in `widgets` table, if `baladiya/widget/{widget_id}/signing_key` is absent in Vault, write `settings.widget_signing_key` as the migration default (idempotent — skip if already present)
- [x] T028 [US3] Run the three new test cases: `python -m pytest tests/test_widget/ -v` — confirm all pass including the 3 new rotation tests and all 9 pre-existing widget tests

**Checkpoint**: Per-widget key rotation working; old tokens invalidated; non-widget tokens unaffected; US3 complete.

---

## Phase 6: User Story 4 — Live Eval Runs (Priority: P2)

**Goal**: Replace all pre-measurement placeholder thresholds in `eval_thresholds.yaml` with measured values; update `EVALS.md` with actual results.

**Independent Test**: All five previously-placeholder thresholds in `eval_thresholds.yaml` contain non-placeholder values with a measurement timestamp comment; CI gates pass.

### Implementation for User Story 4

- [ ] T029 [US4] Start the full docker-compose stack: `docker compose up -d api modelserver guardrails db redis` — confirm all services healthy via `docker compose ps`
- [ ] T030 [US4] Seed the RAG eval content: `python evals/seed_eval_content.py` — confirm 15 CMS entries embedded and queryable
- [ ] T031 [US4] Run RAG evaluation: `python evals/evaluate_rag.py --mode compare` — record `hit@5`, `MRR`, and `faithfulness` scores from the output; if Gemini quota exhausted, run with `--mode baseline` and note the limitation
- [ ] T032 [US4] Update `eval_thresholds.yaml`: replace `rag_hit_at_5`, `rag_mrr`, `rag_faithfulness` pre-measurement values with `measured − 0.02`; add inline comment with measured value, date, and run mode
- [ ] T033 [US4] Run agent evaluation: `python evals/evaluate_agent.py` — record `agent_tool_accuracy` and `workflow_handled_rate` from the output
- [ ] T034 [US4] Update `eval_thresholds.yaml`: replace `agent_tool_accuracy` and `workflow_handled_rate` pre-measurement values with `measured − 0.02`; add inline comment with measured value, date
- [ ] T035 [US4] Update `EVALS.md §3` (RAG evaluation) with the measured hit@5, MRR, faithfulness values and run timestamp
- [ ] T036 [US4] Update `EVALS.md §4` (agent evaluation) with the measured tool accuracy and workflow handled rate values and run timestamp
- [ ] T037 [US4] Bring stack down: `docker compose down`; confirm CI unit tests still pass without live stack: `python -m pytest tests/ -v --ignore=tests/test_rag --ignore=tests/test_agent -x`

**Checkpoint**: All thresholds measured; EVALS.md updated; US4 complete.

---

## Phase 7: User Story 5 — Defense Documentation (Priority: P2)

**Goal**: `DECISIONS.md`, `DATA.md`, and `modelserver/model_card.md` all contain the Phase 7 bilingual retrain results; no TBD rows remain.

**Independent Test**: Each of the three files contains the Phase 7 SHA-256 (`728a4b...`), per-variety F1 table, and an explicit Arabizi caveat.

### Implementation for User Story 5

- [x] T038 [P] [US5] In `DECISIONS.md`, add new section `## Arabic & Bilingual Decisions` then `### D-Arabic-001 — Single Bilingual Model vs Per-Language Models` defending the choice of a single bilingual Classical ML classifier. Include: (a) measured Phase 7 macro-F1 = 0.9980, ar_macro_f1 = 0.9507, arabizi_f1 = 0.8322; (b) comparison with hypothetical per-language approach (higher AR F1 but doubles artifact count, adds routing complexity, violates Constitution II "no scope creep"); (c) the HANDOFF.md §D10 note about validating session TTL from production logs
- [x] T039 [P] [US5] In `DATA.md`, update the dataset section with the 12,731-row breakdown table (varieties × intents), the per-cell AR counts table (msa/lebanese/arabizi × report/question/human/spam), and an explicit paragraph: "Arabizi rows are machine-seeded. F1 = 0.8322 on 41 test rows. Hand-verify before citing this number as reliable in a defense context."
- [x] T040 [P] [US5] In `modelserver/model_card.md`, update the `## Data` section to reflect 12,731 rows (replacing "547 rows") and the new Data SHA-256 (`5f3c9e95...`). Add a `### Phase 7 — Bilingual Retrain (2026-06-06)` subsection with: artifact SHA-256 `728a4bf1...`, per-variety F1 table (en=1.0000, msa=1.0000, lebanese=1.0000, arabizi=0.8322), macro-F1=0.9980, test n=2,525; compare with Phase 2 baseline row (macro-F1=0.8983, 547 rows). Update the `## Artifact` SHA-256 and size to Phase 7 values.

**Checkpoint**: All three defense documents updated with measured Phase 7 numbers; US5 complete.

---

## Phase 8: User Story 6 — Real Resident Text Evaluation (Priority: P3)

**Goal**: EN classifier evaluated on ≥20 non-template resident messages; real-text F1 recorded in model card with honest caveat if below template F1.

**Independent Test**: `modelserver/model_card.md` contains a `### Real-Text EN Evaluation` subsection with a result row (any F1 value acceptable — gate is documentation completeness).

### Implementation for User Story 6

- [x] T041 [US6] Collect ≥20 non-template EN civic messages (use NYC 311 dataset at `/tmp/311_data/nyc_311_2025.csv` if still present, else manually write 20+ paraphrased messages not derived from `dataset_english_large.md` templates); label each with intent (`report`/`question`/`human`/`spam`) and save to `evals/real_text_en_sample.json` as `[{"text": "...", "intent": "..."}]`
- [x] T042 [US6] Write eval script `evals/evaluate_real_text.py` that: loads `modelserver/artifacts/classifier.joblib`, runs predictions on `evals/real_text_en_sample.json`, reports macro-F1 and per-class F1 to stdout; run it: `python evals/evaluate_real_text.py`
- [x] T043 [US6] In `modelserver/model_card.md`, add a `### Real-Text EN Evaluation (2026-06-06)` subsection: sample size (n=≥20), source description (NYC 311 or paraphrased), macro-F1 result; if F1 < 1.0 (template F1), add caveat: "Template test-set F1 reflects template memorisation. Real-text F1 is the more reliable generalisation estimate. Further data collection recommended before production deployment."

**Checkpoint**: Real-text F1 documented; model card complete; US6 done.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Final CI validation, HANDOFF.md update, and git commit.

- [ ] T044 [P] Run full test suite to confirm no regressions: `python -m pytest tests/ -v -x --ignore=tests/test_rag --ignore=tests/test_agent` (exclude live-stack-dependent tests)
- [ ] T045 [P] Update `HANDOFF.md`: change `Active feature` to `009 (next — not yet specified)`, update `Status` to `Phases 1–8 complete`, add Phase 8 summary row to §2, update CI gate table in §5 to show Phase 8 measured values, update §8 with any remaining open items
- [ ] T046 Verify `eval_thresholds.yaml` has no remaining `# pre-measurement` or `# placeholder` comments — all thresholds must be measured values or explicitly documented as "best achieved" with a reason
- [ ] T047 Commit all Phase 8 changes with message: `feat(008): hardening & evals — arabizi F1 gate, Arabic PII redaction, per-widget JWT keys, live eval thresholds`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Empty — skipped
- **Phase 3 (US1 — Arabizi)**: After Phase 1; independent of all other user stories
- **Phase 4 (US2 — PII)**: After Phase 1; independent of all other user stories; **run in parallel with Phase 3**
- **Phase 5 (US3 — JWT rotation)**: After Phase 1; independent of US1 and US2
- **Phase 6 (US4 — Live evals)**: After Phase 1; requires docker stack; independent of US1–US3
- **Phase 7 (US5 — Docs)**: After Phase 1; T038 depends on knowing Phase 8 arabizi_f1 result (T012); T039–T040 can start immediately
- **Phase 8 (US6 — Real text)**: After Phase 1; independent of all other stories
- **Phase 9 (Polish)**: After all user stories complete

### User Story Dependencies

- **US1**: Independent — start after Phase 1
- **US2**: Independent — start after Phase 1 (parallel with US1)
- **US3**: Independent — start after Phase 1
- **US4**: Independent — start after Phase 1 (requires docker stack running)
- **US5 (T038)**: Soft dependency on US1 result (needs Phase 8 arabizi_f1 number for §D-Arabic-001); T039 and T040 are fully independent
- **US6**: Independent — start after Phase 1

### Within Each User Story

- **US1**: T004–T007 (data addition) can run in parallel → T008 (rebuild) → T009 (retrain) → T010 (artifact) → T011–T012 (results + threshold) → T013 (CI verify)
- **US2**: T014–T015 (test setup) → T016 (implementation) → T017–T018 (verify)
- **US3**: T019–T022 (test setup) → T023 (vault helper) → T024 (decode_token) → T025 (token_service) → T026 (rotate endpoint) → T027 (seed.py) → T028 (verify)
- **US4**: T029–T030 (stack + seed) → T031 (RAG eval) → T032 (thresholds) → T033 (agent eval) → T034 (thresholds) → T035–T036 (EVALS.md) → T037 (teardown)
- **US5**: T038–T040 all [P] — run in parallel
- **US6**: T041 → T042 → T043 sequential

### Parallel Opportunities

- Phase 3 (US1) and Phase 4 (US2) run entirely in parallel (no shared files)
- Phase 5 (US3) and Phase 6 (US4) run entirely in parallel (no shared files)
- Phase 7 T039 and T040 run in parallel with each other and with Phase 8 (US6)
- Within US1: T004–T007 (data addition to `build_dataset.md`) can be drafted in parallel but must be merged into the single file before T008
- Within US5: T038, T039, T040 are all [P] — different files (DECISIONS.md, DATA.md, model_card.md)

---

## Parallel Execution Examples

### US1 + US2 (both P1 — run together)

```bash
# Stream A: Arabizi expansion (US1)
# T004–T007: Add rows to build_dataset.md
# T008: python3 build_dataset.md && python3 dataset_english_large.md
# T009: Run notebook, commit outputs
# T010–T013: Artifact, thresholds, CI

# Stream B: Arabic PII (US2) — fully independent files
# T014: Write failing Arabic name test cases to tests/test_security/test_redaction.py
# T016: Add ARABIC_NAME pattern to api/middleware/redaction.py
# T017–T018: Run tests, verify CI
```

### US5 (Defense Docs — all parallel)

```bash
# All three in parallel (different files):
Task T038: DECISIONS.md — add §D-Arabic-001
Task T039: DATA.md — add 12,731-row breakdown
Task T040: modelserver/model_card.md — add Phase 7 row
```

---

## Implementation Strategy

### MVP First: US1 + US2 (both P1)

1. Complete Phase 1: Setup (verify environment)
2. Run US1 (Arabizi) and US2 (Arabic PII) in parallel
3. **STOP and VALIDATE**: Arabizi F1 gated; Arabic names redacted in CI
4. Report P1 items complete

### Incremental Delivery

1. Setup → US1 + US2 in parallel → P1 complete
2. US3 + US4 in parallel → P2 complete (key rotation + live evals)
3. US5 docs (parallel internally) → P2 docs complete
4. US6 real-text eval → P3 complete
5. Phase 9 polish → Phase 8 done

### Solo Strategy (one developer)

Priority order:
1. US2 (Arabic PII — fastest, safest, no external deps) → 1–2 hours
2. US1 (Arabizi expansion — data work + retrain) → 2–4 hours
3. US5 T039–T040 (DATA.md + model card) → 1 hour (while retrain runs)
4. US3 (JWT rotation — most code) → 3–4 hours
5. US4 (Live evals — requires docker stack) → 1–2 hours
6. US5 T038 (DECISIONS.md §D-Arabic-001 — needs arabizi_f1 from US1) → 30 min
7. US6 (Real-text eval) → 1–2 hours
8. Phase 9 (polish + HANDOFF.md) → 30 min

---

## Notes

- [P] tasks = different files, no shared state dependencies
- [Story] label maps each task to its user story for traceability
- US1 retrain (T009) is the longest single task — start it early and run US2/US5 T039–T040 while the notebook runs
- Arabizi expansion rows (T004–T007): mark as `# machine-seeded` in a comment if generated programmatically, or verify manually and leave no comment
- All Vault operations in US3 must be wrapped in `try/except hvac.exceptions.VaultError` — fail-closed (503) if Vault unreachable
- If docker stack is unavailable for US4, record "eval not run — stack unavailable" in EVALS.md with a timestamp and leave pre-measurement thresholds as-is with a note
- Commit after each user story completes (not after individual tasks) to keep the git history clean
