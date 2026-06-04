"""Streamlit admin page: Escalation Tickets — T-051.

Lists escalation_tickets for the authenticated Tenant Admin.
"""
import os
from datetime import datetime

import httpx
import streamlit as st

API_BASE = os.getenv("API_URL", "http://localhost:8000")


def _get_token() -> str | None:
    return st.session_state.get("auth_token")


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _fetch_escalations(token: str) -> list[dict]:
    try:
        r = httpx.get(f"{API_BASE}/admin/escalation-tickets", headers=_auth_header(token), timeout=10)
        if r.status_code == 200:
            return r.json()
        elif r.status_code == 401:
            st.warning("Session expired. Please log in again.")
            st.session_state.pop("auth_token", None)
    except httpx.RequestError as exc:
        st.error(f"Could not reach API: {exc}")
    return []


def main():
    st.set_page_config(page_title="Escalation Tickets", page_icon="🚨", layout="wide")
    st.title("🚨 Escalation Tickets")

    token = _get_token()
    if not token:
        st.warning("Please log in via the CMS page first.")
        st.stop()

    with st.spinner("Loading escalation tickets…"):
        tickets = _fetch_escalations(token)

    if not tickets:
        st.info("No escalation tickets found.")
        return

    open_count = sum(1 for t in tickets if t.get("status") == "open")
    st.metric("Open Tickets", open_count, delta=f"{len(tickets)} total")

    # Status filter
    all_statuses = sorted({t.get("status", "open") for t in tickets})
    selected = st.multiselect("Filter by status", all_statuses, default=all_statuses)
    filtered = [t for t in tickets if t.get("status") in selected]

    for ticket in filtered:
        created = ticket.get("created_at", "")
        if created:
            try:
                created = datetime.fromisoformat(created).strftime("%Y-%m-%d %H:%M")
            except ValueError:
                pass

        status_icon = {"open": "🔴", "closed": "🟢"}.get(ticket.get("status", ""), "⚪")

        with st.expander(
            f"{status_icon} {ticket.get('reason', '')[:80]}  ·  {created}"
        ):
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Ticket ID**: `{ticket.get('id', '')}`")
                st.write(f"**Status**: {ticket.get('status', '—')}")
                st.write(f"**Created**: {created}")
            with col2:
                cr_id = ticket.get("capture_request_id")
                st.write(f"**Linked Request**: `{cr_id}`" if cr_id else "**Linked Request**: —")
            st.write(f"**Reason**: {ticket.get('reason', '—')}")


main()
