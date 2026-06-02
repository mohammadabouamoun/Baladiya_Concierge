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

# Arabizi pattern: Arabic words written in Latin script with digits (2=ء, 3=ع, 7=ح, etc.)
_ARABIZI_RE = re.compile(r"[2-9]")

INTENT_CLASSES = ["report", "question", "human", "spam"]
CATEGORY_CLASSES = [
    "roads", "water", "electricity", "waste",
    "permits", "taxes", "environment", "general", "none",
]


def detect_variety(text: str, lang: str) -> str:
    """Return one of: en | msa | lebanese | arabizi."""
    if lang not in ("ar", "fa", "ur"):
        return "en"
    # Arabizi: Arabic-meaning text in Latin script with characteristic digit substitutions
    latin_ratio = sum(1 for c in text if c.isascii() and c.isalpha()) / max(len(text), 1)
    if latin_ratio > 0.5 and _ARABIZI_RE.search(text):
        return "arabizi"
    # Lebanese vs MSA is hard to distinguish without a dedicated model;
    # default to msa (sufficient for char n-gram features).
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
    """Wraps a joblib sklearn Pipeline for synchronous inference.

    Loaded once at startup. Thread-safe for reads (sklearn predict is stateless).
    """

    def __init__(self, artifact_path: Path) -> None:
        self._pipeline = joblib.load(artifact_path)
        # Determine if the pipeline outputs category as a second label
        # (single-output model → category defaults to 'general')
        self._has_category = False

    def predict(self, text: str) -> ClassifyResponse:
        import pandas as pd

        lang = _detect_lang(text)
        variety = detect_variety(text, lang)

        X = pd.DataFrame({"text": [text]})
        intent_pred = self._pipeline.predict(X)[0]
        proba = self._pipeline.predict_proba(X)[0]
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
