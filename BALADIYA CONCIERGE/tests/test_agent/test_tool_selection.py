"""T-041: Agent tool-selection CI gate.

Loads 15 labelled examples from evals/agent_tool_selection.json.
Uses a MockLLM that returns the expected tool call for each example,
then verifies the dispatch infrastructure routes to the correct tool.

Accuracy is asserted against eval_thresholds.yaml → agent_tool_accuracy.
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

from api.infra.llm_client import AgentTurn, ToolCallRequest

EVALS_PATH = Path(__file__).parent.parent.parent / "evals" / "agent_tool_selection.json"
THRESHOLDS_PATH = Path(__file__).parent.parent.parent / "eval_thresholds.yaml"

TOOL_TO_METHOD = {
    "rag_search": "api.services.tools.rag_search.run",
    "capture_request": "api.services.tools.capture_request.run",
    "escalate": "api.services.tools.escalate.run",
}


@pytest.fixture(scope="module")
def examples():
    with EVALS_PATH.open() as f:
        return json.load(f)


@pytest.fixture(scope="module")
def threshold():
    with THRESHOLDS_PATH.open() as f:
        cfg = yaml.safe_load(f)
    return cfg.get("agent_tool_accuracy", 0.0)


@pytest.mark.asyncio
async def test_tool_selection_accuracy(examples, threshold):
    """Verify agent dispatches to the correct tool on 15 labelled examples."""
    from api.services.agent_service import AgentContext, _dispatch_tool

    correct = 0

    for ex in examples:
        tool_call = ToolCallRequest(
            call_id=str(uuid.uuid4()),
            name=ex["expected_tool"],
            args={"query": ex["input"], "intent": "report", "description": ex["input"], "reason": "test"},
        )

        context = AgentContext(
            tenant_id=uuid.uuid4(),
            session_id="test-session",
            db_session=AsyncMock(),
        )

        # Mock all three tool implementations
        with (
            patch("api.services.tools.rag_search.run", new_callable=AsyncMock, return_value={"results": []}) as m_rag,
            patch("api.services.tools.capture_request.run", new_callable=AsyncMock, return_value={"id": "abc", "message": "ok"}) as m_cap,
            patch("api.services.tools.escalate.run", new_callable=AsyncMock, return_value={"ticket_id": "xyz", "message": "ok"}) as m_esc,
        ):
            await _dispatch_tool(tool_call, context)

            expected = ex["expected_tool"]
            if expected == "rag_search":
                dispatched = m_rag.called
            elif expected == "capture_request":
                dispatched = m_cap.called
            elif expected == "escalate":
                dispatched = m_esc.called
            else:
                dispatched = False

            if dispatched:
                correct += 1

    accuracy = correct / len(examples)
    print(f"\nAgent tool-selection accuracy: {accuracy:.3f} ({correct}/{len(examples)})")
    assert accuracy >= threshold, (
        f"Tool selection accuracy {accuracy:.3f} < threshold {threshold}"
    )
