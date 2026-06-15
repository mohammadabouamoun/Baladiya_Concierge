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
from api.services.lang_detect_service import LangDetectResult, detect as lang_detect

logger = structlog.get_logger(__name__)

# ── Language-aware workflow response strings ───────────────────────────────
# "ar" key is used for variety ∈ {msa, lebanese, arabizi}.
# Arabizi writers communicate in Arabic — formal civic reply is in Arabic script.
_W = {
    "en": {
        "report_ok":     "Your request has been recorded. Reference: {ref}",
        "report_err":    "I wasn't able to record your request. Please try again.",
        "question_miss": (
            "I don't have specific information about this in our knowledge base. "
            "Would you like me to connect you with a staff member who can help?"
        ),
        "human_ok":      "I've notified our staff and they will contact you shortly. Ticket: {ref}",
        "human_err":     "I wasn't able to connect you right now. Please call the municipality directly.",
        "fallback":      "Thank you for your message. Is there anything else I can help you with?",
        "verify_prompt": (
            "To file this report, please verify your phone number. "
            "This ensures accountability for reports submitted to the municipality."
        ),
        "blocked":       (
            "You are currently unable to submit reports due to a previous false report. "
            "Please contact the municipality directly for assistance."
        ),
    },
    "ar": {
        "report_ok":     "تم تسجيل طلبك. رقم المرجع: {ref}",
        "report_err":    "لم نتمكن من تسجيل طلبك. يرجى المحاولة مجدداً.",
        "question_miss": (
            "لا تتوفر لديّ معلومات محددة حول هذا الموضوع. "
            "هل تريد التواصل مع أحد موظفينا؟"
        ),
        "human_ok":      "تم إخطار موظفينا وسيتواصلون معك قريباً. رقم التذكرة: {ref}",
        "human_err":     "لم نتمكن من التواصل معك الآن. يرجى الاتصال بالبلدية مباشرة.",
        "fallback":      "شكراً لرسالتك. هل يمكنني مساعدتك في شيء آخر؟",
        "verify_prompt": (
            "لتقديم هذا البلاغ، يرجى التحقق من رقم هاتفك. "
            "يضمن ذلك مسؤولية البلاغات المقدمة إلى البلدية."
        ),
        "blocked":       (
            "لا يمكنك تقديم بلاغات حالياً بسبب بلاغ كاذب سابق. "
            "يرجى التواصل مع البلدية مباشرة للحصول على المساعدة."
        ),
    },
}

VERIFICATION_REQUIRED = "__VERIFICATION_REQUIRED__"


def _lang_key(variety: str) -> str:
    """Return "ar" for any Arabic variety (msa/lebanese/arabizi), "en" otherwise."""
    return "ar" if variety in ("msa", "lebanese", "arabizi") else "en"


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
    # Use Arabic-specific thresholds for MSA/Lebanese/Arabizi varieties.
    # The AR sub-model is trained on fewer rows so calibrated confidences are
    # lower even when precision/recall = 1.0 — see §8.3 in HANDOFF.md.
    if result.variety in ("msa", "lebanese", "arabizi"):
        thresholds: dict = settings.ar_classifier_confidence_thresholds
    else:
        thresholds = settings.classifier_confidence_thresholds
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
    Language detection runs first; lang result is passed to prompt service for AR routing.
    """
    from api.services.agent_service import AgentContext

    # FR-001: language detection MUST run before classification; defaults to en on failure
    lang_result: LangDetectResult = await lang_detect(text)
    logger.info(
        "router.lang_detected",
        tenant_id=str(tenant_id),
        session_id=session_id,
        lang=lang_result.lang,
        variety=lang_result.variety,
        confidence=round(lang_result.confidence, 3),
    )

    context = AgentContext(
        tenant_id=tenant_id,
        session_id=session_id,
        db_session=db_session,
        lang=lang_result.lang,
        variety=lang_result.variety,
    )

    decision, clf_result = await route(text, tenant_id, session_id)

    # ── Spam: drop silently ────────────────────────────────────────────────
    if decision == RouteDecision.SPAM:
        return "", "spam"

    # ── Agent path ─────────────────────────────────────────────────────────
    if decision == RouteDecision.AGENT:
        from api.services.agent_service import run as agent_run, PhoneVerificationRequired
        strings = _W[_lang_key(lang_result.variety)]
        try:
            response = await agent_run(text, context)
        except PhoneVerificationRequired:
            return strings["verify_prompt"], VERIFICATION_REQUIRED
        logger.info(
            "router.agent_handled",
            tenant_id=str(tenant_id),
            session_id=session_id,
        )
        return response, "agent"

    # ── Workflow path (confident classifier) ───────────────────────────────
    intent = clf_result.intent
    strings = _W[_lang_key(lang_result.variety)]

    if intent == "report":
        from api.repositories.blocked_reporter_repo import BlockedReporterRepository
        from api.services.otp_service import get_session_phone_hash
        from api.infra.redis import get_redis

        redis = get_redis()
        phone_hash = await get_session_phone_hash(redis, session_id, tenant_id)

        if not phone_hash:
            # Phone not verified — ask the resident to verify before filing
            return strings["verify_prompt"], VERIFICATION_REQUIRED

        # Check if this phone is blocked for false reports
        blocked_repo = BlockedReporterRepository(db_session)
        if await blocked_repo.is_blocked(tenant_id, phone_hash):
            logger.warning(
                "router.blocked_reporter",
                tenant_id=str(tenant_id),
                session_id=session_id,
            )
            return strings["blocked"], "workflow"

        # Verified and not blocked — attach phone hash to context for the capture tool
        context.visitor_phone_hash = phone_hash

        from api.services.tools import capture_request as capture_tool
        result = await capture_tool.run(
            {"intent": "report", "description": text},
            context,
        )
        if "error" in result:
            response = strings["report_err"]
        else:
            ref = result.get("id", "")[:8].upper()
            response = strings["report_ok"].format(ref=ref)

    elif intent == "question":
        from api.services.tools import rag_search as rag_tool
        result = await rag_tool.run({"query": text}, context)
        results = result.get("results") or []
        # Off-topic decline (A4): the relevance gate in rag_search is *relative* to the
        # top score, so an off-topic query still returns its "least irrelevant" chunk.
        # Here, on the raw-concat workflow path, apply an *absolute* language-aware floor:
        # if even the best match is below it, the question is off-topic for this KB —
        # decline gracefully (offer a human) instead of dumping loosely-related text.
        floor = get_settings().rag_relevance_floor.get(lang_result.variety, 0.58)
        top_sim = results[0]["similarity"] if results else 0.0
        if "error" in result or not results or top_sim < floor:
            if results and top_sim < floor:
                logger.info(
                    "router.question_offtopic_declined",
                    tenant_id=str(tenant_id),
                    session_id=session_id,
                    top_similarity=top_sim,
                    floor=floor,
                )
            response = strings["question_miss"]
        else:
            top = results[:3]
            response = "\n\n".join(r["chunk"] for r in top)

    elif intent == "human":
        from api.services.tools import escalate as escalate_tool
        result = await escalate_tool.run(
            {"reason": "resident requested human contact"},
            context,
        )
        if "error" in result:
            response = strings["human_err"]
        else:
            ref = result.get("ticket_id", "")[:8].upper()
            response = strings["human_ok"].format(ref=ref)

    else:
        response = strings["fallback"]

    logger.info(
        "router.workflow_handled",
        tenant_id=str(tenant_id),
        session_id=session_id,
        intent=intent,
    )
    return response, "workflow"
