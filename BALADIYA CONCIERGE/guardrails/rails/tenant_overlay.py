"""Tenant rail overlay.

Merges tenant.settings.guardrail_config into the runtime rail context.
Platform rails are NOT in this overlay and cannot be disabled by tenants.

Expected guardrail_config shape (all fields optional):
{
    "blocked_topics":  ["competitor", "politics"],
    "allowed_tools":   ["rag_search", "capture_request", "escalate"],
    "refusal_tone":    "formal" | "friendly" | "custom",
    "custom_refusal_message": "We cannot assist with that."
}
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, ClassVar


@dataclass
class TenantRailConfig:
    blocked_topics: list[str] = field(default_factory=list)
    allowed_tools: list[str] = field(default_factory=list)
    refusal_tone: str = "formal"
    custom_refusal_message: str | None = None

    # Compiled patterns derived from blocked_topics at build time
    _topic_patterns: list[re.Pattern] = field(default_factory=list, repr=False)

    def __post_init__(self) -> None:
        self._topic_patterns = [
            re.compile(re.escape(t), re.IGNORECASE)
            for t in self.blocked_topics
        ]

    def check_blocked_topic(self, message: str) -> bool:
        """Return True if the message mentions a blocked topic."""
        return any(p.search(message) for p in self._topic_patterns)

    # Tone-based template messages (used when custom_refusal_message is not set)
    _TONE_TEMPLATES: ClassVar[dict[str, str]] = {
        "formal": "We are unable to process that request. Please contact us directly for assistance.",
        "friendly": "Sorry, I can't help with that topic! Feel free to ask about other services.",
        "custom": "I'm unable to assist with that request.",  # fallback if no custom_message set
    }

    def refusal_text(self, default: str = "I'm unable to assist with that request.") -> str:
        if self.custom_refusal_message:
            return self.custom_refusal_message
        return self._TONE_TEMPLATES.get(self.refusal_tone, default)


def build_tenant_rail_config(guardrail_config: dict[str, Any] | None) -> TenantRailConfig:
    """Build a TenantRailConfig from raw tenant settings dict."""
    if not guardrail_config:
        return TenantRailConfig()
    return TenantRailConfig(
        blocked_topics=guardrail_config.get("blocked_topics", []),
        allowed_tools=guardrail_config.get("allowed_tools", []),
        refusal_tone=guardrail_config.get("refusal_tone", "formal"),
        custom_refusal_message=guardrail_config.get("custom_refusal_message"),
    )
