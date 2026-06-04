"""T-043: Session memory scoping — Tenant A's session cannot bleed into Tenant B.

Verifies that load() uses the composite key session:{session_id}:{tenant_id}
so two tenants with the same session_id see separate memory.
"""
from __future__ import annotations

import json
import uuid

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock

from api.domain.session import SessionMemory, SessionTurn
from api.services.session_service import SessionService, _session_key


@pytest.fixture
def fake_redis():
    """In-memory Redis mock with get/set/expire/scan_iter support."""
    store: dict[str, str] = {}

    redis = MagicMock()
    redis.get = AsyncMock(side_effect=lambda k: store.get(k))

    async def mock_set(k, v, ex=None):
        store[k] = v

    redis.set = AsyncMock(side_effect=mock_set)

    async def mock_delete(k):
        store.pop(k, None)

    redis.delete = AsyncMock(side_effect=mock_delete)

    async def scan_iter(match="*", count=100):
        import fnmatch
        for key in list(store.keys()):
            if fnmatch.fnmatch(key, match):
                yield key

    redis.scan_iter = scan_iter

    return redis, store


@pytest.mark.asyncio
async def test_different_tenants_same_session_id_are_isolated(fake_redis):
    redis, store = fake_redis
    svc = SessionService(redis)

    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    shared_session_id = "session-xyz"

    # Store something for tenant_a
    mem_a = SessionMemory(turns=[SessionTurn(role="user", content="tenant A message")])
    await svc.save(shared_session_id, tenant_a, mem_a)

    # Tenant B's load with the same session_id must return empty memory
    mem_b = await svc.load(shared_session_id, tenant_b)

    assert len(mem_b.turns) == 0, "Tenant B must not see Tenant A's session memory"


@pytest.mark.asyncio
async def test_session_key_includes_both_session_and_tenant():
    """The Redis key must embed both session_id AND tenant_id."""
    session_id = "sess-abc"
    tenant_id = uuid.uuid4()
    key = _session_key(session_id, tenant_id)
    assert session_id in key
    assert str(tenant_id) in key


@pytest.mark.asyncio
async def test_flush_tenant_only_deletes_own_keys(fake_redis):
    redis, store = fake_redis
    svc = SessionService(redis)

    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()

    # Seed one session each
    mem = SessionMemory(turns=[SessionTurn(role="user", content="hello")])
    await svc.save("s1", tenant_a, mem)
    await svc.save("s2", tenant_b, mem)

    assert len(store) == 2

    deleted = await svc.flush_tenant(tenant_a)

    assert deleted == 1
    # Tenant B's key must still exist
    remaining_key = _session_key("s2", tenant_b)
    assert remaining_key in store


@pytest.mark.asyncio
async def test_expired_session_returns_empty_memory(fake_redis):
    """If the Redis key doesn't exist (TTL expired), load returns empty memory."""
    redis, store = fake_redis
    svc = SessionService(redis)

    tenant_id = uuid.uuid4()
    # Don't save anything — simulate TTL expiry
    memory = await svc.load("nonexistent-session", tenant_id)

    assert memory.turns == []
