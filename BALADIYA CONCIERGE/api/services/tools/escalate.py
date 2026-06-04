"""Agent tool: escalate — creates an EscalationTicket scoped to the current tenant."""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from api.services.agent_service import AgentContext

from api.repositories.escalation_repo import EscalationTicketRepository

logger = structlog.get_logger(__name__)


async def run(args: dict[str, Any], context: AgentContext) -> dict[str, Any]:
    """Create an escalation ticket.

    Links to a capture_request_id if provided and valid UUID.
    tenant_id always from context — never from args.
    Returns {ticket_id, message} or {error}.
    """
    reason = args.get("reason", "").strip()
    if not reason:
        return {"error": "reason cannot be empty"}

    capture_request_id: uuid.UUID | None = None
    raw_cr_id = args.get("capture_request_id")
    if raw_cr_id:
        try:
            capture_request_id = uuid.UUID(str(raw_cr_id))
        except (ValueError, AttributeError):
            pass  # malformed ID — proceed without linking

    try:
        repo = EscalationTicketRepository(context.db_session, context.tenant_id)
        ticket = await repo.create(reason=reason, capture_request_id=capture_request_id)
        await context.db_session.commit()
    except Exception as exc:
        logger.error(
            "tool.escalate.db_failed",
            tenant_id=str(context.tenant_id),
            error=str(exc),
        )
        return {"error": f"Failed to create escalation ticket: {exc}"}

    logger.info(
        "tool.escalate.ok",
        ticket_id=str(ticket.id),
        tenant_id=str(context.tenant_id),
        reason=reason[:80],
        capture_request_id=str(capture_request_id) if capture_request_id else None,
    )
    return {
        "ticket_id": str(ticket.id),
        "message": "A staff member will contact you shortly. Ticket reference: " + str(ticket.id)[:8].upper(),
    }
