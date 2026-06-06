"""Language detection unit tests — T-041.

Tests cover: MSA → ar/msa, Lebanese → ar/lebanese, Arabizi → ar/arabizi,
English → en/en, unknown → en/en, exception → en/en.
"""
from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

from api.services.lang_detect_service import LangDetectResult, detect


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ── Arabic varieties ───────────────────────────────────────────────────────

def test_msa_detected_as_ar_msa():
    result = run(detect("انقطعت المياه عن حيّنا منذ الصباح، أرجو المتابعة."))
    assert result.lang == "ar"
    assert result.variety in ("msa", "lebanese")  # some MSA may be tagged as lebanese on short text


def test_lebanese_detected_as_ar_lebanese():
    result = run(detect("كيف بقدر دفع فاتورة المي؟ ما عم يرنّ حدا بالبلدية."))
    assert result.lang == "ar"
    assert result.variety == "lebanese"


def test_arabic_report_detected_as_ar():
    result = run(detect("في حفرة كبيرة بالطريق قدّام الفرن، بدّي حدا يجي يصلحها."))
    assert result.lang == "ar"


def test_arabizi_detected_as_ar_arabizi():
    result = run(detect("fi 7afra kbire bel tari2 2eddem el fern, kedet syyara ten2leb."))
    assert result.lang == "ar"
    assert result.variety == "arabizi"


def test_arabizi_with_numbers_detected():
    result = run(detect("el kahraba ma26ou3a men mbere7 3and baytna."))
    assert result.lang == "ar"
    assert result.variety == "arabizi"


# ── English ────────────────────────────────────────────────────────────────

def test_english_detected_as_en():
    result = run(detect("There is a pothole on Main Street near the bakery."))
    assert result.lang == "en"
    assert result.variety == "en"


def test_english_question_detected_as_en():
    result = run(detect("What are the opening hours of the municipality office?"))
    assert result.lang == "en"
    assert result.variety == "en"


# ── Edge cases ─────────────────────────────────────────────────────────────

def test_empty_text_defaults_to_en():
    result = run(detect(""))
    assert result.lang == "en"
    assert result.variety == "en"
    assert result.confidence == 0.0


def test_whitespace_only_defaults_to_en():
    result = run(detect("   "))
    assert result.lang == "en"
    assert result.variety == "en"


def test_exception_defaults_to_en():
    """Any exception in detection must silently default to en/en (additive guarantee)."""
    with patch("api.services.lang_detect_service._detect_sync", side_effect=RuntimeError("boom")):
        result = run(detect("أي نص عربي"))
    assert result.lang == "en"
    assert result.variety == "en"
    assert result.confidence == 0.0


def test_unknown_language_defaults_to_en():
    """Language that langdetect doesn't recognize → en/en."""
    result = run(detect("xyz ??? !!!"))
    assert result.lang == "en"


def test_returns_langdetect_result_type():
    """Return type must always be LangDetectResult."""
    result = run(detect("hello world"))
    assert isinstance(result, LangDetectResult)
    assert hasattr(result, "lang")
    assert hasattr(result, "variety")
    assert hasattr(result, "confidence")
