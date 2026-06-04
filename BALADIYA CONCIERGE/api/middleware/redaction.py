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
]


class Redactor:
    """Applies all PII recognizers to a message in sequence."""

    def redact(self, text: str) -> str:
        """Return text with all detected PII replaced by redaction tokens."""
        result = text
        triggered: list[str] = []
        for recognizer in _RECOGNIZERS:
            result, count = recognizer.redact(result)
            if count:
                triggered.append(recognizer.entity_type)
        if triggered:
            logger.debug("redaction.pii_removed", entity_types=triggered)
        return result


# Module-level singleton — no state, safe to share across requests
_redactor = Redactor()


def redact(text: str) -> str:
    """Redact PII from text. Thread-safe; stateless."""
    return _redactor.redact(text)
