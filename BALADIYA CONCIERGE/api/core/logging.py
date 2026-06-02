from __future__ import annotations

import logging
import sys
from contextvars import ContextVar
from typing import Any

import structlog

# Per-request context vars — set by middleware, read by structlog processor
_trace_id: ContextVar[str] = ContextVar("trace_id", default="")
_tenant_id: ContextVar[str] = ContextVar("tenant_id", default="")


def set_trace_id(value: str) -> None:
    _trace_id.set(value)


def set_tenant_id(value: str) -> None:
    _tenant_id.set(value)


def get_trace_id() -> str:
    return _trace_id.get()


def get_tenant_id() -> str:
    return _tenant_id.get()


def _inject_context(
    logger: Any, method: str, event_dict: structlog.types.EventDict
) -> structlog.types.EventDict:
    event_dict["trace_id"] = _trace_id.get()
    event_dict["tenant_id"] = _tenant_id.get()
    return event_dict


def configure_logging(env: str = "development") -> None:
    """Configure structlog. Call once at application startup."""
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        _inject_context,
        structlog.processors.StackInfoRenderer(),
    ]

    if env == "production":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(logging.INFO if env == "production" else logging.DEBUG)
