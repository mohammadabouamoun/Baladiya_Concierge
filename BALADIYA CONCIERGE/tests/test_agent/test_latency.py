"""T-052: SC-004 latency gate — agent loop < 5s p95 for single-tool turns.

Mocks the LLM and tools so the test measures pure infrastructure overhead
(session load/save, dispatch routing, JSON serialisation) without live API calls.
A real p95 measurement with a live LLM is done in evals/evaluate_agent.py.
"""
from __future__ import annotations

import asyncio
import time
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.infra.llm_client import AgentMessage, AgentTurn, ToolCallRequest
from api.services.agent_service import AgentContext, run as agent_run
from api.services.session_service import SessionService

_MOCK_SETTINGS = MagicMock(max_tool_calls=3, max_tokens_per_turn=4096)


def _make_mock_session_svc(turns: list | None = None) -> MagicMock:
    """Build a mock SessionService that returns empty memory and records saves."""
    from api.domain.session import SessionMemory

    svc = MagicMock(spec=SessionService)
    svc.load = AsyncMock(return_value=SessionMemory(turns=turns or []))
    svc.add_turns = AsyncMock()
    return svc


@pytest.mark.asyncio
async def test_single_tool_turn_under_budget():
    """Agent loop with one tool call completes well under the 5s p95 budget."""
    context = AgentContext(
        tenant_id=uuid.uuid4(),
        session_id="latency-test-session",
        db_session=AsyncMock(),
    )
    context.db_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))

    mock_svc = _make_mock_session_svc()

    # First LLM call returns a tool call; second returns text — one-tool turn
    rag_tool_call = ToolCallRequest(call_id=str(uuid.uuid4()), name="rag_search", args={"query": "test"})
    llm_responses = [
        AgentTurn(tool_call=rag_tool_call),
        AgentTurn(text="Here is the information you requested."),
    ]
    call_idx = [0]

    async def mock_complete(*args, **kwargs):
        resp = llm_responses[min(call_idx[0], len(llm_responses) - 1)]
        call_idx[0] += 1
        return resp

    with (
        patch("api.services.agent_service.get_settings", return_value=_MOCK_SETTINGS),
        patch("api.infra.llm_client.complete", side_effect=mock_complete),
        patch("api.services.tools.rag_search.run", new_callable=AsyncMock,
              return_value={"results": [{"chunk": "...", "source": "test", "category": "general", "similarity": 0.9}]}),
    ):
        start = time.perf_counter()
        result = await agent_run("What are the garbage collection days?", context, session_svc=mock_svc)
        elapsed = time.perf_counter() - start

    assert result, "Agent must return a non-empty response"
    # Infrastructure overhead must be well under the 5s budget (should be < 100ms with mocks)
    assert elapsed < 5.0, f"Agent loop took {elapsed:.3f}s — exceeds 5s p95 budget"


@pytest.mark.asyncio
async def test_no_tool_turn_under_budget():
    """Direct text response (no tool call) completes well under budget."""
    context = AgentContext(
        tenant_id=uuid.uuid4(),
        session_id="latency-no-tool",
        db_session=AsyncMock(),
    )
    context.db_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))

    mock_svc = _make_mock_session_svc()

    async def mock_complete(*args, **kwargs):
        return AgentTurn(text="Thank you for your message.")

    with (
        patch("api.services.agent_service.get_settings", return_value=_MOCK_SETTINGS),
        patch("api.infra.llm_client.complete", side_effect=mock_complete),
    ):
        start = time.perf_counter()
        result = await agent_run("Hello!", context, session_svc=mock_svc)
        elapsed = time.perf_counter() - start

    assert result
    assert elapsed < 5.0, f"Agent loop took {elapsed:.3f}s"
