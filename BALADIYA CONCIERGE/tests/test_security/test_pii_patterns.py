"""Unit tests for each PII redaction pattern (T-041).

Each recognizer is tested independently to ensure patterns match
Lebanese civic context formats precisely.
"""
from __future__ import annotations

import pytest

from api.middleware.redaction import redact


# ── Lebanese National ID (6-digit) ─────────────────────────────────────────

class TestLebanesNid:
    def test_standalone_six_digits_redacted(self):
        result = redact("My ID is 123456.")
        assert "[REDACTED_NID]" in result
        assert "123456" not in result

    def test_nid_in_sentence(self):
        result = redact("Please verify ID number 987654 for this request.")
        assert "[REDACTED_NID]" in result
        assert "987654" not in result

    def test_seven_digits_not_redacted(self):
        # 7-digit number is NOT a Lebanese NID
        result = redact("Reference number 1234567")
        assert "[REDACTED_NID]" not in result

    def test_five_digits_not_redacted(self):
        result = redact("Code 12345")
        assert "[REDACTED_NID]" not in result

    def test_multiple_nids_all_redacted(self):
        result = redact("IDs: 111111 and 222222")
        assert "111111" not in result
        assert "222222" not in result
        assert result.count("[REDACTED_NID]") == 2


# ── Lebanese Phone — International format ──────────────────────────────────

class TestLebanesPhoneIntl:
    def test_international_format_with_spaces(self):
        result = redact("Call me at +961 3 123 4567")
        assert "[REDACTED_PHONE]" in result
        assert "+961" not in result

    def test_international_format_with_dashes(self):
        result = redact("Phone: +961-1-234-5678")
        assert "[REDACTED_PHONE]" in result

    def test_international_format_no_separators(self):
        result = redact("Contact +96131234567 for info")
        assert "[REDACTED_PHONE]" in result


# ── Lebanese Phone — Local format ──────────────────────────────────────────

class TestLebanesPhoneLocal:
    def test_local_03_format(self):
        result = redact("My number is 03 123 456")
        assert "[REDACTED_PHONE]" in result
        assert "03 123 456" not in result

    def test_local_07_format(self):
        result = redact("Reach me at 076-543-210")
        assert "[REDACTED_PHONE]" in result

    def test_local_07_no_separator(self):
        result = redact("07 654 321 is my phone")
        assert "[REDACTED_PHONE]" in result

    def test_non_lebanese_prefix_not_redacted(self):
        # 05X or 06X are not Lebanese mobile prefixes
        result = redact("Code 05 123 456")
        assert "[REDACTED_PHONE]" not in result


# ── Email ───────────────────────────────────────────────────────────────────

class TestEmailRedaction:
    def test_simple_email(self):
        result = redact("Contact me at user@example.com please")
        assert "[REDACTED_EMAIL]" in result
        assert "user@example.com" not in result

    def test_email_with_plus(self):
        result = redact("Send to user+tag@domain.org")
        assert "[REDACTED_EMAIL]" in result

    def test_email_with_subdomains(self):
        result = redact("admin@mail.municipality.gov.lb")
        assert "[REDACTED_EMAIL]" in result

    def test_non_email_at_sign_not_redacted(self):
        result = redact("mention @username on twitter")
        assert "[REDACTED_EMAIL]" not in result


# ── Address ─────────────────────────────────────────────────────────────────

class TestAddressRedaction:
    def test_number_before_street(self):
        result = redact("I live at 123 Hamra Street")
        assert "[REDACTED_ADDRESS]" in result
        assert "123 Hamra Street" not in result

    def test_building_prefix(self):
        result = redact("Find me at Building 45 Clemenceau")
        assert "[REDACTED_ADDRESS]" in result

    def test_bloc_prefix(self):
        result = redact("Address: Bloc 7 Verdun Avenue")
        assert "[REDACTED_ADDRESS]" in result

    def test_generic_number_not_address(self):
        # A bare number without street-type word should not trigger
        result = redact("Reference number 99 for your case")
        assert "[REDACTED_ADDRESS]" not in result


# ── Combined & edge cases ───────────────────────────────────────────────────

class TestCombined:
    def test_message_with_multiple_pii_types(self):
        msg = "My ID is 654321, phone +961 3 000 0000, email me@example.com"
        result = redact(msg)
        assert "654321" not in result
        assert "+961" not in result
        assert "me@example.com" not in result
        assert "[REDACTED_NID]" in result
        assert "[REDACTED_PHONE]" in result
        assert "[REDACTED_EMAIL]" in result

    def test_clean_message_unchanged(self):
        msg = "How do I pay my water bill?"
        assert redact(msg) == msg

    def test_arabic_text_with_embedded_nid(self):
        msg = "رقم هويتي هو 123456 أرجو المساعدة"
        result = redact(msg)
        assert "123456" not in result
        assert "[REDACTED_NID]" in result

    def test_phone_redacted_before_nid_pattern_matches(self):
        # Phone patterns run before NID so digit sequences inside phone numbers
        # don't double-trigger as NIDs.
        msg = "Call +961 3 123 456 today"
        result = redact(msg)
        assert "[REDACTED_PHONE]" in result
        # After phone replacement, no bare 6-digit sequence remains → NID fires once max
        assert result.count("[REDACTED_") == 1
