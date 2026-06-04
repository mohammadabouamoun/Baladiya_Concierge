"""PII detection rail using Presidio PatternRecognizers.

Detects Lebanese NID, phone, email, and address patterns in input messages.
This rail flags PII presence; redaction is applied downstream in api/middleware/redaction.py.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from presidio_analyzer import Pattern, PatternRecognizer, RecognizerRegistry
from presidio_analyzer import AnalyzerEngine


@dataclass
class PiiDetectResult:
    has_pii: bool
    entity_types: list[str] = field(default_factory=list)


class _LebanesNidRecognizer(PatternRecognizer):
    """Lebanese national ID — 6-digit numeric string."""

    PATTERNS = [Pattern("LEBANESE_NID", r"\b\d{6}\b", 0.85)]

    def __init__(self) -> None:
        super().__init__(
            supported_entity="LEBANESE_NID",
            patterns=self.PATTERNS,
            supported_language="en",
        )


class _LebanesePhoneRecognizer(PatternRecognizer):
    """Lebanese mobile formats: +961 X XXX XXXX, 07X-XXX-XXX, 03X-XXX-XXX."""

    PATTERNS = [
        Pattern(
            "LEBANESE_PHONE_INTL",
            r"\+961[\s\-]?\d[\s\-]?\d{3}[\s\-]?\d{4}",
            0.9,
        ),
        Pattern(
            "LEBANESE_PHONE_LOCAL",
            r"\b0[37]\d[\s\-]?\d{3}[\s\-]?\d{3}\b",
            0.85,
        ),
    ]

    def __init__(self) -> None:
        super().__init__(
            supported_entity="LEBANESE_PHONE",
            patterns=self.PATTERNS,
            supported_language="en",
        )


class _EmailRecognizer(PatternRecognizer):
    PATTERNS = [
        Pattern("EMAIL", r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b", 0.9)
    ]

    def __init__(self) -> None:
        super().__init__(
            supported_entity="EMAIL_ADDRESS",
            patterns=self.PATTERNS,
            supported_language="en",
        )


def _build_analyzer() -> AnalyzerEngine:
    registry = RecognizerRegistry()
    registry.add_recognizer(_LebanesNidRecognizer())
    registry.add_recognizer(_LebanesePhoneRecognizer())
    registry.add_recognizer(_EmailRecognizer())
    # Disable built-in NLP-based recognizers — only our regex patterns
    registry.global_regex_add_to_context = False
    return AnalyzerEngine(
        registry=registry,
        supported_languages=["en"],
    )


_analyzer: AnalyzerEngine | None = None


def get_analyzer() -> AnalyzerEngine:
    global _analyzer
    if _analyzer is None:
        _analyzer = _build_analyzer()
    return _analyzer


def check_pii(message: str) -> PiiDetectResult:
    """Return PiiDetectResult indicating whether PII was detected."""
    results = get_analyzer().analyze(text=message, language="en")
    if not results:
        return PiiDetectResult(has_pii=False)
    entity_types = list({r.entity_type for r in results})
    return PiiDetectResult(has_pii=True, entity_types=entity_types)
