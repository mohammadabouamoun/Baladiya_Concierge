# HANDOFF.md — Baladiya Concierge

> Snapshot of project state as of **2026-06-02**. Written for the next agent session or future self picking up this repo cold. Read this before touching any spec file or running any skill.

---

## 1. Current Phase

| Field | Value |
|---|---|
| **Active feature** | `001-foundation-isolation` |
| **Status** | **Not started — ready to implement** |
| **Last completed task** | None. All tasks are unchecked. |
| **Next task to start** | `T-001` in `specs/001-foundation-isolation/tasks.md` — initialize repo structure |
| **How to start** | Run `/speckit-implement` — `feature.json` already points to `001-foundation-isolation` |

No code has been written yet. The project is in the spec-complete, pre-implementation state. All documentation has been drafted; implementation starts with Phase 1.

---

## 2. Completed Artifacts

### Documentation (root level)

| File | Status | Notes |
|---|---|---|
| `BALADIYA_CONCIERGE.md` | Complete | Original project spec — source of truth for product requirements |
| `CLAUDE.md` | Complete | Updated with full tech stack including Gemini/Groq API keys and model IDs |
| `DESIGN.md` | Complete | Architecture guide: isolation strategy, component map, cost model, scale story, 7 key design decisions |
| `DECISIONS.md` | Complete | Evidence trail: classifier comparison (TBD filled after Phase 2), RAG choice (TBD after Phase 3), D1–D9 infrastructure decisions |
| `EVALS.md` | Complete | CI gate overview, eval_thresholds.yaml template, golden set formats, all result rows marked TBD |
| `RUNBOOK.md` | Complete | Tenant lifecycle, secret management, sidecar recovery, incident runbook, erasure verification |
| `SECURITY.md` | Complete | Threat model, two-layer rail architecture, PII redaction scope, red-team gate, isolation enforcement |
| `DATA.md` | Complete | Dataset schema, intent definitions, labelling guidelines, split strategy, data quality audit |
| `Data.md` | Complete | User's original spec file — contains model/API key choices; kept separate from generated DATA.md |

### Spec Files (per phase)

| Feature | spec.md | plan.md | tasks.md | Status |
|---|---|---|---|---|
| `001-foundation-isolation` | ✓ | ✓ | ✓ | Ready — `feature.json` points here |
| `002-classifier` | ✓ | ✓ | ✓ | Ready |
| `003-cms-rag` | ✓ | ✓ | ✓ | Ready |
| `004-router-agent` | ✓ | ✓ | ✓ | Ready |
| `005-guardrails-security` | ✓ | ✓ | ✓ | Ready |
| `006-widget` | ✓ | ✓ | ✓ | Ready |
| `007-arabic` | ✓ | ✓ | ✓ | Ready |

### Other Spec Artifacts

| File | Status | Notes |
|---|---|---|
| `specs/tasks.md` | Complete | Master task index across all 7 phases with cross-feature dependency map |
| `specs/data-model.md` | Complete | Full DB schema for all 8 tables, Redis key patterns, RLS policy template, MinIO layout, erasure checklist |
| `.specify/memory/constitution.md` | Complete | 7 non-negotiable governance rules — supersedes all other practices |
| `.specify/extensions.yml` | Complete | Git hooks wired: `before_specify`, `before_plan`, `before_tasks`, `before_implement` |
| `.specify/feature.json` | Complete | Points to `specs/001-foundation-isolation` — created in this session |

### Dataset & Training

| File | Status | Notes |
|---|---|---|
| `civic_intent_dataset.csv` | Seed complete | ~209 rows; split deterministic (sha1 hash); NOT production-ready for Arabic F1 |
| `build_dataset.md` | Complete | Python script with `.md` extension — run with `python3 build_dataset.md` |

---

## 3. Open Decisions / Unknowns (TBD)

These are all the `[TBD]` items across the docs. None are blockers for Phase 1. Each is resolved at the phase noted.

### Classifier (Phase 2)

- `eval_thresholds.yaml → classifier_macro_f1` — placeholder `0.0`; set to (measured − 2pp) after Phase 2 training
- `eval_thresholds.yaml → en_macro_f1` — same
- `eval_thresholds.yaml → ar_macro_f1` — set in Phase 7 after Arabic retrain
- Three-way comparison table in `DECISIONS.md §1` — all F1, latency, and cost cells are `[TBD — Phase 2]`
- **LLM zero-shot candidate**: `Data.md` says to run both `gemini-2.5-flash` AND a Groq Arabic model (e.g., `mistral-saba-24b` or `allam-2-7b`) and compare per-variety Arabizi F1 — the winner becomes primary
- `model_card.md` — does not exist yet; created in Phase 2 (P2-004)
- Artifact SHA-256 — determined after training export

### RAG (Phase 3)

- `eval_thresholds.yaml → rag_hit_at_5`, `rag_mrr`, `rag_faithfulness` — all `0.0`
- Chunking strategy final choice — documented as paragraph-boundary with 512-token cap, but this is a hypothesis; actual choice and measured delta committed to `DECISIONS.md §3` after Phase 3 evaluation
- RAG improvement choice — query rewrite is the default; falls back to metadata filtering if hit@5 gain < 2pp; baseline if that also fails. Decision is confirmed with measured numbers in Phase 3
- Arabic chunk density difference — Arabic text is denser per character; whether a single character limit serves both languages is TBD (noted in DECISIONS.md §3)
- `evals/rag_golden.json` — does not exist yet; 15 hand-labelled triples created in Phase 3 (T-031)
- HNSW index trigger — threshold is set (50k chunks/tenant or 500k total) but the Postgres monitor query is not yet wired

### Agent (Phase 4)

- `eval_thresholds.yaml → agent_tool_accuracy` — `0.0`; set after Phase 4
- `evals/agent_tool_selection.json` — does not exist yet; 15 examples hand-labelled in Phase 4 (T-040)
- `max_tool_calls` and `max_tokens_per_turn` config values — not yet set; determined during Phase 4 agent loop implementation

### Security (Phase 5)

- `evals/redteam_probes.json` — does not exist yet; 12+ probes committed in Phase 5 (P5-006)
- Red-team result rows in `EVALS.md §6` and `SECURITY.md §4` — all `[TBD — Phase 5]`
- Guardrails sidecar p99 latency under load — `DECISIONS.md D4` notes this must be validated in Phase 5; if p99 > 500ms under peak load, timeout may need adjustment

### Arabic (Phase 7)

- Arabic rows in `civic_intent_dataset.csv` have not been hand-verified; thin cells: `human × all Arabic varieties`, `electricity × Arabic`, `arabizi × any intent`
- Per-variety F1 table in `EVALS.md §3` — all `[TBD]`; Arabic F1 is not reliable until each `(intent × variety)` cell has ≥ 20 verified examples

### Infrastructure (Phase 8)

- `eval_thresholds.yaml` — all placeholder values (`0.0`) must be replaced with real measured values minus 1–2pp before Phase 8 tag
- HNSW Alembic migration — planned for Phase 3 but the trigger is a runtime count check, not a fixed migration

---

## 4. Test / Audit Status

| Gate | Current state | Filled in |
|---|---|---|
| Classifier macro-F1 CI | `0.0` placeholder — trivially passes, no signal | Phase 2 |
| Agent tool-selection accuracy | `0.0` placeholder | Phase 4 |
| RAG hit@5 / MRR / faithfulness | `0.0` placeholders | Phase 3 |
| Red-team pass rate | `1.0` — the only non-placeholder threshold | Phase 5 |
| PII redaction test | Not written | Phase 5 |
| Stack smoke test | Not written | Phase 1 (gate for entire Phase 1) |

**Tenant-isolation-audit skill**: installed at `.claude/skills/tenant-isolation-audit/SKILL.md` but has not been run. Run it after every merge that adds a new route or Pydantic schema. It scans all Pydantic schemas in `api/` for any field named `tenant_id` — a developer adding such a field would pass a body-supplied tenant_id to the server.

**Test counts**: 0 tests written. No code exists yet.

**Known dataset gaps**:
- `human` intent: thin across all Arabic varieties — fill first before Phase 7
- `electricity` category × Arabic: scarce
- `arabizi` variety × any intent: hardest to verify authentically
- Do not quote Arabic macro-F1 as reliable until per-cell count ≥ 20

---

## 5. Next Phase Prep

### Phase 1 — Ready Now

1. `feature.json` already points to `specs/001-foundation-isolation` — no change needed
2. Run `/speckit-implement` to begin
3. The prerequisites script at `.specify/scripts/bash/check-prerequisites.sh` has been `chmod +x` — it will work
4. **Git is not initialized** — the `extensions.yml` has a `before_constitute` hook that calls `/speckit-git-initialize`. This will run before the first speckit command. If it doesn't trigger automatically, run `/speckit-git-initialize` manually first to avoid hook failures during implementation

### Phase 2 — Before Starting

1. Update `.specify/feature.json` → `"feature_directory": "specs/002-classifier"`
2. Ensure `civic_intent_dataset.csv` has been validated for near-duplicates (`sha1` split is deterministic but near-paraphrases can straddle the wall)
3. Training runs in a notebook (Colab or local) — **not in any container**
4. Required skill: `/rebuild-dataset` to verify counts before training

### Phase 3 — Before Starting

1. Update `feature.json` → `"feature_directory": "specs/003-cms-rag"`
2. The embedding model (`gemini-embedding-001`, 1536 dims) is permanent — the pgvector column type `vector(1536)` is set in the migration and **cannot change** without re-embedding the entire corpus
3. Hand-label 15 RAG golden triples before running any evaluation (T-031 is a hard prerequisite for T-032 and T-033)

### Phase 4 — Before Starting

1. Update `feature.json` → `"feature_directory": "specs/004-router-agent"`
2. Phase 2 (classifier) must be complete and `modelserver` must be running — the router calls it over HTTP
3. Phase 3 (CMS/RAG) must be complete — the `rag_search` tool calls `rag_service`

### Phases 5–7

Follow the cross-feature dependency map in `specs/tasks.md`:
```
P1 → ALL others
P2 (Classifier) → P4 (Router)
P3 (CMS/RAG)   → P4 (Router)
P4 (Router)    → P5 (Guardrails wraps router/agent)
P5 (Guardrails)→ P6 (Widget calls guarded API)
P6 (Widget)    → P7 (RTL + Arabic end-to-end)
P7 (Arabic)    → P8 (Final evals include Arabic numbers)
```

---

## 6. Notes for Next Agent / Future Self

### Things That Are Not Obvious From the Specs

**`build_dataset.md` is a Python script.** The `.md` extension is intentional — run it with `python3 build_dataset.md`. The row data is embedded directly inside the script as a Python list of dicts, not in a separate source file.

**`Data.md` ≠ `DATA.md`.** Two separate files exist in the root:
- `Data.md` — the user's original spec file; contains model/API key decisions; the authoritative source for model names and Vault key names
- `DATA.md` — the generated documentation file for the dataset; does not contain model info

**The HNSW index is in `tasks.md` for Phase 3** but must be added proactively — it is not retroactively applied cheaply to a large table. The trigger (50k chunks/tenant or 500k total) must be monitored via a Postgres row-count query in the Phase 3 CMS implementation. Do not wait until search is slow.

**Gemini free tier trains on your data.** This is a decided constraint, not an oversight. Documented in `SECURITY.md §Free-Tier API Data Usage`. Tenants and residents must be informed via the widget's privacy notice. If the deployment ever moves to pay-as-you-go, it opts out automatically — that is a key-swap-only change, no code changes needed.

**The embedding model is permanent.** `gemini-embedding-001` at 1536 dims is pinned in the pgvector column type. If this ever needs to change, every row in `cms_chunks` must be deleted and re-embedded. Groq never provides embeddings under any circumstances.

**`check-prerequisites.sh` needed `chmod +x`** — this was done in the session that created this file. If you're in a fresh clone, you may need to run it again: `chmod +x .specify/scripts/bash/check-prerequisites.sh`.

**`feature.json` was created in this session.** Before this session it did not exist. The prerequisites script used to default to `007-arabic` (alphabetically last). The file now correctly points to `001-foundation-isolation`. Update it manually at each phase boundary.

**Phase 8 tasks P8-003 through P8-006** in `specs/tasks.md` list DESIGN.md, DECISIONS.md, RUNBOOK.md, and SECURITY.md as Phase 8 deliverables — these have already been written early. Mark P8-003 through P8-006 as complete (`[X]`) when you reach Phase 8 without doing the work again.

**Git is not initialized in the repo.** The speckit extensions.yml has a `before_constitution` hook that calls `/speckit-git-initialize`. This should run before the first implementation command. If the hooks don't fire, the speckit `check-prerequisites.sh` will emit "Git repository not detected; skipped branch validation" warnings — these are non-fatal but branch-based FEATURE_DIR resolution won't work (use `feature.json` instead).

**LLM zero-shot comparison must include Groq Arabic models.** `Data.md` specifies that both `gemini-2.5-flash` and a Groq Arabic candidate (`mistral-saba-24b` or `allam-2-7b`) should be evaluated in the Phase 2 three-way comparison. The winner on per-variety Arabizi F1 becomes the primary LLM. If a Groq Arabic model beats Gemini on Arabizi, the roles flip — document the flip in `DECISIONS.md` before shipping.

**`tenant_id` is the Redis key suffix, not the prefix.** Session keys follow `session:{session_id}:{tenant_id}`. This is required for right-to-erasure: SCAN pattern `session:*:{tenant_id}` works; a prefix pattern would require knowing every `session_id` in advance. Do not change this key structure.

**`capture_request` never receives a spam-classified message.** Spam is dropped by the classifier before the router makes any tool call. If you are debugging why a spam message reached `capture_request`, the classifier threshold or the router logic is wrong — not the tool.

**Two files are called `spec.md`.** Each phase directory has its own `spec.md` (e.g., `specs/001-foundation-isolation/spec.md`). There is no root-level `SPEC.md`. The root `CLAUDE.md` lists `SPEC.md` as a required doc — treat each phase's `spec.md` as fulfilling this requirement, or add a root `SPEC.md` that cross-references all seven.

### Manual Steps Required Before Go-Live

- Add a privacy notice to the widget informing residents that messages are processed by a third-party AI provider (Gemini free tier)
- Update the escalation section in `RUNBOOK.md §Common Incidents` with real on-call contacts (currently has placeholder text)
- Validate `CLAUDE.md` model identifiers against live docs at `ai.google.dev` and `console.groq.com` before tagging `v0.1.0-final` — free-tier model names and quotas drift

---

*Last updated: 2026-06-02 | Session context: documentation complete, implementation not started*
