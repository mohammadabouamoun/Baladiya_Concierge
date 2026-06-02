"""Async httpx client for the Gemini embedding API (gemini-embedding-001, 1536 dims).

API key is resolved from Vault at startup via Settings.gemini_api_key.
NEVER falls back to a different model — the entire pgvector corpus is pinned
to one model's vector space.
"""
from __future__ import annotations

import structlog
from httpx import AsyncClient, HTTPStatusError, RequestError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from api.core.config import get_settings

logger = structlog.get_logger(__name__)

_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com"
_MODEL = "gemini-embedding-001"
_DIMENSIONS = 1536

_client: AsyncClient | None = None


async def init_embedding_client() -> None:
    global _client
    _client = AsyncClient(base_url=_GEMINI_BASE_URL, timeout=30.0)
    logger.info("embedding_client.ready", model=_MODEL, dimensions=_DIMENSIONS)


async def close_embedding_client() -> None:
    if _client:
        await _client.aclose()


def get_embedding_client() -> AsyncClient:
    if _client is None:
        raise RuntimeError("Embedding client not initialised — call init_embedding_client() at startup")
    return _client


@retry(
    retry=retry_if_exception_type((RequestError,)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4.0),
    reraise=True,
)
async def embed(text: str) -> list[float]:
    """Embed a single text string.  Returns a list of 1536 floats.

    Retries up to 3 times on transient network errors with exponential backoff.
    On 4xx/5xx, re-raises immediately (no retry — caller should handle or mark pending).
    """
    settings = get_settings()
    client = get_embedding_client()

    url = f"/v1beta/models/{_MODEL}:embedContent"
    payload = {
        "model": f"models/{_MODEL}",
        "content": {"parts": [{"text": text}]},
        "outputDimensionality": _DIMENSIONS,  # truncate to 1536; full model is 3072
    }

    try:
        resp = await client.post(
            url,
            json=payload,
            params={"key": settings.gemini_api_key},
        )
        resp.raise_for_status()
    except HTTPStatusError as exc:
        logger.error(
            "embedding_client.http_error",
            status=exc.response.status_code,
            text_preview=text[:80],
        )
        raise
    except RequestError as exc:
        logger.warning("embedding_client.request_error", error=str(exc))
        raise

    values: list[float] = resp.json()["embedding"]["values"]
    if len(values) != _DIMENSIONS:
        raise ValueError(
            f"Unexpected embedding dimension: got {len(values)}, expected {_DIMENSIONS}"
        )
    return values


async def embed_batch(texts: list[str]) -> list[list[float]]:
    """Embed multiple texts sequentially (Gemini embedding API has no batch endpoint)."""
    results = []
    for text in texts:
        results.append(await embed(text))
    return results
