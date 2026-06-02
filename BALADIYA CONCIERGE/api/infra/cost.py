from __future__ import annotations

import uuid
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


def log_llm_cost(
    tenant_id: uuid.UUID | None,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    extra: dict[str, Any] | None = None,
) -> None:
    """Emit a structured log line for every LLM/embedding call tagged with tenant_id.

    This is the cost attribution hook — cost tracking tools aggregate on
    tenant_id + provider + model fields.
    """
    logger.info(
        "cost.llm",
        tenant_id=str(tenant_id) if tenant_id else None,
        provider=provider,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_tokens=input_tokens + output_tokens,
        **(extra or {}),
    )


def log_embedding_cost(
    tenant_id: uuid.UUID | None,
    provider: str,
    model: str,
    token_count: int,
    extra: dict[str, Any] | None = None,
) -> None:
    """Emit a structured log line for every embedding call tagged with tenant_id."""
    logger.info(
        "cost.embedding",
        tenant_id=str(tenant_id) if tenant_id else None,
        provider=provider,
        model=model,
        cost_tokens=token_count,
        **(extra or {}),
    )
