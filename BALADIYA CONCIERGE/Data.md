# DATA.md — Civic Intent Dataset (router/classifier)

Labelled intent data for the **router** (Design C). It is **separate from the tenant CMS/RAG corpus** —
this set never gets embedded into pgvector; it only trains and evaluates the intent classifier.

## Schema

| column | values | notes |
|---|---|---|
| `id` | `{lang}-{variety}-{n}` | stable row id |
| `text` | string | the raw message a resident might type |
| `lang` | `ar` \| `en` | top-level language |
| `variety` | `en` \| `msa` \| `lebanese` \| `arabizi` | register/script — lets you report **per-variety F1** |
| `intent` | `report` \| `question` \| `human` \| `spam` | the router label |
| `category` | `roads, water, electricity, waste, permits, taxes, environment, general, none` | civic domain; `none` for `human`/`spam` |
| `split` | `train` \| `test` | deterministic (hash of `text`), ~20% test, no leakage |

### Intent → router action
| intent | action | gate |
|---|---|---|
| `report` | `capture_request` | the side-effecting write — schema-validate + rate-limit |
| `question` | `rag_search` then answer | tenant-filtered retrieval |
| `human` | `escalate` | open a ticket row |
| `spam` | drop | dropped **before** any write |

## Provenance (be honest about this at the defense)

- **Machine-drafted seed, human-owned.** These rows were drafted with an LLM, then are meant to be
  **read, corrected, and signed off by you**. The spec demands a *hand-curated, hand-verified* Arabic set —
  a generated CSV alone does not satisfy that. Treat this as the starting scaffold, not the final dataset.
- **What to verify, per row:** Is the Lebanese phrasing natural (not MSA in disguise)? Is the Arabizi how
  people actually type (3/7/2/5/9 substitutions, not transliteration)? Is the intent label unambiguous?
  Is `report` vs `question` correct (a *report* asks for an action; a *question* asks for information)?
- Log your edits. "Drafted N rows, hand-corrected M, relabelled K" is a sentence your model card and your
  defense both want.

## Splitting & leakage

- `split` is derived from `sha1(text) % 5 == 0 → test`. It is **deterministic** so the held-out test is
  stable across runs, and it keys on `text` so near-duplicates don't straddle the train/test wall.
- Before training, **de-duplicate** and scan for near-duplicates across the split. Two paraphrases of the
  same complaint on opposite sides of the wall is leakage and inflates your F1.

## Class balance (current seed)

~209 rows: EN 58 · MSA 51 · Lebanese 55 · Arabizi 45. Intents: report 74 · question 74 · human 30 · spam 31.

This is enough to *stand up* the pipeline and prove the additive design. It is **not** enough to trust the
per-variety Arabic F1 yet. Grow each `(intent × variety)` cell toward **50–100 verified examples** before you
quote Arabic numbers as real. `human` and `electricity` are the thinnest cells — fill those first.

## How it plugs into the spec

- **Features that survive Arabizi:** prefer **char n-grams (3–5)** in your TF-IDF, optionally alongside word
  n-grams. Char n-grams handle Arabizi and Lebanese spelling variation far better than word tokens.
- **Language/variety detect** is a feature, not a fork: detect `lang` first; on failure the system defaults to
  English and still runs (the additive guarantee). You can also feed `variety` as a categorical feature.
- **Three-way comparison (Design C):** train classical (TF-IDF + LogReg/linear SVM) → `joblib`; optional small
  DL → `ONNX`; LLM zero-shot via your API. Compare macro-F1, per-class F1, **per-variety F1**, latency, cost on
  this held-out test. Commit the table; ship one; defend it.
- **Confidence threshold:** the spec's hard question is the nuanced Arabic turn routed confidently down the cheap
  path and answered wrong. Calibrate a per-intent confidence floor on this test set; below it, fall through to the
  agent rather than answering directly. Fail *safe* (escalate), not *cheap*.

## Models & API Keys (LLM + embeddings)

Two hosted keys, each with a distinct job. **No torch, no fine-tuning — every call here is a hosted API.**
(For the formal submission, mirror this block into `DECISIONS.md` and back each choice with a number.)

### Keys
- `GEMINI_API_KEY` — Google AI Studio free tier. Used for **embeddings** and as the **primary LLM**.
- `GROQ_API_KEY` — GroqCloud free tier (OpenAI-SDK compatible). Used as the **fallback LLM only**.

Resolve both from **Vault**, not `.env` (spec Standard 5). `.env` holds only the Vault root token and ports.

### Embeddings — Gemini ONLY, singular and permanent
- **Model:** `gemini-embedding-001` (text, GA, multilingual 100+ langs, top of MTEB-multilingual, free-tier).
  `gemini-embedding-2` exists but is multimodal; for text-only civic RAG, `001` is the right pick.
- **Dimensions:** default 3072, truncatable (MRL) to 1536 or 768. **Pick one and pin it** — e.g. `1536` —
  and set the pgvector column to `vector(1536)`. Changing it later means re-embedding the entire corpus.
- **HARD RULE — embeddings never fall back.** The whole pgvector table lives in ONE model's vector space.
  If a query were ever embedded by a different model, retrieval returns garbage. Groq does **not** do
  embeddings here, ever. The embedding model is a permanent decision, unlike the LLM.

### Primary LLM — Gemini (free tier)
- **Model:** `gemini-2.5-flash` (strong multilingual, free tier). Use `gemini-2.5-flash-lite` if you need
  the higher RPM during the live demo. **Do not** rely on `gemini-2.5-pro` — it's trial-only on free
  (~50 requests/day).
- Handles EN and MSA well, Lebanese solidly; Arabizi is its weakest register (true of every model).

### Fallback LLM — Groq (free tier)
- **Agent fallback (needs tool-calling):** `llama-3.3-70b-versatile` — quality tier, supports function calling.
  (`llama-3.1-8b-instant` is the high-RPD workhorse if you want a cheaper text-only fallback.)
- **Arabic-specialist candidates to TEST:** `mistral-saba-24b` and `allam-2-7b` — Arabic-oriented; verify
  tool-calling before putting one behind the agent loop (they may be better as answer/RAG models than as
  tool-callers).

### Rules wiring these together
- **Pick the primary by a number, not by reputation.** Run the Design-C LLM zero-shot baseline on *both*
  `gemini-2.5-flash` and a Groq Arabic model; compare **per-variety F1** (esp. Arabizi). The winner is primary,
  the other is fallback. If a Groq Arabic model beats Flash on Arabizi, flip them — that's the defensible call.
- **Fallback is a documented resilience path, not free scope.** Two LLMs = two behaviors to guardrail and eval.
  The red-team gate and tool-selection eval must hold for whichever model can reach the agent. Wrap the Gemini
  client in `tenacity` retry-with-backoff; trip over to Groq only on sustained failure / 429s after retries.
- **PII redaction happens BEFORE any call leaves the service** — same rule for Gemini and Groq. National IDs,
  Lebanese phone formats, names, addresses, emails are redacted first (spec Design E).
- **Per-tenant cost attribution tags the provider too** — a Gemini call and a Groq call are both stamped with
  `tenant_id` *and* which model served it.
- **Free-tier note for the defense:** this project runs on free tiers throughout. Gemini's free tier may use API traffic for model training — this is a known constraint disclosed to tenants and residents via the widget's privacy notice. See `SECURITY.md §Free-Tier API Data Usage`.

> Model identifiers and free-tier limits drift. Before tagging `v0.1.0-final`, re-check the live model names
> and quotas at `ai.google.dev` and `console.groq.com` so nothing in here is stale at submission.

## Extending

Edit `build_dataset.md` and re-run, or append verified rows to the CSV. Keep the same columns. Re-hash the
split after any large addition so the test set stays ~20% and stratified.
