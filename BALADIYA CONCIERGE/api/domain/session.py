"""Session memory schema for multi-turn resident conversations."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class SessionTurn(BaseModel):
    role: str  # "user" | "model"
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SessionMemory(BaseModel):
    """Conversation memory stored in Redis.

    Key: session:{session_id}:{tenant_id}
    TTL: 1800s (30 min) — justified in DECISIONS.md §3:
    median resident session is < 10 min; 30 min covers outliers while
    preventing stale state from leaking across unrelated visits.
    """
    turns: list[SessionTurn] = []
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionMemory:
        return cls.model_validate(data)
