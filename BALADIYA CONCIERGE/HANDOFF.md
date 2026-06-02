# HANDOFF.md — Baladiya Concierge

> Snapshot of project state as of **2026-06-02**. Written for the next agent session or future self picking up this repo cold. Read this before touching any spec file or running any skill.

---

## 1. Current Phase

| Field | Value |
|---|---|
| **Active feature** | `003-cms-rag` |
| **Status** | **Phases 1 & 2 complete — ready to start Phase 3** |
| **Last completed task** | All tasks in `001-foundation-isolation` and `002-classifier` are `[X]` |
| **Next task to start** | `T-001` in `specs/003-cms-rag/tasks.md` |
| **How to start** | Update `feature.json` → `"feature_directory": "specs/003-cms-rag"`, then run `/speckit-implement` |

---

## 2. What Was Built

### Phase 1 — Foundation & Tenant Isolation (`001-foundation-isolation`) ✅

**All 28 tasks complete.**

| Area | Files Created |
|---|---|
| API scaffold | `api/main.py`, `api/core/config.py`, `api/core/logging.py`, `api/core/security.py` |
| Infra | `api/infra/db.py`, `api/infra/vault.py`, `api/infra/redis.py`, `api/infra/cost.py`, `api/infra/rate_limit.py` |
| Domain models | `api/domain/tenant.py`, `api/domain/audit.py` |
| Repositories | `api/repositories/base.py`, `api/repositories/tenant_repo.py` |
| Services | `api/services/platform_service.py` |
| Platform API | `api/api/platform/router.py`, `api/api/platform/deps.py` |
| DB migrations | `alembic/versions/001_baseline.py` (tenants + RLS), `alembic/env.py`, `alembic.ini` |
| Docker | `docker-compose.yml` (11 services), `docker/api.Dockerfile`, `docker/migrate.Dockerfile` |
| Seed | `scripts/seed.py` — Platform Manager + 2 tenants from env vars (idempotent) |
| Tests | `tests/conftest.py`, `tests/test_isolation/` (RLS + session reset + red-team + PM access), `tests/test_platform/` (provisioning + erasure + rate limiter) |
| Config | `.env.example`, `eval_thresholds.yaml`, `pytest.ini`, `requirements.txt`, `requirements-dev.txt` |

**Key architectural facts:**
- `get_db()` sets `SET LOCAL app.current_tenant` and resets in `finally` — always, even on exception
- `BaseRepository` enforces `.filter(tenant_id == ...)` on every query (second isolation layer)
- Platform Manager token has `tenant_id=None` — RLS is never set for PM routes by design
- Erasure order: Redis sessions → pgvector (future) → content tables → MinIO → TenantAdmin users → Tenant row → AuditLog write

---

### Phase 2 — Classifier & Model Server (`002-classifier`) ✅

**All 17 tasks complete.**

| Area | Files Created |
|---|---|
| Training notebook | `notebooks/train_classifier.ipynb` — executed; outputs committed |
| Model server | `modelserver/main.py`, `modelserver/classifier.py`, `modelserver/Dockerfile`, `modelserver/requirements.txt` |
| Artifact | `modelserver/artifacts/classifier.joblib` (0.53 MB) |
| Model card | `modelserver/model_card.md` — two-way comparison table (Classical ML vs LLM zero-shot) |
| API integration | `api/infra/modelserver_client.py`, `api/services/router_service.py` |
| Tests | `tests/test_classifier/test_classifier_gate.py`, `tests/test_classifier/test_modelserver.py` |
| CI | `.github/workflows/ci.yml` — unit tests, latency gate, image size gate, red-team gate |
| Dataset | `civic_intent_dataset.csv` — 547 rows; `dataset_english.md` for automated expansion |

**Trained model results (2026-06-02, 547-row dataset):**

| Approach | Macro-F1 | EN F1 | AR F1 | p50 |
|---|---|---|---|---|
| **Classical ML (shipped)** | **0.8983** | **0.8784** | **0.8117** | **2.2ms** |
| LLM zero-shot (Groq llama-3.3-70b) | 0.8291 | 0.7358 | 0.8512 | 2220ms |

**Artifact SHA-256**: `1ace7e21afd41ea78872a6ed262e75f3bac4b1fe10ef7e520c27117cbe26f9a9`
**Data SHA-256**: `afbb5e166f49102ac3618c35b690294efb6ef014982ee489c7d9a7af7ff2bfc1`

---

## 3. Completed Documentation

| File | Status | Notes |
|---|---|---|
| `BALADIYA_CONCIERGE.md` | Complete | Original product spec |
| `CLAUDE.md` | Complete | Tech stack, hard constraints |
| `DESIGN.md` | Complete | Architecture, component map, 7 key decisions |
| `DECISIONS.md` | Complete | Evidence trail — classifier §1 filled; RAG/agent TBD |
| `EVALS.md` | Complete | Classifier results filled; RAG/agent/red-team TBD |
| `RUNBOOK.md` | Complete | Tenant lifecycle, incident runbook |
| `SECURITY.md` | Complete | Threat model, isolation enforcement |
| `DATA.md` | Complete | Dataset schema, labelling guidelines |
| `modelserver/model_card.md` | Complete | Two-way comparison, real F1 numbers, SHA-256 |
| `.specify/memory/constitution.md` | Complete | 7 non-negotiable governance rules |

---

## 4. Open Decisions / TBDs

### Resolved in Phase 2 ✅
- `eval_thresholds.yaml → classifier_macro_f1` = **0.88** (measured 0.8983)
- `eval_thresholds.yaml → en_macro_f1` = **0.86** (measured 0.8784)
- Three-way comparison table → now two-way: Classical ML vs LLM zero-shot (DL/ONNX dropped)
- `model_card.md` — created and filled with real numbers
- Artifact SHA-256 — recorded and verified at startup

### Still Open

**Phase 3 (RAG)**
- `eval_thresholds.yaml → rag_hit_at_5`, `rag_mrr`, `rag_faithfulness` — `0.0` placeholder
- Chunking strategy final choice — hypothesis: paragraph-boundary 512-token cap; confirm with measurement
- `evals/rag_golden.json` — does not exist; 15 triples hand-labelled in Phase 3 T-031
- Arabic chunk density — single char-limit may not serve both languages equally

**Phase 4 (Agent)**
- `eval_thresholds.yaml → agent_tool_accuracy` — `0.0` placeholder
- `evals/agent_tool_selection.json` — does not exist; 15 examples in Phase 4
- `max_tool_calls` config — not yet set

**Phase 5 (Security)**
- `evals/redteam_probes.json` — does not exist; 12+ probes in Phase 5
- Red-team gate rows in `EVALS.md §6` — all `[TBD — Phase 5]`
- Guardrails sidecar p99 under load — must validate in Phase 5

**Phase 7 (Arabic)**
- `eval_thresholds.yaml → ar_macro_f1` — `0.0`; set after Arabic dataset grows to ≥20 verified rows per cell
- Arabizi (F1=0.50) and Lebanese (F1=0.71) cells are thin — only 5 test rows each

---

## 5. CI Gate Status

| Gate | Threshold | Measured | Status |
|---|---|---|---|
| `classifier_macro_f1` | 0.88 | 0.8983 | ✅ Real value — gate active |
| `en_macro_f1` | 0.86 | 0.8784 | ✅ Real value — gate active |
| `ar_macro_f1` | 0.0 | 0.8117 | ⚠️ Placeholder — set in Phase 7 |
| `agent_tool_accuracy` | 0.0 | — | ⚠️ Placeholder — Phase 4 |
| `rag_hit_at_5` | 0.0 | — | ⚠️ Placeholder — Phase 3 |
| `rag_mrr` | 0.0 | — | ⚠️ Placeholder — Phase 3 |
| `rag_faithfulness` | 0.0 | — | ⚠️ Placeholder — Phase 3 |
| `redteam_pass_rate` | 1.0 | — | ✅ Non-negotiable — never lower |

**CI workflow**: `.github/workflows/ci.yml` — runs on every push. Gates: unit tests, latency p95 < 50ms (real artifact), modelserver image < 500 MB, red-team isolation probes.

---

## 6. Dataset State

| Source | Rows | Intent | Notes |
|---|---|---|---|
| `build_dataset.md` (hand-crafted) | 258 | all 4 | Run `python3 build_dataset.md` to regenerate |
| NYC 311 Kaggle (`nyc_311_2025.csv`) | ~229 | report only | Cached at `/tmp/311_data/nyc_311_2025.csv` |
| HuggingFace `enron_spam` | ~60 | spam only | Streamed — no download needed |
| **Total** | **547** | | |

**Workflow**: `python3 build_dataset.md` → `python3 dataset_english.md` → retrain notebook.

`build_dataset.md` **rewrites** the CSV from scratch. Always re-run `dataset_english.md` after it to re-append the 311/spam rows.

**Known thin cells** (need more data before quoting F1):
- `arabizi` × any intent: 5 test rows — F1 not reliable
- `lebanese` × any intent: 5 test rows — F1 not reliable
- `spam` × Arabic: scarce

---

## 7. Environment Notes

| Tool | Location | Notes |
|---|---|---|
| Python venv | `/home/usermohammad/.venv` | Python 3.11; all project deps installed |
| Jupyter | `/home/usermohammad/.venv/bin/jupyter` | Kernel spec updated to use venv Python |
| Kaggle credentials | `/home/usermohammad/.kaggle/kaggle.json` | User: `mohammadabouamoun` |
| API keys | `BALADIYA CONCIERGE/.env` | `GEMINI_API_KEY`, `GROQ_API_KEY` — never commit |
| Git remote | `https://github.com/mohammadabouamoun/Baladiya_Concierge.git` | Pushed to `main` |
| NYC 311 dataset | `/tmp/311_data/nyc_311_2025.csv` | 68 MB; `/tmp` — not persisted across reboots |

**onnxruntime WSL locale issue**: ONNX inference fails with `en_US.UTF-8 locale not found`. Fix: `sudo apt-get install locales language-pack-en && sudo locale-gen en_US.UTF-8`. This does not affect the shipped `classifier.joblib`.

**uv pip**: Use `uv pip install <pkg>` for faster installs. For venv-specific: `uv pip install <pkg> --python /home/usermohammad/.venv/bin/python3`.

---

## 8. Next Phase Prep — Phase 3 (CMS/RAG)

1. `feature.json` → `"feature_directory": "specs/003-cms-rag"`
2. The embedding model (`gemini-embedding-001`, 1536 dims) is permanent — pgvector column type is set at migration and **cannot change** without re-embedding the entire corpus
3. Hand-label 15 RAG golden triples before running any evaluation (T-031 is a hard prerequisite for T-032 and T-033)
4. Phase 1 DB must be running (`docker-compose up db vault migrate api redis`) before implementing RAG

---

## 9. Non-Obvious Facts

**`build_dataset.md` is a Python script.** `.md` extension is intentional. Run with `python3 build_dataset.md`.

**`Data.md` ≠ `DATA.md`.** `Data.md` is the user's original spec with model/API key decisions. `DATA.md` is the generated dataset documentation. Both exist at root.

**`feature.json` controls which phase is active.** The prerequisites script reads it. Update manually at each phase boundary.

**Gemini free tier: 20 calls/day for `gemini-2.5-flash`.** Not enough to run the LLM eval on 98 test examples. The LLM zero-shot baseline uses **Groq llama-3.3-70b** (generous free tier). See `notebooks/train_classifier.ipynb` cell-17/18.

**`classifier_confidence_thresholds` is now in `Settings`.** It was missing before — `router_service.py` was silently using hardcoded fallbacks. Fixed in the speckit-analyze remediation pass.

**Two-way comparison, not three-way.** The spec originally said "three approaches" but DL/ONNX was dropped. The comparison is now Classical ML vs LLM zero-shot only. FR-006 in `spec.md` has been updated to reflect this.

**`tenant_id` is the Redis key suffix.** Session keys: `session:{session_id}:{tenant_id}`. SCAN pattern for erasure: `session:*:{tenant_id}`. Do not change this structure.

**`capture_request` never receives spam.** Spam is dropped by the classifier BEFORE any tool call. If spam reaches the tool, the router logic is broken.

**Phase 8 docs already written.** `DESIGN.md`, `DECISIONS.md`, `RUNBOOK.md`, `SECURITY.md` are pre-written. Mark their Phase 8 tasks `[X]` without redoing the work.

---

## 10. Cross-Feature Dependency Map

```
P1 (Foundation) → ALL others
P2 (Classifier) → P4 (Router calls modelserver)
P3 (CMS/RAG)   → P4 (Router calls rag_search)
P4 (Router)    → P5 (Guardrails wraps router/agent)
P5 (Guardrails)→ P6 (Widget calls guarded API)
P6 (Widget)    → P7 (RTL + Arabic end-to-end)
P7 (Arabic)    → P8 (Final evals include AR numbers)
```

---

*Last updated: 2026-06-02 | Phases 1 & 2 complete | Next: 003-cms-rag*
