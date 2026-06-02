# DATA.md — Baladiya Concierge

> Dataset documentation for the civic intent classifier. Covers schema, build process, split strategy, distribution, labelling guidelines, and growth targets.

---

## 1. Dataset Overview

**File**: `civic_intent_dataset.csv`
**Purpose**: trains and evaluates the civic intent classifier (`modelserver`). This dataset is **never** embedded into pgvector — it is classifier training data only.
**Current size**: ~209 rows (as of initial build)
**Rebuild command**: `python3 build_dataset.md` (this is a Python script with a `.md` extension)

---

## 2. Schema

| Column | Type | Values |
|---|---|---|
| `id` | string | Unique row identifier |
| `text` | string | The resident's message, in its original language and spelling |
| `lang` | string | `ar` \| `en` |
| `variety` | string | `en` \| `msa` \| `lebanese` \| `arabizi` |
| `intent` | string | `report` \| `question` \| `human` \| `spam` |
| `category` | string | `roads` \| `water` \| `electricity` \| `waste` \| `permits` \| `taxes` \| `environment` \| `general` \| `none` |
| `split` | string | `train` \| `test` — deterministic, see §4 |

### Field Notes

- **`variety`**: `en` applies to English rows; `msa`, `lebanese`, `arabizi` apply to Arabic rows. `arabizi` is Arabic written in Latin characters (e.g., "shu fi shi?").
- **`category`**: `none` is used for `spam` and `human` intents where no service category applies.
- **`text`**: stored verbatim — no normalisation, no spelling correction. The classifier must handle real-world variation.

---

## 3. Intent Definitions

| Intent | Definition | Example |
|---|---|---|
| `report` | Resident reports a problem requiring municipal action | "The streetlight on Hamra has been broken for two weeks" |
| `question` | Resident asks for information the municipality can answer | "What documents do I need to renew my building permit?" |
| `human` | Resident explicitly requests a human agent or expresses frustration requiring escalation | "I need to speak to someone", "This is urgent, please help me" |
| `spam` | Message with no civic intent: gibberish, test inputs, automated probes, off-topic | "asdfgh", "hello hello hello", "buy cheap watches" |

**Labelling rule**: when in doubt between `question` and `human`, label `human` only if the resident explicitly requests a person or the message carries strong urgency/distress markers. Ambiguous questions default to `question`.

**Boundary cases — `question` vs `human`**:

| Message | Label | Reason |
|---|---|---|
| "What are the permit office hours?" | `question` | Information request, no urgency |
| "I need to speak to someone about my permit" | `human` | Explicit human request |
| "Can someone call me back? I've tried 3 times." | `human` | Explicit contact request + repeated-attempt urgency marker |
| "Is there anyone who can help with electricity?" | `human` | "anyone who can help" = implicit human request |
| "How do I file a noise complaint?" | `question` | Process question, no urgency, no human request |

---

## 4. Train/Test Split

The split is **deterministic and leakage-free**:

```python
import hashlib
row['split'] = 'test' if int(hashlib.sha1(row['text'].encode()).hexdigest(), 16) % 5 == 0 else 'train'
```

- ~20% of rows land in `test` (every row whose SHA-1 hash mod 5 equals 0)
- The split is computed from the text content, not row order — identical text always lands in the same split
- New rows added to the dataset are automatically assigned to train or test by the same rule
- **Never tune on the test split.** Evaluation is run once per approach with no further tuning after test-set exposure

---

## 5. Distribution & Coverage

### Intent Distribution (target)

| Intent | Min rows (total) | Min rows (test) | Status |
|---|---|---|---|
| `report` | 50–100 | 10–20 | [TBD — count after rebuild] |
| `question` | 50–100 | 10–20 | [TBD] |
| `human` | 50–100 | 10–20 | **Thin — priority for growth** |
| `spam` | 50–100 | 10–20 | [TBD] |

### Variety Distribution (target per intent)

| Variety | Target rows | Status |
|---|---|---|
| `en` | 50+ per intent | [TBD] |
| `msa` | 20+ per intent | [TBD] |
| `lebanese` | 20+ per intent | [TBD] |
| `arabizi` | 20+ per intent | **Thin — priority for growth** |

### Thinnest Cells (require growth before Arabic F1 is reliable)

1. **`human` × all Arabic varieties** — human escalation in Arabic dialects is underrepresented
2. **`electricity` category × Arabic** — electricity reports in Arabic are scarce
3. **`arabizi` × any intent** — Arabizi spelling variation is the hardest to cover

Do not quote Arabic macro-F1 as reliable until each `(intent × variety)` cell has at least 20 verified examples. Current counts are below this threshold for the cells above.

---

## 6. Build & Rebuild

### Rebuild Command

```bash
python3 build_dataset.md
```

This script:
1. Reads source row files or a seed CSV
2. Computes the deterministic `split` column
3. Validates schema (no missing fields, valid enum values)
4. Writes `civic_intent_dataset.csv`

### Adding Rows

The rows are defined directly inside `build_dataset.md` — there is no separate source file. To add new examples, open `build_dataset.md` and append to the rows list (a Python list of dicts near the top of the script):

```python
{"id": "en-report-042", "text": "The pothole on Bliss Street is getting worse", "lang": "en", "variety": "en", "intent": "report", "category": "roads"},
```

Each new row must have:
- `text`: the original, unmodified resident message
- `lang`: `ar` or `en`
- `variety`: one of the four valid values
- `intent`: one of the four valid values (apply labelling rules from §3)
- `category`: the appropriate service category, or `none` for spam/human

Do not set `split` — the build script computes it deterministically from the text hash.

### Validation

After rebuild, check:
```bash
# Row count
wc -l civic_intent_dataset.csv

# Intent + variety totals
python3 -c "
import csv
from collections import Counter
with open('civic_intent_dataset.csv') as f:
    rows = list(csv.DictReader(f))
print('Intent:', Counter(r['intent'] for r in rows))
print('Variety:', Counter(r['variety'] for r in rows))
print('Split:', Counter(r['split'] for r in rows))
"

# Arabic cross-tab: (variety × intent × split) — critical for checking Arabic coverage
python3 -c "
import csv
from collections import Counter
with open('civic_intent_dataset.csv') as f:
    rows = list(csv.DictReader(f))
for split in ('train', 'test'):
    print(f'\n--- {split} ---')
    cell = Counter(
        (r['variety'], r['intent'])
        for r in rows if r['lang'] == 'ar' and r['split'] == split
    )
    for (variety, intent), n in sorted(cell.items()):
        warn = ' ⚠ thin' if n < 4 else ''
        print(f'  {variety:12} {intent:10} {n}{warn}')
"
```

Any cell with fewer than 4 test rows is too thin to produce a reliable per-cell F1 estimate — add more source rows before quoting Arabic macro-F1.

---

## 7. Labelling Guidelines

### General Rules

1. **Label the intent, not the category.** A message about a broken road that asks a question is `question`, not `report`.
2. **Use the text as written.** Do not mentally correct spelling or dialect — the classifier sees the raw text.
3. **Single label per row.** If a message contains both a report and a question, pick the primary intent (the one the resident most needs answered first).
4. **When uncertain, add a `note` column** with your reasoning. Disputed labels are reviewed before inclusion.

### Arabic-Specific Rules

5. **Label dialect first, then intent.** Identify the variety (`msa`, `lebanese`, `arabizi`) before assigning intent — this prevents cross-variety bias in labelling.
6. **Arabizi requires transliteration awareness.** "shko" and "shkou" and "shu kou" may all mean the same thing. Label the intent from the meaning, not the spelling.
7. **Lebanese colloquial markers**: "shu" (what), "kifak" (how are you → human), "3anjad" (seriously/urgent → often human), "ma3leh" (no matter → often spam).

### Spam Labelling

8. Label `spam` conservatively — only messages with clearly zero civic intent. A poorly spelled report is still `report`. A test message ("hello are you there?") is `spam`. A message that is off-topic but not abusive is `spam`.
9. Do not label adversarial injection probes as `spam` — these are test probes that belong in `evals/redteam_probes.json`, not the training dataset.

---

## 8. Data Quality Audit

Before quoting classifier F1 numbers in EVALS.md or DECISIONS.md, run the Arabic quality audit:

```bash
# List all Arabic rows for manual spot-check
python3 -c "
import csv
with open('civic_intent_dataset.csv') as f:
    for row in csv.DictReader(f):
        if row['lang'] == 'ar':
            print(row['variety'], row['intent'], repr(row['text'][:60]))
" | less
```

Log any corrections in `model_card.md` under a "Data Corrections" section. Corrected rows increment the version number in the model card.

`model_card.md` is the classifier's artifact record — it lives in the repo root alongside `civic_intent_dataset.csv` and records the trained model's SHA-256 checksum, evaluation results, and data correction history. It is created in Phase 2 (P2-004). Until Phase 2 is complete, log provisional corrections as comments in `build_dataset.md` next to the corrected row.
