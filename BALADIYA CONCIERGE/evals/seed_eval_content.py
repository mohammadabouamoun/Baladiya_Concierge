"""Seed the test DB with CMS entries from the golden set.

Usage:
    EVAL_TOKEN=<tenant_admin_jwt> EVAL_TENANT_ID=<uuid> python evals/seed_eval_content.py

Creates one CMS entry per unique source_entry in rag_golden.json and waits
for embeddings to complete (status=done) before exiting.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).parent.parent
GOLDEN_PATH = ROOT / "evals" / "rag_golden.json"
API_BASE = os.environ.get("API_BASE_URL", "http://localhost:8000")
EVAL_TOKEN = os.environ.get("EVAL_TOKEN", "")


async def _main() -> None:
    if not EVAL_TOKEN:
        print("ERROR: Set EVAL_TOKEN.", file=sys.stderr)
        sys.exit(1)

    data = json.loads(GOLDEN_PATH.read_text())
    headers = {"Authorization": f"Bearer {EVAL_TOKEN}"}

    # Deduplicate by source entry title
    seen: set[str] = set()
    entries_to_create: list[dict] = []
    for triple in data["triples"]:
        if "source_entry" in triple:
            entry = triple["source_entry"]
            if entry["title"] not in seen:
                seen.add(entry["title"])
                entries_to_create.append(entry)

    async with httpx.AsyncClient(base_url=API_BASE, timeout=60.0) as client:
        for entry in entries_to_create:
            resp = await client.post("/cms/entries", headers=headers, json=entry)
            if resp.status_code == 201:
                print(f"Created: {entry['title']} (status={resp.json()['embedding_status']})")
            else:
                print(f"ERROR creating {entry['title']}: {resp.status_code} {resp.text}")

        # Wait for all embeddings to complete
        print("\nWaiting for embeddings to complete...")
        for attempt in range(12):
            await asyncio.sleep(5)
            resp = await client.get("/cms/entries", headers=headers)
            entries = resp.json()
            pending = [e for e in entries if e["embedding_status"] != "done"]
            if not pending:
                print("All entries embedded successfully.")
                break
            print(f"  Still pending: {len(pending)} entries...")
        else:
            print("WARNING: Some entries did not finish embedding within 60s.")


if __name__ == "__main__":
    asyncio.run(_main())
