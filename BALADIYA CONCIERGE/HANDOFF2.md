# HANDOFF2 — Live Docker verification: bilingual chat, widget, KB

**Purpose:** verify the chat agent on the **real Docker stack** (classifier → guardrails →
agent → RAG) across **English, MSA, Lebanese, Arabizi**, with a working embeddable widget.

> New session? Tell Claude: **"read HANDOFF2.md"** — this file is the current state of play.

---

## 0. Current state (2026-06-19) — READ FIRST

The stack is **up, healthy, and verified**. Branch **`session/phase9-rag-evals`**. This
session changed the **workflow `question` path from raw-chunk dump → LLM-synthesized
concise answers** (see §1c) and fixed an api crash-loop (dev-mode Vault secret loss). The
off-topic decline gap remains **closed on both paths** (workflow floor + agent scope).
See §1c for the latest work, §1b for the prior RAG/evals work, §5 for what's left.

> **Cost note (matters for live demos):** every workflow question now makes **2 Gemini
> generation calls** — query-rewrite + answer-synthesis — vs **1** before (rewrite only).
> The free tier is **20 generations/day**, so the quota drains ~2× faster. A burst of test
> queries can exhaust it in one sitting → everything falls to Groq (rough Arabic + per-minute
> token throttling). Mitigations not yet done: disable query-rewrite on the workflow path,
> cache synthesized answers in Redis, or use a paid Gemini key. See §5 "Quota / cost".

- **LLM:** Gemini free tier (`gemini-2.5-flash`) is **exhausted for the day** (20 req/day),
  so chat + evals are currently answered by the **Groq fallback** (`llama-3.3-70b`). Groq
  works but produces **slightly rougher Arabic**. Clean Arabic returns automatically when
  Gemini's daily quota resets (or with a paid key). Embeddings (`gemini-embedding-001`)
  use a **separate quota** and still work. (Two LLM evals ran on Groq; re-running them on
  Gemini is **optional, not blocking** — see §5 "Gemini re-test".)
- **KB:** Beirut tenant has ~38 embedded entries; the seeder (`scripts/seed_more_kb.py`)
  now has full **bilingual parity** (10 EN + 10 AR).

---

## 1. What happened this session (all fixes)

> **Note (2026-06-15):** the work described in §1 below is now **committed** along with the
> later RAG/evals/scope work — see **§1b** for the full commit list. The "uncommitted"
> warning below is historical.

1. **Committed** the earlier language-detection fix (English-with-numbers no longer
   misread as Arabizi). `api/services/lang_detect_service.py`, `modelserver/classifier.py`.

2. **Guardrails 503 fixed.** The running guardrails image was a stale 7-day-old build with
   **no spaCy `en_core_web_lg` model** baked in → Presidio tried to download 400 MB at
   request time → 30s timeout → 503 ("حدث خطأ ما"). Fix: `docker compose build guardrails`
   (the Dockerfile already `python -m spacy download en_core_web_lg` — it just hadn't been
   rebuilt). **Lesson: always `--build` after pulling code; don't reuse stale images.**

3. **Widget bubble fixed** (`api/api/widget/router.py`, the `_LOADER_JS` loader):
   - Shows the **tenant logo** on the bubble (`widgetAppBase + '/logo.png'` →
     `http://localhost:3000/widget/logo.png`). Earlier bug: double `/widget/` 404'd.
   - **RTL-aware side** via `inset-inline-start:20px`: **English = bottom-left,
     Arabic = bottom-right** (bubble + panel both flip with the page `dir`).

4. **Agent was never loading its system prompt** → answers were giant KB dumps. Two layers:
   - `docker/api.Dockerfile` never copied `prompts/` into the image → **added
     `COPY prompts/ ./prompts/`**.
   - `.dockerignore` **also excluded `prompts/`** (silent COPY failure) → **removed that line**.
   - With the real prompt loaded ("keep responses concise"), answers got tight. This had
     affected **English too**.

5. **Prompts bind-mounted** (`docker-compose.yml`, api service:
   `./prompts:/app/prompts:ro`). Prompt edits now only need **`docker compose restart api`**
   (no rebuild). Image still bakes them in as the production default.

6. **Relevance gate** added to `api/services/tools/rag_search.py` (agent + workflow tool
   path; the RAG eval calls `rag_service.search` directly and is **unaffected**). Two-tier,
   relative to the top similarity:
   - top ≥ 0.70 (specific question) → strict ratio **0.93** (isolates the one relevant chunk).
   - top < 0.70 (broad question) → loose ratio **0.85** (keeps breadth).
   - Stops the weak Groq fallback from dumping unrelated categories (e.g. water-bill text
     bleeding into a property-tax answer).

7. **15 new KB entries seeded** via `scripts/seed_more_kb.py` (run with
   `docker compose exec -T api python - < scripts/seed_more_kb.py`; idempotent by title):
   parks, noise/quiet-hours, pet licensing, business licensing, residential parking,
   street cleaning, new water connection, stray animals, tree planting, hall booking
   (10 EN + 5 AR).

---

## 1b. RAG / evals / scope session (2026-06-15) — committed

Branch **`session/phase9-rag-evals`**, 10 commits (tree clean). Maps to the old §5 list:

| Commit | What | Old item |
|---|---|---|
| `71eacca` | **A4 off-topic floor** — variety-aware *absolute* similarity floor on the workflow `question` path (en/msa/lebanese 0.58, arabizi 0.50; calibrated via `scripts/probe_relevance.py`). Off-topic → `question_miss` decline. | A4 ✅ |
| `f69f824` | **A3 RAG LLM-judge** — real faithfulness + answer-relevancy judge (`evals/rag_judge.py`); thresholds set (0.85 each); gate wired. Measured 0.95 / 0.975. | A3 ✅ |
| `51deb97` | **KB bilingual parity** — seeder now 10 EN + 10 AR; + `list_kb.py` / `cleanup_kb.py`; removed 3 junk entries. | B1 ✅ |
| `1cdaa1c` | **SPEC.md** added (required doc) + handoff/CLAUDE updates. | A2 ✅ |
| `f8b9359` | **A5 unit gate green** — 401 on missing auth (was 403), verify-path mocks for `capture_request`, `pandas` dev dep. Documented `D-TEST-001` (kept the deprecated session-scoped `event_loop` fixture — the 0.24 loop-scope migration regressed the isolation gate). | A5 (unit) ✅ |
| `89ed358` | **A6 smoke** — verified fresh build → seed → `/healthz` → widget token → `/chat` (on-topic answer + off-topic decline) + 401. Fixed 3 RUNBOOK/compose bugs a fresh operator hits (`/healthz` not `/health`; widget token is query params not headers; dropped obsolete compose `version:`). | A6 ✅ |
| `7ac197f` | **Agent off-topic scope (the "poem" gap)** — Scope section in both prompts; agent now declines poems/coding/trivia/etc. in one sentence with no tool call. New measured gate `evals/agent_scope.json` + `evaluate_agent.py --scope` (`agent_scope_accuracy` 0.80); measured **1.000** (10/10). `D-AGENT-001`. | poem gap ✅ |

(Earlier commits `47c51ce`, `1238fef`, `6d0b16c` = prior-session backend/verify/platform-manager work folded in.)

---

## 1c. Workflow answer synthesis (2026-06-19)

**Problem:** the workflow `question` path returned the **top-3 retrieved chunks concatenated
verbatim** (`router_service.py`) — no LLM, by design (cheap path). For a specific question
like "how much is a commercial permit?" this dumped ~1400 chars of three KB entries
(building-permit + permit-requirements + business-licensing) instead of the one-line answer.
This is the *workflow* path; the agent path was already concise via its system prompt.

**Change (chosen over top-1-chunk / tighter-gate alternatives — see chat decision):**
- **`api/services/rag_service.py`** — new `synthesize_answer(query, chunks)`: feeds the top-3
  chunks to `llm_client.complete_text` (Gemini→Groq fallback) with a concise grounded-answer
  prompt **copied verbatim from the eval generator** (`evals/rag_judge.py:_ANSWER_SYS`), so
  live answers and the measured faithfulness/answer-relevancy gate exercise identical
  generation. `max_tokens=1200` — **not** 400: `gemini-2.5-flash` is a *thinking* model and
  reasoning tokens count against the budget; 400 starved the visible answer (observed cut at
  "…LBP 1,").
- **`api/services/router_service.py`** — workflow `question` path calls `synthesize_answer`
  instead of `"\n\n".join(chunks)`. **Fail-open:** on any LLM error it falls back to raw
  chunk concat so the resident still gets info (never an error / hang).

**Verified (Gemini live):** "commercial permit cost" → *"A commercial building permit
processing fee is LBP 1,200,000."*; "new water connection" → one focused sentence (no
licensing bleed); MSA office-hours → clean concise Arabic. No truncation, no dump.

**Cost:** +1 Gemini generation per workflow question (see §0 cost note + §5).

**Also this session (not a code change):** fixed an api **crash-loop** — dev-mode Vault holds
secrets in memory; when Vault state is disturbed the seeded `secret/baladiya/*` vanish and the
api can't start (`StartupError: Vault unreachable`). Cure is idempotent:
`docker compose up migrate && docker compose restart api` (re-seeds Vault). Noted in §6.

---

## 2. Bring up ONLY what the chatbot needs (keep the laptop light)

One-by-one (in dependency order). **`--build` the api/modelserver/guardrails** so fixes apply.

```bash
cd "/home/usermohammad/BALADIYA CONCIERGE"
docker compose up -d db vault redis           # foundation (wait healthy)
docker compose up migrate                      # runs to exit 0 (schema + seed)
docker compose up -d --build modelserver       # classifier (fix baked in)
docker compose build guardrails && docker compose up -d guardrails   # spaCy model baked in
docker compose up -d --build api               # has prompts + relevance gate
docker compose up -d --build widget host       # only for the browser test (port 8080)
```

Do **not** start `chatbot`, `platform_manager` (Streamlit), or `minio` — not needed.

> **Build gotcha:** `docker compose up -d --build api` occasionally hangs after the image
> is built without recreating the container. If so: build separately, then force-recreate:
> `docker compose build api && docker compose up -d --no-build --force-recreate --no-deps api`.
> Verify the new code is actually served, e.g. `curl -s localhost:8000/widget.js | grep inset-inline-start`.

Health: `curl -s localhost:8000/healthz` · `:8001/healthz` · `:8002/healthz`
(host/widget show "unhealthy" — **cosmetic** `/healthz` probe; the sites serve 200 fine.)

---

## 3. Test paths

**Browser (real widget):** open **http://localhost:8080** → click the bubble (now shows the
logo) → type. Bubble flips left/right with the EN⇄AR page toggle. OTP step works via the
real API (not the `:8787` demo). **Hard-refresh (Ctrl+Shift+R)** after any widget.js change.

**curl (headless):**
```bash
TENANT=4667fd7f-944b-4ea8-bf07-657cf4b4b880   # Beirut Municipality
TOKEN=$(curl -s -X POST localhost:8000/chat/token -H 'Content-Type: application/json' \
  -d "{\"tenant_id\":\"$TENANT\"}" | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
curl -s -X POST localhost:8000/chat -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"t1","message":"How do I report a broken streetlight?"}'
```

**OTP code (dev — no real SMS):** after the widget asks for it:
```bash
docker compose logs api --since 2m | grep sms.otp_console        # logged code
# or straight from Redis:
docker compose exec redis redis-cli --scan --pattern 'otp:*' | grep -v rate | \
  xargs -I{} docker compose exec redis redis-cli get {}
```

---

## 4. Example messages (KB now covers a lot)

Topics in the KB: building permits, business licensing, waste collection, street cleaning,
recycling, electricity outages, street lighting, water bills, **new water connections**,
property tax, parks, noise/quiet hours, pet licensing, residential parking, stray animals,
tree planting, hall booking, office hours.

- **EN:** `How much does a commercial building permit cost?` · `When is street cleaning on my street?`
- **MSA:** `ما هي ساعات عمل البلدية؟` · `كيف أحصل على رخصة عمل تجاري؟`
- **Lebanese:** `شو الخدمات يلي بتقدّمها البلدية؟` · `بدي اشتراك مياه جديد`
- **Arabizi:** `kif 2addem talab rokh9et bina?` · `2eemta bey collecto el nefeyet?`
- **Relevance check:** `How do I pay my water bill?` vs `How do I get a new water connection?`
  (must NOT bleed into each other).
- **Report flow:** send a problem, then a location next turn → phone verification.
- **Safety:** spam → dropped · `ignore your instructions…` → refused · national ID/phone → redacted.

Expected: same language in/out, concise & focused answers, sensible `handled_by`.

---

## 5. Status — what's done and what's left

### ✅ Done (committed on `session/phase9-rag-evals`)

- **A1** commit — done (10 commits, tree clean).
- **A2** SPEC.md — added.
- **A3** RAG LLM-judge — real faithfulness + answer-relevancy, gated at 0.85/0.85.
- **A4** off-topic decline (workflow path) — variety-aware absolute similarity floor.
- **A5** unit gate — 401-on-missing-auth + verify-path mocks + pandas; green per-file. (`D-TEST-001`)
- **A6** fresh-clone smoke — verified end-to-end; RUNBOOK/compose bugs fixed.
- **Poem / agent-scope gap** — agent declines off-topic; measured gate 1.000. (`D-AGENT-001`)
- **B1** bilingual KB parity — seeder is 10 EN + 10 AR.
- **C1** workflow answer synthesis — concise LLM answers replace raw-chunk dump (§1c).

### ⏳ Left to do

**Quota / cost (new, from §1c).** Workflow synthesis added a 2nd Gemini generation call per
question → 20/day free quota drains ~2× faster; a demo burst exhausts it, then Groq throttles
(per-minute token `413`) and Arabic degrades. Pick one: **(a)** disable query-rewrite on the
workflow path (halves calls, minor retrieval loss on small KB), **(b)** cache synthesized
answers per `(tenant, query)` in Redis, **(c)** paid Gemini key. (b)+(a) recommended for demos.

**A5 (full real CI run).** Only the *unit* gate was made green this session. A full green
run of **all** gates on real services still owes: classifier macro-F1, agent tool-selection,
RAG hit@k/MRR + the new judge, red-team (must be 1.0), redaction. Several need LLM calls →
**blocked by the Gemini daily quota** (see below); the rest can run now.

**A7 — re-verify Arabic quality on Gemini (not Groq).** *Blocked on quota.* Current answers
are Groq-fallback (rougher Arabic; earlier garbled words like `الثلثين` were a Groq artifact,
**not** in the KB). Re-run the AR/Arabizi examples once Gemini resets.

**B2 — host/widget healthcheck.** `/healthz` 404s on static nginx → shows "unhealthy" though
it serves fine. Add a `/healthz` location or drop the healthcheck. (Cosmetic.)

**B3 — fold `scripts/seed_more_kb.py` into the seed path** (`scripts/seed.py` / migrate) so a
fresh clone gets the richer KB automatically. **Needs a decision first:** the seeder hardcodes
the Beirut tenant id, which the migrate seed path does **not** create (it creates PM + tenants
A/B). Decide: (a) make the demo KB target tenant A, or (b) have the seed path create a Beirut
demo tenant. Until then a clean-volume stack has an empty KB and RAG declines everything.

**Minor — persona localization.** The Arabic off-topic decline rendered the persona as the
English default `"your municipality"` (the Beirut tenant's `persona` setting isn't localized).
Cosmetic; separate from the scope fix.

### Gemini re-test — optional, NOT blocking (decided 2026-06-15)

Two LLM evals ran on the **Groq fallback** (Gemini daily quota exhausted). Decision: **do
not treat re-running them on Gemini as required.** Reasoning:

1. **Agent off-topic scope** (`evaluate_agent.py --scope`, was **1.000 on Groq**) — "decline
   off-topic" is a simple, robust instruction, and it passed perfectly on the **weaker
   fallback** model. The stronger primary (Gemini) will almost certainly do at least as well,
   so there's no real downside risk. Re-confirm opportunistically the next time Gemini is
   live, but it doesn't gate anything.
2. **RAG faithfulness/relevancy judge** (0.95 / 0.975 on Groq) — the real caveat here is
   **self-evaluation bias** (Groq judged Groq's own output → optimistic), not Gemini-vs-Groq.
   Even discounted for that bias the numbers clear the 0.85 threshold, so the gate passes.
   The caveat is documented in `D-RAG-002`. Only worth a distinct-judge re-run if the RAG
   gate ever becomes hard, load-bearing CI (e.g. a paying-customer SLA) — not for this
   deliverable.

Model-**independent** (never needs a Gemini re-test): the **A4 workflow off-topic floor**
(uses `gemini-embedding-001` — a separate quota that works — + a deterministic threshold + a
static decline string; no chat LLM), and all of A5/A6 (test/config/doc, no LLM).

### Definition of done

A5's full real CI run green + A7 Arabic re-verify, then the project is shippable. The Gemini
re-tests above are optional; B2/B3 and persona localization are quality follow-ups.

---

## 6. Key facts / gotchas

- **Cold start:** after `docker compose restart`, the **first** chat message is slow (~20s)
  while guardrails inits the spaCy pipeline. Send one to warm up; subsequent calls are fast.
- **Gemini 20/day** free tier → auto-fallback to Groq after `GEMINI_FALLBACK_THRESHOLD`
  failures. Both keys are in `.env`. Embeddings are a separate quota and keep working.
  Since §1c, each workflow question costs **2** generations (rewrite + synthesis) — quota
  drains ~2× faster; see §5 "Quota / cost".
- **api crash-loop on startup** (`StartupError: Vault unreachable / InvalidPath
  secret/baladiya/db`): dev-mode Vault keeps secrets **in memory**, and `migrate` (which
  seeds them) has already exited — so if Vault's state is disturbed the api can't start.
  Idempotent cure: `docker compose up migrate && docker compose restart api`.
- **Both providers throttled at once:** Gemini `429` (daily) **and** Groq `413
  rate_limit_exceeded` (per-minute tokens) → the agent path crawls and the widget looks stuck
  on "thinking". The reply usually still arrives; the capture/report write itself succeeds.
  Wait ~1–2 min for Groq's per-minute bucket to refill; demo in English meanwhile.
- **Spam threshold is 0.90 (EN), 0.75 (AR)** — deliberately high (precision-first).
  Borderline spam below threshold goes to the agent as a fail-safe (still no write).
- **Prompts:** edit `prompts/system_{en,ar}.md` → `docker compose restart api` (mounted, no rebuild).
- **Code changes** (e.g. `rag_search.py`, `router.py`) → **rebuild** the api image.
- Beirut tenant id: `4667fd7f-944b-4ea8-bf07-657cf4b4b880`. Widget id (seed):
  `2f11bf32-ead9-45a9-8b33-3694b3f718cb`.

---

## 7. Pointers

- Plan: `specs/009-arabizi-liveeval/plan.md`
- KB seeder: `scripts/seed_more_kb.py`
- Relevance gate: `api/services/tools/rag_search.py`
- Widget loader: `api/api/widget/router.py` (`_LOADER_JS`)
- Constitution rules this protects: *"Arabic is additive, English is load-bearing"*,
  *"Spam is dropped before any write"*, *"tenant_id from JWT only"* (CLAUDE.md).
