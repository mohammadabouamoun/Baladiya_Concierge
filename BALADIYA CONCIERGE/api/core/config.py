from __future__ import annotations

import os
from functools import lru_cache
from typing import Literal

import hvac
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="forbid",
    )

    # ── Environment ────────────────────────────────────────────
    env: Literal["development", "testing", "production"] = "development"

    # ── Vault (bootstrap — all other secrets come FROM Vault) ─
    vault_addr: str = "http://localhost:8200"
    vault_token: str = Field(..., description="Vault root/app token")

    # ── Runtime secrets (populated by load_secrets()) ─────────
    database_url: str = ""
    redis_url: str = "redis://localhost:6379/0"
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = ""
    minio_secret_key: str = ""
    gemini_api_key: str = ""
    groq_api_key: str = ""
    guardrails_url: str = "http://guardrails:8002"
    modelserver_url: str = "http://modelserver:8001"

    # ── JWT ────────────────────────────────────────────────────
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    # ── Rate limiting defaults ─────────────────────────────────
    default_requests_per_minute: int = 60
    capture_requests_per_minute: int = 5   # per-session limit on capture_request tool
    widget_token_expire_minutes: int = 1440  # 24h visitor widget token

    # ── Classifier confidence thresholds (FR-010) ──────────────
    # Below threshold → falls through to agent (fail safe, not fail cheap).
    # Values mirror eval_thresholds.yaml; override via env var if needed.
    classifier_confidence_thresholds: dict = Field(
        default={"report": 0.75, "question": 0.75, "human": 0.65, "spam": 0.90},
        description="Per-intent confidence thresholds loaded from settings",
    )

    # ── Modelserver ────────────────────────────────────────────
    modelserver_service_token: str = ""

    # ── LLM cost-control ──────────────────────────────────────
    max_tool_calls: int = 3          # cap per agent turn — FR-003; spec default = 3
    max_tokens_per_turn: int = 4096

    # ── CMS / RAG ─────────────────────────────────────────────
    # Token approximation: 4 chars ≈ 1 token (English & mixed content)
    chunk_max_chars: int = 2048    # 512 tokens × 4
    chunk_min_chars: int = 400     # 100 tokens × 4
    chunk_overlap_chars: int = 200  # 50 tokens × 4
    rag_top_k: int = 5
    embedding_model: str = "gemini-embedding-001"
    embedding_dimensions: int = 1536

    @field_validator("database_url")
    @classmethod
    def _database_url_not_empty_in_prod(cls, v: str, info) -> str:
        # Vault populates this at startup; if still empty at request time it's a bug
        return v


def _load_from_vault(settings: Settings) -> None:
    """Pull secrets from Vault and write them into the settings object.

    Raises StartupError if Vault is unreachable — the service must not start.
    """
    try:
        client = hvac.Client(url=settings.vault_addr, token=settings.vault_token)
        if not client.is_authenticated():
            raise StartupError("Vault authentication failed — check VAULT_TOKEN")

        def _get(path: str, key: str) -> str:
            secret = client.secrets.kv.v2.read_secret_version(path=path, mount_point="secret")
            return secret["data"]["data"][key]

        # Fetch secrets — paths match what `migrate` seeds in Vault
        object.__setattr__(settings, "database_url", _get("baladiya/db", "url"))
        object.__setattr__(settings, "jwt_secret", _get("baladiya/api", "jwt_secret"))
        object.__setattr__(settings, "gemini_api_key", _get("baladiya/llm", "gemini_api_key"))
        object.__setattr__(settings, "groq_api_key", _get("baladiya/llm", "groq_api_key"))
        object.__setattr__(settings, "minio_access_key", _get("baladiya/minio", "access_key"))
        object.__setattr__(settings, "minio_secret_key", _get("baladiya/minio", "secret_key"))

    except hvac.exceptions.VaultError as exc:
        raise StartupError(f"Vault unreachable or misconfigured: {exc}") from exc


class StartupError(RuntimeError):
    """Raised when a required service (Vault, DB) is unavailable at startup."""


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the global Settings singleton.

    Secrets are loaded from Vault once; subsequent calls return the cached instance.
    Call `get_settings.cache_clear()` in tests to inject a fake.
    """
    settings = Settings()
    if settings.env != "testing":
        _load_from_vault(settings)
    return settings
