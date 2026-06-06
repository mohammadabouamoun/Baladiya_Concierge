from __future__ import annotations

import time
import uuid

import hvac
import structlog

from api.core.config import StartupError

logger = structlog.get_logger(__name__)

_client: hvac.Client | None = None

# Per-widget key LRU cache: widget_id (str) → (key, expires_at)
# Cache TTL = 300s. On rotation, entry is overwritten immediately.
_widget_key_cache: dict[str, tuple[str, float]] = {}
_WIDGET_KEY_CACHE_TTL = 300.0
_WIDGET_KEY_CACHE_MAX = 128


def get_vault_client() -> hvac.Client:
    if _client is None:
        raise RuntimeError("Vault not initialised — call load_secrets() at startup")
    return _client


def load_secrets(vault_addr: str, vault_token: str) -> None:
    """Authenticate to Vault; raise StartupError if unreachable."""
    global _client
    try:
        client = hvac.Client(url=vault_addr, token=vault_token)
        if not client.is_authenticated():
            raise StartupError(f"Vault at {vault_addr} rejected authentication")
        _client = client
        logger.info("vault.connected", addr=vault_addr)
    except Exception as exc:
        raise StartupError(f"Vault unreachable: {vault_addr} — {exc}") from exc


def get_widget_signing_key(widget_id: uuid.UUID) -> str:
    """Fetch the per-widget signing key from Vault (LRU-cached, TTL 300s).

    Raises RuntimeError if Vault is not initialised or the key is absent.
    """
    cache_key = str(widget_id)
    cached = _widget_key_cache.get(cache_key)
    if cached is not None:
        key, expires_at = cached
        if time.monotonic() < expires_at:
            return key
        del _widget_key_cache[cache_key]

    client = get_vault_client()
    try:
        secret = client.secrets.kv.v2.read_secret_version(
            path=f"baladiya/widget/{widget_id}",
            mount_point="secret",
        )
        key = secret["data"]["data"]["signing_key"]
    except Exception as exc:
        raise RuntimeError(f"Vault: widget signing key not found for {widget_id}: {exc}") from exc

    if len(_widget_key_cache) >= _WIDGET_KEY_CACHE_MAX:
        oldest = min(_widget_key_cache, key=lambda k: _widget_key_cache[k][1])
        del _widget_key_cache[oldest]

    _widget_key_cache[cache_key] = (key, time.monotonic() + _WIDGET_KEY_CACHE_TTL)
    return key


def invalidate_widget_key_cache(widget_id: uuid.UUID) -> None:
    """Remove the cached key for a widget immediately (call on rotation)."""
    _widget_key_cache.pop(str(widget_id), None)
