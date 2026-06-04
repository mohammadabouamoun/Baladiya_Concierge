"""Cross-tenant data extraction and system prompt extraction detection rail."""
from __future__ import annotations

import re

_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        # System prompt / instructions extraction
        r"(what\s+is|show|reveal|tell\s+me|print|output|display|repeat|write\s+out)\s+(your|the)\s+system\s+(prompt|message|context|instructions?)",
        r"(what\s+are|show|reveal|tell\s+me)\s+(your|the)\s+(instructions?|rules?|guidelines?|initial\s+prompt|context)",
        r"(show|print|reveal|output|display|repeat)\s+(\w+\s+)?(raw|full|complete|entire|original|exact)\s+(prompt|instructions?|context|system\s+message|system\s+prompt)",
        r"(ignore|skip|bypass)\s+(and\s+)?(show|print|reveal)\s+(your|the)\s+(prompt|instructions?)",
        r"what\s+(instructions?|rules?|guidelines?)\s+(were\s+you|have\s+you\s+been)\s+given",
        r"(reveal|show|print|output|display)\s+your\s+(full|complete|entire|initial|original|exact)?\s*(instructions?|guidelines?|context|system\s+message)",
        r"(repeat|recite|output|print)\s+the\s+(exact|full|complete)?\s*(system\s+message|system\s+prompt|instructions?|initial\s+context)",
        # Cross-tenant data access
        r"(show|list|get|fetch|display|access|retrieve)\s+(\w+\s+)?(all\s+)?(other\s+)?(tenants?|municipalities?|clients?|organizations?|users?)\b",
        r"(data|information|records?)\s+(from|of|about|belonging\s+to)\s+(other|another|different)\s+(tenants?|municipalities?|clients?|organizations?)",
        r"(give|provide|share)\s+(\w+\s+)?(data|information|records?)\s+(from|of|about)\s+(other|another|all|the)\s+(tenants?|municipalities?|clients?)",
        r"tenant[_\s]?id\s*[=:]\s*['\"]?[0-9a-f-]{8,}",
        r"(access|read|query|fetch)\s+(tenant|municipality)\s+[a-z]\b",
        r"(list|show|get)\s+all\s+(municipalities?|tenants?|clients?|organizations?|users?\s+in\s+the\s+system)",
        r"other\s+(tenants?|municipalities?)['']?\s+(data|information|records?|conversations?|requests?)",
        # Config/internal inspection
        r"(what|show|reveal)\s+(is|are)\s+(your|the)\s+(config|configuration|settings?|environment|env\s+vars?)",
        r"(database|db)\s+(schema|tables?|structure|credentials?)",
        r"(vault|secret|api\s+key|token|password|credential)\s+(value|content|secret)",
    ]
]


def check_cross_tenant(message: str) -> bool:
    """Return True if the message attempts cross-tenant data extraction or system prompt exposure."""
    return any(p.search(message) for p in _PATTERNS)
