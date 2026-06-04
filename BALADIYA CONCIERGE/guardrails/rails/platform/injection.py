"""Prompt injection detection rail.

Regex-based for determinism and speed (< 5ms). Catches the most common
injection patterns. LLM-based fallback can be wired via config.yml prompts
for novel patterns not covered here.
"""
from __future__ import annotations

import re

# Patterns that indicate an attempt to override system instructions
_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"ignore\s+(previous|all|prior|above|the\s+above|your)\s+(instructions?|rules?|prompt|context|guidelines?)",
        r"forget\s+(everything|all|your\s+instructions?|the\s+above|previous)",
        r"disregard\s+(your|the|all|previous|prior)\s+(instructions?|rules?|guidelines?|context)",
        r"(new|updated|revised|override)\s+instructions?\s*(are|follow|:)",
        r"your\s+(new\s+)?instructions?\s+(are|will\s+be|follow)",
        r"(override|bypass|skip)\s+(your|the|all)?\s*(instructions?|rules?|guidelines?|safety|filters?)",
        r"(system\s+prompt|system\s+message|system\s+context)\s*(is|are|should|will)\s*(now|be)",
        r"you\s+are\s+now\s+(in\s+)?(developer|admin|god|jailbreak|unrestricted|free)\s+mode",
        r"pretend\s+(that\s+)?(you\s+(have\s+no|don'?t\s+have)\s+(instructions?|guidelines?|restrictions?))",
        r"act\s+as\s+if\s+(you\s+)?(have\s+no|were\s+not|are\s+not)\s+(restricted|limited|bound)",
        r"from\s+now\s+on\s+(you\s+)?(will|must|should|are\s+to)\s+(ignore|bypass|disregard|forget)",
        r"<\s*/?system\s*>",  # Attempted system tag injection
        r"\[INST\]|\[/INST\]",  # Llama instruction tags
        r"###\s*(Instruction|System|Human|Assistant)\s*:",  # Common injection delimiters
    ]
]


def check_injection(message: str) -> bool:
    """Return True if the message appears to be a prompt injection attempt."""
    return any(p.search(message) for p in _PATTERNS)
