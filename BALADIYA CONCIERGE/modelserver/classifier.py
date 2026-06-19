from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

import joblib
import numpy as np

try:
    from langdetect import detect as _langdetect, LangDetectException
    def _detect_lang(text: str) -> str:
        try:
            return _langdetect(text)
        except LangDetectException:
            return "en"
except ImportError:
    def _detect_lang(text: str) -> str:
        return "en"

# Arabizi detection pattern. Two signal types — both count toward the >= 2 threshold:
#   1. Digit EMBEDDED in a word: letter+digit or digit+letter (share3, 7ufra, ndfa3).
#      Bare digits like "12" (space-separated) do NOT match and do NOT false-trigger
#      on English text like "building 12" or "3 weeks".
#   2. Unambiguously-Arabizi words (cannot appear in normal English civic text).
#      Excluded: may/mei/bade/fi/jemb — too common or valid in English.
# detect_variety() requires >= 2 total matches to avoid false positives on
# English text with single occurrences like "5pm" or ordinals like "3rd".
_ARABIZI_WORDS = re.compile(
    r"(?<!\w)(?:emta|imta|lazem|lezem|badde|"
    r"kahraba|kahrabeh|zbele|zbala|"
    r"hafra|mwazzaf|baladiyye|halla2|kif)(?!\w)",
    re.IGNORECASE,
)
# Plain English number tokens (12, 3rd, 5pm, 2am, 5k) that must NOT be read as
# Arabizi digit substitutions — they are stripped before counting.
_ENGLISH_NUM_TOKEN = re.compile(r"^\d+(?:st|nd|rd|th|pm|am|k|m|kg|km|h|s)?$", re.IGNORECASE)
_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")
_SUB_DIGITS = "23578"


def _arabizi_signal_count(text: str) -> int:
    """Count Arabizi signals: digit-embedded words (share3, 7ufra) + Arabizi words.

    English number/ordinal/time tokens (5pm, 2nd, 12) are skipped so English text
    with numbers does not false-trigger.
    """
    hits = len(_ARABIZI_WORDS.findall(text))
    for tok in _TOKEN_RE.findall(text):
        if _ENGLISH_NUM_TOKEN.match(tok):
            continue
        if any(c.isalpha() for c in tok) and any(d in tok for d in _SUB_DIGITS):
            hits += 1
    return hits

INTENT_CLASSES = ["report", "question", "human", "spam"]
CATEGORY_CLASSES = [
    "roads", "water", "electricity", "waste",
    "permits", "taxes", "environment", "general", "none",
]


def detect_variety(text: str, lang: str) -> str:
    """Return one of: en | msa | lebanese | arabizi."""
    # Arabizi check must run before the lang gate — langdetect returns European
    # language codes for Arabizi text (Latin script + digit substitutions 2/3/7/etc).
    # Require >= 2 pattern matches to avoid false positives on English text that
    # happens to contain "5pm", "3rd", or other single digit-letter combos.
    latin_ratio = sum(1 for c in text if c.isascii() and c.isalpha()) / max(len(text), 1)
    if latin_ratio > 0.5 and _arabizi_signal_count(text) >= 2:
        return "arabizi"
    if lang not in ("ar", "fa", "ur"):
        return "en"
    return "msa"


class ClassifyResponse:
    __slots__ = ("intent", "category", "confidence", "lang", "variety")

    def __init__(
        self,
        intent: str,
        category: str,
        confidence: float,
        lang: str,
        variety: str,
    ) -> None:
        self.intent = intent
        self.category = category
        self.confidence = confidence
        self.lang = lang
        self.variety = variety

    def to_dict(self) -> dict:
        return {
            "intent": self.intent,
            "category": self.category,
            "confidence": self.confidence,
            "lang": self.lang,
            "variety": self.variety,
        }


class ClassifierService:
    """Wraps one or two joblib sklearn Pipelines for synchronous inference.

    If an Arabic-specific artifact is provided, Arabic text is routed to it
    (§8.3 per-language split) while English text uses the main pipeline.
    Both are loaded once at startup; thread-safe for reads.
    """

    def __init__(self, artifact_path: Path, ar_artifact_path: Path | None = None) -> None:
        self._pipeline = joblib.load(artifact_path)
        self._ar_pipeline = joblib.load(ar_artifact_path) if ar_artifact_path and ar_artifact_path.exists() else None

    def predict(self, text: str) -> ClassifyResponse:
        lang = _detect_lang(text)
        variety = detect_variety(text, lang)

        # Route Arabic varieties to the dedicated AR sub-model when available.
        # EN text always uses the main (EN-dominated) pipeline.
        pipeline = self._ar_pipeline if (variety != "en" and self._ar_pipeline is not None) else self._pipeline

        # Pipeline was trained on a list/Series of strings — pass a plain list,
        # not a DataFrame (iterating a DataFrame yields column names, not values).
        intent_pred = pipeline.predict([text])[0]
        proba = pipeline.predict_proba([text])[0]
        confidence = float(np.max(proba))

        # Category is not yet a separate classifier output — default to 'general'
        # (wired up in feature 003 when CMS categories are available)
        category = "general"

        return ClassifyResponse(
            intent=intent_pred,
            category=category,
            confidence=confidence,
            lang=lang,
            variety=variety,
        )
