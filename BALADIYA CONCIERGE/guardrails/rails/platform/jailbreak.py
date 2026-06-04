"""Jailbreak detection rail.

Detects DAN-style, roleplay-as, and hypothetical-override patterns.
"""
from __future__ import annotations

import re

_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        # DAN and named jailbreak personas
        r"\bDAN\b",  # Do Anything Now
        r"do\s+anything\s+now",
        r"jailbreak(ed|ing)?\b",
        r"(STAN|DUDE|AIM|KEVIN|ANTI[-\s]?GPT|UCAR)\b",
        # Roleplay-as bypasses
        r"(roleplay|role\s*-?\s*play)\s+as\s+(an?\s+)?(evil|unrestricted|unfiltered|uncensored|malicious|dangerous)",
        r"pretend\s+(you\s+are|you're|to\s+be)\s+(an?\s+)?(evil|unrestricted|unfiltered|dangerous|malicious|AI\s+without)",
        r"act\s+as\s+(an?\s+)?(evil|unrestricted|unfiltered|uncensored|malicious|dangerous|AI\s+without)",
        r"you\s+are\s+(now\s+)?(an?\s+)?(evil|unrestricted|unfiltered|dangerous|malicious)\s+(AI|assistant|bot)",
        # Hypothetical override patterns
        r"hypothetically\s+(speaking|if|assume|you\s+could|you\s+were)",
        r"in\s+a\s+hypothetical\s+(world|scenario|universe|situation)\s+where\s+you\s+(have\s+no|are\s+not|don'?t\s+have)",
        r"imagine\s+(you\s+)?(have\s+no\s+restrictions|are\s+free|are\s+not\s+bound|don'?t\s+follow\s+rules)",
        # Capability unlock patterns
        r"(unlock|enable|activate)\s+(your\s+)?(full|true|real|hidden|secret)\s+(potential|capabilities|mode|self)",
        r"without\s+(any\s+)?(restrictions?|limitations?|filters?|guidelines?|rules?|safety)",
        r"(no\s+)?(ethical|moral|safety)\s+(guidelines?|restrictions?|limits?|filters?|constraints?)",
        r"(developer|debug|god|admin|root|superuser)\s+mode",
    ]
]


def check_jailbreak(message: str) -> bool:
    """Return True if the message appears to be a jailbreak attempt."""
    return any(p.search(message) for p in _PATTERNS)
