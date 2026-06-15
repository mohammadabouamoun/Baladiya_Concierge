"""Async LLM client: Gemini-2.5-flash (primary) with Groq llama-3.3-70b fallback.

Uses asyncio.to_thread for the synchronous google-generativeai SDK.
Falls back to Groq after GEMINI_FALLBACK_THRESHOLD consecutive failures.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from typing import Any

import structlog
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from api.core.config import get_settings

logger = structlog.get_logger(__name__)

GEMINI_FALLBACK_THRESHOLD = 3


class _GeminiFailureTracker:
    """Tracks consecutive Gemini failures to trigger the Groq fallback.

    A class rather than a bare module global so tests can reset state
    by calling tracker.reset() without patching module internals.
    """
    def __init__(self) -> None:
        self.count: int = 0

    def record(self) -> None:
        self.count += 1

    def reset(self) -> None:
        self.count = 0

    @property
    def use_fallback(self) -> bool:
        return self.count >= GEMINI_FALLBACK_THRESHOLD


_gemini_tracker = _GeminiFailureTracker()

# ── Data types ─────────────────────────────────────────────────────────────

@dataclass
class ToolCallRequest:
    call_id: str
    name: str
    args: dict[str, Any]


@dataclass
class AgentMessage:
    """Neutral message format for conversation history across providers."""
    role: str  # "user" | "model" | "tool_result"
    content: str | None = None
    tool_call: ToolCallRequest | None = None
    tool_result_name: str | None = None
    tool_result_call_id: str | None = None


@dataclass
class AgentTurn:
    text: str | None = None
    tool_call: ToolCallRequest | None = None

    @property
    def is_tool_call(self) -> bool:
        return self.tool_call is not None


# ── Tool schemas (provider-neutral JSON Schema) ────────────────────────────

AGENT_TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "rag_search",
        "description": (
            "Search the civic knowledge base to answer a resident's question. "
            "Use this when the resident asks about policies, services, schedules, "
            "or information that may be in the knowledge base."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query in the resident's language.",
                }
            },
            "required": ["query"],
        },
    },
    {
        "name": "capture_request",
        "description": (
            "Capture a civic service request from a resident. "
            "Use for reports, complaints, or service requests. "
            "Do NOT include tenant_id in arguments — it is set automatically from the token."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "intent": {
                    "type": "string",
                    "description": "One of: report, question, human",
                },
                "description": {
                    "type": "string",
                    "description": "Clear description of the issue or request.",
                },
                "name": {"type": "string", "description": "Resident name (optional)."},
                "contact": {"type": "string", "description": "Phone or email (optional)."},
                "location": {"type": "string", "description": "Location of issue (optional)."},
            },
            "required": ["intent", "description"],
        },
    },
    {
        "name": "escalate",
        "description": (
            "Escalate to a human staff member. "
            "Use when the resident explicitly asks to speak with a person, "
            "or the issue is complex and requires human judgment."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {"type": "string", "description": "Reason for escalation."},
                "capture_request_id": {
                    "type": "string",
                    "description": "UUID of an existing capture request to link (optional).",
                },
            },
            "required": ["reason"],
        },
    },
]


# ── Gemini adapter ─────────────────────────────────────────────────────────

def _build_gemini_tools(schemas: list[dict]) -> list:
    import google.generativeai as genai
    declarations = [
        genai.types.FunctionDeclaration(
            name=s["name"],
            description=s["description"],
            parameters=s["parameters"],
        )
        for s in schemas
    ]
    return [genai.types.Tool(function_declarations=declarations)]


def _to_gemini_contents(history: list[AgentMessage], user_message: str | None) -> list:
    """Convert neutral history + optional new user message to Gemini contents list."""
    import google.generativeai.protos as protos

    contents = []
    for msg in history:
        if msg.role == "user":
            contents.append(
                protos.Content(role="user", parts=[protos.Part(text=msg.content or "")])
            )
        elif msg.role == "model":
            if msg.tool_call:
                contents.append(
                    protos.Content(
                        role="model",
                        parts=[
                            protos.Part(
                                function_call=protos.FunctionCall(
                                    name=msg.tool_call.name,
                                    args=msg.tool_call.args,
                                )
                            )
                        ],
                    )
                )
            else:
                contents.append(
                    protos.Content(role="model", parts=[protos.Part(text=msg.content or "")])
                )
        elif msg.role == "tool_result":
            # Function responses are "user" role in Gemini
            contents.append(
                protos.Content(
                    role="user",
                    parts=[
                        protos.Part(
                            function_response=protos.FunctionResponse(
                                name=msg.tool_result_name or "tool",
                                response={"result": msg.content or ""},
                            )
                        )
                    ],
                )
            )

    if user_message is not None:
        contents.append(
            protos.Content(role="user", parts=[protos.Part(text=user_message)])
        )

    return contents


def _call_gemini_sync(
    system_prompt: str,
    history: list[AgentMessage],
    user_message: str | None,
    tool_schemas: list[dict],
) -> AgentTurn:
    """Synchronous Gemini call (runs in thread pool)."""
    import google.generativeai as genai

    settings = get_settings()
    genai.configure(api_key=settings.gemini_api_key)

    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        system_instruction=system_prompt,
        tools=_build_gemini_tools(tool_schemas),
    )

    contents = _to_gemini_contents(history, user_message)
    response = model.generate_content(
        contents=contents,
        generation_config={"max_output_tokens": get_settings().max_tokens_per_turn},
    )

    # Parse function call if present
    try:
        for part in response.parts:
            if hasattr(part, "function_call") and part.function_call.name:
                fc = part.function_call
                return AgentTurn(
                    tool_call=ToolCallRequest(
                        call_id=str(uuid.uuid4()),
                        name=fc.name,
                        args=dict(fc.args),
                    )
                )
    except (AttributeError, ValueError):
        pass

    return AgentTurn(text=response.text or "")


async def _complete_gemini(
    system_prompt: str,
    history: list[AgentMessage],
    user_message: str | None,
    tool_schemas: list[dict],
) -> AgentTurn:
    return await asyncio.to_thread(
        _call_gemini_sync, system_prompt, history, user_message, tool_schemas
    )


# ── Groq fallback ──────────────────────────────────────────────────────────

def _to_groq_messages(
    system_prompt: str,
    history: list[AgentMessage],
    user_message: str | None,
) -> list[dict]:
    msgs: list[dict] = [{"role": "system", "content": system_prompt}]
    for msg in history:
        if msg.role == "user":
            msgs.append({"role": "user", "content": msg.content or ""})
        elif msg.role == "model":
            if msg.tool_call:
                msgs.append(
                    {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": msg.tool_call.call_id,
                                "type": "function",
                                "function": {
                                    "name": msg.tool_call.name,
                                    "arguments": json.dumps(msg.tool_call.args),
                                },
                            }
                        ],
                    }
                )
            else:
                msgs.append({"role": "assistant", "content": msg.content or ""})
        elif msg.role == "tool_result":
            msgs.append(
                {
                    "role": "tool",
                    "tool_call_id": msg.tool_result_call_id or "unknown",
                    "content": msg.content or "",
                }
            )
    if user_message is not None:
        msgs.append({"role": "user", "content": user_message})
    return msgs


def _build_groq_tools(schemas: list[dict]) -> list[dict]:
    return [
        {"type": "function", "function": {
            "name": s["name"],
            "description": s["description"],
            "parameters": s["parameters"],
        }}
        for s in schemas
    ]


def _truncate_history(history: list[AgentMessage], max_turns: int = 6) -> list[AgentMessage]:
    """Keep only the last max_turns user/model pairs to stay within token limits."""
    if len(history) <= max_turns * 2:
        return history
    return history[-(max_turns * 2):]


async def _complete_groq(
    system_prompt: str,
    history: list[AgentMessage],
    user_message: str | None,
    tool_schemas: list[dict],
) -> AgentTurn:
    from groq import AsyncGroq

    settings = get_settings()
    client = AsyncGroq(api_key=settings.groq_api_key)

    messages = _to_groq_messages(system_prompt, _truncate_history(history), user_message)
    tools = _build_groq_tools(tool_schemas)

    try:
        response = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            tools=tools,
            tool_choice="auto",
            parallel_tool_calls=False,  # prevents llama from generating Hermes-style <function=...> syntax
            temperature=0,
            max_tokens=min(settings.max_tokens_per_turn, 1024),
        )
    except Exception as exc:
        # Groq SDK raises groq.APIStatusError (not httpx.HTTPStatusError), so check generically.
        status = getattr(exc, "status_code", None)
        if status in (400, 413):
            # 400: llama generated malformed tool syntax (Hermes format).
            # 413: history too large — retry with aggressively trimmed history and no tools.
            logger.warning("llm_client.groq_retrying_plain", status=status, error=str(exc)[:200])
            trimmed = _to_groq_messages(system_prompt, _truncate_history(history, max_turns=2), user_message)
            response = await client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=trimmed,
                temperature=0,
                max_tokens=min(settings.max_tokens_per_turn, 1024),
            )
        else:
            raise

    choice = response.choices[0]
    if choice.finish_reason == "tool_calls" and choice.message.tool_calls:
        tc = choice.message.tool_calls[0]
        return AgentTurn(
            tool_call=ToolCallRequest(
                call_id=tc.id,
                name=tc.function.name,
                args=json.loads(tc.function.arguments),
            )
        )
    return AgentTurn(text=choice.message.content or "")


# ── Public interface ───────────────────────────────────────────────────────

@retry(
    retry=retry_if_exception_type(Exception),
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=0.2, min=0.2, max=2.0),
    reraise=True,
)
async def _try_gemini(
    system_prompt: str,
    history: list[AgentMessage],
    user_message: str | None,
    tool_schemas: list[dict],
) -> AgentTurn:
    return await _complete_gemini(system_prompt, history, user_message, tool_schemas)


async def complete(
    system_prompt: str,
    history: list[AgentMessage],
    user_message: str | None,
    tool_schemas: list[dict] | None = None,
) -> AgentTurn:
    """Complete one agent turn.

    user_message: the new user message, or None after a tool call (continue from tool result).
    Tries Gemini first; falls back to Groq after GEMINI_FALLBACK_THRESHOLD consecutive failures.
    """
    schemas = tool_schemas if tool_schemas is not None else AGENT_TOOL_SCHEMAS

    if not _gemini_tracker.use_fallback:
        try:
            result = await _try_gemini(system_prompt, history, user_message, schemas)
            _gemini_tracker.reset()
            return result
        except Exception as exc:
            _gemini_tracker.record()
            logger.warning(
                "llm_client.gemini_failed",
                failure_count=_gemini_tracker.count,
                threshold=GEMINI_FALLBACK_THRESHOLD,
                error=str(exc),
            )

    logger.info("llm_client.groq_fallback", failure_count=_gemini_tracker.count)
    try:
        result = await _complete_groq(system_prompt, history, user_message, schemas)
        _gemini_tracker.reset()
        return result
    except Exception as groq_exc:
        # Groq failed (e.g. malformed tool call → 400). Reset the tracker so the
        # next request retries Gemini rather than staying on a broken Groq path.
        logger.warning("llm_client.groq_failed", error=str(groq_exc))
        _gemini_tracker.reset()
        return await _try_gemini(system_prompt, history, user_message, schemas)


# ── Plain-text completion (no tools) ───────────────────────────────────────
# Used by RAG generation and the eval LLM-judge — a single prompt → text, with
# the same Gemini→Groq fallback as complete(). Kept separate from complete() so
# the tool-calling machinery (which errors on empty tool lists) is not involved.

def _call_gemini_text_sync(system_prompt: str, user_message: str, max_tokens: int) -> str:
    import google.generativeai as genai

    settings = get_settings()
    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash", system_instruction=system_prompt
    )
    response = model.generate_content(
        user_message,
        generation_config={"max_output_tokens": max_tokens, "temperature": 0.0},
    )
    return response.text or ""


async def _complete_groq_text(system_prompt: str, user_message: str, max_tokens: int) -> str:
    from groq import AsyncGroq

    settings = get_settings()
    client = AsyncGroq(api_key=settings.groq_api_key)
    response = await client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=0.0,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content or ""


async def complete_text(system_prompt: str, user_message: str, max_tokens: int = 800) -> str:
    """One prompt → text. Gemini primary, Groq fallback (mirrors complete())."""
    if not _gemini_tracker.use_fallback:
        try:
            result = await asyncio.to_thread(
                _call_gemini_text_sync, system_prompt, user_message, max_tokens
            )
            _gemini_tracker.reset()
            return result
        except Exception as exc:
            _gemini_tracker.record()
            logger.warning(
                "llm_client.gemini_text_failed",
                failure_count=_gemini_tracker.count,
                error=str(exc),
            )

    try:
        result = await _complete_groq_text(system_prompt, user_message, max_tokens)
        _gemini_tracker.reset()
        return result
    except Exception as groq_exc:
        logger.warning("llm_client.groq_text_failed", error=str(groq_exc))
        _gemini_tracker.reset()
        return await asyncio.to_thread(
            _call_gemini_text_sync, system_prompt, user_message, max_tokens
        )
