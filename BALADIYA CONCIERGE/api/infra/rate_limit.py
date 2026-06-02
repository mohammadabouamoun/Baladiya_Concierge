from __future__ import annotations

import time
from typing import Annotated

import structlog
from fastapi import Depends, HTTPException, Request, status

from api.core.security import TokenClaims, get_current_user
from api.infra.redis import get_redis

logger = structlog.get_logger(__name__)

DEFAULT_REQUESTS_PER_MINUTE = 60


async def rate_limit(
    request: Request,
    token: Annotated[TokenClaims, Depends(get_current_user)],
) -> None:
    """Redis sliding-window rate limiter scoped per (tenant_id, endpoint).

    Reads requests_per_minute from tenant.settings if available; falls back
    to DEFAULT_REQUESTS_PER_MINUTE.

    Returns 429 when the window is exhausted.
    """
    if token.tenant_id is None:
        # Platform Manager routes are not rate-limited
        return

    redis = get_redis()
    endpoint = request.url.path
    window_key = f"ratelimit:{token.tenant_id}:{endpoint}"
    now = time.time()
    window_start = now - 60.0

    pipe = redis.pipeline()
    pipe.zremrangebyscore(window_key, 0, window_start)
    pipe.zadd(window_key, {str(now): now})
    pipe.zcard(window_key)
    pipe.expire(window_key, 120)
    results = await pipe.execute()

    count = results[2]

    # TODO: fetch tenant.settings.requests_per_minute from DB/cache
    limit = DEFAULT_REQUESTS_PER_MINUTE

    if count > limit:
        logger.warning(
            "rate_limit.exceeded",
            tenant_id=str(token.tenant_id),
            endpoint=endpoint,
            count=count,
            limit=limit,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded: {limit} requests/minute",
        )
