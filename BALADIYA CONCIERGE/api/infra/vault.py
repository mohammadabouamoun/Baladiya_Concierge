from __future__ import annotations

import structlog
import hvac

from api.core.config import StartupError

logger = structlog.get_logger(__name__)

_client: hvac.Client | None = None


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
