from __future__ import annotations

import structlog
from httpx import AsyncClient, HTTPStatusError, RequestError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from api.core.config import get_settings

logger = structlog.get_logger(__name__)

_client: AsyncClient | None = None


async def init_modelserver_client() -> None:
    global _client
    settings = get_settings()
    _client = AsyncClient(
        base_url=settings.modelserver_url,
        headers={"X-Service-Token": _get_service_token()},
        timeout=15.0,
    )
    logger.info("modelserver_client.ready", url=settings.modelserver_url)


async def close_modelserver_client() -> None:
    if _client:
        await _client.aclose()


def _get_service_token() -> str:
    settings = get_settings()
    # Token is resolved from Vault at startup via config
    return getattr(settings, "modelserver_service_token", "")


def get_client() -> AsyncClient:
    if _client is None:
        raise RuntimeError("modelserver client not initialised — call init_modelserver_client() at startup")
    return _client


class ClassifyResponse:
    __slots__ = ("intent", "category", "confidence", "lang", "variety")

    def __init__(self, intent: str, category: str, confidence: float, lang: str, variety: str) -> None:
        self.intent = intent
        self.category = category
        self.confidence = confidence
        self.lang = lang
        self.variety = variety


@retry(
    retry=retry_if_exception_type((RequestError,)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.1, min=0.1, max=1.0),
    reraise=True,
)
async def classify(text: str) -> ClassifyResponse:
    """Call the modelserver /classify endpoint with tenacity retries on transient errors."""
    client = get_client()
    try:
        resp = await client.post("/classify", json={"text": text})
        resp.raise_for_status()
    except HTTPStatusError as exc:
        logger.error("modelserver.http_error", status=exc.response.status_code, text=text[:80])
        raise
    except RequestError as exc:
        logger.warning("modelserver.request_error", error=str(exc))
        raise

    data = resp.json()
    return ClassifyResponse(
        intent=data["intent"],
        category=data["category"],
        confidence=data["confidence"],
        lang=data["lang"],
        variety=data["variety"],
    )
