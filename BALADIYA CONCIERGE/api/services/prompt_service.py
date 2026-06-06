"""Prompt selection service — selects system prompt variant by language.

FR-002: Arabic system prompt used when lang=="ar"; English otherwise.
FR-007: No English code path imports or depends on system_ar.md.

The English path never loads the Arabic prompt file — even on import.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)

_PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"


@lru_cache(maxsize=8)
def _load_template(name: str) -> str:
    path = _PROMPTS_DIR / f"{name}.md"
    return path.read_text(encoding="utf-8")


def select_system_prompt(lang: str, tenant_persona: str) -> str:
    """Return the system prompt for the given language, with persona injected.

    lang="ar" → system_ar.md
    anything else → system_en.md

    The English branch never references system_ar.md — additive guarantee
    (constitution §III).
    """
    if lang == "ar":
        template = _load_template("system_ar")
    else:
        template = _load_template("system_en")

    return template.replace("{{persona}}", tenant_persona)
