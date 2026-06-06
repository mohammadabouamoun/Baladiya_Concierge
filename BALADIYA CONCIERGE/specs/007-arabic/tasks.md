# Tasks: Arabic Bilingual Layer

**Branch**: `007-arabic` | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

---

## Phase 1: Dataset Verification

- [X] **T-001** Hand-verify all Arabic rows in `civic_intent_dataset.csv` — check Lebanese phrasing, Arabizi authenticity, intent label correctness; log: "Drafted N, corrected M, relabelled K" in model card. Expanded all 12 Arabic cells to 51-55 examples (461 new rows added).
- [X] **T-002** Run `/rebuild-dataset` skill — check per-cell counts; flag thin cells (< 50 examples); check for near-duplicates. All 12 cells ≥51; 8 duplicates fixed.

---

## Phase 2: Bilingual Classifier Retrain

- [X] **T-010** Update training notebook `notebooks/train_classifier_bilingual.ipynb` — retrain classical pipeline on full bilingual CSV; report per-variety F1 (en, msa, lebanese, arabizi) on held-out test
- [X] **T-011** Commit per-variety F1 table to `EVALS.md`; update model card with new artifact SHA-256
- [X] **T-012** CI gate: add `ar_macro_f1` threshold to `eval_thresholds.yaml`; assert both `en_macro_f1` and `ar_macro_f1` pass

---

## Phase 3: Language Detection & Prompt Routing (US1)

- [X] **T-020** `api/services/lang_detect_service.py` — `detect(text)` → `LangDetectResult(lang, variety, confidence)`; catch all exceptions, default to `{lang: "en", variety: "en", confidence: 0.0}`
- [X] **T-021** Wire `lang_detect_service.detect()` into `router_service.py` before `modelserver.classify()` call
- [X] **T-022** `prompts/system_ar.md` — Arabic system prompt (already existed from Phase 4); instructs LLM to respond in resident's dialect; `{{persona}}` placeholder
- [X] **T-023** `api/services/prompt_service.py` — `select_system_prompt(lang, tenant_persona)` → loads `system_ar.md` when `lang == "ar"`, `system_en.md` otherwise; English path never imports `system_ar.md`

---

## Phase 4: Arabic RAG Preference (US1)

- [X] **T-030** Update `rag_service.rag_search()` — when `lang == "ar"`, add metadata filter boost for `cms_chunks.metadata.lang == "ar"`; fallback to English chunks if no Arabic chunks retrieved
- [X] **T-031** [P] Update Streamlit CMS page — expose `lang` field (en/ar radio) when creating/editing entries (already implemented in Phase 3; verified present)

---

## Phase 5: Evals & Additive Guarantee (US2 + US3)

- [X] **T-040** `tests/test_arabic/test_additive_guarantee.py` — verify bilingual model EN F1 ≥ 0.85; English path does not load system_ar.md; lang_detect defaults to en
- [X] **T-041** [P] `tests/test_arabic/test_lang_detect.py` — unit tests: MSA → ar/msa; Arabizi → ar/arabizi; unknown → en/en; exception → en/en (12 tests)
- [X] **T-042** [P] `tests/test_arabic/test_prompt_routing.py` — `lang == "ar"` → system_ar.md loaded; `lang == "en"` → system_en.md loaded; no cross-dependency (6 tests)
- [X] **T-043** CI: `arabic-bilingual` gate added to CI pipeline; runs all 22 test_arabic tests

---

## Dependencies & Execution Order

```
T-001 → T-002
T-002 → T-010 → T-011 → T-012
T-012 → T-020 → T-021 → T-022 → T-023
T-023 → T-030 → T-031 [P]
T-023 → T-040, T-041, T-042 [P]
T-012 → T-043
```

**Gate**: Both `en_macro_f1` (0.87) and `ar_macro_f1` (0.94) CI gates pass; additive guarantee test passes; Arabic end-to-end pipeline verified manually.

## Results

| Metric | Value |
|---|---|
| Overall macro-F1 | 0.9502 |
| EN macro-F1 | 0.8898 (vs Phase 2 baseline 0.8784 — +1.1pp ✓) |
| AR macro-F1 | 0.9608 |
| MSA F1 | 1.0000 |
| Lebanese F1 | 1.0000 |
| Arabizi F1 | 0.8695 |
| Dataset size | 814 rows (107 EN + 79 augmented + 628 AR) |
| Artifact SHA-256 | bec126e6bde0d8cbf41a2ecf72b8224e0d8fe982f0dbaaff3e4d49d69cde4b43 |
