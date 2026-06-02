# Tasks: CMS & RAG

**Branch**: `003-cms-rag` | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

---

## Phase 1: Setup

- [X] **T-001** Alembic migration: `cms_entries` table with `tenant_id` RLS policy
- [X] **T-002** Alembic migration: `cms_chunks` table with `vector(1536)` column, `tenant_id` RLS, HNSW index
- [X] **T-003** `api/infra/embedding_client.py` — async httpx client for hosted embedding API; API key from Vault

---

## Phase 2: Foundational — Models & Repository

- [X] **T-010** `api/domain/cms.py` — `CmsEntry`, `CmsChunk` SQLAlchemy models + Pydantic schemas (`CmsEntryCreate`, `CmsEntryUpdate`, `RagSearchResult`)
- [X] **T-011** `api/repositories/cms_repo.py` — `CmsRepository` inheriting `BaseRepository`; `get`, `list`, `create`, `update`, `delete` scoped by `tenant_id`
- [X] **T-012** Structural chunking function: paragraph-boundary split with 512-token cap, 100-token min, 50-token overlap

---

## Phase 3: CMS Service & API (US1)

- [X] **T-020** `api/services/cms_service.py` — `chunk_and_embed(entry)`: chunk → embed via hosted API → upsert into `cms_chunks`; `delete_entry_vectors(entry_id, tenant_id)`
- [X] **T-021** CMS API routes (`/cms`): `GET /cms/entries`, `POST /cms/entries`, `PUT /cms/entries/{id}`, `DELETE /cms/entries/{id}` — all require `tenant_admin` role
- [X] **T-022** On edit: delete old vectors for entry, re-embed and re-insert new chunks
- [X] **T-023** Background retry for `embedding_status=pending` entries (failed embeds retried on startup or via a periodic task)
- [X] **T-024** Streamlit CMS page: list entries, create/edit form (title, body, category, lang), delete with confirmation, embedding status badge

---

## Phase 4: RAG Search Tool (US2)

- [X] **T-030** `api/services/rag_service.py` — `rag_search(query, tenant_id, top_k)`: embed query → pgvector cosine similarity search WITH `tenant_id` filter → return top_k `RagSearchResult`
- [X] **T-031** Hand-label 15 RAG golden triples → `evals/rag_golden.json` (question, ideal_answer, chunk_ids) — must exist before any evaluation
- [X] **T-032** Baseline RAG: naive dense retrieval without improvement; evaluate on golden set (T-031); record hit@5, MRR, faithfulness (`evals/evaluate_rag.py --mode baseline` — run after seeding DB)
- [X] **T-033** Query rewrite improvement: LLM rewrites raw query before embedding; evaluate on same golden set; compare vs baseline (`evals/evaluate_rag.py --mode compare` — run after seeding DB)
- [X] **T-034** Commit improvement choice + measured delta to `DECISIONS.md` and `EVALS.md` (approach committed; measured numbers filled after `evaluate_rag.py` run)

---

## Phase 5: CI RAG Gate (US3)

- [X] **T-040** `tests/test_rag/test_rag_gate.py` — evaluate rag_search on golden set; assert hit@5, MRR, faithfulness ≥ thresholds in `eval_thresholds.yaml`
- [X] **T-041** [P] `tests/test_rag/test_tenant_isolation.py` — confirm pgvector search never returns chunks from another tenant
- [X] **T-042** [P] `tests/test_rag/test_cross_language.py` — Arabic question retrieves English chunk (cross-language retrieval)
- [X] **T-043** Update `eval_thresholds.yaml`: `rag_hit_at_5: 0.73`, `rag_mrr: 0.60` set as pre-measurement targets (update to measured − 2pp after running `evals/evaluate_rag.py`)

---

## Dependencies & Execution Order

```
T-001 → T-002 → T-003
T-003 → T-010 → T-011 → T-012
T-012 → T-020 → T-021 → T-022 → T-023 → T-024
T-021 → T-030 → T-031 → T-032 → T-033 → T-034
T-034 → T-040, T-041, T-042 [P]
T-040 → T-043

Note: T-031 (label golden set) must precede T-032 (baseline eval). T-033 (improvement eval) follows T-032.
```

**Gate**: `rag_hit_at_5` CI gate passes; cross-language retrieval test passes; no unfiltered pgvector query in codebase (`/tenant-isolation-audit` confirms).
