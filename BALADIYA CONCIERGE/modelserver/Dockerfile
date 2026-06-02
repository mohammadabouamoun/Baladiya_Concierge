# modelserver — lean inference image
# Constitution: NO torch, NO transformers. Final image must be < 500 MB.
# CI build step verifies size: docker image inspect ... | jq '.[0].Size' < 524288000

FROM python:3.11-slim

WORKDIR /app

# ── OS deps (minimal) ─────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ── Python deps (no torch, no transformers) ───────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Application code ──────────────────────────────────────────────────────
COPY __init__.py classifier.py main.py ./

# ── Artifact (committed if < 50 MB, else pulled from MinIO at startup) ───
# Artifacts live in artifacts/ — copy if present, skip if not (MinIO path)
COPY artifacts/ ./artifacts/

EXPOSE 8001

# Healthcheck
HEALTHCHECK --interval=10s --timeout=5s --retries=5 \
  CMD curl -f http://localhost:8001/healthz || exit 1

CMD ["uvicorn", "modelserver.main:app", "--host", "0.0.0.0", "--port", "8001"]
