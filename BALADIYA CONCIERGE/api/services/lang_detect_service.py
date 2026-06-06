"""Language detection service — runs before classification on every inbound message.

Detects lang (en | ar) and variety (en | msa | lebanese | arabizi).
On any failure, defaults to lang="en", variety="en" — additive guarantee
(constitution §III: Arabic is additive, English is load-bearing).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import structlog

logger = structlog.get_logger(__name__)

# Arabizi: Arabic meaning expressed in Latin letters with number substitutions.
# 3=ع  7=ح  2=ء/أ  5=خ  6=ط  8=غ  9=ص
_ARABIZI_PATTERN = re.compile(
    r"(?:[37259268])|"         # bare number substitutions
    r"(?:[a-zA-Z][37259268])|" # letter+number combo
    r"(?:[37259268][a-zA-Z])", # number+letter combo
    re.UNICODE
)
_ARABIC_SCRIPT = re.compile(r"[؀-ۿݐ-ݿࢠ-ࣿ]+")

# Common Lebanese lexical markers absent from MSA
_LEBANESE_MARKERS = re.compile(
    r"\b(شو|كيف|وين|هيك|هلّق|هلق|بدّي|بدي|ما في|ما عم|عم |"
    r"كتير|منيح|مش|هيدا|هيدي|عنا|فيني|فيك|بقدر|منقدر|"
    r"جمعة|امبارح|مبارح|تيام|بالتيام|هلأ)\b",
    re.UNICODE
)


@dataclass
class LangDetectResult:
    lang: str       # "en" | "ar"
    variety: str    # "en" | "msa" | "lebanese" | "arabizi"
    confidence: float


async def detect(text: str) -> LangDetectResult:
    """Detect language and Arabic variety of a message.

    Falls back to en/en on any error — callers must never get an exception here.
    """
    if not text or not text.strip():
        return LangDetectResult(lang="en", variety="en", confidence=0.0)

    try:
        return _detect_sync(text)
    except Exception as exc:
        logger.warning("lang_detect.failed", error=str(exc), text_preview=text[:40])
        return LangDetectResult(lang="en", variety="en", confidence=0.0)


def _detect_sync(text: str) -> LangDetectResult:
    # Fast-path: check if predominantly Arabizi (Latin letters + number substitutions)
    latin_chars = sum(1 for c in text if c.isascii() and c.isalpha())
    arabic_chars = len(_ARABIC_SCRIPT.findall(text))
    arabizi_hits = len(_ARABIZI_PATTERN.findall(text))

    if latin_chars > arabic_chars and arabizi_hits >= 2:
        return LangDetectResult(lang="ar", variety="arabizi", confidence=0.75)

    from langdetect import detect as ld_detect, detect_langs
    from langdetect.lang_detect_exception import LangDetectException

    try:
        probs = {p.lang: p.prob for p in detect_langs(text)}
    except LangDetectException:
        return LangDetectResult(lang="en", variety="en", confidence=0.0)

    ar_prob = probs.get("ar", 0.0)
    en_prob = probs.get("en", 0.0)

    if ar_prob < 0.4 and en_prob < 0.4:
        # Ambiguous — default to English
        return LangDetectResult(lang="en", variety="en", confidence=max(ar_prob, en_prob))

    if ar_prob >= 0.4:
        variety = _infer_arabic_variety(text)
        return LangDetectResult(lang="ar", variety=variety, confidence=ar_prob)

    return LangDetectResult(lang="en", variety="en", confidence=en_prob)


def _infer_arabic_variety(text: str) -> str:
    """Distinguish MSA from Lebanese dialect using lexical markers."""
    if _LEBANESE_MARKERS.search(text):
        return "lebanese"
    return "msa"
