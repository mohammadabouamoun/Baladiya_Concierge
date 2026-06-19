"""Bounded tool-calling agent: handles hard/ambiguous messages the router cannot classify.

Cap: max_tool_calls (from Settings, default 3 per FR-003) — auto-escalates if exceeded.
All tools receive AgentContext, which carries tenant_id from JWT (never from payload).
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.config import get_settings
from api.infra import llm_client
from api.infra.llm_client import AgentMessage, AgentTurn, ToolCallRequest
from api.services.session_service import SessionService

logger = structlog.get_logger(__name__)


class PhoneVerificationRequired(Exception):
    """Raised by the agent when a tool requires phone verification before proceeding."""


FALLBACK_MESSAGE = (
    "I wasn't able to fully process your request. "
    "I've notified our staff and they will follow up with you shortly."
)

_PROMPT_DIR = Path(__file__).parent.parent.parent / "prompts"


@dataclass
class AgentContext:
    tenant_id: uuid.UUID
    session_id: str
    db_session: AsyncSession
    lang: str = "en"                       # detected language — "en" | "ar"
    variety: str = "en"                    # detected variety — "en" | "msa" | "lebanese" | "arabizi"
    visitor_phone_hash: str | None = None  # set when session phone is verified


async def _get_persona(context: AgentContext) -> str:
    """Fetch tenant persona from tenant.settings — never hardcoded (Spec Assumptions §3)."""
    from api.domain.tenant import Tenant
    try:
        result = await context.db_session.execute(
            select(Tenant).where(Tenant.id == context.tenant_id)
        )
        tenant = result.scalar_one_or_none()
        if tenant and isinstance(tenant.settings, dict):
            return tenant.settings.get("persona", "your municipality")
    except Exception as exc:
        logger.warning("agent.persona_lookup_failed", tenant_id=str(context.tenant_id), error=str(exc))
    return "your municipality"


def _load_system_prompt(persona: str, lang: str = "en") -> str:
    """Load and render system prompt for the detected language (FR-002).

    English path never imports Arabic resources (constitution §III).
    Falls back to inline English string if prompt file is missing.
    """
    try:
        from api.services.prompt_service import select_system_prompt
        return select_system_prompt(lang, persona)
    except Exception as exc:
        logger.warning("agent.system_prompt_failed", lang=lang, error=str(exc))
        return f"You are a helpful civic services assistant for {persona}."


def _session_to_history(session_turns: list) -> list[AgentMessage]:
    """Convert session memory turns to agent message history."""
    history = []
    for turn in session_turns:
        role = turn.role if turn.role in ("user", "model") else "user"
        history.append(AgentMessage(role=role, content=turn.content))
    return history


async def _dispatch_tool(tool_call: ToolCallRequest, context: AgentContext) -> dict:
    """Route a tool call to the correct Python implementation."""
    from api.services.tools import capture_request as capture_tool
    from api.services.tools import escalate as escalate_tool
    from api.services.tools import rag_search as rag_tool

    try:
        if tool_call.name == "rag_search":
            return await rag_tool.run(tool_call.args, context)
        elif tool_call.name == "capture_request":
            return await capture_tool.run(tool_call.args, context)
        elif tool_call.name == "escalate":
            return await escalate_tool.run(tool_call.args, context)
        else:
            logger.warning(
                "agent.unknown_tool",
                tool=tool_call.name,
                tenant_id=str(context.tenant_id),
            )
            return {"error": f"Unknown tool: {tool_call.name}"}
    except Exception as exc:
        logger.error(
            "agent.tool_dispatch_error",
            tool=tool_call.name,
            tenant_id=str(context.tenant_id),
            error=str(exc),
        )
        return {"error": str(exc)}


async def run(
    message: str,
    context: AgentContext,
    session_svc: SessionService | None = None,
) -> str:
    """Run the bounded tool-calling loop for one resident turn.

    session_svc: injectable for testing; defaults to a live Redis-backed SessionService.
    Returns the final text response. Guarantees: never raises — FALLBACK_MESSAGE on error.
    """
    settings = get_settings()

    # D1: session_svc is injectable — tests can pass a mock without module-level patching
    if session_svc is None:
        from api.infra.redis import get_redis
        session_svc = SessionService(get_redis())

    # Load prior conversation memory
    memory = await session_svc.load(context.session_id, context.tenant_id)
    history = _session_to_history(memory.turns)

    # C1: Fetch tenant persona at request time — never hardcoded (Spec Assumptions §3)
    persona = await _get_persona(context)
    system_prompt = _load_system_prompt(persona, lang=context.lang)

    current_user_message: str | None = message

    try:
        for iteration in range(settings.max_tool_calls):
            turn: AgentTurn = await llm_client.complete(
                system_prompt=system_prompt,
                history=history,
                user_message=current_user_message,
            )

            # Append the user message to history (only on first iteration or if present)
            if current_user_message is not None:
                history.append(AgentMessage(role="user", content=current_user_message))
                current_user_message = None  # subsequent iterations continue from tool result

            if not turn.is_tool_call:
                # Final text response
                history.append(AgentMessage(role="model", content=turn.text))
                await session_svc.add_turns(
                    context.session_id,
                    context.tenant_id,
                    [("user", message), ("model", turn.text or "")],
                )
                logger.info(
                    "agent.completed",
                    tenant_id=str(context.tenant_id),
                    session_id=context.session_id,
                    iterations=iteration + 1,
                )
                return turn.text or ""

            # Tool call
            logger.info(
                "agent.tool_call",
                tool=turn.tool_call.name,
                tenant_id=str(context.tenant_id),
                iteration=iteration,
            )

            history.append(AgentMessage(role="model", tool_call=turn.tool_call))
            tool_result = await _dispatch_tool(turn.tool_call, context)
            if tool_result.get("verification_required"):
                raise PhoneVerificationRequired()
            history.append(
                AgentMessage(
                    role="tool_result",
                    tool_result_name=turn.tool_call.name,
                    tool_result_call_id=turn.tool_call.call_id,
                    content=json.dumps(tool_result),
                )
            )

        # Max iterations reached — auto-escalate
        logger.warning(
            "agent.max_tool_calls_exceeded",
            tenant_id=str(context.tenant_id),
            session_id=context.session_id,
            iterations=settings.max_tool_calls,
        )
        from api.services.tools import escalate as escalate_tool
        await escalate_tool.run({"reason": "max_tool_calls_exceeded"}, context)
        await session_svc.add_turns(
            context.session_id,
            context.tenant_id,
            [("user", message), ("model", FALLBACK_MESSAGE)],
        )
        return FALLBACK_MESSAGE

    except PhoneVerificationRequired:
        raise  # let router_service handle this — do NOT swallow into fallback

    except Exception as exc:
        logger.error(
            "agent.unhandled_error",
            tenant_id=str(context.tenant_id),
            session_id=context.session_id,
            error=str(exc),
        )
        return FALLBACK_MESSAGE
