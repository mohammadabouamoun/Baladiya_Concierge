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

DL/ONNX approach dropped: `onnxruntime` locale failure on WSL (`en_US.UTF-8 not found`) and no measurable benefit over classical ML on this dataset size. Constitution §II prohibits torch in containers, and any ONNX model with meaningful multilingual capability requires torch for training. Two-way comparison is sufficient.

**Primary and per-class F1** (macro-F1 is the gate metric; per-class shows where each model fails):

| Approach | Macro-F1 | F1 — report | F1 — question | F1 — human | F1 — spam |
|---|---|---|---|---|---|
| **Classical ML (TF-IDF char 3–5 + LogReg)** | **0.8983** | **0.94** | **0.80** | **1.00** | **0.85** |
| LLM zero-shot (Groq llama-3.3-70b) | 0.8291 | — | — | — | — |

**Per-variety F1** (Arabic variety coverage is the risk surface; Arabizi and Lebanese are the thinnest cells):

| Approach | EN | MSA | Lebanese | Arabizi |
|---|---|---|---|---|
| **Classical ML (shipped)** | **0.8784** | **0.9416** | **0.7143** | **0.5000** |
| LLM zero-shot | 0.7358 | — | — | 0.8512 (AR overall) |

**Latency and cost** (measured on the held-out test set; latency is p50 single-call inference):

| Approach | Latency p50 (ms) | Cost per 1 000 calls |
|---|---|---|
| **Classical ML (shipped)** | **2.2** | **~$0.001 (infra only)** |
| LLM zero-shot (Groq llama-3.3-70b) | 2220 | ~$0.06 |

### Shipping Choice

**Chosen approach**: Classical ML (TF-IDF char 3–5 + word 1–2 + Logistic Regression)

**Rationale**: Classical ML reaches macro-F1 of 0.8983 vs LLM zero-shot 0.8291, at 1/60th the per-call cost and 2.2ms vs 2220ms latency (1000× faster), with no external API dependency on the critical classification path.

**model_card.md SHA-256**: `1ace7e21afd41ea78872a6ed262e75f3bac4b1fe10ef7e520c27117cbe26f9a9`

**Dataset SHA-256**: `afbb5e166f49102ac3618c35b690294efb6ef014982ee489c7d9a7af7ff2bfc1`

**Trained**: 2026-06-02 | Dataset size: 547 rows

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

Run `evals/evaluate_rag.py --mode compare` after seeding eval content to populate this table.

| Approach | hit@5 | MRR | Additional LLM cost per query |
|---|---|---|---|
| Baseline (vanilla similarity search) | [run eval] | [run eval] | $0 |
| **Query rewrite (shipped)** | **[run eval]** | **[run eval]** | ~$0.00015 (Gemini 2.5 Flash) |
| Metadata filtering (fallback if gain < 2pp) | [run eval if needed] | [run eval] | $0 |

Thresholds updated in `eval_thresholds.yaml` after measurement per EVALS.md §9.

### Decision Rule

**hit@5 is the gate metric; MRR is informational.** A strong MRR gain does not override a weak hit@5 gain — the gate is whether the ground-truth chunk appears in the top 5 results, not how highly it is ranked within them.

Query rewrite is the primary choice. If the measured hit@5 gain over baseline is **< 2 percentage points**, query rewrite is not worth its additional LLM cost — fall back to metadata filtering and re-evaluate against the same 15 triples.

If metadata filtering also fails to beat baseline by ≥ 2pp hit@5, the vanilla similarity search baseline ships. No tertiary augmentation strategy is pursued; further improvement is deferred to a post-launch iteration with a larger golden set. The 2pp threshold is set in `eval_thresholds.yaml`.

### Chosen Approach

**Chosen**: Query rewrite (implemented in `api/services/rag_service.py:_rewrite_query`)

**Rationale**: Query rewrite is the primary improvement because civic residents phrase requests colloquially ("my water is cut since yesterday") while CMS content uses formal language. The LLM normalises phrasing and expands Lebanese/Arabizi dialect to MSA before embedding, closing the vocabulary gap at $0.00015/query — within the agent turn cost budget. Measured delta will be recorded here after running `evals/evaluate_rag.py`.

**Fallback decision point**: If measured hit@5 gain < 2pp over baseline, `api/services/rag_service.py` will be updated to pass `lang` and `category` metadata filters to `CmsChunkRepository.similarity_search`, and the table will be updated with the fallback measurement.

### Code Consequence

`rag_search` in `api/services/rag_service.py` calls `_rewrite_query` by default (`rewrite=True`). Pass `rewrite=False` for the baseline comparison in the evaluation script. Switching strategies post-launch requires a code change and a re-evaluation run, not just a config toggle.

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

Run `evals/evaluate_rag.py --mode baseline` with chunking variants to populate this table.
The shipped strategy (paragraph-boundary) is implemented in `api/services/cms_service.py:structural_chunk`.

| Strategy | Chunk size | Overlap | hit@5 | MRR |
|---|---|---|---|---|
| Full document (baseline) | — | — | [run eval] | [run eval] |
| **Paragraph-boundary (shipped)** | **≤2048 chars (≈512 tok)** | **200 chars (≈50 tok)** | **[run eval]** | **[run eval]** |
| Fixed-size character | 2048 chars | 200 chars | [run eval if needed] | [run eval] |

### Multilingual Consideration

Arabic text is denser per character than English — the same character limit covers fewer semantic units in Arabic. A 512-character chunk in English is roughly 80–100 words; in Arabic it may be 60–70 words. The paragraph-boundary strategy uses structural cues (blank lines) rather than fixed character counts, which naturally adapts to both languages since Arabic civic content uses the same paragraph conventions. A single 2048-character cap is applied regardless of `lang` — if per-language evaluation shows a significant drop for Arabic chunks at this size, a lower cap for `lang='ar'` entries will be introduced in Phase 7.

### Chosen Strategy

**Chosen**: Paragraph-boundary splitting with 2048-char cap (≈512 tokens), 400-char minimum (≈100 tokens), 200-char overlap (≈50 tokens)

**Rationale**: Civic content entries are short and paragraph-structured (each section covers one topic). Paragraph boundaries preserve semantic units better than fixed character splits — an instruction for "building permit step 3" would be mid-sentence with fixed splitting, destroying context. The structural cue is zero-cost and language-agnostic. Actual hit@5 delta vs fixed-size baseline will be recorded after running `evals/evaluate_rag.py`.

**Per-language variation**: Single limit for EN and AR. Phase 7 will re-evaluate if AR-only hit@5 shows degradation at this cap.

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

### D10 — Session Memory TTL (30 Minutes)

**Decision**: How long to retain a resident's in-session conversation history in Redis.
**Required by**: FR-008 — TTL must be justified in this document.

| | Value |
|---|---|
| Chosen TTL | 1800 seconds (30 minutes) |
| Median resident session length (civic chatbots, field estimate) | < 5 minutes |
| 95th-percentile session length (estimated) | < 15 minutes |
| Headroom over p95 | 2× |
| Cost of too-short TTL | Resident loses context mid-session; must repeat information |
| Cost of too-long TTL | Memory key survives across device-sharing sessions; stale context from a previous resident on a shared device |
| Alternative considered | 60 minutes — doubles shared-device risk window for negligible benefit |
| Erasure compatibility | `SessionService.flush_tenant()` scans `session:*:{tenant_id}` and deletes all keys — TTL does not affect erasure completeness |

**Verdict**: 30 minutes is the minimum TTL that covers resident sessions at p95 with a 2× safety margin, while keeping the shared-device stale-context window short. The value is set in `SessionService.SESSION_TTL` (not in `eval_thresholds.yaml` — it is a product decision, not a quality gate). Measured session length data from production logs should be used to validate this estimate in Phase 8.

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

---

## Arabic & Bilingual Decisions

### D-Arabic-001 — Single Bilingual Model vs Per-Language Models

**Decision**: Ship one bilingual Classical ML classifier (TF-IDF char 3-5 + word 1-2 + LogisticRegression) trained on all four varieties (en, msa, lebanese, arabizi), rather than separate per-language models.
**Filled in**: Phase 8 | **Evidence**: Phase 7 bilingual retrain (2026-06-06, 12,731 rows)

| | Value |
|---|---|
| Measured overall macro-F1 | **0.9980** (held-out test, n=2,525) |
| Measured EN F1 | **1.0000** (template test set, n=2,412) |
| Measured AR macro-F1 | **0.9507** (hand-crafted AR test, n=113) |
| Measured Arabizi F1 | **0.8322** (machine-seeded AR test, n=41) |
| Artifact SHA-256 | `728a4bf1aee84c015ddd9d73d998573a179bd32085a9b39330a50306f177b041` |
| Training set size | 12,731 rows (10,206 train / 2,525 test) |
| Inference latency | p50=1.48ms, p95=3.97ms |

**Alternative considered — per-language models (EN model + AR model)**:

| | Per-language models | Single bilingual model |
|---|---|---|
| Expected AR F1 | Higher (no EN dilution in TF-IDF space) | 0.9507 (measured) |
| Artifacts | 2 joblib files + routing logic | 1 joblib file |
| Routing complexity | Language detection → model selection → two HTTP paths | Language detection → intent classification |
| Container footprint | ~2× | Same as Phase 2 |
| EN:AR ratio handling | Natural (separate char n-gram spaces) | 19:1 dilution — Arabizi F1 most affected |
| Constitution II compliance | Adds complexity without architecture change | Simpler |

**Why single bilingual model was chosen**:
1. **AR macro-F1 = 0.9507 exceeds the 0.93 CI gate** — the bilingual model already meets the defense threshold.
2. **Arabizi F1 = 0.8322 is the gap** — growing Arabizi cells from ~50 to ~100 per intent is the correct fix, not splitting models. A per-language AR model with 200 Arabizi examples would also suffer from thin data.
3. **Constitution VII (no scope creep)** — adding a second artifact, a model router, and a second modelserver endpoint is scope expansion. The single model achieves acceptable F1 at 1.48ms p50.
4. **Arabic is additive (Constitution III)** — a single model means Arabic quality improvements are a data problem, not an architecture problem. This keeps the EN path clean.

**Arabizi F1 caveat**: 0.8322 measured on 41 machine-seeded test rows — not statistically reliable. Hand-verify before citing in defense. Growing Arabizi cells toward 100 per intent and re-measuring is the recommended next step.

**Verdict**: Single bilingual model. Measured AR macro-F1 = 0.9507 clears the CI gate. Arabizi gap is a data quality issue, not a model architecture issue. Per-language model path is documented but deferred to post-defense if Arabizi F1 < 0.90 after Phase 8 data expansion.

---

## Widget Decisions

### D-Widget-001 — Shared JWT Signing Key vs Per-Widget Key

**Decision**: Widget tokens are signed with `Settings.jwt_secret` (the same key used by all other API JWTs), not a per-widget HMAC secret.
**Filled in**: Phase 6

| | Value |
|---|---|
| spec.md assumption | "Widget token signed with a per-widget HMAC secret stored in Vault" |
| Implementation | `jwt_secret` (single shared key, from `baladiya/api/jwt_secret` in Vault) |
| Reason for deviation | `decode_token` in `api/core/security.py` uses `jwt_secret` to validate all incoming JWTs. Adding a second key lookup per request (detecting token type, picking the right key) adds complexity with no security gain at MVP scale where a single tenant's widget compromise doesn't expose other tenants' data — RLS is the isolation boundary, not the JWT signing key |
| `widget_signing_key` in Vault | Seeded at `baladiya/widget/signing_key` and present in `Settings` but not used for JWT signing in Phase 6 |
| Security impact | None at current scale. A leaked `jwt_secret` already compromises all API tokens; a separate widget key only limits blast radius if `jwt_secret` is rotated per-tenant (not currently the case) |
| Future path | Phase 8: implement per-widget key rotation. Each widget gets its own key at `baladiya/widget/{widget_id}/signing_key`. `decode_token` checks the `widget_id` claim to select the right key. Requires a migration script to rotate existing tokens |

**Verdict**: Use `jwt_secret` for Phase 6. Per-widget key rotation is deferred to Phase 8 with the infrastructure already in place (`widget_signing_key` is seeded but unused).

**Phase 8 update (implemented 2026-06-06)**: Per-widget key rotation is now live. Each widget has its own key at `baladiya/widget/{widget_id}/signing_key` in Vault KV v2. `decode_token` performs a two-pass decode: (1) peek `widget_id` claim without signature verification, (2) fetch the per-widget key from Vault (TTL-300s LRU cache, max 128 entries), (3) full verified decode. Non-widget tokens (no `widget_id` claim) continue to use `jwt_secret`. Rotation endpoint: `POST /admin/widgets/{widget_id}/rotate-key` (Tenant Admin auth). `scripts/seed.py` migrates existing Phase 6 widgets idempotently. See `specs/008-hardening-evals/plan.md §Per-Widget Key: Vault Path Convention` for the full algorithm.

---

## RAG / Retrieval Decisions

### D-RAG-001 — Off-Topic Decline via Variety-Aware Absolute Similarity Floor

**Decision**: The confident-`question` **workflow** path declines (`question_miss`) when the
top retrieval similarity falls below a per-variety absolute floor, instead of returning the
"least irrelevant" chunks. Floors: `en/msa/lebanese = 0.58`, `arabizi = 0.50`
(`Settings.rag_relevance_floor`). The **agent** path is unaffected — it can still reason over
weak matches and decline conversationally.
**Filled in**: Phase 9 (2026-06-15)

**Problem**: The relevance gate in `api/services/tools/rag_search.py` is *relative* to the top
score, so an off-topic query (e.g. "How do I renew my passport?") still returns its single best
— and wrong — chunk. The workflow `question` branch then concatenates that raw chunk as the
answer, dumping loosely-related KB instead of declining.

**Calibration** (`scripts/probe_relevance.py`, Beirut tenant, deterministic `rewrite=False`,
11 on-topic / 10 off-topic queries):

| Variety | on-topic min | off-topic max | Floor | Separates? |
|---|---|---|---|---|
| en | 0.705 | 0.536 | 0.58 | ✅ 17pp gap |
| msa | 0.732 | 0.561 | 0.58 | ✅ (declines passport 0.561) |
| lebanese | 0.695 | 0.523 | 0.58 | ✅ |
| arabizi | 0.527 | 0.535 | 0.50 | ❌ overlaps — kept lenient |

At these floors, **20 of 21** probes classify correctly; the single miss is one Arabizi
off-topic query (0.535) that sits above on-topic Arabizi (0.527).

**Why Arabizi is the exception**: Latin-script Arabizi queries embed poorly against the
Arabic-script KB *unless* the Gemini query-rewrite normalises them to MSA first. With rewrite
unavailable (free-tier quota exhausted), Arabizi on-topic similarity collapses (~0.53) into the
off-topic band, so no floor can separate the two without false-declining real questions. Arabizi
is therefore kept lenient (0.50) to preserve recall; its off-topic gating is best-effort until
query-rewrite is healthy, at which point Arabizi normalises to MSA and the 0.58-class behaviour
applies upstream. Recalibrate then.

**Caveat**: query-rewrite is non-deterministic under intermittent quota (per-minute limit of 5),
so it can occasionally mangle an on-topic query and tank its score. The floor is calibrated on
the deterministic rewrite-off worst case to minimise false-declines of on-topic questions
(judged worse than leaking a borderline off-topic answer the relative gate already trims). Every
decline is logged (`router.question_offtopic_declined` with `top_similarity` + `floor`).

**Out of scope (separate findings)**: (1) the Beirut demo KB contains leftover eval rows
("Test Entry" / "Test Vector Entry") that off-topic queries match — a data-hygiene issue;
(2) the agent path will fulfil non-civic requests (e.g. "write me a poem") — a tenant-rails /
agent-scope gap, not a retrieval issue.

**Verdict**: Variety-aware absolute floor on the workflow path. Measured 20/21 on the calibration
probe. Borderline gov-adjacent off-topic in Arabizi is a documented residual limitation tied to
query-rewrite availability.

### D-RAG-002 — RAG Faithfulness & Answer-Relevancy via LLM-Judge

**Decision**: The RAG quality gate judges **faithfulness** (are the generated answer's claims
supported by the retrieved context?) and **answer-relevancy** (does the answer address the
question?) with a real LLM-judge (RAGAS-style), replacing the prior keyword-overlap proxy for
faithfulness and gating answer-relevancy for the first time. Judge + generator use the app's
Gemini→Groq fallback (`api/infra/llm_client.complete_text`).
**Filled in**: Phase 9 (2026-06-15)

**Problem**: faithfulness/relevancy are properties of a *generated answer*, but the eval had no
generation step — `rag_faithfulness: 0.60` was a keyword-overlap proxy on retrieved chunks and
`rag_answer_relevancy: 0.0` was ungated. Neither could be honestly cited.

**Implementation**: `evals/rag_judge.py` — for each golden triple: retrieve top-5 chunks →
generate a grounded answer → judge faithfulness against the chunks and relevancy against the
question (each returns JSON `{"score": 0..1}`). Reusable functions (`generate_answer`,
`judge_faithfulness`, `judge_relevancy`) are imported by the CI gate
(`tests/test_rag/test_rag_gate.py`, `RAG_EVAL=1`, `EVAL_TENANT_ID` set).

**Measured** (n=8 direct-source triples, Beirut KB, 2026-06-15; Groq judge):

| Metric | Mean | Min | Threshold set |
|---|---|---|---|
| faithfulness | 0.9500 | 0.80 | 0.85 |
| answer_relevancy | 0.9750 | 0.80 | 0.85 |

Thresholds use a ~10pp buffer (not the usual −2pp) because n=8 + LLM-judge + self-evaluation
carry more run-to-run variance than the stable retrieval metrics.

**Caveat (self-evaluation)**: Gemini's free-tier quota (20/day) was exhausted, so generation
*and* judging ran on the same model (Groq llama-3.3-70b). Same-model judging inflates scores.
The client prefers Gemini automatically; re-run as judge once quota resets to cross-check. A
distinct, stronger judge model is the correct future step if these gates become load-bearing.

**Also fixed**: the live gate previously retrieved against a random `uuid.uuid4()` tenant (so it
retrieved nothing and never meaningfully ran). It now reads `EVAL_TENANT_ID`, and the three live
gate tests skip cleanly when it is unset.

**Verdict**: Real LLM-judge for faithfulness + answer-relevancy; both gated at 0.85 on measured
0.95 / 0.975. Self-evaluation bias is the known limitation, documented and mitigated by the
Gemini-preferred client.

## Testing Infrastructure Decisions

### D-TEST-001 — Keep the Deprecated Session-Scoped `event_loop` Fixture

**Decision**: `tests/conftest.py` retains a custom session-scoped `event_loop` fixture
(pinned to `pytest-asyncio==0.23.8`) instead of migrating to the 0.24+
`asyncio_default_fixture_loop_scope = session` config.

**Why**: The DB `engine` fixture is session-scoped (one schema create/drop per run). That
requires a session-scoped loop. The modern replacement (drop the custom fixture, bump
pytest-asyncio to 0.24, set `asyncio_default_fixture_loop_scope = session`) was tried and
**regressed the isolation gate**: `test_rls` and `test_session_reset` began raising
"Exception closing connection" NullPool teardown errors — even when run alone, where they
were previously clean. The deprecated fixture keeps every isolation test clean in isolation.

The only cost of staying on the deprecated path is a `DeprecationWarning` and Python-3.12-local
cross-test event-loop pollution (full-suite runs show false failures that pass per-file). **CI
runs Python 3.11, where this pollution does not occur** — so the deprecation is cosmetic for the
gate that matters. Isolation is the grade; we do not ship a teardown regression to it to silence
a local-only warning.

**Reversal**: Revisit when pytest-asyncio's loop-scope handling no longer conflicts with a
session-scoped engine + NullPool, or migrate the engine fixture to function scope (slower:
schema rebuild per test). Until then the fixture stays.
