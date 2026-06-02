# Baladiya Concierge — Final Project Spec
**AIE Program | Final Project** · كونسيرج البلدية · Arabic + English · ML + LLM Engineering · `v0.1.0-final`

A **multi-tenant civic SaaS**. Any municipality signs up, manages its services content in a **CMS**, and embeds a bilingual **(Arabic + English)** agent on its public site. The agent **acts**: it routes requests with a **classifier you trained**, retrieves from the tenant's own content, captures requests, and escalates to staff. **No fine-tuning.** Trained offline, served lean (sklearn / ONNX, no torch). The wall between tenants is the grade.

> **Scope** — Your repo. Your code. Build English-first so the system always works; Arabic is layered in as an additive second language. Tenant isolation, a router + one acting agent, lean RAG, guardrails, and right-to-erasure. You answer every question at the defense.

> **The two hard problems** — Isolation (a visitor on Tenant A can never reach Tenant B's data or your prompt) and the bilingual data (English always works; Arabic enriches it without ever being load-bearing).

---

## The Mission

Build **Baladiya Concierge**: a SaaS where any municipality signs up, gets an isolated tenant, manages its civic-services content in a CMS, and embeds an AI agent on its public site. A resident opens the widget and asks — in Arabic or English — to report a pothole, ask which department handles water cut-offs, or reach a human. The agent doesn't just answer: it **routes** each message with a classifier you trained, **retrieves** from that municipality's own content, **captures** the request as a lead/ticket, and **escalates** to staff when it's out of depth. Each tenant configures its agent's persona, enabled tools, and guardrails. The same CMS content powers both the public site and the agent's knowledge.

**The hard problem is isolation.** A resident chatting on Municipality A must never extract Municipality B's data or your system prompt — even on purpose. Get that wrong and nothing else matters.

**No fine-tuning. No torch in any container.** The LLM and embeddings are hosted-API calls. Your own classifier is trained offline (notebook / Colab) and served lean — classical ML via `scikit-learn` + `joblib`, an optional small DL model via `ONNX` + `onnxruntime`. Images stay under ~500 MB and build in seconds. This is the honest stack for an early-stage SaaS and it runs on a modest laptop.

**Arabic is additive, never load-bearing.** The system is built and proven in English first; Arabic is layered on as a parallel data stream and a language-detection step. If the Arabic work stalls, the English product still classifies, retrieves, acts, and ships — nothing breaks.

---

## Architecture at a Glance

| Tenant Admin (Streamlit) | Public site + embedded Widget (React, RTL-aware) |
|---|---|
| manage CMS content · configure agent + guardrails · view requests · copy embed snippet | resident chats with the agent (AR/EN) · signed per-widget token, not CORS |

One FastAPI backend · Platform Manager provisions / suspends / erases tenants.

```
inbound msg → CLASSIFIER ROUTER ──easy──> workflow handles it directly
                                 ──hard──> tool-calling AGENT picks tools (bounded loop)

AGENT → [ rag_search | capture_request | escalate ]   scoped by tenant_id
        platform rails (locked) + tenant rails (config)

modelserver (onnxruntime / sklearn) = the router · pgvector (tenant-filtered)
Postgres · Redis · MinIO · Vault · guardrails sidecar + traces + redacted logs → fail CI
```

---

## Bilingual Plan — English-First, Arabic Additive

Two decisions on day one make Arabic a "pour in more data" step, never a rewrite: **(1)** a **multilingual hosted-API embedding** for RAG from the start, and **(2)** a classifier pipeline that accepts either language (a language-detect step + multilingual-friendly features). English is the load-bearing path.

**Phase 1 — English, fully working**
- Whole SaaS built and proven in English: isolation, CMS, router, agent, RAG, guardrails, widget, erasure, CI.
- Classifier trained on English intent data; served lean. Multilingual embedding chosen up front.
- This phase alone is a complete, gradeable product.

**Phase 2 — Arabic, layered in**
- Add Arabic CMS content + Arabic intent examples (MSA / Lebanese dialect / Arabizi).
- Language detection routes to the right prompt; the multilingual embedding already covers Arabic retrieval.
- Bilingual guardrails + RTL widget toggle. Report per-language numbers.

> **The additive guarantee:** no English code path depends on an Arabic resource existing. If the Arabic dataset is empty, language detection simply always returns English and the product runs unchanged. Start collecting Arabic data *during* Phase 1 — curation is the long pole and is independent of the code.

---

## Design A — Multi-Tenancy & Isolation (the graded heart)

Written deliverable: `DESIGN.md`. Cross-tenant leakage is the #1 way real multi-tenant AI products fail.

### Isolation strategy (decided and defended)
- Every row carries a `tenant_id`. **Postgres Row-Level Security (RLS)** is the enforced boundary — a session variable set per request, one POLICY per table. The database refuses cross-tenant rows.
- **Depth:** the repository layer *also* scopes every query (`.filter(tenant_id == ...)`). RLS catches the query a tired developer forgets to scope.
- **Vector isolation:** the pgvector embeddings table carries `tenant_id` under the same RLS policy. RAG retrieval is tenant-filtered at query time — tenant-safe by construction.
- Pooled connections persist the session variable — **reset it at the end of every request**; a leftover value is a cross-tenant leak.

### Roles — three roles, two levels, no more
- **Platform Manager** (platform): provisions, suspends, and erases tenants; reads aggregate cost/usage. The only role that crosses the tenant boundary — and the most dangerous.
- **Tenant admin** (per municipality): configures its own agent, widgets, guardrails; sees its own requests.
- **Visitor**: anonymous resident using the chat.
- The Platform Manager gets **no content bypass**: it can destroy a tenant's data through a narrow write/delete-only maintenance path but can never read a tenant's conversations or requests. Every crossing is audit-logged with the actor id. Resist building a general permission matrix.

### Cost, rate limits & scale
- Per-tenant cost & token attribution: every LLM and embedding call is tagged with a tenant.
- Per-tenant rate limiting + a deliberate caching decision (what you cache and what you pointedly don't). One noisy tenant can't starve the others.
- One page in `DESIGN.md`: where this breaks at 10 tenants vs 1,000, and the next bottleneck.

---

## Design B — Routing + One Agent That Acts

A hybrid, which is what mature LLM apps actually ship: a cheap deterministic workflow out front, and one agent reserved for the turns the workflow can't resolve.

### The router (a workflow) — your trained classifier
- Each inbound message is classified; a fixed graph handles the nameable cases directly: spam → drop; a clear service request → `rag_search` then answer; an obvious "report this" intent → `capture_request`; an explicit "talk to a human" → `escalate`.
- Only ambiguous or multi-step turns reach the agent. Measure the fraction kept off the agent and what it saves per tenant (feeds Design A).
- Argue agent vs pure workflow vs hybrid in `DECISIONS.md`. Reaching for an agent when a workflow would do is the most common, most expensive junior mistake.

### The agent & its three tools
- `rag_search` — retrieve from the tenant's CMS content and answer.
- `capture_request` — write a resident's name, contact, location, and intent to the tenant's requests table. A real side-effecting action.
- `escalate` — flag the conversation for municipal staff (open a ticket row) when out of scope or asked for a person.
- **Bound the loop:** cap tool-call iterations and tokens per turn — a cost control and a safety control at once.
- `capture_request` is an unauthenticated, LLM-triggered write: schema-validate the payload, rate-limit per visitor/session, scope the write to the token's tenant. An injected prompt must not turn it into a spam cannon or a write into another tenant's table. **Spam is dropped by the classifier before it is ever stored.**

### Memory & prompts
- Short-term session memory in Redis, scoped per conversation, with an explicit justified TTL.
- Prompts live in `prompts/`, version-controlled, with Arabic and English variants. Tenant persona is injected at runtime from config — never hardcoded.

---

## Design C — Your Own Model: ML vs DL, Trained Offline, Served Lean

The product is not only LLM calls. You train, evaluate, and ship a real classifier — without ever putting torch in a container. **No fine-tuning.**

- **The task:** classify each inbound message by intent — e.g. *service-request* (and which civic category) / *question* / *spam*. The result drives the router and gates the unauthenticated `capture_request` write.
- **Three approaches, one number:** a classical ML baseline (TF-IDF + logistic regression or gradient boosting), an optional small DL model, and an LLM zero-shot baseline via your API. Compare on a held-out test set — macro-F1, per-class F1, latency, cost — pick one to ship and defend it in `DECISIONS.md`.
- **Train offline, serve lean:** training in a notebook / Colab (ephemeral, never in your stack). Export the classical model to `joblib`, the optional DL model to `ONNX`. The `modelserver` runs only `onnxruntime` + `scikit-learn` + `numpy` — no torch, no transformers.
- **Bilingual without fine-tuning:** the classical pipeline accepts both languages via language-aware preprocessing + multilingual TF-IDF (or character n-grams, which handle Arabic and Arabizi gracefully). Report per-language F1. English is the baseline that must always pass; Arabic is the enrichment.
- **Model card:** task, data source + hash, the three results, deployment choice, and the artifact's SHA-256. The model-server refuses to boot if the artifact hash doesn't match the card.
- Served behind the lean model-server, called over HTTP with the service credential from Design E. The classifier is a service, not an import.

> Dataset: a small public labeled intent/spam set for English, plus your hand-curated bilingual civic intent set for Arabic (MSA / dialect / Arabizi, hand-verified). Held-out test, no leakage. Separate from the tenant CMS corpus.

---

## Design D — RAG Over Tenant Content (kept lean)

Deliberately lean. Naive fixed-size chunking + plain dense retrieval is the baseline you beat with **one** justified improvement — not a five-technique stack.

- Corpus = the tenant's own CMS content. Embeddings via a **multilingual hosted API** into pgvector, every chunk tagged with `tenant_id`.
- One non-naive chunking choice + dense retrieval + **one** improvement (a rerank step, a query rewrite, or metadata filtering) — backed by a number on your golden set.
- Retrieval is tenant-filtered at query time — part of isolation, not an afterthought. The most common real leak is a vector search that forgot the tenant filter.
- Because the embedding is multilingual, Arabic retrieval works the moment Arabic content is indexed — no separate Arabic RAG stack.

---

## Design E — Security, Guardrails & Compliance

The guardrail you never tried to break is a guardrail you don't have.

- **Cross-tenant + prompt-injection red-team test, in CI.** A visitor on Tenant A tries to extract Tenant B's data or reveal the system prompt; the agent must refuse. This test gates merges so a future refactor can't silently reopen the hole.
- **Service-to-service auth:** API → guardrails sidecar → model endpoints use a shared service credential (or mTLS) resolved from Vault. "It's on the internal network" is not authentication.
- **Two guardrail layers, only one tenant-editable.** Platform rails (injection, jailbreak, cross-tenant refusal, PII redaction) are mandatory, identical for everyone, and fail CI when they regress. Tenant rails (allowed/blocked topics, refusal tone, persona, enabled tools) are configurable per tenant. A tenant can never dial down the wall that protects every other tenant.
- **PII redaction before anything leaves the service** (logs, traces, memory). For civic text: national ID numbers, Lebanese phone formats, names, exact addresses, emails. A test proves a fake key/ID pasted into chat never appears unredacted anywhere.
- **Right to erasure** — a real "delete tenant" path purging Postgres rows, pgvector embeddings, MinIO blobs, and Redis sessions. Audit-logged. "We deleted the row but the embeddings are still searchable" is a compliance failure and a leak.

### Guardrails sidecar
Run guardrails as a separate sidecar the API calls over HTTP with a service credential. Default to **NeMo Guardrails** for topical + injection + cross-tenant rails (vendor-neutral, clean sidecar); reach for **Guardrails.ai / Presidio** only if PII validation is the part you want a library to own. Pick one primary; don't build a platform.

---

## Design F — The Embeddable Widget (CORS is not auth)

- A standalone React widget (Vite), small bundle, served from the API or MinIO with cache headers, **RTL-aware with an Arabic/English toggle**. Theme + greeting (per language) from tenant config at load time.
- A loader at `/widget.js` — the host pastes one `<script>` with `data-widget-id` and the loader injects the iframe.
- **The widget authenticates with a short-lived, tenant-scoped signed token.** The loader exchanges the public `widget_id` (+ allowed origin) for a signed expiring token (JWT/HMAC); every chat request carries it. The token is what the API trusts.
- The verified token sets the RLS tenant context. `tenant_id` comes from the verified token, **never from a client-supplied field** — trusting a body field is a one-line cross-tenant breach.
- Per-tenant `allowed_origins` drives CORS + `CSP: frame-ancestors` — embedding control, not authentication. Validate the origin server-side too and reject mismatches with a 403.

> Defense demo: widget loads on an allowed host, is blocked on a disallowed host (real console), and a raw `curl` with a stale token is rejected by the API.

---

## The CMS

- Each tenant manages its civic-services content in a simple CMS in the admin app: pages/entries with title, body, category, and language.
- The same content powers both the public-site knowledge and the agent's RAG corpus — edit once, both update.
- On save, content is chunked and embedded into tenant-filtered pgvector. Editing or deleting content re-indexes; deleting a tenant purges it (right-to-erasure).
- Content is bilingual-aware: an entry's language tag lets the agent prefer same-language chunks while the multilingual embedding still allows cross-language recall.

---

## Engineering Standards (the how)

These nine standards are graded, mapped onto this project.

| Standard | Applied here |
|---|---|
| **1 · Async all the way down** | Every route, LLM call, embedding call, model-server call, DB query, retrieval is `async`; `httpx` + async SQLAlchemy. The classifier call is a fast HTTP hop to the lean model-server, off the event loop. |
| **2 · Dependency injection** | `Depends()` for DB session, LLM client, current actor, retriever, redactor, and the **per-request tenant context**. No globals — this is what lets the red-team and redaction tests inject fakes. |
| **3 · Singletons via lifespan** | Load once on startup: LLM/embedding HTTP clients, DB engine, Redis pool, vector-store connection. The model lives in the *model-server*, loaded once there. |
| **4 · Caching where it pays** | `lru_cache` on settings/label-mapping/prompt loaders; a deliberate per-tenant cache decision for embeddings/retrieval (Design A). Never cache across tenants. |
| **5 · Config via pydantic-settings** | One typed `Settings`, `extra="forbid"`; secrets resolve from Vault — never in `.env`, which holds only the Vault root token and ports. |
| **6 · Types & Pydantic at the boundary** | Pydantic on HTTP bodies, every tool input (the three tools), classifier I/O (typed result), widget config. The `capture_request` payload is schema-validated before any write. |
| **7 · Errors, retries, failure isolation** | Timeouts + `tenacity` retries on transient errors only; tools return a structured `ToolError` so the agent recovers and never 500s. The audit path failing never breaks the resident's reply. |
| **8 · Code hygiene** | Layered (`api/services/repositories/domain/infra`), thin `main.py`, `structlog` with `trace_id` + `tenant_id` on every line, `ruff` in pre-commit, never `print()`. |
| **9 · Tests on the critical path** | Schema tests, tool-logic tests (LLM + model-server mocked), one end-to-end agent pass — alongside the four eval gates and the red-team + redaction tests, all on every push. |

---

## How You Build — Spec-Driven + CI/CD

- **Write the spec before the code.** A `SPEC.md` per major component — the tool contracts, the isolation rules, the role model, the eval thresholds are specs you write first.
- Commit the **skills and subagents** you built to scaffold the work — e.g. a "tenant-isolation auditor" subagent that greps for unscoped queries. No vibe coding: you own every line.
- **CI on every push:** lint, type-check, build images, then the gates. Thresholds in `eval_thresholds.yaml`. Any regression blocks merge.

---

## Evaluation — Four CI Gates

- **Classifier** — macro-F1 on the held-out test (per-language reported), with the ML/DL/LLM three-way comparison committed alongside so the shipped model can't silently fall behind.
- **Agent tool-selection** — 15 examples: given a message, did the agent pick the right tool (or correctly pick none)?
- **RAG** — 15 triples (question / ideal-answer / ground-truth-chunks): hit@k, MRR, faithfulness, answer relevancy. RAGAS or a frozen judge; hand-label a few and report agreement.
- **Red-team** — a handful of injection + cross-tenant probes. All must be refused for the build to pass.
- Plus the **redaction test** and a **stack smoke test** (compose comes up clean from a fresh clone).

---

## Suggested Schedule (Solo)

| Day | Work |
|---|---|
| **Specs & skeleton** | Specs + scaffolding skills. Compose stack up (reuse Wk6/7 infra), Vault + tracing wired, Alembic baseline, **tenant model + RLS + three-role model**, seed two tenants. `eval_thresholds.yaml` with placeholder numbers. |
| **Model, CMS & RAG** | Train classifier offline (classical + optional DL→ONNX + LLM baseline), export, stand up the lean model-server. Tenant CMS content, multilingual API embeddings into tenant-filtered pgvector, retrieval with a number. |
| **Router + agent** | Classifier-driven router for easy cases; bounded tool-calling agent for hard turns. Redis session memory, guardrails sidecar wired (injection + cross-tenant rails). |
| **Widget, evals, erasure** | React widget + loader + signed per-widget token + per-tenant origin allowlist, admin config + CMS page, all four eval suites in CI, the delete-tenant path. |
| **Arabic + polish** | Layer Arabic CMS + intent data, language detection, RTL toggle, per-language numbers. Final integration, CI green, READMEs, practice. Demo. |

> Solo & no fine-tuning keeps this tractable: the heaviest Week-8 burdens (a team's worth of slices, torch dependency hell) are gone. If time is short, ship Phase 1 (English) fully and present Arabic as in-progress — the additive design means that's still a complete product.

---

## Hardware Budget & Local Footprint

Built and run on **8 GB RAM, ~20 GB disk**. No fine-tuning and no torch in containers makes this comfortable.

- **No torch in any container.** Training (classical sklearn, or an optional small DL model) happens in a notebook/Colab and is exported to `joblib` / `ONNX`. The model-server runs `onnxruntime` + `scikit-learn` + `numpy` only — image under ~500 MB.
- **LLM + embeddings are hosted-API calls** — zero local model weight, zero local RAM for inference. This is also what makes the build 30 seconds, not 30 minutes.
- **RAM is the binding constraint.** Run services in subsets, not all at once. Prune Docker regularly; cap blob retention.
- If you do train a small DL model, install CPU-only torch *in the notebook environment only* (`--index-url https://download.pytorch.org/whl/cpu`) — it never enters a container.

| Working on | Run only |
|---|---|
| Model/CMS work | `db` + `modelserver` (+ a notebook for training). |
| Router/agent | `db` + `redis` + `api` + `modelserver` + `guardrails`. |
| Widget/admin | `api` + `widget` + `chatbot` + `host`. |
| Full stack | All services — only for the smoke test and the final demo. |

---

## Compose Stack

| Service | Role |
|---|---|
| `api` | FastAPI backend (auth, tenancy/RLS, chat, router, agent, RAG orchestration, CMS, widget tokens, cost attribution). |
| `chatbot` | Streamlit tenant-admin (CMS, agent + guardrail config, requests view, embed snippet) + platform-manager console. |
| `widget` | Static server for the built React widget bundle and the `/widget.js` loader. |
| `modelserver` | Lean FastAPI inference (classifier). `onnxruntime` / `sklearn`, no torch. |
| `guardrails` | NeMo Guardrails sidecar (platform + tenant rails), called over HTTP with a service credential. |
| `host` | nginx serving the mock municipality demo site. |
| `migrate` | Alembic entrypoint, exits. |
| `db` | `postgres:16` with pgvector + RLS. |
| `redis` | `redis:7` — session memory, cache, rate limits. |
| `minio` | `minio/minio` — blob (model manifest, eval reports, snapshots). |
| `vault` | `hashicorp/vault` — secrets + service credentials. |

`docker-compose up` from a fresh clone after `cp .env.example .env` and filling the Vault root token. CI: lint, type-check, build images, run the four eval gates + redaction test, smoke-test the stack.

---

## From Projects 7 & 8 — Reuse & Improve

**Reuse as-is (Wk6/7 scaffolding)**
- Layered architecture (api / services / repositories / domain / infra).
- Vault secrets + refuse-to-boot, MinIO blob, Alembic + migrate container.
- `fastapi-users` JWT auth.
- Tracing, redaction, exception-handling infra.
- Streamlit admin + React widget + loader patterns.
- Eval-harness-fails-CI discipline; committed thresholds.
- Single tool-calling-LLM design.

**New from Week 8 + Arabic**
- Multi-tenant SaaS + RLS isolation + tenant-filtered pgvector.
- Platform-Manager / tenant-admin / visitor role model + provisioning + erasure.
- CMS powering both site and agent knowledge.
- Classifier-as-router + bounded acting agent (hybrid).
- Lean ONNX/sklearn serving, no torch; ML/DL/LLM three-way.
- Guardrails sidecar (platform + tenant rails); red-team CI gate.
- Signed per-widget token + server-side origin check.
- Per-tenant cost attribution + rate limiting; scaling story.
- Bilingual (AR/EN) additive layer + RTL widget; per-language metrics.

> **Don't add scope beyond this.** It is already ambitious for a solo build. New ideas go in a "future work" slide, not the repo.

---

## Think About

- Your DL model beats the classical baseline by 3 macro-F1 points but doubles latency and ships a 40 MB ONNX artifact. Which ships — and does that survive a 10x traffic jump or a tighter latency budget?
- Your router keeps most turns off the agent and cuts cost — until it confidently routes a nuanced Arabic turn down the cheap path and answers wrong. How do you set the confidence threshold, and which way should it fail?
- Where exactly is the tenant filter enforced — and what happens the day a new developer writes a query that forgets it?
- A resident pastes their national ID into the chat. Name every place that string could land. How would you know it leaked before they did?
- The injection test passes today. What refactor next month silently reopens the hole, and what stops that refactor from merging?
- "Delete my tenant." Name every place that data lives — rows, vectors, blobs, sessions, traces, logs. Did you get all of them?
- You set the RLS tenant variable per request, but connections are pooled. A request for Tenant A reuses a connection still holding Tenant B's variable. Where do you reset it, and how do you prove the reset never gets skipped?
- The Arabic dataset never materializes. Prove the English product still classifies, retrieves, acts, and ships — name the exact line where language detection makes that safe.

_These are your problems to solve. No hints._

---

## Submission

Public GitHub repo, tag `v0.1.0-final`, comes up cleanly with `docker-compose up` from a fresh clone after `cp .env.example .env`.

```
Project — Final — Baladiya Concierge — [Name]
Repo: [GitHub URL]   Tag: v0.1.0-final
Tenants seeded: [N]   Isolation: RLS + repo-layer + tenant-filtered pgvector
Roles: platform_manager | tenant_admin | visitor — no content RLS bypass
Languages: English (load-bearing) + Arabic (additive)   Widget: RTL yes
Classifier task: intent (service / question / spam)   data: [dataset]
Classifier — ML F1=[n] | DL(ONNX) F1=[n] | LLM F1=[n]   ships: [choice] — because [one line]
  per-language F1: EN=[n] / AR=[n]
Model served: [ONNX/onnxruntime | sklearn/joblib] — artifact SHA-256 pinned in model card
Agent tools: rag_search | capture_request | escalate
Routing: workflow handled [n]% | agent handled [n]% (cost saved: [one line])
RAG — chunking: [choice] improvement: [choice] hit@5=[n] faithfulness=[n]
Embedding model: [name, hosted multilingual API]
Guardrails sidecar: [NeMo | Guardrails.ai] — rails: [input/output/topical/jailbreak]
Widget auth: signed per-widget token + server-side origin check (CORS/CSP = depth)
Service-to-service auth: [service token | mTLS] from Vault
Redis short-term TTL: [n] — because [one line]
Tracing backend: [name]   Widget bundle size: [n] KB gzipped
LLM: [provider + model]
Docs: DESIGN.md, SPEC.md, DECISIONS.md, RUNBOOK.md, EVALS.md, SECURITY.md, DATA.md
```

---

## Rules

- **ISOLATION IS THE GRADE.** A working agent that leaks across tenants scores below a plainer one that holds the wall. The wall is the assignment.
- **CORS IS NOT AUTHENTICATION.** The widget authenticates with a signed, short-lived token and a server-side origin check. CORS and CSP are defense-in-depth around it, never the boundary.
- **THE EVALS ARE THE GRADE.** Committed thresholds that fail CI when you regress. A polished demo with no working gates scores below a rougher one whose CI is real.
- **EVERY DECISION IS BACKED BY A NUMBER.** Chunking, embedding model, retrieval improvement, deployment choice — every choice in DESIGN.md / DECISIONS.md is backed by a number on your golden set.
- **LEAN CONTAINERS — NO TORCH, NO FINE-TUNING.** LLM and embeddings are hosted-API calls. Your classifier is trained offline and served lean — DL via ONNX, classical via joblib. No torch or transformers in any container; if an image is over ~500 MB, something is wrong.
- **ARABIC IS ADDITIVE, ENGLISH IS LOAD-BEARING.** No English path depends on an Arabic resource. If the Arabic data never lands, the product still works — prove it.
- **NO VIBE CODING.** Spec'd or AI-scaffolded, you own every line. You will be asked about any part of the system at the defense.

**SHIP IT.**

_END OF SPEC_
