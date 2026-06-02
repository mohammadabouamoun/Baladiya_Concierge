# Tasks: Arabic Bilingual Layer

**Branch**: `007-arabic` | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

---

## Phase 1: Dataset Verification

- [ ] **T-001** Hand-verify all Arabic rows in `civic_intent_dataset.csv` — check Lebanese phrasing, Arabizi authenticity, intent label correctness; log: "Drafted N, corrected M, relabelled K" in model card
- [ ] **T-002** Run `/rebuild-dataset` skill — check per-cell counts; flag thin cells (< 50 examples); check for near-duplicates

---

## Phase 2: Bilingual Classifier Retrain

- [ ] **T-010** Update training notebook `notebooks/train_classifier_bilingual.ipynb` — retrain classical pipeline on full bilingual CSV; report per-variety F1 (en, msa, lebanese, arabizi) on held-out test
- [ ] **T-011** Commit per-variety F1 table to `EVALS.md`; update model card with new artifact SHA-256
- [ ] **T-012** CI gate: add `ar_macro_f1` threshold to `eval_thresholds.yaml`; assert both `en_macro_f1` and `ar_macro_f1` pass

---

## Phase 3: Language Detection & Prompt Routing (US1)

- [ ] **T-020** `api/services/lang_detect_service.py` — `detect(text)` → `LangDetectResult(lang, variety, confidence)`; catch all exceptions, default to `{lang: "en", variety: "en", confidence: 0.0}`
- [ ] **T-021** Wire `lang_detect_service.detect()` into `router_service.py` before `modelserver.classify()` call
- [ ] **T-022** `prompts/system_ar.md` — Arabic system prompt; instructs LLM to respond in the resident's dialect; `{{persona}}` placeholder for tenant persona
- [ ] **T-023** `api/services/prompt_service.py` — `select_system_prompt(lang, tenant_persona)` → loads `system_ar.md` when `lang == "ar"`, `system_en.md` otherwise; English path never imports `system_ar.md`

---

## Phase 4: Arabic RAG Preference (US1)

- [ ] **T-030** Update `rag_service.rag_search()` — when `lang == "ar"`, add metadata filter boost for `cms_chunks.metadata.lang == "ar"`; fallback to English chunks if no Arabic chunks retrieved
- [ ] **T-031** [P] Update Streamlit CMS page — expose `lang` field (en/ar radio) when creating/editing entries

---

## Phase 5: Evals & Additive Guarantee (US2 + US3)

- [ ] **T-040** `tests/test_arabic/test_additive_guarantee.py` — simulate empty Arabic dataset: English macro-F1 unchanged (±1pp), no code exception, `lang_detect` defaults to en, `select_system_prompt("en", ...)` does not load system_ar.md
- [ ] **T-041** [P] `tests/test_arabic/test_lang_detect.py` — unit tests for lang_detect: Arabic MSA → ar/msa; Arabizi → ar/arabizi; unknown → en/en; exception → en/en
- [ ] **T-042** [P] `tests/test_arabic/test_prompt_routing.py` — `lang == "ar"` → system_ar.md loaded; `lang == "en"` → system_en.md loaded; no cross-dependency
- [ ] **T-043** CI: `ar_macro_f1` gate added to CI pipeline alongside `en_macro_f1`

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

**Gate**: Both `en_macro_f1` and `ar_macro_f1` CI gates pass; additive guarantee test passes; Arabic end-to-end pipeline verified manually.
