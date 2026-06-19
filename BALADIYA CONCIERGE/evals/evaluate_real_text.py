"""Evaluate the classifier on non-template English resident messages.

Loads evals/real_text_en_sample.json (NYC 311 descriptions + manual examples)
and runs the classifier artifact against it, reporting macro-F1 and per-class F1.
Results go into modelserver/model_card.md §Real-Text EN Evaluation.

Usage:
    python evals/evaluate_real_text.py
"""
from __future__ import annotations

import json
import pathlib

ROOT = pathlib.Path(__file__).parent.parent


def main() -> None:
    import joblib
    from sklearn.metrics import classification_report, f1_score

    artifact = ROOT / "modelserver" / "artifacts" / "classifier.joblib"
    sample_file = ROOT / "evals" / "real_text_en_sample.json"

    clf = joblib.load(artifact)
    samples = json.loads(sample_file.read_text())

    texts = [s["text"] for s in samples]
    labels = [s["intent"] for s in samples]

    preds = clf.predict(texts)

    macro_f1 = f1_score(labels, preds, average="macro", zero_division=0)
    report = classification_report(labels, preds, zero_division=0)

    print(f"Real-text EN Evaluation — n={len(samples)}")
    print(f"Source: NYC 311 (n=10) + manual (n=15)")
    print(f"\nMacro-F1: {macro_f1:.4f}")
    print("\nPer-class report:")
    print(report)

    sources = {}
    for s, pred in zip(samples, preds):
        src = s.get("source", "unknown")
        correct = pred == s["intent"]
        sources.setdefault(src, {"correct": 0, "total": 0})
        sources[src]["total"] += 1
        if correct:
            sources[src]["correct"] += 1
    print("Per-source accuracy:")
    for src, counts in sources.items():
        acc = counts["correct"] / counts["total"]
        print(f"  {src}: {counts['correct']}/{counts['total']} = {acc:.2f}")


if __name__ == "__main__":
    main()
