"""Session service: Redis-backed conversation memory scoped per (session_id, tenant_id)."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import structlog
from redis.asyncio import Redis

from api.domain.session import SessionMemory, SessionTurn

logger = structlog.get_logger(__name__)

SESSION_TTL = 1800  # 30 minutes — see DECISIONS.md §3


def _session_key(session_id: str, tenant_id: uuid.UUID) -> str:
    return f"session:{session_id}:{tenant_id}"


class SessionService:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def load(self, session_id: str, tenant_id: uuid.UUID) -> SessionMemory:
        """Load session memory. Returns empty memory if key not found or expired."""
        key = _session_key(session_id, tenant_id)
        raw = await self._redis.get(key)
        if raw is None:
            return SessionMemory()
        try:
            return SessionMemory.from_dict(json.loads(raw))
        except Exception as exc:
            logger.warning("session.load_failed", key=key, error=str(exc))
            return SessionMemory()

    async def save(self, session_id: str, tenant_id: uuid.UUID, memory: SessionMemory) -> None:
        """Persist session memory with TTL refresh."""
        key = _session_key(session_id, tenant_id)
        memory.last_updated = datetime.now(timezone.utc)
        await self._redis.set(key, json.dumps(memory.to_dict()), ex=SESSION_TTL)

    async def add_turns(
        self,
        session_id: str,
        tenant_id: uuid.UUID,
        turns: list[tuple[str, str]],
    ) -> None:
        """Append (role, content) pairs to session memory atomically."""
        memory = await self.load(session_id, tenant_id)
        for role, content in turns:
            memory.turns.append(SessionTurn(role=role, content=content))
        await self.save(session_id, tenant_id, memory)

    async def flush_tenant(self, tenant_id: uuid.UUID) -> int:
        """Delete all session keys for a tenant (right-to-erasure path).

        Uses SCAN with pattern session:*:{tenant_id} to avoid KEYS blocking.
        Returns count of deleted keys.
        """
        pattern = f"session:*:{tenant_id}"
        deleted = 0
        async for key in self._redis.scan_iter(match=pattern, count=100):
            await self._redis.delete(key)
            deleted += 1
        if deleted:
            logger.info("session.tenant_flushed", tenant_id=str(tenant_id), deleted=deleted)
        return deleted


def get_session_service(redis: Redis) -> SessionService:
    return SessionService(redis)
