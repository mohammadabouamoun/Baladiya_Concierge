#!/usr/bin/env python3
"""
dataset_english.md
==================
Builds balanced English rows for civic_intent_dataset.csv using:
  - NYC 311 Kaggle dataset  → intent=report   (Descriptor field, real resident text)
  - HuggingFace enron_spam  → intent=spam

Sources:
  Kaggle: pablomonleon/311-service-requests-nyc  (235 MB unzipped, read in chunks)
  HF:     SetFit/enron_spam  (streaming, no full download)

Usage:
    # One-time Kaggle download (cached in /tmp/311_data):
    python3 -m kaggle datasets download pablomonleon/311-service-requests-nyc -p /tmp/311_data --unzip
    # Then run this script:
    python3 dataset_english.md
    # Rebuild the master CSV:
    python3 build_dataset.md

Dependencies:  pandas  datasets  kaggle
    pip install pandas datasets kaggle
"""
from __future__ import annotations

import csv
import hashlib
import os
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

REPO_ROOT     = Path(__file__).parent
OUT_CSV       = REPO_ROOT / "civic_intent_dataset.csv"
RAW_311_CSV   = Path("/tmp/311_data/nyc_311_2025.csv")

# ── Size caps ──────────────────────────────────────────────────────────────
PER_CELL_REPORT = 60    # target new report rows per Baladiya category
SPAM_ROWS       = 60    # total new spam rows
CHUNK_ROWS      = 50_000
RANDOM_SEED     = 42
random.seed(RANDOM_SEED)

# ── NYC 311 complaint-type → Baladiya category ─────────────────────────────
# First matching keyword wins (most-specific first)
COMPLAINT_MAP: list[tuple[str, str]] = [
    # Roads
    ("street light",       "roads"),
    ("street light condition", "roads"),
    ("lamppost",           "roads"),
    ("pothole",            "roads"),
    ("street condition",   "roads"),
    ("sidewalk",           "roads"),
    ("blocked driveway",   "roads"),
    ("traffic signal",     "roads"),
    ("abandoned vehicle",  "roads"),
    ("illegal parking",    "roads"),
    # Water
    ("heat/hot water",     "water"),
    ("water system",       "water"),
    ("water leak",         "water"),
    ("water supply",       "water"),
    ("water",              "water"),
    ("plumbing",           "water"),
    # Electricity
    ("electric",           "electricity"),
    # Waste
    ("missed collection",  "waste"),
    ("dirty condition",    "waste"),
    ("illegal dumping",    "waste"),
    ("litter",             "waste"),
    ("recycling",          "waste"),
    ("garbage",            "waste"),
    ("sanitation",         "waste"),
    ("unsanitary",         "waste"),
    ("rodent",             "waste"),
    # Environment
    ("sewer",              "environment"),
    ("catch basin",        "environment"),
    ("drainage",           "environment"),
    ("noise",              "environment"),
    ("graffiti",           "environment"),
    ("damaged tree",       "environment"),
    ("air quality",        "environment"),
    # Permits
    ("general construction", "permits"),
    ("permit",             "permits"),
]

BALADIYA_CATS = {"roads", "water", "electricity", "waste", "permits", "environment"}


def map_complaint(complaint_type: str) -> str | None:
    ct = (complaint_type or "").lower()
    for keyword, category in COMPLAINT_MAP:
        if keyword in ct:
            return category
    return None


# ── Helpers ────────────────────────────────────────────────────────────────

def deterministic_split(text: str) -> str:
    h = int(hashlib.sha1(text.encode("utf-8")).hexdigest(), 16)
    return "test" if h % 5 == 0 else "train"


def load_existing_texts() -> set[str]:
    if not OUT_CSV.exists():
        return set()
    texts = set()
    with open(OUT_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            texts.add(row["text"])
    return texts


def append_rows(new_rows: list[dict]) -> None:
    if not new_rows:
        return
    fieldnames = ["id", "text", "lang", "variety", "intent", "category", "split"]
    write_header = not OUT_CSV.exists()
    with open(OUT_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            w.writeheader()
        w.writerows(new_rows)
    print(f"  Appended {len(new_rows)} rows → {OUT_CSV.name}")


# ── Source 1: NYC 311 CSV → intent=report ─────────────────────────────────

def fetch_report_rows(existing: set[str]) -> list[dict]:
    if not RAW_311_CSV.exists():
        print(f"  NYC 311 CSV not found at {RAW_311_CSV}")
        print("  Download with:")
        print("    python3 -m kaggle datasets download pablomonleon/311-service-requests-nyc -p /tmp/311_data --unzip")
        return []

    bucket: dict[str, list[str]] = defaultdict(list)   # category → [text]
    need = {cat: PER_CELL_REPORT for cat in BALADIYA_CATS}

    print(f"  Reading {RAW_311_CSV.name} in {CHUNK_ROWS:,}-row chunks ...")
    reader = pd.read_csv(
        RAW_311_CSV,
        usecols=["Complaint Type", "Descriptor"],
        chunksize=CHUNK_ROWS,
        dtype=str,
        on_bad_lines="skip",
        low_memory=False,
    )

    for chunk_idx, chunk in enumerate(reader, 1):
        for _, row in chunk.iterrows():
            cat = map_complaint(row.get("Complaint Type", ""))
            if not cat:
                continue
            if need.get(cat, 0) <= 0:
                continue
            text = str(row.get("Descriptor") or "").strip()
            if len(text) < 10 or text in existing:
                continue
            bucket[cat].append(text)
            existing.add(text)
            need[cat] -= 1

        filled = sum(1 for v in need.values() if v <= 0)
        print(f"    chunk {chunk_idx}: filled {filled}/{len(BALADIYA_CATS)} categories")
        if all(v <= 0 for v in need.values()):
            print("    All categories filled — stopping early")
            break

    rows: list[dict] = []
    idx = 300_000   # start id high to avoid collisions with build_dataset rows
    for cat, texts in bucket.items():
        for text in texts:
            rows.append({
                "id":       f"en-en-{idx:05d}",
                "text":     text,
                "lang":     "en",
                "variety":  "en",
                "intent":   "report",
                "category": cat,
                "split":    deterministic_split(text),
            })
            idx += 1

    print(f"  Report rows collected: {len(rows)}")
    for cat, n in sorted(Counter(r["category"] for r in rows).items()):
        print(f"    {cat}: {n}")
    return rows


# ── Source 2: HF enron_spam → intent=spam ─────────────────────────────────

def fetch_spam_rows(want: int, existing: set[str]) -> list[dict]:
    try:
        from datasets import load_dataset
    except ImportError:
        print("  datasets not installed — skipping spam. Run: pip install datasets")
        return []

    print(f"  Streaming {want} spam rows from SetFit/enron_spam ...")
    ds = load_dataset("SetFit/enron_spam", split="train", streaming=True)

    rows: list[dict] = []
    idx = 400_000
    for item in ds:
        if item.get("label_text") != "spam":
            continue
        text = str(item.get("message") or "").strip()
        if (len(text) < 15 or len(text) > 400 or text in existing
                or any(w in text.lower() for w in ["enron", "hou.", "ect.", "eps.", "corp."])):
            continue
        existing.add(text)
        rows.append({
            "id":       f"en-en-{idx:05d}",
            "text":     text,
            "lang":     "en",
            "variety":  "en",
            "intent":   "spam",
            "category": "none",
            "split":    deterministic_split(text),
        })
        idx += 1
        if len(rows) >= want:
            break

    print(f"  Spam rows collected: {len(rows)}")
    return rows


# ── Main ───────────────────────────────────────────────────────────────────

def main() -> None:
    print(f"Loading existing texts ...")
    existing = load_existing_texts()
    print(f"  {len(existing)} texts in CSV already (duplicates will be skipped)\n")

    print("=== Source 1: NYC 311 Kaggle CSV (intent=report) ===")
    report_rows = fetch_report_rows(existing)
    existing.update(r["text"] for r in report_rows)

    print("\n=== Source 2: HuggingFace enron_spam (intent=spam) ===")
    spam_rows = fetch_spam_rows(SPAM_ROWS, existing)

    all_new = report_rows + spam_rows
    print(f"\n=== Total new rows: {len(all_new)} ===")
    for intent, n in sorted(Counter(r["intent"] for r in all_new).items()):
        print(f"  intent={intent}: {n}")

    if not all_new:
        print("Nothing to append.")
        return

    append_rows(all_new)
    print("\nNext step: python3 build_dataset.md  (rebuilds full CSV with dedup + split report)")


if __name__ == "__main__":
    main()
