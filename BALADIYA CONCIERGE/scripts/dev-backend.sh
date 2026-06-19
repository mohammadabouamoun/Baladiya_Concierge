#!/usr/bin/env bash
# Hybrid local dev: run ONLY the backend in Docker.
# The Streamlit admins (8501/8502) and the widget (vite 5173) run natively
# and point at this API on http://localhost:8000 — far lighter than the full stack.
set -euo pipefail

cd "$(dirname "$0")/.."

# Heavy backend only — no chatbot/platform_manager/widget/host containers.
SERVICES="db vault migrate redis minio modelserver guardrails api"

# `docker compose` (v2) or fall back to `docker-compose` (v1)
if docker compose version >/dev/null 2>&1; then DC="docker compose"; else DC="docker-compose"; fi

echo "▶ Building & starting backend: $SERVICES"
$DC up -d --build $SERVICES

echo
echo "✔ Backend starting. Useful commands:"
echo "   API logs (watch OTP codes here):  $DC logs -f api"
echo "   All backend logs:                 $DC logs -f $SERVICES"
echo "   Stop backend:                     $DC stop $SERVICES"
echo
echo "Now run the UIs natively (separate terminals):"
echo "   Tenant admin:      streamlit run chatbot/pages/cms.py --server.port 8501"
echo "   Platform manager:  streamlit run platform_manager/app.py --server.port 8502"
echo "   Widget (real chat): cd widget && npm install && npm run dev   # http://localhost:5173"
