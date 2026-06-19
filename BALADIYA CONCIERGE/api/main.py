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
from api.infra.embedding_client import close_embedding_client, init_embedding_client
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
        await init_embedding_client()
        from api.infra.modelserver_client import init_modelserver_client
        await init_modelserver_client()
        from api.infra.guardrails_client import init_guardrails_client
        await init_guardrails_client()
    except Exception as exc:
        raise StartupError(f"Startup failed: {exc}") from exc

    # Retry any CMS entries that failed to embed in a previous run (T-023)
    try:
        from api.services.cms_service import retry_all_pending_entries
        await retry_all_pending_entries()
    except Exception as exc:
        # Non-fatal: log and continue — the retry will be attempted on next restart
        logger.warning("startup.cms_retry_failed", error=str(exc))

    log.info("ready")
    yield

    await close_db()
    await close_redis()
    await close_embedding_client()
    from api.infra.modelserver_client import close_modelserver_client
    await close_modelserver_client()
    from api.infra.guardrails_client import close_guardrails_client
    await close_guardrails_client()
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
    allow_origins=["*"],   # depth-in-defense; true auth boundary is widget JWT + origin check
    allow_credentials=False,  # must be False when allow_origins=["*"]; widget uses Bearer not cookies
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Trace-Id"],
    expose_headers=["X-Trace-Id"],
)


@app.middleware("http")
async def _request_context_middleware(request: Request, call_next) -> Response:
    trace_id = request.headers.get("X-Trace-Id", str(uuid.uuid4()))
    set_trace_id(trace_id)
    # tenant_id is set later by get_db after JWT validation
    set_tenant_id("")
    response = await call_next(request)
    response.headers["X-Trace-Id"] = trace_id
    # Baseline security headers on all widget paths.
    # /widget/config sets a dynamic frame-ancestors CSP per-request (FR-009).
    # All other widget paths get a restrictive fallback.
    if request.url.path.startswith("/widget/"):
        response.headers["X-Content-Type-Options"] = "nosniff"
        if "Content-Security-Policy" not in response.headers:
            response.headers["Content-Security-Policy"] = "frame-ancestors 'self'"
    return response


@app.get("/healthz", tags=["ops"])
async def healthz() -> dict:
    return {"status": "ok"}


# ── Routers ────────────────────────────────────────────────────────────────
from api.api.platform.router import router as platform_router  # noqa: E402
from api.api.cms.router import router as cms_router  # noqa: E402
from api.api.rag.router import router as rag_router  # noqa: E402
from api.api.auth.router import router as auth_router  # noqa: E402
from api.api.chat.router import router as chat_router  # noqa: E402
from api.api.admin.router import router as admin_router  # noqa: E402
from api.api.widget.router import router as widget_router  # noqa: E402
from api.api.verify.router import router as verify_router  # noqa: E402

app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(platform_router, prefix="/platform", tags=["platform"])
app.include_router(cms_router, prefix="/cms", tags=["cms"])
app.include_router(rag_router, prefix="/rag", tags=["rag"])
app.include_router(chat_router, prefix="/chat", tags=["chat"])
app.include_router(admin_router, prefix="/admin", tags=["admin"])
app.include_router(widget_router, prefix="/widget", tags=["widget"])
app.include_router(verify_router, prefix="/verify", tags=["verify"])
