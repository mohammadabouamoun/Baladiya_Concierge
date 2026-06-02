from __future__ import annotations

import structlog
from redis.asyncio import Redis, from_url

logger = structlog.get_logger(__name__)

_redis: Redis | None = None


async def init_redis(redis_url: str) -> None:
    global _redis
    _redis = from_url(redis_url, decode_responses=True)
    await _redis.ping()
    logger.info("redis.connected", url=redis_url)


async def close_redis() -> None:
    if _redis:
        await _redis.aclose()
        logger.info("redis.disconnected")


def get_redis() -> Redis:
    if _redis is None:
        raise RuntimeError("Redis not initialised — call init_redis() at startup")
    return _redis
