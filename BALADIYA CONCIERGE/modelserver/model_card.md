# Model Card — Baladiya Civic Intent Classifier

## Task

4-class intent classification for civic service messages:
`report | question | human | spam`

Secondary output: category (`roads | water | electricity | waste | permits | taxes | environment | general | none`) — wired in feature 003.

## Data

**Source**: `civic_intent_dataset.csv` (repo root)
**Size**: 547 rows (258 hand-crafted + 289 from NYC 311 Kaggle + enron_spam HF)
**Split**: deterministic `sha1(text) % 5 == 0 → test` (~20%) — 449 train / 98 test
**Languages**: English (en), MSA Arabic (msa), Lebanese dialect (lebanese), Arabizi
**Data SHA-256**: `afbb5e166f49102ac3618c35b690294efb6ef014982ee489c7d9a7af7ff2bfc1`

## Three-Way Comparison

Trained 2026-06-02. Run `notebooks/train_classifier.ipynb` to reproduce.

| Approach | Macro-F1 | EN F1 | AR F1 | p50 ms | p95 ms | Cost/1k |
|---|---|---|---|---|---|---|
| **Classical ML (TF-IDF char 3-5 + word 1-2 + LogReg)** | **0.8983** | **0.8784** | **0.8117** | **2.2ms** | **4.2ms** | **~$0.001** |
| LLM zero-shot (Groq llama-3.3-70b) | 0.8291 | 0.7358 | 0.8512 | 2220ms | 2292ms | ~$0.06 |

## Shipping Choice

**Shipped model**: Classical ML — TF-IDF (char n-grams 3-5 + word n-grams 1-2) + LogisticRegression (balanced class weights)

**Justification**: Best macro-F1 (0.8983 vs 0.8291 for LLM zero-shot). 1000× faster (2.2ms vs 2220ms p50). Near-zero inference cost (~$0.001/1k vs $0.06/1k for Groq). No API dependency — runs fully offline. See `DECISIONS.md §1`.

## Artifact

**File**: `artifacts/classifier.joblib`
**Size**: 0.53 MB
**SHA-256**: `1ace7e21afd41ea78872a6ed262e75f3bac4b1fe10ef7e520c27117cbe26f9a9`

Set `ARTIFACT_SHA256=1ace7e21afd41ea78872a6ed262e75f3bac4b1fe10ef7e520c27117cbe26f9a9` in environment (via Vault in production). The modelserver refuses to start if the hash does not match.

## Per-Class F1 (held-out test, n=98)

| | report | question | human | spam |
|---|---|---|---|---|
| Precision | 0.92 | 0.80 | 1.00 | 0.93 |
| Recall | 0.97 | 0.80 | 1.00 | 0.78 |
| **F1** | **0.94** | **0.80** | **1.00** | **0.85** |
| Support | 62 | 15 | 3 | 18 |

## Per-Variety F1 (held-out test)

| | en | msa | lebanese | arabizi |
|---|---|---|---|---|
| F1 | 0.8784 | 0.9416 | 0.7143 | 0.5000 |
| Test rows | ~80 | 13 | 5 | 5 |

## Known Limitations

- **Arabizi F1 is low (0.50)** — only 5 Arabizi test rows; not statistically reliable. Grow the arabizi cell to 50+ before quoting this number.
- **Lebanese F1 is moderate (0.71)** — also thin at 5 test rows.
- **Category is a placeholder** (`general`) until feature 003 adds CMS categories to the training pipeline.
- **Language detection** falls back to `en` on very short or mixed-script texts (< 10 chars).
- **Spam recall is 78%** — the spam cell could benefit from more diverse examples beyond email spam (SMS spam, chatbot abuse, etc.).
