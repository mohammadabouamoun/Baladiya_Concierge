"""PII redaction middleware — Presidio-style custom recognizers.

Applied to every message BEFORE structlog write and BEFORE Redis session write.
All patterns target Lebanese civic context.

False positives (e.g. a 6-digit code that matches NID pattern) are acceptable;
false negatives (real PII reaching logs) are not. Logged at DEBUG on match.
"""
from __future__ import annotations

import re
import structlog

logger = structlog.get_logger(__name__)


class _PatternRecognizer:
    """Regex-based recognizer mirroring Presidio PatternRecognizer interface."""

    def __init__(self, entity_type: str, pattern: str, replacement: str) -> None:
        self.entity_type = entity_type
        self._re = re.compile(pattern, re.IGNORECASE)
        self._replacement = replacement

    def redact(self, text: str) -> tuple[str, int]:
        """Return (redacted_text, match_count)."""
        new_text, count = self._re.subn(self._replacement, text)
        return new_text, count


# ── Custom recognizers (Lebanese civic context) ───────────────────────────

_RECOGNIZERS: list[_PatternRecognizer] = [
    # Phone patterns run BEFORE NID to prevent digit sequences inside phone
    # numbers from triggering the 6-digit NID pattern.
    #
    # Lebanese mobile international: +961 X XXX XXX or +961 XX XXX XXX
    _PatternRecognizer(
        "LEBANESE_PHONE_INTL",
        r"\+961[\s\-]?\d{1,2}[\s\-]?\d{3}[\s\-]?\d{3,4}",
        "[REDACTED_PHONE]",
    ),
    # Lebanese mobile local: 03 XXX XXX, 07X XXX XXX, 076-543-210
    _PatternRecognizer(
        "LEBANESE_PHONE_LOCAL",
        r"\b0[37]\d{0,1}[\s\-]?\d{3}[\s\-]?\d{3}\b",
        "[REDACTED_PHONE]",
    ),
    # Lebanese national ID — 6-digit numeric string (after phone patterns)
    _PatternRecognizer(
        "LEBANESE_NID",
        r"\b\d{6}\b",
        "[REDACTED_NID]",
    ),
    # Email address
    _PatternRecognizer(
        "EMAIL_ADDRESS",
        r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b",
        "[REDACTED_EMAIL]",
    ),
    # Street address: building number adjacent to street-type word
    # Matches "123 Hamra Street", "Building 45 Clemenceau", "Bloc 7 Avenue Charles"
    _PatternRecognizer(
        "STREET_ADDRESS",
        r"\b(?:\d+\s+[A-Za-z][A-Za-z\s]{2,20}(?:Street|St\.?|Avenue|Ave\.?|Road|Rd\.?|Blvd|Boulevard|Highway|Hwy)"
        r"|(?:Building|Bldg|Bloc|Block)\s+\d+(?:\s+[A-Za-z][A-Za-z\s]{2,30})?)\b",
        "[REDACTED_ADDRESS]",
    ),
    # Arabic personal names — two-pattern approach:
    # Pattern A: formal name-introducing prefix (السيد, اسمي, etc.) + one or two Arabic words.
    # Pattern B: known Arabic given name (first word) + any Arabic word.
    #
    # A bare two-word Arabic regex (e.g. [؀-ۿ]{3,}\s+[؀-ۿ]{3,}) falsely redacts civic
    # phrases like مواعيد دفع and breaks RAG queries. Pattern B uses an explicit given-name
    # list so مياه/كهرباء/مواعيد (not names) are never matched, while محمد/رنا/أحمد are.
    _PatternRecognizer(
        "ARABIC_NAME",
        (
            r"(?:اسمي|اسمه|اسمها|اسمكم|اسمنا|يدعى|تدعى|يسمى|تسمى|"
            r"المواطن|المواطنة|السيد|السيدة|الآنسة|"
            r"الدكتور|الدكتورة|الأستاذ|الأستاذة|المهندس|المهندسة)"
            r"\s+[؀-ۿ]{3,}(?:\s+[؀-ۿ]{3,})?"
        ),
        "[NAME]",
    ),
    _PatternRecognizer(
        "ARABIC_GIVEN_NAME",
        (
            # Muslim male — common Lebanese/Syrian/Palestinian names
            r"(?:محمد|أحمد|علي|حسن|حسين|خالد|يوسف|عمر|سامر|طارق|باسل|كريم|زياد|وليد|رامي|"
            r"جمال|ماجد|نادر|فادي|ربيع|غسان|عماد|بلال|نزار|رشيد|صالح|ياسر|منير|سعيد|"
            r"عبدالله|عبدالرحمن|عبدالكريم|عبدالعزيز|عبدالرحيم|"
            r"إبراهيم|إسماعيل|إسحاق|سليمان|موسى|عيسى|يحيى|داوود|هارون|"
            r"حمزة|عباس|جعفر|صادق|باقر|كاظم|مهدي|حيدر|مصطفى|محمود|"
            # Muslim female
            r"فاطمة|عائشة|زينب|مريم|رنا|سارة|نورا|هند|رانيا|دانا|ريم|لينا|نادين|"
            r"سلمى|سلوى|منى|هبة|وفاء|إيمان|أمل|غادة|رولا|ديانا|علا|أسماء|"
            r"خديجة|حفصة|رقية|أم كلثوم|ميسون|سوسن|نسرين|روان|شيرين|دلال|"
            # Christian Lebanese — male
            r"جورج|بيار|أنطوان|ميشال|إيلي|طوني|شربل|مارون|إلياس|نقولا|جوزيف|"
            r"ريمون|سمير|مارك|ماريو|روبير|روني|كلود|بول|لويس|ألبير|هنري|"
            r"مارسيل|جاك|أندريه|بطرس|يوحنا|بندلي|"
            # Christian Lebanese — female
            r"كارين|ميرنا|كريستينا|ريتا|سيلفيا|ديانا|ليلى|جويل|نيكول|ميشلين|"
            r"ماريا|مادلين|مايا|ميا|جوانا|ميراي|نانسي|إيفا|ليز|سيسيل|كلير|"
            # Druze / mixed
            r"وليد|جنبلاط|نصري|فؤاد|مروان|أكرم|نايف|رياض|"
            # Arabizi transliterations — common in chat
            r"mohamad|mohammad|ahmad|ali|hassan|hussein|khalid|youssef|omar|samer|"
            r"tariq|bassil|karim|ziad|walid|rami|fadi|ghassan|nazar|bilal|"
            r"fatima|aisha|zeinab|mariam|rana|sara|nour|rania|dana|leen|lina|nadine|"
            r"maya|mia|joelle|rita|karen|mirna|karen)"
            r"\s+[؀-ۿ]{3,}"
        ),
        "[NAME]",
    ),
]


class Redactor:
    """Applies all PII recognizers to a message in sequence."""

    def redact(self, text: str) -> str:
        """Return text with all detected PII replaced by redaction tokens."""
        result = text
        triggered: list[str] = []
        for recognizer in _RECOGNIZERS:
            try:
                result, count = recognizer.redact(result)
                if count:
                    triggered.append(recognizer.entity_type)
            except Exception:
                logger.debug("redaction.pattern_error", entity_type=recognizer.entity_type)
        if triggered:
            logger.debug("redaction.pii_removed", entity_types=triggered)
        return result


# Module-level singleton — no state, safe to share across requests
_redactor = Redactor()


def redact(text: str) -> str:
    """Redact PII from text. Thread-safe; stateless."""
    return _redactor.redact(text)
