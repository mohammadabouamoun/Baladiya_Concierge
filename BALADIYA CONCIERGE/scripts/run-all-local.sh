#!/usr/bin/env bash
# One-shot LOCAL demo launcher (no Docker). Starts every surface so the whole
# project can be shown in Chrome on the laptop. Ctrl-C stops everything.
#
#   bash scripts/run-all-local.sh
#
# Preview flags (CHATBOT_PREVIEW / PLATFORM_PREVIEW) are set here for LOCAL ONLY.
# They are never set in docker-compose, so no auth bypass exists in deployment.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export DEMO_API_URL="http://localhost:8787"

PIDS=()
cleanup() {
  echo; echo "[run-all] stopping all services …"
  for pid in "${PIDS[@]}"; do kill "$pid" 2>/dev/null || true; done
}
trap cleanup EXIT INT TERM

echo "[run-all] 1/5 demo API        → http://localhost:8787"
python3 "$ROOT/scripts/demo_api.py" & PIDS+=($!)

echo "[run-all] 2/5 website         → http://localhost:3000"
( cd "$ROOT/host" && python3 -m http.server 3000 >/dev/null 2>&1 ) & PIDS+=($!)

echo "[run-all] 3/5 tenant requests → http://localhost:8501"
CHATBOT_PREVIEW=1 python3 -m streamlit run "$ROOT/chatbot/pages/requests.py" \
  --server.headless true --server.port 8501 --browser.gatherUsageStats false >/dev/null 2>&1 & PIDS+=($!)

echo "[run-all] 4/5 tenant CMS      → http://localhost:8503"
CHATBOT_PREVIEW=1 python3 -m streamlit run "$ROOT/chatbot/pages/cms.py" \
  --server.headless true --server.port 8503 --browser.gatherUsageStats false >/dev/null 2>&1 & PIDS+=($!)

echo "[run-all] 5/5 platform mgr    → http://localhost:8502"
PLATFORM_PREVIEW=1 python3 -m streamlit run "$ROOT/platform_manager/app.py" \
  --server.headless true --server.port 8502 --browser.gatherUsageStats false >/dev/null 2>&1 & PIDS+=($!)

sleep 4
echo
echo "[run-all] all services started. Open in Chrome:"
echo "   Website (chat bubble) : http://localhost:3000"
echo "   Tenant Admin · CMS    : http://localhost:8503   (click Preview)"
echo "   Tenant Admin · Requests: http://localhost:8501  (click Preview)"
echo "   Platform Manager      : http://localhost:8502   (click Preview)"
echo
echo "[run-all] Ctrl-C to stop everything."
wait
