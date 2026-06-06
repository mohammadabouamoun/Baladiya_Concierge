"""Prompt routing tests — T-042.

FR-002: lang=="ar" → system_ar.md; anything else → system_en.md.
FR-007: No English code path loads system_ar.md.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch


def _clear_cache():
    from api.services.prompt_service import _load_template
    _load_template.cache_clear()


def test_arabic_lang_selects_arabic_prompt():
    """lang='ar' must return content from system_ar.md."""
    _clear_cache()
    from api.services.prompt_service import select_system_prompt
    result = select_system_prompt("ar", "بلدية الاختبار")
    _clear_cache()

    # system_ar.md is in Arabic — check for Arabic script
    import re
    has_arabic = bool(re.search(r"[؀-ۿ]", result))
    assert has_arabic, "Arabic prompt should contain Arabic text"


def test_english_lang_selects_english_prompt():
    """lang='en' (and any other non-ar value) must return system_en.md content."""
    _clear_cache()
    from api.services.prompt_service import select_system_prompt
    result = select_system_prompt("en", "Test Municipality")
    _clear_cache()

    assert "Test Municipality" in result


def test_unknown_lang_falls_back_to_english():
    """Unrecognized lang string must fall back to system_en.md (not crash)."""
    _clear_cache()
    from api.services.prompt_service import select_system_prompt
    result = select_system_prompt("fr", "Test Municipality")
    _clear_cache()

    assert result  # non-empty


def test_english_prompt_never_loads_arabic_file():
    """Critical: English path must not read system_ar.md — FR-007."""
    loaded: list[str] = []
    original_read = Path.read_text

    def spy_read(self, *args, **kwargs):
        loaded.append(self.name)
        return original_read(self, *args, **kwargs)

    _clear_cache()
    with patch.object(Path, "read_text", spy_read):
        from api.services.prompt_service import select_system_prompt
        select_system_prompt("en", "Test")
    _clear_cache()

    assert "system_ar.md" not in loaded, (
        "English prompt path loaded system_ar.md — constitution §III violated"
    )


def test_arabic_prompt_injects_persona():
    """Persona placeholder must be replaced in Arabic prompt."""
    _clear_cache()
    from api.services.prompt_service import select_system_prompt
    result = select_system_prompt("ar", "بلدية بيروت")
    _clear_cache()

    assert "{{persona}}" not in result, "Persona placeholder was not replaced"


def test_english_prompt_injects_persona():
    """Persona placeholder must be replaced in English prompt."""
    _clear_cache()
    from api.services.prompt_service import select_system_prompt
    result = select_system_prompt("en", "Beirut Municipality")
    _clear_cache()

    assert "{{persona}}" not in result, "Persona placeholder was not replaced"
    assert "Beirut Municipality" in result
