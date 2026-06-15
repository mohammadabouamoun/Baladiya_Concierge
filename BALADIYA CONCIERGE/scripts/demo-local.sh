#!/usr/bin/env bash
# Local, no-Docker demo: real Gemini chat answers + working phone/OTP in the
# host page's chat bubble. Starts the demo API (port 8787) and a static server
# for the host page (port 3000). Ctrl-C stops both.
#
#   bash scripts/demo-local.sh
#   → open http://localhost:3000
#
# Nothing here touches Docker or the real API.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "[demo-local] starting demo API on :8787 …"
python3 "$ROOT/scripts/demo_api.py" &
API_PID=$!

cleanup() {
  echo
  echo "[demo-local] stopping …"
  kill "$API_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

sleep 1
echo "[demo-local] serving host page on http://localhost:3000  (Ctrl-C to stop)"
cd "$ROOT/host"
python3 -m http.server 3000
