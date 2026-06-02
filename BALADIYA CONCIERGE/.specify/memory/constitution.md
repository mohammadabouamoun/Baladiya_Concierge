# Baladiya Concierge Constitution

## I. Isolation Is The Grade (NON-NEGOTIABLE)

A resident on Tenant A must never reach Tenant B's data, system prompt, or any other tenant's resources — even on purpose. Every feature is secondary to this wall.

- Every DB table carries `tenant_id`. Postgres Row-Level Security (RLS) is the enforced boundary — one POLICY per table, a session variable set per request.
- The repository layer *also* scopes every query (`.filter(tenant_id == ...)`). RLS catches what a tired developer forgets.
- pgvector embeddings are tenant-filtered at query time — same RLS policy, same `tenant_id` column.
- The RLS session variable **must be reset** at the end of every request. Pooled connections that carry a leftover `tenant_id` are a cross-tenant leak.
- `tenant_id` comes from the verified signed JWT token **only** — never from a client-supplied body field, query param, or header.

## II. No Torch In Any Container (NON-NEGOTIABLE)

Training is offline (notebook / Colab). Containers run `onnxruntime` + `scikit-learn` + `numpy` only. No `torch`, no `transformers` in any image. Images over ~500 MB are a build failure, not a style issue.

## III. Arabic Is Additive, English Is Load-Bearing (NON-NEGOTIABLE)

The system is built and proven in English first. Arabic is layered in as a parallel data stream and a language-detection step. No English code path may depend on an Arabic resource existing. If Arabic data is absent, language detection returns English and the product classifies, retrieves, acts, and ships unchanged.

## IV. CORS Is Not Authentication

The widget authenticates with a short-lived, tenant-scoped signed token (JWT/HMAC). CORS and `CSP: frame-ancestors` are defense-in-depth around that token, never the authentication boundary. Trusting an origin is not the same as trusting an actor.

## V. The Evals Are The Grade

Committed thresholds in `eval_thresholds.yaml` that fail CI when regressed. A polished demo with no working CI gates scores below a rougher product whose gates are real. Four gates: classifier F1, agent tool-selection, RAG quality, red-team.

## VI. Every Decision Backed By A Number

Every architectural choice in `DESIGN.md` / `DECISIONS.md` — chunking strategy, embedding model, retrieval improvement, classifier deployment choice — must be backed by a measured number on the golden/test set. "It felt right" is not a defense answer.

## VII. No Fine-Tuning, No Scope Creep

No model fine-tuning. No torch in any container. New ideas go in a "future work" slide, not the repo. The scope is ambitious enough solo without additions.

## Engineering Standards (mandatory)

- **Async all the way:** every route, LLM call, embedding call, DB query, Redis call uses `async`.
- **DI via `Depends()`:** DB session, LLM client, current actor, retriever, redactor, per-request tenant context. No globals — DI is what lets red-team and redaction tests inject fakes.
- **Config via `pydantic-settings`, `extra="forbid"`:** secrets from Vault. `.env` holds only Vault root token and ports.
- **Logging:** `structlog` with `trace_id` + `tenant_id` on every line. Never `print()`.
- **Layers:** `api / services / repositories / domain / infra`. Thin `main.py`.
- **Retries:** `tenacity` on transient errors only. Tools return `ToolError`, never 500s.
- **Spec before code:** write `SPEC.md` per component before implementing it.

## Roles (exactly three, no more)

| Role | Boundary |
|------|----------|
| Platform Manager | Crosses tenant boundary only via narrow maintenance write/delete path. Never reads tenant conversations or requests. Every crossing audit-logged. |
| Tenant Admin | Configures its own tenant. Sees its own data only. |
| Visitor | Anonymous. Identified only by session in Redis. |

## Governance

This constitution supersedes all other practices. Amendments require justification in `DECISIONS.md`. CI gates must pass on every push — a regression that's "only temporary" is a constitution violation.

**Version**: 1.0.0 | **Ratified**: 2026-06-02 | **Last Amended**: 2026-06-02
