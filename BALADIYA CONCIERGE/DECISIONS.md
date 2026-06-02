# DECISIONS.md — Baladiya Concierge

> Every architectural choice in this project is backed by a measured number. This document is the evidence trail.
> Rows marked `[TBD — Phase N]` are filled in once the relevant evaluation phase runs. The structure is intentional: it forces the decision to be made explicitly, not implicitly.

---

## 1. Classifier Choice

**Decision**: Which classifier to ship in `modelserver` for civic intent classification.
**Filled in**: Phase 2 | **Artifact**: `model_card.md` (SHA-256 hash committed alongside this table)

### Evaluation Setup

All three approaches are evaluated on the same held-out test set: rows where `sha1(text) % 5 == 0` (~20% of the dataset, no leakage from training). Evaluation is run once per approach with no further tuning after test-set exposure.

### Comparison Table

**Primary and per-class F1** (macro-F1 is the gate metric; per-class shows where each model fails):

| Approach | Macro-F1 | F1 — report | F1 — question | F1 — human | F1 — spam |
|---|---|---|---|---|---|
| Classical ML (TF-IDF + LogReg/SVM) | [TBD — Phase 2] | [TBD] | [TBD] | [TBD] | [TBD] |
| DL → ONNX (distilbert-multilingual) | [TBD — Phase 2] | [TBD] | [TBD] | [TBD] | [TBD] |
| LLM zero-shot (Gemini 2.5 Flash / Groq Arabic candidates) | [TBD — Phase 2] | [TBD] | [TBD] | [TBD] | [TBD] |

**Per-variety F1** (Arabic variety coverage is the risk surface; Arabizi and Lebanese are the thinnest cells):

| Approach | EN | MSA | Lebanese | Arabizi |
|---|---|---|---|---|
| Classical ML (TF-IDF + LogReg/SVM) | [TBD — Phase 2] | [TBD] | [TBD] | [TBD] |
| DL → ONNX (distilbert-multilingual) | [TBD — Phase 2] | [TBD] | [TBD] | [TBD] |
| LLM zero-shot (GPT-4o-mini) | [TBD — Phase 2] | [TBD] | [TBD] | [TBD] |

**Latency and cost** (measured on the held-out test set; latency is p50 single-call inference):

| Approach | Latency p50 (ms) | Cost per 1 000 calls |
|---|---|---|
| Classical ML (TF-IDF + LogReg/SVM) | [TBD — Phase 2] | ~$0.001 (infra only) |
| DL → ONNX (distilbert-multilingual) | [TBD — Phase 2] | ~$0.001 (infra only) |
| LLM zero-shot (Gemini 2.5 Flash) | [TBD — Phase 2] | ~$0.15 |

### Shipping Choice

**Chosen approach**: [TBD — Phase 2]

**Rationale**: [TBD — one sentence: "Classical ML reaches macro-F1 of X vs LLM zero-shot Y, at 1/150th the per-call cost and Zms vs Wms latency."]

**model_card.md SHA-256**: [TBD — Phase 2]

### Why Char N-Grams in the TF-IDF Pipeline

The classical ML baseline uses character n-grams (3–5) in addition to word tokens. This is not a generic choice — it is the primary reason classical ML is a competitive baseline here. Arabizi (Arabic written in Latin characters) and Lebanese dialect have highly variable spelling: "shu" / "shou" / "shoo", "ktir" / "ktiir" / "kteer". Word tokens cannot generalise across these variants; char n-grams can. The per-variety Arabizi F1 column above shows whether this hypothesis holds on the actual dataset.

---

## 2. RAG Improvement Choice

**Decision**: Which retrieval augmentation strategy to wire into the `rag_search` tool.
**Filled in**: Phase 3 | **Evaluated against**: `evals/rag_golden.json` (15 hand-labelled triples)

### Candidates

Two approaches are evaluated against a no-augmentation baseline:

- **Query rewrite** *(primary)*: an LLM call rewrites the resident's raw question into a cleaner retrieval query before embedding. Targets the gap between colloquial phrasing ("my road is broken since forever") and the formal language of CMS content.
- **Metadata filtering** *(fallback)*: the similarity search is narrowed by `lang` and `category` columns on `cms_chunks` before ranking. No additional LLM call; relies on accurate classification of the incoming message's category.

### Evaluation Protocol

Each approach is evaluated on the same 15 golden triples: `(question, ideal_answer, ground_truth_chunk_id)`. Metrics:

| Metric | Definition |
|---|---|
| hit@5 | Ground-truth chunk appears in top-5 results |
| MRR | Mean reciprocal rank of the ground-truth chunk |

### Results

| Approach | hit@5 | MRR | Additional LLM cost per query |
|---|---|---|---|
| Baseline (vanilla similarity search) | [TBD — Phase 3] | [TBD] | $0 |
| Query rewrite | [TBD — Phase 3] | [TBD] | ~$0.00015 (one Gemini 2.5 Flash call) |
| Metadata filtering | [TBD — Phase 3] | [TBD] | $0 |

### Decision Rule

**hit@5 is the gate metric; MRR is informational.** A strong MRR gain does not override a weak hit@5 gain — the gate is whether the ground-truth chunk appears in the top 5 results, not how highly it is ranked within them.

Query rewrite is the primary choice. If the measured hit@5 gain over baseline is **< 2 percentage points**, query rewrite is not worth its additional LLM cost — fall back to metadata filtering and re-evaluate against the same 15 triples.

If metadata filtering also fails to beat baseline by ≥ 2pp hit@5, the vanilla similarity search baseline ships. No tertiary augmentation strategy is pursued; further improvement is deferred to a post-launch iteration with a larger golden set. The 2pp threshold is set in `eval_thresholds.yaml`.

### Chosen Approach

**Chosen**: [TBD — Phase 3]

**Measured gain over baseline**: hit@5 [TBD], MRR [TBD]

**Rationale**: [TBD — one sentence, e.g., "Query rewrite improved hit@5 by Xpp (baseline Y → rewrite Z) at a per-query cost of $0.00015, within budget for the agent turn cost model."]

### Code Consequence

This decision directly determines the implementation of `rag_search` in `api/tools/rag_search.py`. The chosen approach is wired at implementation time — switching strategies post-launch requires a code change and a re-evaluation run, not just a config toggle.

---

## 3. Chunking Strategy

**Decision**: Chunk size, overlap, and splitting method for indexing CMS entries into `cms_chunks`.
**Filled in**: Phase 3 | **Evaluated against**: `evals/rag_golden.json` (15 hand-labelled triples)

### Why This Decision Is Load-Bearing

Chunk size directly controls retrieval quality. Chunks that are too large produce noisy similarity scores — the ground-truth passage is buried in surrounding context. Chunks that are too small lose the surrounding context the LLM needs to generate a faithful answer. The right value is empirical, not theoretical, and is hard to reverse: re-chunking existing content requires re-embedding every chunk (compute cost + API cost), so the decision is effectively locked in at Phase 3 launch.

### Candidate Strategies

| Strategy | Description |
|---|---|
| Full document (baseline) | Each CMS entry embedded as one vector — establishes the retrieval floor |
| Fixed-size character chunks | Split at N characters with M character overlap |
| Sentence-boundary chunks | Split at sentence endings; variable chunk size |
| Paragraph-boundary chunks | Split at blank lines; preserves semantic units |

### Evaluation Results

Evaluated on the 15 golden triples (hit@5, MRR):

| Strategy | Chunk size | Overlap | hit@5 | MRR |
|---|---|---|---|---|
| Full document (baseline) | — | — | [TBD — Phase 3] | [TBD] |
| Fixed-size character | [TBD] chars | [TBD] chars | [TBD — Phase 3] | [TBD] |
| Sentence-boundary | variable | 1 sentence | [TBD — Phase 3] | [TBD] |
| Paragraph-boundary | variable | 0 | [TBD — Phase 3] | [TBD] |

### Multilingual Consideration

Arabic text is denser per character than English — the same character limit covers fewer semantic units in Arabic. A 512-character chunk in English is roughly 80–100 words; in Arabic it may be 60–70 words. If fixed-size chunking is chosen, the evaluation should test whether a single character limit serves both languages adequately, or whether separate limits per `lang` field are warranted. This finding is recorded in the rationale below.

### Chosen Strategy

**Chosen**: [TBD — Phase 3]

**Chunk size**: [TBD] characters | **Overlap**: [TBD] characters

**Per-language variation**: [TBD — same limit for EN and AR, or separate limits]

**Rationale**: [TBD — one sentence, e.g., "Paragraph-boundary splitting improved hit@5 by Xpp over fixed-size at 512 chars, with no additional cost, and preserved semantic coherence in Arabic better than character limits."]

### Reversal Cost

Changing the chunking strategy post-launch requires deleting all rows in `cms_chunks`, re-splitting every `cms_entry`, and re-embedding — one hosted API call per chunk. At 10 000 entries × avg 3 chunks each × ~$0.000004/embedding = ~$0.12 per full re-index. Cheap in absolute terms, but disruptive operationally because search is degraded during re-indexing.

**Mitigation**: re-index into a shadow table (`cms_chunks_new`) while the live table continues serving queries. Cut over by renaming tables atomically once re-indexing is complete. This avoids any search downtime but doubles storage temporarily. Treat this decision as stable once Phase 3 launches — the shadow-table path is the escape hatch, not the plan.

---

## 4. Infrastructure & Architecture Choices

These decisions are structural — they are set at design time and changing them requires significant rework. Each is backed by a number that justifies the choice over the alternative.

---

### D1 — No Torch in modelserver

| | Value |
|---|---|
| Image size **with** torch (PyTorch base) | ~2.5 GB |
| Image size **without** torch (onnxruntime + sklearn + numpy) | ~350 MB |
| Hard gate | < 500 MB |
| ONNX inference quality loss vs PyTorch | None (identical weights, different runtime) |

**Verdict**: ONNX export is a one-time offline step with no inference quality cost and a 7× image size reduction. Torch is excluded from all containers permanently.

---

### D2 — RLS over Schema-Per-Tenant

| | Value |
|---|---|
| Alembic migration time: RLS (single schema) | O(1) — one migration regardless of tenant count |
| Alembic migration time: schema-per-tenant at 100 tenants | O(N) — runs against each schema; [TBD — Phase 1: measure on 2-tenant seed] |
| Isolation strength difference at 10–100 tenants | None — both provide full logical isolation |
| Connection pool model | Shared pool (RLS) vs per-tenant pool or `SET search_path` (schema) |

**Verdict**: RLS provides identical isolation at this scale with O(1) migration cost and a simpler connection pool. Schema-per-tenant re-evaluated at > 500 tenants.

---

### D3 — Hybrid Router Workflow Target (≥ 60%)

| | Value |
|---|---|
| LLM cost per agent turn (1 000 tokens, Gemini 2.5 Flash) | ~$0.00015 |
| LLM cost per workflow turn | $0 |
| Monthly LLM spend at 0% workflow, 1 000 turns/day | ~$4.50 |
| Monthly LLM spend at 60% workflow, 1 000 turns/day | ~$1.80 |
| Monthly saving per tenant at 60% workflow target | ~$2.70 |
| Measured workflow % | [TBD — Phase 4: logged via cost attribution middleware] |

**Verdict**: 60% workflow routing saves ~$2.70/tenant/month at reference load, scales linearly with volume. Target is measured in production and reported per tenant.

---

### D4 — Fail-Closed Guardrails with 2-Second Timeout

| | Value |
|---|---|
| Guardrails sidecar p50 latency | 50–200 ms (NeMo Guardrails, CPU) |
| Guardrails sidecar p99 latency | [TBD — measure under load in Phase 5] |
| Chosen timeout | 2 000 ms |
| Timeout headroom over p50 | 10–40× |
| Timeout headroom over p99 | [TBD — if p99 > 500 ms under load, 2s may cause widespread 503s at peak concurrency] |
| Behaviour on timeout | HTTP 503 returned to client; no unguarded processing |
| Cost of fail-open during outage | Prompt injection / cross-tenant exfiltration window |
| Cost of fail-closed during outage | Resident sees 503; retries after sidecar recovers |

**Verdict**: 2s timeout gives ample headroom over p50 latency. The timeout value must be validated against p99 under realistic concurrency in Phase 5 load testing — if p99 exceeds ~500 ms under peak load, the timeout may need adjustment or sidecar replicas added before production. Fail-closed is the only acceptable behaviour regardless of timeout value — an unguarded window is not recoverable.

---

### D5 — Widget JWT TTL (5 Minutes)

| | Value |
|---|---|
| Token exchange round-trip latency | ~50 ms (p50) |
| Chosen TTL | 300 seconds (5 minutes) |
| Token exchanges per 10-minute session | 2 (one at open, one at mid-session refresh) |
| Security window if token is stolen | ≤ 5 minutes before expiry |
| Alternative considered | 30-minute TTL (fewer exchanges, larger theft window) |

**Verdict**: 5 minutes balances exchange frequency (negligible UX impact) against the theft window. A stolen widget token is only useful to an attacker for the remainder of its TTL — 5 minutes is an acceptable bound for a public-facing civic service.

---

### D6 — HNSW Index Trigger (50 000 Chunks per Tenant)

| | Value |
|---|---|
| pgvector O(n) scan at 1 M vectors | ~300 ms per query |
| pgvector HNSW O(log n) at 1 M vectors | < 10 ms per query |
| Latency improvement | ~30× |
| HNSW accuracy trade-off | ~1–2% recall drop (configurable via `ef_search`) |
| Trigger threshold | 50 000 chunks in any single tenant, or 500 000 total in `cms_chunks` |
| Re-indexing cost to add HNSW after growth | High — index build on a large table locks writes briefly and takes minutes |

**Verdict**: HNSW must be added proactively. At the trigger threshold, O(n) scan latency becomes user-visible. The index is planned in the Phase 3 CMS migration; the trigger threshold is monitored via a Postgres row-count query.

---

### D7 — Vault HA Trigger (Before First Paying Tenant)

| | Value |
|---|---|
| Single-node Vault: SPOF impact | All services refuse to boot if Vault is unreachable (`StartupError`) |
| Vault HA configuration | Raft consensus, 3-node cluster |
| Node count for quorum | 2 of 3 nodes must be healthy |
| Code change required for HA migration | None — connection string change in Compose/K8s only |
| Trigger | Before first paying tenant goes live in production |

**Verdict**: Single-node Vault is acceptable for development and pilot. The HA upgrade is a Vault configuration change with zero `api` code changes — it should be completed before commercial exposure, not after.

---

### D8 — `tenant_id` From JWT Only (Structural Enforcement)

| | Value |
|---|---|
| Attack: client sends `{"tenant_id": "<other-tenant>"}` in body | Blocked — no code path reads body `tenant_id` |
| Runtime validation required | None — the field does not exist in any request schema |
| Alternative: validate body `tenant_id` against token | Requires every developer to remember to add the check |
| Structural enforcement: remove the field entirely | Zero developer-error surface; check cannot be forgotten |
| Automated gate | Red-team CI probe (Phase 1): POST with valid Tenant A token + Tenant B `tenant_id` in body → response must be scoped to Tenant A. Gate blocks merge on failure. |

**Verdict**: This is a security invariant, not a performance tradeoff. The number is the attack surface: 0 code paths that read a client-supplied `tenant_id`. Structural enforcement means the isolation holds even if a future developer adds a new endpoint without reading the security documentation. The red-team CI probe makes this an automated gate — if a developer inadvertently adds a `tenant_id` field to a Pydantic schema and the server reads it, the probe catches it before merge.

---

### D9 — Embedding Model Permanence (`gemini-embedding-001`, 1536 dims)

| | Value |
|---|---|
| Chosen model | `gemini-embedding-001` (Google AI Studio, GA, multilingual 100+ langs) |
| Chosen dimensions | 1536 (MRL-truncated from 3072 default) |
| pgvector column type | `vector(1536)` — set at table creation, never changed |
| Fallback embedding model | None — no fallback exists |
| Cost of changing the model | Re-embed entire `cms_chunks` corpus at current hosted API rate; delete + rewrite all pgvector rows |
| Why no fallback | Mixing two models' vector spaces in one table produces garbage retrieval: cross-model cosine distances are meaningless |

**Verdict**: The embedding model is a one-time permanent decision, unlike the LLM which can be swapped. `gemini-embedding-001` tops MTEB-multilingual benchmarks, is free-tier GA, and handles Arabic natively. 1536 dims is pinned at the pgvector column level — changing it later means re-embedding the entire corpus. Groq is never used for embeddings under any circumstances.
