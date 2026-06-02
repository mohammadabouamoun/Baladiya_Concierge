from __future__ import annotations

import uuid
from enum import Enum

import structlog

from api.core.config import get_settings
from api.infra.modelserver_client import ClassifyResponse, classify

logger = structlog.get_logger(__name__)


class RouteDecision(str, Enum):
    WORKFLOW = "workflow"   # classifier confident → route to workflow handler
    AGENT = "agent"         # below confidence threshold → fall through to agent
    SPAM = "spam"           # spam → drop before any write


async def route(
    text: str,
    tenant_id: uuid.UUID,
    session_id: str,
) -> tuple[RouteDecision, ClassifyResponse]:
    """Classify the inbound message and decide routing.

    Returns (RouteDecision, ClassifyResponse).

    Below-threshold → AGENT (fail safe, not fail cheap).
    spam (above threshold) → SPAM (dropped before capture_request).
    All other above-threshold intents → WORKFLOW.
    """
    result = await classify(text)

    settings = get_settings()
    thresholds: dict = settings.classifier_confidence_thresholds
    threshold = thresholds.get(result.intent, 0.75)

    if result.intent == "spam" and result.confidence >= threshold:
        logger.info(
            "router.spam_dropped",
            tenant_id=str(tenant_id),
            session_id=session_id,
            confidence=result.confidence,
            text_preview=text[:60],
        )
        return RouteDecision.SPAM, result

    if result.confidence < threshold:
        logger.info(
            "router.below_threshold",
            tenant_id=str(tenant_id),
            session_id=session_id,
            intent=result.intent,
            confidence=result.confidence,
            threshold=threshold,
        )
        return RouteDecision.AGENT, result

    logger.info(
        "router.workflow",
        tenant_id=str(tenant_id),
        session_id=session_id,
        intent=result.intent,
        category=result.category,
        confidence=result.confidence,
    )
    return RouteDecision.WORKFLOW, result
