"""Classifier-driven router: classifies → routes to workflow or agent.

Easy turns (confident classifier) → workflow handler (no agent LLM call).
Hard/ambiguous turns (below threshold) → agent_service bounded loop.
Spam → dropped before any write (constitution requirement).

T-034: workflow vs agent % is logged per tenant for cost attribution.
"""
from __future__ import annotations

import uuid
from enum import Enum

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.config import get_settings
from api.infra.modelserver_client import ClassifyResponse, classify

logger = structlog.get_logger(__name__)


class RouteDecision(str, Enum):
    WORKFLOW = "workflow"
    AGENT = "agent"
    SPAM = "spam"


async def route(
    text: str,
    tenant_id: uuid.UUID,
    session_id: str,
) -> tuple[RouteDecision, ClassifyResponse]:
    """Classify and return routing decision.

    Below confidence threshold → AGENT (fail safe, not fail cheap).
    Spam above threshold → SPAM (dropped before any write).
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


async def handle(
    text: str,
    tenant_id: uuid.UUID,
    session_id: str,
    db_session: AsyncSession,
) -> tuple[str, str]:
    """Handle an inbound message end-to-end.

    Returns (response_text, handled_by) where handled_by ∈ {"workflow", "agent", "spam"}.
    The caller logs handled_by for cost attribution (T-034).

    Workflow path never makes an agent LLM call — tools are invoked directly.
    """
    from api.services.agent_service import AgentContext

    context = AgentContext(
        tenant_id=tenant_id,
        session_id=session_id,
        db_session=db_session,
    )

    decision, clf_result = await route(text, tenant_id, session_id)

    # ── Spam: drop silently ────────────────────────────────────────────────
    if decision == RouteDecision.SPAM:
        return "", "spam"

    # ── Agent path ─────────────────────────────────────────────────────────
    if decision == RouteDecision.AGENT:
        from api.services.agent_service import run as agent_run
        response = await agent_run(text, context)
        logger.info(
            "router.agent_handled",
            tenant_id=str(tenant_id),
            session_id=session_id,
        )
        return response, "agent"

    # ── Workflow path (confident classifier) ───────────────────────────────
    intent = clf_result.intent

    if intent == "report":
        from api.services.tools import capture_request as capture_tool
        result = await capture_tool.run(
            {"intent": "report", "description": text},
            context,
        )
        if "error" in result:
            response = f"I wasn't able to record your request: {result['error']}"
        else:
            response = (
                "Your request has been recorded. "
                + result.get("message", "We will follow up with you shortly.")
            )

    elif intent == "question":
        from api.services.tools import rag_search as rag_tool
        result = await rag_tool.run({"query": text}, context)
        if "error" in result or not result.get("results"):
            response = (
                "I don't have specific information about this in our knowledge base. "
                "Would you like me to connect you with a staff member who can help?"
            )
        else:
            top = result["results"][:3]
            response = "\n\n".join(r["chunk"] for r in top)

    elif intent == "human":
        from api.services.tools import escalate as escalate_tool
        result = await escalate_tool.run(
            {"reason": "resident requested human contact"},
            context,
        )
        if "error" in result:
            response = "I wasn't able to connect you right now. Please call the municipality directly."
        else:
            response = (
                "I've notified our staff and they will contact you shortly. "
                + result.get("message", "")
            )

    else:
        response = "Thank you for your message. Is there anything else I can help you with?"

    logger.info(
        "router.workflow_handled",
        tenant_id=str(tenant_id),
        session_id=session_id,
        intent=intent,
    )
    return response, "workflow"
