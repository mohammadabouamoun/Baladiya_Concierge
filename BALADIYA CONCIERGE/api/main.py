from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from api.core.config import StartupError, get_settings
from api.core.logging import configure_logging, set_tenant_id, set_trace_id
from api.infra.db import close_db, init_db
from api.infra.redis import close_redis, init_redis

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    configure_logging(settings.env)

    log = structlog.get_logger("startup")
    log.info("starting", env=settings.env)

    try:
        await init_db(settings.database_url)
        await init_redis(settings.redis_url)
    except Exception as exc:
        raise StartupError(f"Startup failed: {exc}") from exc

    log.info("ready")
    yield

    await close_db()
    await close_redis()
    log.info("shutdown complete")


app = FastAPI(
    title="Baladiya Concierge API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tightened per-tenant in feature 004 (widget)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def _request_context_middleware(request: Request, call_next) -> Response:
    trace_id = request.headers.get("X-Trace-Id", str(uuid.uuid4()))
    set_trace_id(trace_id)
    # tenant_id is set later by get_db after JWT validation
    set_tenant_id("")
    response = await call_next(request)
    response.headers["X-Trace-Id"] = trace_id
    return response


@app.get("/healthz", tags=["ops"])
async def healthz() -> dict:
    return {"status": "ok"}


# ── Routers ────────────────────────────────────────────────────────────────
from api.api.platform.router import router as platform_router  # noqa: E402

app.include_router(platform_router, prefix="/platform", tags=["platform"])
