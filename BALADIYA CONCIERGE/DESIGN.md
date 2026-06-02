# DESIGN.md — Baladiya Concierge

> Architecture guide for the Baladiya Concierge multi-tenant civic AI platform.
> Primary audience: defense panel (architectural rationale) + future engineering team (operational guidance).

---

## 1. System Overview

Baladiya Concierge is a multi-tenant civic AI SaaS. Any municipality signs up, receives an isolated tenant, and embeds a bilingual (Arabic + English) AI agent on its public-facing website. Residents interact through a lightweight chat widget without creating accounts.

### What It Does

A resident sends a message. The system classifies the intent and routes it:

- **Spam** — dropped before any write or LLM call
- **Question** — answered via RAG over the municipality's knowledge base
- **Report** — captured as a structured service request in the municipality's database
- **Human** — escalated to a staff ticket queue
- **Ambiguous / multi-step** — handled by a bounded tool-calling agent

All of this happens within the tenant's isolation boundary. Municipality A cannot read, write, or infer anything about Municipality B — by design, by database policy, and by verified test.

### What Makes It Architecturally Interesting

Three properties distinguish this from a generic chatbot deployment:

1. **Isolation is the primary correctness property.** Postgres Row-Level Security, session variable lifecycle management, and a mandatory repository-layer filter operate in parallel on every request. The system is designed so that a bug in any one layer does not produce a cross-tenant data exposure.

2. **The majority of turns cost nothing in LLM tokens.** A classifier routes clear-intent messages to deterministic workflow handlers. The LLM agent is invoked only for ambiguous turns. This is a cost architecture decision, not just a latency optimization.

3. **Arabic is a progressive enhancement, not a structural dependency.** The system is fully operational in English with no Arabic data. Arabic support is layered additively — language detection, bilingual classifier training, and RTL widget rendering — such that removing all Arabic data leaves every English test passing unchanged.

### Roles

| Role | Access | Isolation |
|---|---|---|
| **Resident** | Anonymous chat via widget | Scoped to the widget's tenant |
| **Tenant Admin** | Manages own agent, CMS, widgets, guardrail config | Sees only own tenant's data |
| **Platform Manager** | Provisions, suspends, erases tenants; reads aggregate cost | Cannot read any tenant's conversations or content |

### Tech Stack Summary

| Layer | Technology |
|---|---|
| API | FastAPI, fully async |
| Admin UI | Streamlit |
| Widget | React (Vite), RTL-aware |
| Database | PostgreSQL 16 + pgvector + RLS |
| Session / Cache | Redis 7 |
| Secrets | HashiCorp Vault |
| Classifier | sklearn/ONNX served by lean `modelserver` (no torch) |
| Guardrails | NeMo Guardrails sidecar, fail-closed |
| Embeddings | `gemini-embedding-001` (Gemini API, 1536 dims, pinned; never falls back) |
| LLM (primary) | `gemini-2.5-flash` via Gemini API |
| LLM (fallback) | Groq `llama-3.3-70b-versatile` — on sustained Gemini failure only |
| Blob storage | MinIO |

---

## 2. Tenant Isolation Strategy

Isolation is the primary correctness property of this system. A cross-tenant data leak is not a performance bug — it is a compliance failure. The architecture enforces isolation at three independent layers so that no single implementation mistake can expose one tenant's data to another.

### Three-Layer Defense

| Layer | Mechanism | Fails safe by |
|---|---|---|
| 1. Database | Postgres Row-Level Security policy | Refusing the query at the storage engine |
| 2. Session | `SET LOCAL app.current_tenant` per request | Scoping every query on that connection to one tenant |
| 3. Application | `BaseRepository` mandatory `tenant_id` filter | Raising `TenantScopeError` before the query is issued |

Each layer is independently sufficient to prevent a cross-tenant read. All three run on every request. A bug in the application layer is caught by the session variable; a bug in connection-pool management is caught by RLS.

### Layer 1 — Postgres RLS

Every tenant-owned table carries the policy:

```sql
ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON {table}
    USING (tenant_id = current_setting('app.current_tenant')::uuid);
```

The `::uuid` cast is intentional: it prevents string-comparison bypass attempts and will raise a Postgres error if the session variable is not a valid UUID, failing the request rather than returning wrong data.

### Layer 2 — Session Variable Lifecycle

The `get_db` dependency sets and resets the session variable around every request:

```python
async def get_db(token) -> AsyncGenerator[AsyncSession, None]:
    async with session_factory() as session:
        await session.execute(
            text("SET LOCAL app.current_tenant = :tid"),
            {"tid": str(token.tenant_id)}
        )
        try:
            yield session
        finally:
            await session.execute(text("RESET app.current_tenant"))
```

`RESET` in the `finally` block is mandatory because connections are pooled. A connection that skips the reset carries the previous request's `tenant_id` into the next request. `SET LOCAL` (not `SET`) means the variable is also automatically cleared on transaction rollback — double protection.

### Layer 3 — Repository Guard

`BaseRepository` enforces `.filter(Model.tenant_id == self.tenant_id)` on every query. `self.tenant_id` is injected at construction from the validated JWT token. If `tenant_id` is `None` (e.g., a Platform Manager route calling the wrong repository), the repository raises `TenantScopeError` immediately — it never issues the query.

A developer who bypasses `BaseRepository` entirely and writes raw SQL via `session.execute()` directly is still protected by the session variable and RLS — the database engine enforces the policy regardless of how the query was constructed. `BaseRepository` is an early-warning layer, not the last line of defence.

### Tenant Identity Source

`tenant_id` comes exclusively from the verified JWT token payload. It is never read from the request body, query parameters, or headers. This is enforced structurally: the `get_current_user` dependency extracts it from the decoded token, and `get_db` receives it from `get_current_user` — not from the request object. A client cannot supply a different `tenant_id` because there is no code path that reads one.

### Platform Manager Isolation

Platform Manager routes use a separate `require_platform_manager` dependency that validates the JWT role but **never sets `app.current_tenant`**. Platform Manager queries target only `tenants` and `platform_managers` tables, which carry no `tenant_id` column and have no RLS policies. A Platform Manager cannot read conversation, request, or content data through any API route.

### Vector Store Isolation

`cms_chunks` (pgvector) carries a `tenant_id` column and an RLS policy identical to other tenant-owned tables. Every similarity search includes an explicit `WHERE tenant_id = :tid` clause in addition to the RLS wall. This is not redundant: the vector index planner can choose a different access path than RLS alone, so the explicit filter ensures the index scan is also tenant-scoped.

### Redis Namespace

Session memory keys follow the pattern `session:{session_id}:{tenant_id}`. The `tenant_id` is the **suffix**, not the prefix. This is required for tenant erasure: deleting all sessions for a tenant requires a `SCAN` with pattern `session:*:{tenant_id}`, which works correctly with suffix placement. A prefix pattern (`session:{tenant_id}:*`) would require exact knowledge of every `session_id` — not available at erasure time.

### Right-to-Erasure Sequence

Tenant deletion runs in dependency order to avoid orphaned references:

1. `SCAN session:*:{tenant_id}` → `DEL` all Redis session keys
2. Delete pgvector embeddings (`DELETE FROM cms_chunks WHERE tenant_id = :tid`)
3. Delete tenant content tables in FK order (cms_entries, capture_requests, escalation_tickets, widgets, conversations)
4. Delete MinIO blobs under the tenant's bucket prefix
5. Delete tenant admin users
6. Delete the tenant row itself
7. Write a final `audit_log` entry (actor: platform_manager, action: erase, subject: tenant_id)

The audit log entry is written **after** deletion and survives because `audit_log` is not a tenant-owned table — it is platform-owned with no RLS policy scoped to the deleted tenant.

### Why Not Schema-Per-Tenant?

Schema-per-tenant (one Postgres schema per customer) is the common alternative. It is rejected here because:

- **Migration cost**: every schema change requires running Alembic against N schemas. At 10–100 tenants this becomes a deployment bottleneck.
- **No isolation benefit at this scale**: schema separation provides the same logical isolation as RLS at 10–100 tenants, but RLS enforces it at the engine level without the operational overhead.
- **Connection pool complexity**: schema-per-tenant requires per-tenant connection pools or `SET search_path` switching — the same session-variable problem RLS already solves.

The architecture re-evaluates this decision at > 500 tenants, where a dedicated Postgres instance per enterprise tenant may be warranted for SLA reasons.

---

## 3. Component Architecture

### Service Map

The system is composed of 11 Docker Compose services. Not all are active in every phase — services are stubbed early and activated when their feature phase begins:

| Service | Role | Active from |
|---|---|---|
| `db` | PostgreSQL 16 + pgvector + RLS | Phase 1 |
| `vault` | HashiCorp Vault — all secrets | Phase 1 |
| `migrate` | Alembic runner + seed script | Phase 1 |
| `api` | FastAPI — all routes | Phase 1 |
| `redis` | Session memory + rate limiting | Phase 1 |
| `modelserver` | sklearn/ONNX classifier HTTP service | Phase 2 |
| `guardrails` | NeMo Guardrails sidecar | Phase 5 |
| `minio` | Blob storage (uploaded assets) | Phase 3 |
| `admin` | Streamlit (tenant admin + platform manager UI) | Phase 3 |
| `widget` | React (Vite) embeddable chat widget | Phase 6 |
| `host` | nginx mock municipality site for demo | Phase 6 |

### Request Data Flow

```
Resident browser
    │
    ├─ widget.js (loader script on municipality site)
    │       │
    │       └─ GET /widget/token  ← checks request Origin against tenant's allowed_origins list
    │               │               rejects with 403 if Origin not in list
    │               └─ signed JWT (5-minute TTL, HMAC from Vault)
    │
    ├─ iframe (widget React app)
    │       │
    │       └─ POST /chat  ← JWT in Authorization header
    │               │
    │               ├─ [guardrails sidecar] → platform rail check (injection / jailbreak / PII)
    │               │
    │               └─ CLASSIFIER ROUTER
    │                       │
    │                       ├─ easy turn → WORKFLOW (no LLM call)
    │                       │     spam   → drop, no write
    │                       │     question → rag_search → answer
    │                       │     report → capture_request → confirm
    │                       │     human → escalate → ticket
    │                       │
    │                       └─ hard turn → AGENT (bounded loop)
    │                                       ├─ rag_search
    │                                       ├─ capture_request
    │                                       └─ escalate
    │
    └─ response → widget iframe → resident
```

### Hybrid Router

The classifier routes each inbound message to one of two handlers:

- **Workflow** — deterministic handlers for clear-intent turns (spam drop, single-tool question, report capture, human escalation). No LLM call is made. Cost: one classifier HTTP call + one DB/Redis write.
- **Agent** — a bounded tool-calling loop for ambiguous or multi-step turns. Cost: one classifier call + N LLM calls (N ≤ `max_tool_calls` from config).

The target is ≥ 60% of turns handled by workflow. This is a cost control target, not just a safety property — every agent turn costs roughly 10–30× more than a workflow turn in LLM token spend.

### Agent Tools

Three tools are available to the agent. Each has a distinct trust and write profile:

| Tool | Write? | Auth required | Key constraint |
|---|---|---|---|
| `rag_search` | No | None (read-only) | Result always tenant-filtered |
| `capture_request` | Yes | None (visitor-facing) | Pydantic-validated payload; per-session rate limit; `tenant_id` from JWT only |
| `escalate` | Yes | None (visitor-facing) | Writes `escalation_ticket` scoped to token's tenant |

`capture_request` is the highest-risk tool: it accepts unauthenticated LLM-triggered writes. Pydantic schema validation, per-session rate limiting (Redis sliding window), and `tenant_id` sourced exclusively from the JWT token are the three controls that make this safe.

### Service-to-Service Authentication

There is no internal network trust. Every service-to-service call carries an `X-Service-Token` header sourced from Vault at startup. This applies to:

- `api` → `modelserver` (classify endpoint)
- `api` → `guardrails` (validate endpoint)
- `admin` → `api` (all admin routes use tenant admin JWT)

A request without a valid service token receives a 401. This is verified in CI.

### modelserver

`modelserver` runs only `onnxruntime`, `scikit-learn`, and `numpy`. No `torch`. This keeps the image under 500 MB and eliminates GPU dependency from the serving path. At startup, it verifies the SHA-256 checksum of the loaded model artifact against the value committed in `model_card.md` — the service refuses to boot if the checksum does not match.

### Guardrails Sidecar

The NeMo Guardrails sidecar exposes a single `/validate` endpoint. The `api` calls it synchronously before processing any chat turn with a 2-second timeout. If the sidecar is unreachable or does not respond within that window, the `api` returns `503` to the client — it never falls back to unguarded processing (fail-closed).

Two rail layers run independently:

- **Platform rails** — identical for every tenant: injection, jailbreak, cross-tenant refusal, PII redaction. Locked; no tenant can disable them.
- **Tenant rails** — configurable per tenant: allowed topics, tone, persona, enabled tools. Stored in `tenant.settings.guardrail_config`.

A tenant configuring their rails to maximum permissiveness has no effect on the platform rail outcomes.

### Storage Services

**MinIO** stores uploaded assets under a per-tenant bucket prefix (`/{tenant_id}/...`). Assets are deleted in the right-to-erasure sequence before the tenant row is removed.

**Redis** serves two independent roles:
- *Session memory*: `session:{session_id}:{tenant_id}` keys with a 1800s TTL store per-conversation context for the agent.
- *Rate limiting*: a sliding-window counter per `(tenant_id, visitor_session)` enforces `tenant.settings.requests_per_minute`.

### External API Calls

LLM inference and embedding generation are external hosted API calls made via `httpx` async clients. Both are tagged with `tenant_id` at call time and logged with a `cost_tokens` field by the cost attribution middleware. This enables per-tenant cost reporting without any changes to the external API.

**Primary LLM**: `gemini-2.5-flash` (Gemini API, `GEMINI_API_KEY` from Vault). Wrapped in `tenacity` retry-with-backoff. On sustained failure or repeated 429s after retries, the `api` falls over to the **fallback LLM**: Groq `llama-3.3-70b-versatile` (`GROQ_API_KEY` from Vault, OpenAI-SDK-compatible). The fallback path is a documented resilience route — both models are guarded by the same red-team probes.

**Embeddings**: `gemini-embedding-001` at 1536 dimensions. This is a permanent decision: every vector in `cms_chunks` lives in this model's vector space. Groq does not do embeddings here, ever. If the embedding call fails, the request fails — there is no fallback embedding model because mixing vector spaces produces garbage retrieval results.

There is no shared LLM sidecar. Routing every LLM call through an intermediate service would add one HTTP round-trip to every agent turn — at p99 this adds 20–50ms of latency with no architectural benefit over a direct async call.

### Async Discipline

Every route handler, database query, Redis operation, LLM call, and embedding call uses `async`/`await`. There are no synchronous blocking calls in the event loop. This is enforced structurally: all dependencies are injected via FastAPI's `Depends()`, which propagates the async context automatically. The `modelserver` and `guardrails` calls use `httpx.AsyncClient` — not `requests`.

---

## 4. Cost Model & Attribution

### Per-Tenant Cost Tagging

Every LLM inference and embedding call passes through a cost attribution middleware that logs two fields to structlog: `tenant_id` (from the request context) and `cost_tokens` (input + output token count). These fields are present on every log line that touches a paid API. Aggregating on `cost_tokens` grouped by `tenant_id` gives per-tenant monthly spend without any changes to the external API or a separate billing database.

### Cost Per Turn Type

The hybrid router creates two distinct cost tiers:

**Workflow turn** (≥ 60% of turns targeted):
- 1 HTTP call to `modelserver` (classifier inference, in-process sklearn/ONNX, sub-millisecond)
- 0 LLM tokens
- Cost: effectively zero beyond infrastructure

**Agent turn** (≤ 40% of turns):
- 1 classifier call
- N LLM calls, N ≤ `max_tool_calls` (configured per deployment)
- Up to N embedding calls if `rag_search` is invoked

The ≥ 60% workflow routing target is primarily a cost gate, not just a safety property. Every percentage point of traffic shifted from agent to workflow is a linear reduction in LLM spend.

### Rough Unit Economics

Using current hosted API pricing as a reference baseline:

| Call type | Model / API | Est. tokens/call | Est. cost/call |
|---|---|---|---|
| LLM inference | `gemini-2.5-flash` (Gemini API) | ~1 000 (in+out) | ~$0.00015 |
| Embedding | `gemini-embedding-001` (Gemini API) | ~200 | ~$0.000004 |
| Classifier | modelserver (in-process) | — | ~$0.000001 (infra only) |

At 1 000 turns/day per tenant, 40% agent, 1.5 avg tool calls/agent turn:

| Item | Calculation | Monthly estimate |
|---|---|---|
| LLM (agent turns) | 1 000 × 0.4 × 1.5 × $0.00015 × 30 | **~$2.70** |
| Embeddings | 1 000 × 0.4 × 1.5 × $0.000004 × 30 | **~$0.07** |
| Infrastructure (DB, Redis, MinIO) | Fixed, shared across tenants | **~$5–15** (shared) |
| **Total per active tenant/month** | | **~$3–18** depending on turn volume and infra allocation |

These numbers shift significantly with model choice. The three-way classifier comparison (Phase 2) includes a cost-per-call column for the LLM zero-shot baseline — that data informs whether LLM routing is economically viable at scale.

### Spam Economics

Spam messages are dropped by the classifier before any write and before any LLM call. A spam turn costs exactly one classifier HTTP call. At high spam rates (e.g., 50% of inbound messages), the workflow-first architecture prevents what would otherwise be a significant cost amplification — a pure-agent design would run LLM inference on every spam message before detecting it.

### Cost Control Levers

Four levers bound per-tenant and per-turn spend:

| Lever | Config location | Effect |
|---|---|---|
| `max_tool_calls` | `tenant.settings` or platform default | Caps LLM calls per agent turn |
| `max_tokens_per_turn` | `tenant.settings` or platform default | Caps token spend per turn |
| Workflow routing target | Classifier confidence thresholds in `eval_thresholds.yaml` | Shifts traffic from agent to workflow |
| `requests_per_minute` | `tenant.settings` | Redis sliding-window rate limit per visitor session |

### Infrastructure Cost Allocation

Redis and Postgres are shared infrastructure. Their cost does not scale linearly with tenant count — a single Postgres instance with RLS serves 10–100 tenants with no per-tenant overhead beyond storage. MinIO storage cost is negligible at this tenant scale unless tenants upload large binary assets, which is not a supported workflow in the current product.

### Cost Dashboard

The structlog output is the cost ledger. To read per-tenant spend: filter log lines where `cost_tokens` is present, group by `tenant_id`, sum `cost_tokens`, and apply the per-token price for the relevant API. No separate billing service is required in the 10–100 tenant range.

---

## 5. Scale Story: 10 → 100 Tenants

### What Is Already Ready

The isolation architecture scales to 100 tenants with no structural changes. RLS policies apply at the table level — they are not per-tenant objects, so adding a tenant is one `INSERT` into the `tenants` table and one seed of a tenant admin user. There are no schema changes, no new policies, and no new configuration files. Migrations stay O(1) regardless of tenant count.

The cost attribution, JWT auth, service-to-service auth, and Redis session model are all scale-invariant — they operate identically whether there are 2 tenants or 200.

### Connection Pool and Memory at 100 Tenants

Postgres and Redis both handle 100 tenants comfortably on a single instance. Key sizing:

- **Postgres `max_connections`**: async SQLAlchemy uses a shared connection pool, not one pool per tenant. A pool of 20–50 async connections serves 100 tenants with concurrent traffic without exhaustion. The exact number depends on peak concurrency per tenant — set it deliberately at deployment time, not at the Postgres default (100).
- **Redis session memory**: 100 tenants × 50 active sessions × 2 KB/session ≈ 10 MB. This is negligible. The TTL of 1 800s bounds total memory consumption automatically — stale sessions expire without manual cleanup.

### modelserver Scaling

`modelserver` is stateless and CPU-only. Horizontal scaling is one replica declaration in Docker Swarm or Kubernetes — no shared state, no sticky sessions required. At 100 tenants with async classification calls, a single replica handles the load comfortably (sklearn inference is sub-millisecond). A second replica adds fault tolerance, not capacity.

### First Bottleneck: guardrails Sidecar

The NeMo Guardrails sidecar adds 50–200ms of synchronous latency per turn. At high concurrency, a single sidecar replica becomes the chokepoint before any other service. The `api` calls it with `httpx.AsyncClient` so it does not block the event loop, but queue depth still builds under load. Multiple sidecar replicas behind a load balancer is the first scaling action needed beyond a single-node deployment.

### pgvector Index

Similarity search without an index is O(n) over all vectors. At 100 tenants × 10 000 chunks each, that is 1 million vectors — a full scan per query adds hundreds of milliseconds. The HNSW index (available in pgvector 0.5+) reduces this to O(log n) with a small accuracy trade-off. The HNSW index must be created before reaching this vector count; it is not retroactively applied cheaply to a large table. **Trigger**: add the HNSW index migration when any single tenant exceeds 50 000 chunks, or when `cms_chunks` total row count exceeds 500 000 — whichever comes first. This threshold should be monitored via a Postgres row-count query in the Phase 3 CMS implementation.

### Deployment Topology

The current single-node Docker Compose topology maps directly onto Docker Swarm (add `deploy.replicas`) or Kubernetes (convert to Deployment manifests). All services are stateless except `db`, `redis`, and `minio`, which are already treated as external dependencies with connection strings from Vault. No architectural change is required to move from Compose to Swarm/K8s — the isolation model, auth, and cost attribution remain identical.

### Vault High Availability

A single Vault node is a single point of failure for secrets access. At startup, if Vault is unreachable, every service refuses to boot (`StartupError`). In production at 10+ tenants, Vault HA (Raft consensus, 3-node cluster) eliminates this SPOF. The current single-node setup is adequate for development and pilot; the HA migration is a Vault configuration change with no `api` code changes.

### The Decision to Revisit at > 500 Tenants

At 10–100 tenants, RLS on a single Postgres instance is the correct choice. At > 500 tenants — particularly if enterprise SLA commitments require per-tenant database isolation — a dedicated Postgres instance per enterprise tenant becomes worth the operational cost. This is a topology change (connection string per tenant from Vault, routing at the `api` layer), not a fundamental architectural change. The repository and RLS layers remain intact; only the connection factory changes.

---

## 6. Key Design Decisions

Each decision below follows the format: **what was chosen**, **what was rejected**, **why**. Numbers backing each choice are committed to `DECISIONS.md` after the relevant phase's evaluation runs.

---

### D1 — No Torch in Any Container

**Chosen:** Training runs offline (Colab / local notebook), exported to `joblib` (sklearn) or `ONNX`. The `modelserver` container runs only `onnxruntime`, `scikit-learn`, and `numpy`.

**Rejected:** Serving a PyTorch model from the inference container.

**Why:** A PyTorch base image adds ~2–3 GB to the container. GPU availability in a CI/CD environment cannot be assumed. ONNX export from any training framework is a one-time step that produces a portable artifact — inference quality is identical, image size stays under 500 MB, and no GPU is required at serve time. The SHA-256 boot check ensures the exported artifact is exactly what was evaluated.

---

### D2 — Arabic is Additive, English is Load-Bearing

**Chosen:** Language detection determines which system prompt and which classifier variety features to use. Detection failure (or absence of Arabic data) defaults silently to English. No English code path imports, reads, or depends on an Arabic resource.

**Rejected:** A separate Arabic-first code path or a bilingual monolith where Arabic and English processing are interleaved.

**Why:** Arabic data is thinner and harder to verify. Making English dependent on Arabic creates a fragile dependency that breaks CI if Arabic data is missing or malformed. The additive guarantee is mechanically verified: remove all Arabic rows from the dataset, run CI — all English gates must still pass with no code exceptions. Arabic becomes a progressive enhancement, not a structural requirement.

---

### D3 — Widget Auth = Signed JWT + Server-Side Origin Check, Not CORS

**Chosen:** `widget.js` exchanges a `widget_id` and request `Origin` for a signed JWT (5-minute TTL, HMAC secret from Vault). Before issuing the token, the server checks the request `Origin` header against the tenant's `allowed_origins` list — a non-browser client spoofing the `Origin` header is blocked here, not at the browser. The iframe uses this token for all subsequent calls. The server validates the token's `origin` claim against `allowed_origins` on every request.

**Rejected:** Relying on CORS headers as the auth boundary.

**Why:** CORS is a browser hint. It is enforced by the browser, not the server — a non-browser client (curl, a script, another server) ignores it entirely. A signed token makes the auth boundary server-enforced and explicit: a request without a valid token receives a 401 regardless of the Origin header. CORS and CSP (`frame-ancestors`) are retained as defense-in-depth, not as the primary control.

---

### D4 — Guardrails Fail-Closed

**Chosen:** If the NeMo Guardrails sidecar is unreachable, the `api` returns `503` to the client. Processing never continues without a guardrails validation response.

**Rejected:** Fail-open fallback — continue processing if the sidecar times out.

**Why:** A fail-open design means a sidecar outage (deploy, crash, network partition) silently removes all prompt injection and jailbreak protection for every turn processed during the outage. The outage is recoverable; a prompt injection breach that exfiltrates cross-tenant data during the window is not. The operational cost of a 503 (user sees an error, retries) is lower than the security cost of an unguarded window.

---

### D5 — `tenant_id` From JWT Only, Never From Request Body

**Chosen:** `tenant_id` is extracted exclusively in `get_current_user` from the decoded, verified JWT payload. It flows into `get_db` and all repositories from there. There is no code path that reads a `tenant_id` from the request body, query string, or headers.

**Rejected:** Accepting a `tenant_id` field in the request body as a convenience for clients.

**Why:** A body-supplied `tenant_id` is a one-line cross-tenant breach: any client can send `{"tenant_id": "<other-tenant-uuid>", ...}` and, if the server trusts it, will write or read that tenant's data under a valid session token for a different tenant. The structural fix is to make the body field impossible — not to validate it, but to never read it. The isolation holds even if a developer forgets to add a validation check.

---

### D6 — Hybrid Router: Workflow-First, Agent-Second

**Chosen:** The classifier routes clear-intent turns (spam, single-tool question, report, escalation) to deterministic workflow handlers. The bounded agent handles only ambiguous or multi-step turns. Target: ≥ 60% of turns handled by workflow.

**Rejected:** Pure-agent architecture — route everything to the tool-calling agent.

**Why:** A pure-agent design processes every turn through at least one LLM call. At 1 000 turns/day per tenant, that is ~$2–3/month in LLM spend before any complexity. Workflow handling reduces this to near-zero for the majority of turns. Beyond cost, workflow handlers are deterministic and testable — their behavior does not drift with model updates. The 60% target is measured via the cost attribution middleware and reported per tenant.

---

### D7 — Three-Way Classifier Comparison Before Shipping

**Chosen:** Train and evaluate three approaches — classical ML (TF-IDF + LogReg/linear SVM), optional DL → ONNX, and LLM zero-shot via API — on the same held-out test set. Commit the comparison table to `EVALS.md` before selecting the shipped model.

**Rejected:** Defaulting to the LLM zero-shot approach without a baseline comparison.

**Why:** "Just use GPT" is not a defensible architectural choice without measured evidence that it outperforms a simpler model on this specific dataset and task. A TF-IDF + sklearn classifier trained on civic intent data may reach comparable macro-F1 at 1/100th the per-call cost and sub-millisecond latency. The comparison is required to defend the choice. Char n-grams (3–5) in the TF-IDF pipeline handle Arabizi and Lebanese spelling variation that word-token models would miss — this is the primary reason classical ML is a strong baseline here, not just a strawman.
