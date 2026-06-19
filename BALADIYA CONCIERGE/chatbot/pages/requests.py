"""Streamlit admin page: Capture Requests — T-050.

Lists capture_requests for the authenticated Tenant Admin.
Requires a valid auth token (from the login form on the CMS page or sidebar).
"""
import os
import sys
from datetime import datetime

import httpx
import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from chatbot._style import inject as _inject_css

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")
# Local design-preview only. Never set in docker-compose, so the bypass cannot exist in deployment.
PREVIEW_ENABLED = os.environ.get("CHATBOT_PREVIEW") == "1"
# Local demo API (scripts/demo_api.py) — source of reports captured by the chat bubble.
DEMO_API = os.environ.get("DEMO_API_URL", "http://localhost:8787")


def _get_token() -> str | None:
    # cms.py logs in under "token"; older code used "auth_token" — accept either.
    return st.session_state.get("token") or st.session_state.get("auth_token")


def _fetch_demo_requests() -> list[dict]:
    """Preview mode: read reports the chat bubble captured into the demo API."""
    try:
        r = httpx.get(f"{DEMO_API}/demo/requests", timeout=5)
        if r.status_code == 200:
            return r.json().get("requests", [])
    except httpx.RequestError:
        st.info(
            "Demo API not running. Start it with `python3 scripts/demo_api.py` and "
            "file a report from the website chat bubble to see it here."
        )
    return []


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


def _flag_false_report(token: str, request_id: str) -> dict | None:
    try:
        r = httpx.post(
            f"{API_BASE}/admin/requests/{request_id}/flag-false",
            headers=_auth_header(token),
            timeout=10,
        )
        if r.status_code == 200:
            return r.json()
        st.error(f"Flag failed: {r.status_code} {r.text}")
    except httpx.RequestError as exc:
        st.error(f"Could not reach API: {exc}")
    return None


def main():
    st.set_page_config(page_title="Capture Requests", layout="wide")
    _inject_css()
    st.title("Capture Requests")

    token = _get_token()
    preview = token == "preview" or (PREVIEW_ENABLED and not token)
    if not token and not preview:
        st.warning("Please log in via the CMS page first.")
        st.stop()

    if preview:
        st.caption("Preview — reports captured by the website chat bubble (local demo API).")
        records = _fetch_demo_requests()
    else:
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

        is_false = rec.get("is_false_report", False)
        false_label = " 🚩 FALSE" if is_false else ""
        with st.expander(
            f"{status_icon} [{rec.get('intent', '—').upper()}]{false_label}  {rec.get('description', '')[:80]}…  ·  {created}"
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
                has_phone = bool(rec.get("visitor_phone_hash"))
                st.write(f"**Phone verified**: {'Yes' if has_phone else 'No'}")
            st.write(f"**Description**: {rec.get('description', '—')}")

            if not is_false and rec.get("intent") == "report":
                btn_key = f"flag_{rec.get('id', '')}"
                if st.button("🚩 Flag as False Report", key=btn_key, type="secondary"):
                    if preview:
                        st.info("Preview mode — flagging is disabled (no backend write).")
                        st.stop()
                    result = _flag_false_report(token, rec["id"])
                    if result:
                        blocked_msg = " Reporter is now **blocked** from filing further reports." if result.get("blocked") else ""
                        st.success(f"Marked as false report.{blocked_msg}")
                        st.rerun()
            elif is_false:
                st.warning("This report has been confirmed as false.")


main()
