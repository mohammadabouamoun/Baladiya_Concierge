# Implementation Plan: Arabic Bilingual Layer

**Branch**: `007-arabic` | **Date**: 2026-06-02 | **Spec**: [spec.md](./spec.md)

## Summary

Layer Arabic support additively on the working English product: hand-verify the Arabic dataset rows, retrain the classifier with bilingual data, wire language detection into the router, select the Arabic prompt variant, add soft same-language preference in RAG, and report per-language/per-variety F1.

## Technical Context

**Language/Version**: Python 3.11

**Primary Dependencies**: langdetect (or langid) — lightweight, no model weights; re-uses all existing services (modelserver, rag_service, router_service)

**Storage**: No new tables; `cms_entries.lang` field already exists; classifier retrained offline

**Testing**: pytest; additive guarantee test (remove Arabic rows → English CI gates still pass); per-variety F1 in CI

**Target Platform**: `modelserver` (retrained artifact); `api` (lang detection + prompt routing)

**Performance Goals**: Language detection < 5ms p95; no regression in English classification latency or F1

**Constraints**: No English code path depends on Arabic resource; if Arabic data absent → defaults to English; langdetect failure → default to English (never raise exception); Arabic F1 threshold lower than English but must be committed in eval_thresholds.yaml

## Constitution Check

- [x] Arabic is additive — zero English code path depends on Arabic resource existing
- [x] Language detection failure → default to English (additive guarantee)
- [x] Per-variety F1 committed in EVALS.md before claiming Arabic works
- [x] Arabic dataset hand-verified; model card logs corrections

## Project Structure

```text
api/
├── services/
│   └── lang_detect_service.py  ← detect(text) → {lang, variety, confidence}; default to en on failure
└── services/
    └── prompt_service.py       ← select_prompt(lang) → prompts/system_en.md | system_ar.md

prompts/
├── system_en.md                ← already exists from phase 004
└── system_ar.md                ← Arabic system prompt; instructs LLM to respond in resident's dialect

notebooks/
└── train_classifier_bilingual.ipynb  ← retrain with full bilingual CSV; report per-variety F1

evals/
└── classifier_bilingual_results.json  ← macro-F1 breakdown by lang + variety
```

## Language Detection Logic

```python
async def detect(text: str) -> LangDetectResult:
    try:
        lang = langdetect.detect(text)          # returns ISO 639-1 code
        variety = infer_variety(text, lang)     # heuristic: arabizi char patterns → "arabizi"
        return LangDetectResult(lang=lang, variety=variety, confidence=...)
    except Exception:
        return LangDetectResult(lang="en", variety="en", confidence=0.0)  # additive guarantee
```

## Prompt Routing

```python
def select_system_prompt(lang: str, tenant_persona: str) -> str:
    template = load_prompt("system_ar" if lang == "ar" else "system_en")
    return template.replace("{{persona}}", tenant_persona)
```

No Arabic resource is loaded if `lang != "ar"` — the English path never touches `system_ar.md`.

## Variety Detection Heuristic

Arabizi is detected by the presence of number substitutions (2, 3, 5, 6, 7, 8, 9) adjacent to Latin letters in an otherwise Arabic-context message. Lebanese dialect distinguished from MSA by presence of Lebanese lexical markers (common Lebanese words vs MSA equivalents). These heuristics are rough — the variety feature improves classifier F1 but is not load-bearing for routing.

## Additive Guarantee Test

```python
def test_additive_guarantee():
    # Remove all ar rows from the training CSV
    # Retrain classifier
    # Assert: English macro-F1 unchanged (within ±1pp)
    # Assert: no ImportError, no FileNotFoundError
    # Assert: lang_detect("hello") returns LangDetectResult(lang="en", ...)
    # Assert: select_system_prompt("en", ...) returns English prompt without touching system_ar.md
```
