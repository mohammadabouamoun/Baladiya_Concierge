# Baladiya Concierge

> Multi-tenant civic SaaS — any municipality signs up, gets an isolated tenant, and embeds a bilingual (Arabic + English) AI assistant on its public website.

Residents ask questions or report problems (potholes, water cuts, uncollected garbage) in English, Modern Standard Arabic, or Lebanese dialect. The assistant answers from the town's own knowledge base, captures reports with a verified phone number, and escalates to a human when needed — and every town's data stays completely separate from every other town's.

Think Shopify, but for town halls: one platform, an isolated private assistant per municipality.

## Demo

A walkthrough of the running system, one clip per surface.



**1. Resident website + chat bubble** — bilingual (Arabic/English) chat, file a report, phone/OTP verification, reference number.


https://github.com/user-attachments/assets/d3bd7a3e-a03b-4f0e-a1bd-d3b849267eaa

**2. Tenant Admin · Requests** — the captured report appears with category, location, and **Phone verified: Yes**.

https://github.com/user-attachments/assets/4fa9854d-13c5-447c-9498-f8d600234cd1

**3. Tenant Admin · CMS** — managing the tenant's bilingual knowledge base.

https://github.com/user-attachments/assets/36015777-c985-47ad-ab6e-c2abab04e3c9

**4. Platform Manager** — control plane: tenant provisioning, status, suspend/erase.

https://github.com/user-attachments/assets/b79f7e25-8e9b-444c-aff8-b855e5f5e888


## How it works

```
inbound msg → CLASSIFIER ROUTER ──easy──> workflow answers directly
                                 ──hard──> tool-calling AGENT picks tools (bounded loop)

AGENT tools: rag_search | capture_request | escalate   (all scoped by tenant_id)

modelserver (onnxruntime / sklearn) ← called over HTTP, never imported
guardrails sidecar ← platform rails locked + tenant rails configurable
pgvector ← tenant-filtered at query time
Redis ← per-conversation session memory with explicit TTL
```

1. A classifier service labels each message (`report` / `question` / `human` / `spam`) and routes it.
2. Easy messages are answered directly by a workflow; hard ones go to a bounded tool-calling agent.
3. The agent grounds answers in the tenant's documents via RAG over pgvector, logs reports, or escalates.
4. Spam is dropped by the classifier before any write happens.

## Core principles

- **Tenant isolation is the grade.** Every query is scoped by `tenant_id` — Postgres RLS is the enforced wall, the repository layer adds a second filter, and the RLS session variable is reset at the end of every request. `tenant_id` comes only from the verified JWT, never a client body field.
- **English is load-bearing, Arabic is additive.** No English code path depends on an Arabic resource.
- **Offline training only.** No torch in any container — models are trained offline and exported to `joblib` / `ONNX`, served by a lean `modelserver` HTTP service.
- **Layered guardrails.** Mandatory platform rails (injection, jailbreak, cross-tenant refusal, PII redaction) are identical for every tenant; tenant rails (topics, tone, persona, enabled tools) are configurable. A tenant can never dial down the platform wall.
- **Widget auth** = signed short-lived token + server-side origin check. CORS/CSP are depth, not the boundary.

## Roles

| Role | Can do | Cannot do |
|---|---|---|
| **Platform Manager** | Provision / suspend / erase tenants, read aggregate cost & usage | Read tenant conversations (all boundary crossings audit-logged) |
| **Tenant Admin** | Configure its own agent, widgets, guardrails; see its own requests | See any other tenant's data |
| **Visitor** | Chat anonymously via the widget | — |

## Tech stack

| Layer | Technology |
|---|---|
| API | FastAPI (fully async), `httpx`, async SQLAlchemy |
| Admin UI | Streamlit (tenant admin + platform manager) |
| Widget | React (Vite), RTL-aware |
| DB | PostgreSQL 16 + pgvector + RLS |
| Session / cache | Redis 7 |
| Blob | MinIO |
| Secrets | HashiCorp Vault |
| Guardrails | NeMo Guardrails sidecar (HTTP) |
| Classifier | scikit-learn / joblib (+ optional ONNX), served by `modelserver` |
| Embeddings | `gemini-embedding-001` (1536 dims) |
| LLM (primary) | `gemini-2.5-flash` (EN + MSA + Lebanese) |
| LLM (fallback) | Groq `llama-3.3-70b-versatile` |

## Repository layout

```
api/              FastAPI service (api / services / repositories / domain / infra)
modelserver/      Lean classifier HTTP service (onnxruntime + sklearn)
guardrails/       NeMo Guardrails sidecar + rails
chatbot/          Streamlit tenant admin (CMS + requests)
platform_manager/ Streamlit platform manager UI
widget/           React (Vite) embeddable chat widget
host/             Demo municipality website hosting the chat bubble
evals/            CI eval harnesses (classifier, agent, RAG, red-team)
tests/            Test suites (isolation, security, classifier, agent, rag, ...)
alembic/          DB migrations
scripts/          Local demo runners (demo_api.py, run-all-local.sh)
specs/            Spec Kit feature specs (001–009)
notebooks/        Offline model training
```

## Running it

### Docker (full architecture)

The complete, graded system — Postgres + RLS isolation, RAG grounding, guardrails, Vault, MinIO — runs via Docker Compose:

```bash
docker-compose up
```

Services: `db`, `redis`, `vault`, `minio`, `migrate`, `api`, `modelserver`, `guardrails`, `widget`, `chatbot`, `platform_manager`, `host`.

### Local (no Docker, demo path)

A lighter laptop demo path is documented in [`run_locally.md`](run_locally.md):

```bash
bash scripts/run-all-local.sh      # Ctrl-C stops everything
```

| Service | URL |
|---|---|
| Website + chat bubble | http://localhost:3000 |
| Tenant Admin · Requests | http://localhost:8501 |
| Platform Manager | http://localhost:8502 |
| Tenant Admin · CMS | http://localhost:8503 |

> **Note:** the local demo path uses raw Gemini with no RAG/guardrails/RLS and persists reports to a JSON file. The real isolation work runs under Docker.

## Dataset

`civic_intent_dataset.csv` (`id | text | lang | variety | intent | category | split`) trains the **classifier only** — it is never embedded into pgvector. Rebuild with `python3 build_dataset.md` (a Python script with a `.md` extension). Deterministic split: `sha1(text) % 5 == 0 → test`. See [`DATA.md`](DATA.md).

## CI gates

All must pass (thresholds in [`eval_thresholds.yaml`](eval_thresholds.yaml)):

1. **Classifier** — macro-F1 on held-out test, per-language reported
2. **Agent tool-selection** — 15 labelled examples
3. **RAG** — 15 triples: hit@k, MRR, faithfulness, answer relevancy
4. **Red-team** — injection + cross-tenant probes, all refused

Plus a **redaction test** (fake national ID / phone never appears unredacted) and a **stack smoke test** (`docker-compose up` from a fresh clone).

## Documentation

| Doc | Contents |
|---|---|
| [`BALADIYA_CONCIERGE.md`](BALADIYA_CONCIERGE.md) | Full product spec |
| [`DESIGN.md`](DESIGN.md) | Architecture & design decisions |
| [`SPEC.md`](SPEC.md) | Functional specification |
| [`DECISIONS.md`](DECISIONS.md) | Decision log (backed by measured numbers) |
| [`EVALS.md`](EVALS.md) | Evaluation methodology & results |
| [`SECURITY.md`](SECURITY.md) | Threat model & isolation guarantees |
| [`DATA.md`](DATA.md) | Dataset construction & coverage |
| [`RUNBOOK.md`](RUNBOOK.md) | Operations runbook |
| [`CLAUDE.md`](CLAUDE.md) | Engineering standards & hard constraints |
