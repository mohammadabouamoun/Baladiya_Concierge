# Feature Specification: CMS & RAG (Design D)

**Feature Branch**: `003-cms-rag`

**Created**: 2026-06-02

**Status**: Draft

**Covers**: The tenant CMS (content management) and RAG retrieval over that content

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Tenant Admin Manages CMS Content (Priority: P1)

A Tenant Admin logs into the Streamlit admin app, creates/edits/deletes civic content entries (pages), and those entries become immediately searchable by the agent via RAG.

**Why this priority**: Without CMS content, the agent has nothing to retrieve. This is the knowledge foundation.

**Independent Test**: Tenant Admin creates an entry "Water bill payment: visit city hall or pay at baladiya.gov". Agent is asked "where can I pay my water bill?" and retrieves this chunk in the top-3 results.

**Acceptance Scenarios**:

1. **Given** a Tenant Admin creates a CMS entry `{title, body, category, lang}`, **When** the save completes, **Then** the entry is chunked, embedded via the multilingual hosted API, and stored in pgvector with `tenant_id` tag — all within the same request (or via a queued background job completing within 30s).
2. **Given** a Tenant Admin edits a CMS entry, **When** the save completes, **Then** the old vectors for that entry are deleted and new ones are inserted (re-index).
3. **Given** a Tenant Admin deletes a CMS entry, **When** the deletion completes, **Then** all vectors for that entry are removed from pgvector — the entry is no longer retrievable by the agent.
4. **Given** the tenant is erased (from `001-foundation-isolation`), **When** erasure completes, **Then** all vectors for that tenant are purged from pgvector (right-to-erasure compliance).

---

### User Story 2 — Resident Asks a Civic Question (Priority: P1)

A resident asks a civic question in English or Arabic. The agent retrieves the most relevant chunks from the tenant's CMS and returns a grounded answer.

**Why this priority**: RAG is the agent's primary answer mechanism. Ungrounded hallucinated answers are a product failure.

**Independent Test**: 15 RAG golden triples (question / ideal-answer / ground-truth-chunk) evaluated; hit@5 ≥ threshold in `eval_thresholds.yaml`.

**Acceptance Scenarios**:

1. **Given** a resident asks "What documents do I need for a building permit?", **When** the `rag_search` tool runs, **Then** it retrieves chunks from the tenant's CMS matching the query (tenant-filtered), ranked by similarity, and returns at most `top_k` chunks.
2. **Given** the same CMS content, **When** a resident asks the same question in Arabic ("ما هي المستندات المطلوبة لرخصة البناء؟"), **Then** the multilingual embedding retrieves the same relevant chunks — no separate Arabic RAG stack needed.
3. **Given** a retrieval query, **When** it runs, **Then** the pgvector search MUST include a `tenant_id` filter — a query that returns chunks from another tenant's CMS is a critical isolation failure.

---

### User Story 3 — RAG Quality Improvement (Priority: P2)

The RAG pipeline uses one justified improvement beyond naive fixed-size chunking + dense retrieval.

**Why this priority**: The spec requires "one non-naive improvement backed by a number on your golden set." This is an eval gate.

**Independent Test**: Baseline (naive chunking + dense retrieval) vs improved approach measured on the 15-triple golden set. Improvement must show measurable gain (hit@5, MRR, or faithfulness) documented in `EVALS.md`.

**Acceptance Scenarios**:

1. **Given** the baseline and improved RAG pipelines evaluated on the same 15-triple golden set, **When** results are compared, **Then** the improved approach shows measurable gain on at least one metric (hit@5, MRR, faithfulness, or answer relevancy) committed in `EVALS.md`.
2. **Given** the chosen improvement (rerank / query rewrite / metadata filtering), **When** it is applied, **Then** retrieval latency stays under 500ms p95 for a tenant with up to 500 CMS chunks.

---

### Edge Cases

- What if embedding API call fails during a CMS save? The entry is saved to Postgres but marked `embedding_status=pending`. A background retry re-embeds it. The admin sees a "pending" indicator.
- What if a chunk contains PII (e.g., a staff member's phone number in a CMS entry)? PII in CMS content is the tenant admin's responsibility. The platform does not redact CMS content — only chat output is redacted.
- What if the same content is authored in both Arabic and English? Both entries are stored with their `lang` tag. The multilingual embedding allows cross-language retrieval; the agent prefers same-language chunks via metadata filtering.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: CMS entries MUST be stored in a `cms_entries` table with `tenant_id`, `title`, `body`, `category`, `lang`, `embedding_status`.
- **FR-002**: On CMS save, entries MUST be chunked and embedded via the multilingual hosted-API embedding model; vectors stored in pgvector with `tenant_id`.
- **FR-003**: On CMS delete, all vectors for that entry MUST be removed from pgvector.
- **FR-004**: Every pgvector similarity search MUST filter by `tenant_id` — a search without this filter is a critical isolation bug.
- **FR-005**: The `rag_search` tool MUST return at most `top_k` (configurable, default 5) chunks with their source entry id and similarity score.
- **FR-006**: The RAG pipeline MUST use a multilingual hosted-API embedding model that handles Arabic without a separate pipeline.
- **FR-007**: One non-naive improvement (rerank / query rewrite / metadata filtering) MUST be implemented and its gain documented in `EVALS.md` vs the naive baseline.
- **FR-008**: The CI RAG gate MUST evaluate hit@5, MRR, faithfulness, and answer relevancy on 15 golden triples against thresholds in `eval_thresholds.yaml`.
- **FR-009**: Chunking strategy MUST be documented and justified in `DECISIONS.md` (not naive fixed-size; at least one structural cue used).
- **FR-010**: The embedding model MUST be called via hosted API (never a local model) — zero local model weights.

### Key Entities

- **CmsEntry**: `id`, `tenant_id`, `title`, `body`, `category`, `lang`, `embedding_status (pending|done|failed)`, `created_at`, `updated_at`
- **CmsChunk**: `id`, `entry_id`, `tenant_id`, `chunk_text`, `embedding (vector)`, `chunk_index`, `metadata (jsonb)`
- **RagSearchResult**: `{chunk_text, entry_id, similarity, source_title, lang}`

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: RAG hit@5 ≥ threshold in `eval_thresholds.yaml` (placeholder: 0.80) on 15 golden triples.
- **SC-002**: RAG faithfulness score ≥ threshold (placeholder: 0.75) using RAGAS or a frozen judge prompt.
- **SC-003**: The improved approach beats the naive baseline on at least one metric by a measurable margin documented in `EVALS.md`.
- **SC-004**: CMS entry embedding completes within 30s of save (or background job completes within 30s).
- **SC-005**: Retrieval latency < 500ms p95 for a tenant with up to 500 chunks.
- **SC-006**: Arabic question retrieves the correct English chunk (cross-language retrieval verified on at least 3 golden triples).

---

## Assumptions

- The multilingual embedding model is a hosted API (e.g., `text-embedding-3-small` with multilingual capability, or a comparable multilingual model) — no local weights.
- Chunking is done server-side in Python at CMS save time. Chunk size and overlap are configurable parameters in `Settings`.
- The Streamlit admin CMS UI is a CRUD form — no rich text editor needed for v1.
- The 15-triple RAG golden set is hand-labeled and committed under `evals/rag_golden.json`.
- RAGAS or a frozen judge LLM is used for faithfulness evaluation — the choice is committed in `DECISIONS.md`.
