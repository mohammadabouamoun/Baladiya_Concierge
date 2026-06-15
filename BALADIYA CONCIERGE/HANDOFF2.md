# HANDOFF2 — Live Docker verification: bilingual chat, widget, KB

**Purpose:** verify the chat agent on the **real Docker stack** (classifier → guardrails →
agent → RAG) across **English, MSA, Lebanese, Arabizi**, with a working embeddable widget.

> New session? Tell Claude: **"read HANDOFF2.md"** — this file is the current state of play.

---

## 0. Current state (2026-06-15) — READ FIRST

The stack is **up, healthy, and verified**. A full smoke-test pass was run — all core
behaviors PASS (language routing, relevance, spam, injection, PII redaction, report flow).
One known polish item remains (off-topic decline — see §5).

- **LLM:** Gemini free tier (`gemini-2.5-flash`) is **exhausted for the day** (20 req/day),
  so chat is currently answered by the **Groq fallback** (`llama-3.3-70b`). Groq works but
  produces **slightly rougher Arabic**. Clean Arabic returns automatically when Gemini's
  daily quota resets (or with a paid key). Embeddings (`gemini-embedding-001`) use a
  **separate quota** and still work.
- **KB:** Beirut tenant now has **38 embedded entries** (23 original + 15 added this session).

---

## 1. What happened this session (all fixes)

All committed work so far = **only** the lang-detect fix (commit `c97a50f`). Everything
below is **uncommitted** (see §5 — needs a commit).

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

## 5. What we need to do to FINALIZE the project

Two buckets: **(A) must-do to call it finished/shippable**, then **(B) polish**.
Do A1 first — committing protects everything else.

### A. Must-do to ship (blocking)

**A1. Commit this session's work** (everything is currently uncommitted). Suggested grouping:
   - `fix(widget): logo + RTL-aware bubble in loader`
   - `fix(prompts): bake prompts into api image + bind-mount; un-ignore prompts/`
   - `feat(rag): two-tier relevance gate in rag_search tool`
   - `feat(kb): seed 15 more KB entries (scripts/seed_more_kb.py)`
   - Then `git status` should be clean. This is the single biggest risk right now —
     a large body of working changes lives only in the working tree.

**A2. Write `SPEC.md`** — it's a **required doc** (CLAUDE.md "Required Docs") and is
   currently **missing**. Should capture: problem, scope, the multi-tenant isolation model,
   the classifier→workflow/agent routing contract, and the constitution's hard constraints
   as acceptance criteria. Cross-check the other required docs exist and are current:
   `DESIGN.md`, `DECISIONS.md`, `RUNBOOK.md`, `EVALS.md`, `SECURITY.md`, `DATA.md`.

**A3. Finish the RAG eval (LLM-judge).** CI gate currently uses a **keyword proxy** for
   faithfulness (`rag_faithfulness` 0.60) and **does not gate** answer-relevancy
   (`rag_answer_relevancy` 0.0). To honestly claim the RAG gate: implement a real
   LLM-judge for faithfulness + answer-relevancy and set non-zero thresholds in
   `eval_thresholds.yaml`. (Use Gemini/Groq as judge; document the choice in `DECISIONS.md`.)

**A4. Off-topic decline (open correctness finding).** Off-topic questions (e.g. "renew my
   passport") are classified as a confident `question` → the **workflow** path concatenates
   raw top chunks (no LLM) and dumps loosely-related KB instead of declining. The relevance
   gate is *relative*, so a weak top match still returns the "least irrelevant" chunks.
   - Fix direction: add an **absolute similarity floor** — below it, return `question_miss`
     (decline) or defer to the agent. **Calibration is tricky:** off-topic "passport"
     scored **0.522**, but a legit **Arabizi** question scored **0.551** — too close. Collect
     more off-topic vs on-topic samples before setting the floor, or apply it only to the
     workflow raw-concat path and let the agent handle borderline cases. Files:
     `api/services/router_service.py` (workflow `question` branch, ~line 232).

**A5. Run the full CI gates green on a real run** (thresholds in `eval_thresholds.yaml`):
   classifier macro-F1, agent tool-selection, RAG (hit@k/MRR + the new A3 judge), red-team
   (must be 1.0), redaction test. Capture the numbers and make sure `EVALS.md` reflects the
   latest measured values (not stale ones).

**A6. Fresh-clone stack smoke test.** Per CI Gates: `docker compose up` from a **clean
   clone** must come up healthy end-to-end. Verify the image bakes everything (prompts now
   COPY'd; guardrails spaCy model baked) so it works **without** the dev bind-mounts or a
   warm cache. This is the "does it actually ship" test.

**A7. Re-verify Arabic quality on Gemini (not Groq).** Current answers are Groq-fallback
   (rougher Arabic). Once Gemini's daily quota resets (or with a paid key), re-run the
   Arabic/Arabizi examples and confirm clean output. The earlier garbled words
   (`الثلثين`, `أجهزة تشرير`) were a Groq artifact, **not** in the KB (KB chunks are clean).

### B. Polish (non-blocking, nice-to-have)

**B1. Bilingual parity for new KB.** Of the 15 new entries, 10 are EN-only (parks, parking,
   street cleaning, strays, trees, hall booking). Add AR versions for full bilingual coverage.

**B2. host/widget healthcheck.** Their `/healthz` probe 404s (static nginx) → shown
   "unhealthy" though they serve fine. Either add a `/healthz` location or drop the healthcheck.

**B3. Fold `scripts/seed_more_kb.py` into the seed path** (`scripts/seed.py` / migrate) so a
   fresh clone gets the richer KB automatically, instead of a manual exec step.

### Definition of done

All of **A1–A7** complete, `git status` clean, CI gates green on a real run, and a
fresh-clone `docker compose up` passes the smoke test. At that point the project is
finished/shippable; **B** items are quality improvements that can follow.

---

## 6. Key facts / gotchas

- **Cold start:** after `docker compose restart`, the **first** chat message is slow (~20s)
  while guardrails inits the spaCy pipeline. Send one to warm up; subsequent calls are fast.
- **Gemini 20/day** free tier → auto-fallback to Groq after `GEMINI_FALLBACK_THRESHOLD`
  failures. Both keys are in `.env`. Embeddings are a separate quota and keep working.
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
