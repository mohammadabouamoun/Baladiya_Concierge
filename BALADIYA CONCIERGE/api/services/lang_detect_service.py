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
_ARABIZI_SUB_DIGITS = "2356789"
# Plain English number tokens that contain those digits but are NOT Arabizi:
# bare numbers (12), ordinals (3rd, 2nd), times (5pm, 2am), units (5k, 3km).
# These are skipped so English text with numbers is never mistaken for Arabizi.
_ENGLISH_NUM_TOKEN = re.compile(r"^\d+(?:st|nd|rd|th|pm|am|k|m|kg|km|h|s)?$", re.IGNORECASE)
_TOKEN = re.compile(r"[A-Za-z0-9]+")


def _arabizi_digit_hits(text: str) -> int:
    """Count word-tokens that carry an Arabizi number substitution.

    A token counts only when a substitution digit is embedded with a Latin
    letter (share3, 7afra, 2eddem) AND the token is not a plain English number/
    ordinal/time/unit (12, 3rd, 5pm, 2am). Bare standalone digits never count.
    """
    hits = 0
    for tok in _TOKEN.findall(text):
        if _ENGLISH_NUM_TOKEN.match(tok):
            continue
        if any(c.isalpha() for c in tok) and any(d in tok for d in _ARABIZI_SUB_DIGITS):
            hits += 1
    return hits
# Common Arabic function words / particles written in Latin script (Arabizi)
_ARABIZI_LEXICAL = re.compile(
    r"\b(el|il|al|bil|bel|lal|lel|min|men|msh|mish|ma|fi|fiy|la|le|"
    r"3al|3and|3anna|3ando|shu|shi|chi|kif|wين|wla|wlo|hala2|halla2|"
    r"imbere7|mbere7|kbir|kbire|share3|tari2|bayt|baladiyye|baladiyyi|"
    r"zbele|nfeyet|may|kahraba|rasif|majrour|7ay|mante2a)\b",
    re.IGNORECASE
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
    arabizi_hits = _arabizi_digit_hits(text)

    lexical_hits = len(_ARABIZI_LEXICAL.findall(text))
    is_arabizi = latin_chars > arabic_chars and (
        arabizi_hits >= 2 or (arabizi_hits >= 1 and lexical_hits >= 2)
    )
    if not is_arabizi and latin_chars > arabic_chars and lexical_hits >= 3:
        # Pure lexical Arabizi: no number substitutions but ≥3 distinct Arabic
        # function words written in Latin script (e.g. "el zbele min el share3")
        is_arabizi = True
    if is_arabizi:
        return LangDetectResult(lang="ar", variety="arabizi", confidence=0.75)

    # Fast-path for Arabic script — no langdetect needed.
    # Handles the case where langdetect is unavailable or raises on Arabic text.
    if arabic_chars > 2 and arabic_chars >= latin_chars:
        variety = _infer_arabic_variety(text)
        return LangDetectResult(lang="ar", variety=variety, confidence=0.90)

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
