# Run Baladiya Concierge locally (no Docker)

This brings up the **entire project on the laptop without Docker**, viewable in Chrome.
It's the demo path — light enough that the machine doesn't lag.

> **Tell Claude:** "read `run_locally.md` and run them" → Claude starts every service
> below as background tasks and gives you the Chrome URLs.

---

## What runs

| Service | Port | Open in Chrome | What it is |
|---|---|---|---|
| Demo API | 8787 | (no UI) | Local Gemini chat + OTP + report store. **Backs the chat bubble.** |
| Website | 3000 | http://localhost:3000 | Municipality site + AI chat bubble (real answers, phone/OTP, report capture) |
| Tenant Admin · CMS | 8503 | http://localhost:8503 | Knowledge-base management (click **Preview** to enter) |
| Tenant Admin · Requests | 8501 | http://localhost:8501 | Captured reports from the chat bubble (click **Preview**) |
| Platform Manager | 8502 | http://localhost:8502 | Tenant provisioning, KPIs, suspend/erase (click **Preview**) |

The website chat bubble and the Requests page share one store
(`/tmp/baladiya_demo_requests.json`), so a report filed on the site appears in the
admin on refresh.

---

## The live demo loop
1. **http://localhost:3000** — open the chat bubble, ask something (Arabic or English →
   real Gemini answer), then file a report: describe the issue + location → verify phone
   (the demo code shows on screen) → you get a reference number `BEY-YYYY-#####`.
2. **http://localhost:8501** — refresh (`R`) → your report is there with its category,
   description, and **Phone verified: Yes**.
3. **http://localhost:8503** / **http://localhost:8502** — browse the two admin surfaces.

---

## What this is (and isn't)
- **Real:** live Gemini answers (bilingual), working OTP, capture → admin visibility loop.
- **Simplified (demo only):** the Demo API is raw Gemini — **no RAG grounding, no
  guardrails, no Postgres/RLS multi-tenant isolation**. Reports persist to a JSON file,
  not a database. The real architecture (the graded isolation work) runs in **Docker**;
  use the Docker recording/screenshots to prove that part.
- **Security:** `CHATBOT_PREVIEW` / `PLATFORM_PREVIEW` enable the no-password Preview
  button. They are set **only** by these local commands and **never in docker-compose**,
  so the bypass cannot exist in deployment.

---

## FOR CLAUDE — when asked to "run them", start these as background tasks

Project root: `/home/usermohammad/BALADIYA CONCIERGE`  (note the space — quote paths)
Use `DEMO_API_URL=http://localhost:8787` for the Streamlit pages.

1. **Demo API** — `cd "<root>" && python3 scripts/demo_api.py`
2. **Website** — `cd "<root>/host" && python3 -m http.server 3000`
3. **Requests (8501)** — `CHATBOT_PREVIEW=1 DEMO_API_URL=http://localhost:8787 python3 -m streamlit run chatbot/pages/requests.py --server.headless true --server.port 8501 --browser.gatherUsageStats false`
4. **Tenant CMS (8503)** — `CHATBOT_PREVIEW=1 DEMO_API_URL=http://localhost:8787 python3 -m streamlit run chatbot/pages/cms.py --server.headless true --server.port 8503 --browser.gatherUsageStats false`
5. **Platform Manager (8502)** — `PLATFORM_PREVIEW=1 DEMO_API_URL=http://localhost:8787 python3 -m streamlit run platform_manager/app.py --server.headless true --server.port 8502 --browser.gatherUsageStats false`

Then probe each port (`curl -s -o /dev/null -w "%{http_code}" http://localhost:<port>/`),
expect HTTP 200, and report the Chrome URLs back. If a port is already in use, first run
`pkill -f "scripts/demo_api.py"; pkill -f "http.server 3000"; pkill -f "streamlit run"`.

---

## Run it yourself (one terminal)
```bash
bash scripts/run-all-local.sh      # Ctrl-C stops everything
```

## Stop everything
```bash
pkill -f "scripts/demo_api.py"; pkill -f "http.server 3000"; pkill -f "streamlit run"
```
