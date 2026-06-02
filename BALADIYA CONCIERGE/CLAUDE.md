
# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**Baladiya Concierge** — multi-tenant civic SaaS. Any municipality signs up, gets an isolated tenant, and embeds a bilingual (Arabic + English) AI agent on its public site. See `BALADIYA_CONCIERGE.md` for the full spec.

## Hard Constraints — Never Violate

- **No torch in any container.** Training is offline (notebook/Colab), exported to `joblib` (sklearn) or `ONNX`. The `modelserver` runs only `onnxruntime` + `scikit-learn` + `numpy`. Images must stay under ~500 MB.
- **Isolation is the grade.** Every DB query must scope by `tenant_id`. Postgres RLS is the enforced wall; the repository layer adds a second filter (`.filter(tenant_id == ...)`). A query missing the tenant filter is a bug, not a style issue.
- **Reset the RLS session variable at the end of every request.** Connections are pooled — a leftover `tenant_id` is a cross-tenant leak.
- **`tenant_id` comes from the verified JWT token only — never from a client-supplied body field.** Trusting a body field is a one-line cross-tenant breach.
- **Widget auth = signed short-lived token + server-side origin check. CORS/CSP are depth, not the boundary.**
- **Arabic is additive, English is load-bearing.** No English code path may depend on an Arabic resource. If Arabic data is absent, language detection returns English and everything still runs unchanged.
- **Spam is dropped by the classifier before any write.** `capture_request` never receives a spam-classified message.

## Tech Stack (already decided — don't propose alternatives)

| Layer | Technology |
|---|---|
| API | FastAPI, fully async, `httpx`, async SQLAlchemy |
| Admin UI | Streamlit (tenant admin + platform manager) |
| Widget | React (Vite), RTL-aware |
| DB | PostgreSQL 16 + pgvector + RLS |
| Session/Cache | Redis 7 |
| Blob | MinIO |
| Secrets | HashiCorp Vault — never in `.env` beyond the Vault root token + ports |
| Guardrails | NeMo Guardrails sidecar, called over HTTP with service credential |
| Classifier | sklearn/joblib (classical) + optional ONNX — served by lean `modelserver` HTTP service |
| Embeddings | `gemini-embedding-001` (Gemini API, pinned at 1536 dims, MTEB-multilingual; NEVER falls back — entire pgvector corpus lives in one model's vector space) |
| LLM (primary) | `gemini-2.5-flash` via Gemini API — EN + MSA + Lebanese; wrap in `tenacity` retry-with-backoff |
| LLM (fallback) | Groq `llama-3.3-70b-versatile` — tool-calling capable; activated only on sustained Gemini failure / 429s after retries |
| Vector store | pgvector, tenant-filtered at query time |

## Architecture

```
inbound msg → CLASSIFIER ROUTER ──easy──> workflow handles it directly
                                 ──hard──> tool-calling AGENT picks tools (bounded loop)

AGENT tools: rag_search | capture_request | escalate   (all scoped by tenant_id)

modelserver (onnxruntime/sklearn) ← called over HTTP, never imported
guardrails sidecar ← platform rails locked + tenant rails configurable
pgvector ← tenant-filtered at query time (part of isolation, not afterthought)
Redis ← session memory scoped per conversation, with explicit TTL
```

- The classifier is a **separate HTTP service** — import it via HTTP, not as a Python module.
- `capture_request` is an unauthenticated LLM-triggered write: schema-validate payload with Pydantic, rate-limit per visitor/session, scope write to token's tenant.
- Cap tool-call iterations and tokens per turn (cost control + safety control).
- Platform rails (injection, jailbreak, cross-tenant refusal, PII redaction) are mandatory and identical for every tenant. Tenant rails (topics, tone, persona, enabled tools) are configurable. A tenant can never dial down the platform wall.

## Dataset: `civic_intent_dataset.csv`

Schema: `id | text | lang | variety | intent | category | split`

| Column | Values |
|---|---|
| `lang` | `ar` \| `en` |
| `variety` | `en` \| `msa` \| `lebanese` \| `arabizi` |
| `intent` | `report` \| `question` \| `human` \| `spam` |
| `category` | `roads` \| `water` \| `electricity` \| `waste` \| `permits` \| `taxes` \| `environment` \| `general` \| `none` |
| `split` | deterministic: `sha1(text) % 5 == 0 → test` (~20%, no leakage) |

Rebuild: `python3 build_dataset.md` — this is a Python script with a `.md` extension.

This dataset trains the **classifier only** — it is never embedded into pgvector. Current size: ~209 rows. Grow each `(intent × variety)` cell toward 50–100 verified examples before quoting Arabic F1 as reliable. `human` and `electricity` are the thinnest cells.

## Roles

- **Platform Manager** — provisions/suspends/erases tenants; reads aggregate cost/usage. Never reads tenant conversations. All tenant-boundary crossings are audit-logged with actor id.
- **Tenant Admin** — configures its own agent, widgets, guardrails; sees its own requests only.
- **Visitor** — anonymous resident using the chat widget.

## Classifier: Three-Way Comparison Required

Train three approaches and commit the comparison table before choosing one to ship:
1. Classical ML (TF-IDF + LogReg or linear SVM) → `joblib`
2. Optional small DL model → `ONNX`
3. LLM zero-shot via API

Report: macro-F1, per-class F1, per-variety F1 (EN/MSA/Lebanese/Arabizi), latency, cost on the held-out test set. Defend the shipping choice in `DECISIONS.md`.

Char n-grams (3–5) in TF-IDF handle Arabizi and Lebanese spelling variation better than word tokens.

## Engineering Standards

- **Async all the way:** every route, LLM call, embedding call, DB query, Redis call uses `async`.
- **DI via `Depends()`:** DB session, LLM client, current actor, retriever, redactor, per-request tenant context. No globals — this is what lets red-team and redaction tests inject fakes.
- **Config:** `pydantic-settings`, `extra="forbid"`. Secrets from Vault. `.env` holds only Vault root token and ports.
- **Logging:** `structlog` with `trace_id` + `tenant_id` on every log line. Never `print()`.
- **Code layers:** `api / services / repositories / domain / infra`. Thin `main.py`.
- **Errors:** `tenacity` retries on transient errors only. Tools return structured `ToolError` — agent recovers, never 500s. Audit path failure never breaks the resident's reply.

## CI Gates (all must pass — thresholds in `eval_thresholds.yaml`)

1. **Classifier** — macro-F1 on held-out test, per-language reported
2. **Agent tool-selection** — 15 labelled examples
3. **RAG** — 15 triples: hit@k, MRR, faithfulness, answer relevancy
4. **Red-team** — injection + cross-tenant probes: all must be refused

Plus: **redaction test** (fake national ID/phone in chat never appears unredacted anywhere) and **stack smoke test** (`docker-compose up` from fresh clone).

## Required Docs

`DESIGN.md`, `SPEC.md`, `DECISIONS.md`, `RUNBOOK.md`, `EVALS.md`, `SECURITY.md`, `DATA.md`

Every architectural choice in `DESIGN.md` / `DECISIONS.md` must be backed by a measured number on the golden/test set.

<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan
<!-- SPECKIT END -->
