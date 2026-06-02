# Implementation Plan: CMS & RAG

**Branch**: `003-cms-rag` | **Date**: 2026-06-02 | **Spec**: [spec.md](./spec.md)

## Summary

Implement the tenant CMS (CRUD content entries in Streamlit), chunk and embed content into tenant-filtered pgvector on save, and build the `rag_search` tool with one justified retrieval improvement backed by a number on the golden set.

## Technical Context

**Language/Version**: Python 3.11

**Primary Dependencies**: FastAPI, async SQLAlchemy, pgvector, httpx (hosted embedding API), streamlit, asyncpg

**Storage**: PostgreSQL 16 + pgvector (`cms_entries`, `cms_chunks` tables); MinIO for CMS media attachments

**Testing**: pytest + pytest-asyncio; real DB with two seeded tenants; 15-triple golden set in `evals/rag_golden.json`

**Target Platform**: `api` + `chatbot` (Streamlit) Docker services

**Performance Goals**: Embedding completes within 30s of CMS save; retrieval < 500ms p95 for ≤ 500 chunks/tenant

**Constraints**: pgvector search MUST always include `tenant_id` filter; embedding via hosted API only (no local model weights); one non-naive improvement, justified by number

## Constitution Check

- [x] Every pgvector query filters by `tenant_id` — no unfiltered similarity search
- [x] Embedding via hosted multilingual API — zero local model weights
- [x] One improvement, not five — backed by a measured number
- [x] CMS delete triggers vector delete (right-to-erasure path)

## Project Structure

```text
api/
├── domain/
│   └── cms.py                  ← CmsEntry, CmsChunk models + Pydantic schemas
├── repositories/
│   └── cms_repo.py             ← CmsRepository (inherits BaseRepository)
├── infra/
│   └── embedding_client.py     ← httpx AsyncClient for hosted embedding API
├── services/
│   ├── cms_service.py          ← chunk_and_embed(), delete_entry_vectors()
│   └── rag_service.py          ← rag_search() tool: retrieve + optional improvement
└── api/
    └── cms/
        └── router.py           ← /cms CRUD routes (tenant admin only)

chatbot/
└── pages/
    └── cms.py                  ← Streamlit CMS page: create/edit/delete entries

evals/
└── rag_golden.json             ← 15 triples: {question, ideal_answer, chunk_ids}
```

## Chunking Strategy

Structural chunking by paragraph boundary with a max-token cap (512 tokens), minimum chunk size (100 tokens), and 50-token overlap. Rationale: civic content entries are short and paragraph-structured — paragraph boundaries preserve semantic units better than fixed-size splits. Justified in `DECISIONS.md` vs fixed-size baseline using hit@5 on the golden set.

## One RAG Improvement: Query Rewrite

Before similarity search, the agent's raw query is rewritten by the LLM into a cleaner retrieval query (removes filler words, expands acronyms, normalizes dialect to MSA for Arabic). Measured vs naive baseline on the 15-triple golden set. If gain < 2pp hit@5, fall back to metadata filtering as the improvement instead.

## Embedding + Indexing Flow

```
CMS save →
  chunk_and_embed(entry):
    chunks = structural_chunk(entry.body)
    for chunk in chunks:
      embedding = await embedding_client.embed(chunk.text)   # hosted API
      insert CmsChunk(tenant_id, entry_id, chunk_text, embedding, metadata)
  mark entry.embedding_status = "done"

CMS delete →
  DELETE FROM cms_chunks WHERE entry_id = ? AND tenant_id = ?   (RLS enforced)
  DELETE FROM cms_entries WHERE id = ? AND tenant_id = ?
```

## Service-to-Service Auth

Embedding API calls use the hosted provider's API key, resolved from Vault at startup. No unauthenticated embedding calls.
