# SPEC.md — Baladiya Concierge

System specification for the Baladiya Concierge platform. This document defines **what**
the system must do and the **acceptance criteria** it is judged against. It complements,
and does not duplicate, the other required docs:

- **`DESIGN.md`** — *how* it is built (architecture, isolation layers, data flow).
- **`DECISIONS.md`** — *why* each choice was made, each backed by a measured number.
- **`EVALS.md`** — the measured numbers themselves (classifier, agent, RAG, red-team).
- **`SECURITY.md`** — threat model and the controls that answer it.
- **`RUNBOOK.md`** / **`DATA.md`** — operations and dataset provenance.

> Scope note: this is the **project-level** specification. Per-feature specs live under
> `specs/NNN-*/spec.md` (e.g. `specs/009-arabizi-liveeval/spec.md`). When the two disagree,
> this document governs the product; the feature spec governs that feature's increment.

---

## 1. Problem

Municipalities ("baladiya") field a steady stream of resident requests — pothole reports,
permit questions, bill enquiries, complaints — through phone lines and walk-in counters that
do not scale and do not operate after hours. Residents in this region write in **English,
Modern Standard Arabic, spoken Lebanese, and Arabizi** (Arabic in Latin characters), often
mixing them in a single message.

**Baladiya Concierge** is a multi-tenant civic SaaS: any municipality signs up, gets an
isolated tenant, and embeds a bilingual AI agent on its public website. The agent answers
questions from the municipality's own knowledge base, captures actionable requests (e.g. a
broken streetlight) as structured records, and escalates to a human when needed — all in the
resident's own language, anonymously, with no login.

---

## 2. Scope

### In scope

- Multi-tenant onboarding: a tenant is provisioned, configured, suspended, and erased.
- An embeddable, RTL-aware chat widget served to anonymous visitors.
- Bilingual (EN + AR, including MSA / Lebanese / Arabizi) intent classification, retrieval,
  and generation.
- Three agent capabilities, all tenant-scoped: **`rag_search`**, **`capture_request`**,
  **`escalate`**.
- Per-tenant knowledge base (CMS) management by the tenant admin.
- Platform-level rails (injection / jailbreak / cross-tenant / PII) plus tenant-configurable
  rails (topics, tone, persona, enabled tools).
- Aggregate cost/usage reporting to the platform manager.

### Out of scope

- Native mobile apps; the product is a website-embedded widget.
- Resident accounts / authentication — visitors are always anonymous.
- Outbound case management beyond `capture_request` + `escalate` (no ticket-tracking UI for
  residents, no SLA engine).
- Real SMS delivery in dev (OTP is logged/console-stubbed; production SMS is a deployment
  concern, not a product feature here).
- Any on-device or in-container model training. Training is **offline** only (notebook /
  Colab), exported to `joblib` / `ONNX`.

---

## 3. Actors

| Actor | Can do | Can never do |
|---|---|---|
| **Visitor** | Anonymous chat via the widget; trigger `capture_request` / `escalate` indirectly through the agent. | See another visitor's session; bypass guardrails. |
| **Tenant Admin** | Configure its own agent, widgets, guardrails, KB; read its own requests/escalations. | See any other tenant's data; weaken platform rails. |
| **Platform Manager** | Provision / suspend / erase tenants; read aggregate cost/usage. | Read any tenant's conversations or KB content. Every tenant-boundary crossing is audit-logged with the actor id. |

---

## 4. System behaviour

### 4.1 Inbound message routing (classifier → workflow / agent)

Every inbound resident message follows this contract:

```
inbound msg
   → language detection (EN | MSA | Lebanese | Arabizi)  → reply language is fixed here
   → CLASSIFIER ROUTER (separate HTTP service)
        ├─ spam                         → DROPPED before any write (never reaches capture_request)
        ├─ easy / high-confidence       → WORKFLOW handles it directly (cheaper, deterministic)
        └─ hard / low-confidence        → tool-calling AGENT (bounded loop) picks tools
```

- **Classifier output** is `intent ∈ {report, question, human, spam}` plus a confidence. The
  router uses confidence + intent to choose the workflow vs. agent path (see
  `DECISIONS.md §D3`, workflow target ≥ 60%).
- **Agent tools**: `rag_search` | `capture_request` | `escalate` — every tool is scoped by
  `tenant_id`. The agent loop is **bounded** (capped iterations and tokens per turn) for cost
  and safety.
- The classifier is consumed **over HTTP** (`modelserver`), never imported as a Python module.

### 4.2 Language contract

- Language is detected once per message; the reply is produced in the **same** language/variety.
- **English is load-bearing; Arabic is additive.** No English code path may depend on an
  Arabic resource. If Arabic data is absent, detection returns English and the system runs
  unchanged.

### 4.3 `capture_request` (unauthenticated, LLM-triggered write)

- Payload is Pydantic schema-validated before any write.
- Rate-limited per visitor/session.
- The write is scoped to the **token's** tenant — never a body-supplied `tenant_id`.
- A message classified as **spam never reaches `capture_request`**.

### 4.4 Guardrails

- **Platform rails** (prompt-injection, jailbreak, cross-tenant refusal, PII redaction) are
  **mandatory and identical for every tenant**. A tenant can never dial them down.
- **Tenant rails** (allowed topics, tone, persona, enabled tools) are configurable per tenant.
- Guardrails run as an HTTP sidecar (NeMo Guardrails), called with a service credential, and
  fail **closed** within a bounded timeout (`DECISIONS.md §D4`).

### 4.5 Tenant lifecycle

- **Provision** → isolated tenant with its own RLS scope, secrets, widget signing context.
- **Suspend** → tenant traffic refused; data retained.
- **Erase** → right-to-erasure sequence removes the tenant's data (`DESIGN.md §Right-to-Erasure`).

---

## 5. Hard constraints → acceptance criteria

These are the constitution's non-negotiables (CLAUDE.md "Hard Constraints"). Each is restated
here as a **testable acceptance criterion** with the gate that enforces it.

| # | Constraint | Acceptance criterion | Enforced by |
|---|---|---|---|
| **AC-1** | Every DB query scopes by `tenant_id`. | No query path returns rows for a tenant other than the request's. RLS is the wall; the repository layer adds a second `tenant_id` filter. | `tests/test_isolation/test_rls.py`, `tenant-isolation-audit`, red-team CI gate (must = 1.0). |
| **AC-2** | RLS session variable is reset at the **end of every request**. | After any request completes, a pooled connection carries no leftover `app.current_tenant`. | `tests/test_isolation/test_session_reset.py`. |
| **AC-3** | `tenant_id` comes from the **verified JWT only**. | A request supplying a different `tenant_id` in the body is ignored; the JWT value is authoritative. | `tests/test_isolation/*`, `DECISIONS.md §D8`. |
| **AC-4** | Widget auth = signed short-lived token + server-side origin check. | A request with an expired/forged token or disallowed origin is rejected. CORS/CSP are depth, not the boundary. | Widget token tests; `DECISIONS.md §D5`, `§D-Widget-001`. |
| **AC-5** | Vector store is tenant-filtered at query time. | A `rag_search` for tenant A never returns tenant B's chunks. | `tenant-isolation-audit`, RAG eval seeded per-tenant. |
| **AC-6** | Arabic is additive; English is load-bearing. | With all Arabic resources removed, every English path still works and detection returns English. | Language-detection tests; classifier per-variety F1 in `EVALS.md`. |
| **AC-7** | Spam is dropped before any write. | A spam-classified message produces no `capture_request` row. | Classifier gate + `capture_request` tests. |
| **AC-8** | PII (national ID, phone) is redacted everywhere it is persisted or logged. | A fake national ID / phone injected in chat appears redacted in DB, logs, and any export. | Redaction test (CI gate). |
| **AC-9** | Platform manager never reads tenant conversations; boundary crossings are audit-logged. | Platform-manager endpoints expose aggregates only; each tenant-boundary access writes an audit row with actor id. | `tests/test_isolation/test_platform_manager_access.py`, `tests/test_platform/*`. |
| **AC-10** | No torch in any container; modelserver image < ~500 MB. | `modelserver` runs only `onnxruntime` + `scikit-learn` + `numpy`; the image builds under the size budget. | `modelserver/Dockerfile`, `DECISIONS.md §D1`. |
| **AC-11** | Tools never 500 the resident reply. | A tool failure returns a structured `ToolError`; the agent recovers. Audit-path failure never breaks the resident's reply. | Agent error-path tests. |

---

## 6. Quality gates (must pass in CI)

Thresholds are the source of truth in **`eval_thresholds.yaml`**; measured values live in
**`EVALS.md`**. Every architectural choice in `DESIGN.md` / `DECISIONS.md` must be backed by a
measured number on the golden/test set.

1. **Classifier** — macro-F1 on the held-out test split, reported per language and per variety
   (EN / MSA / Lebanese / Arabizi).
2. **Agent tool-selection** — accuracy on the 15-example labelled golden set.
3. **RAG** — hit@k, MRR, faithfulness, answer-relevancy on 15 golden triples.
4. **Red-team** — injection + cross-tenant probes; **all must be refused (1.0)**.
5. **Redaction test** — injected PII never appears unredacted anywhere.
6. **Stack smoke test** — `docker-compose up` from a fresh clone comes up healthy end-to-end.

---

## 7. Known gaps (tracked, not yet closed)

These are open items at time of writing; see `HANDOFF2.md §5` for the working plan.

- **RAG judge**: the faithfulness gate currently uses a keyword proxy and answer-relevancy is
  not gated (threshold 0.0). A real LLM-judge for both, with non-zero thresholds, is required
  before the RAG gate can be honestly claimed.
- **Off-topic decline**: the workflow `question` path returns the "least irrelevant" chunks
  for off-topic queries instead of declining. An absolute similarity floor is needed;
  calibration is sensitive (off-topic "passport" 0.522 vs. a legit Arabizi query 0.551).
- **Bilingual KB parity**: 10 of the most recently seeded KB entries are EN-only and need AR
  counterparts.

These gaps do not relax any AC in §5 — they are completeness items for the eval and KB layers.
