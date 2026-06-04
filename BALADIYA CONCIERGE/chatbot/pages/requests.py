"""Streamlit admin page: Capture Requests — T-050.

Lists capture_requests for the authenticated Tenant Admin.
Requires a valid auth token (from the login form on the CMS page or sidebar).
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


def _fetch_requests(token: str) -> list[dict]:
    try:
        r = httpx.get(f"{API_BASE}/admin/capture-requests", headers=_auth_header(token), timeout=10)
        if r.status_code == 200:
            return r.json()
        elif r.status_code == 401:
            st.warning("Session expired. Please log in again.")
            st.session_state.pop("auth_token", None)
    except httpx.RequestError as exc:
        st.error(f"Could not reach API: {exc}")
    return []


def main():
    st.set_page_config(page_title="Capture Requests", page_icon="📋", layout="wide")
    st.title("📋 Capture Requests")

    token = _get_token()
    if not token:
        st.warning("Please log in via the CMS page first.")
        st.stop()

    with st.spinner("Loading requests…"):
        records = _fetch_requests(token)

    if not records:
        st.info("No capture requests found.")
        return

    st.metric("Total Requests", len(records))

    # Status filter
    all_statuses = sorted({r.get("status", "open") for r in records})
    selected = st.multiselect("Filter by status", all_statuses, default=all_statuses)
    filtered = [r for r in records if r.get("status") in selected]

    for rec in filtered:
        created = rec.get("created_at", "")
        if created:
            try:
                created = datetime.fromisoformat(created).strftime("%Y-%m-%d %H:%M")
            except ValueError:
                pass

        status_icon = {"open": "🟡", "escalated": "🔴", "resolved": "🟢"}.get(rec.get("status", ""), "⚪")

        with st.expander(
            f"{status_icon} [{rec.get('intent', '—').upper()}] {rec.get('description', '')[:80]}…  ·  {created}"
        ):
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**ID**: `{rec.get('id', '')}`")
                st.write(f"**Status**: {rec.get('status', '—')}")
                st.write(f"**Intent**: {rec.get('intent', '—')}")
                st.write(f"**Session**: `{rec.get('session_id', '')[:16]}…`")
            with col2:
                st.write(f"**Name**: {rec.get('name') or '—'}")
                st.write(f"**Contact**: {rec.get('contact') or '—'}")
                st.write(f"**Location**: {rec.get('location') or '—'}")
            st.write(f"**Description**: {rec.get('description', '—')}")


main()
