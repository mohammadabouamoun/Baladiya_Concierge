"""Audit log — all platform-level actions."""
from __future__ import annotations

import os

import httpx
import streamlit as st

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from platform_manager._style import inject as _inject_css

API_BASE = os.environ.get("API_BASE_URL", "http://localhost:8000")

st.set_page_config(page_title="Audit Log — Baladiya", layout="wide")
_inject_css()


def _headers() -> dict:
    return {"Authorization": f"Bearer {st.session_state.get('token', '')}"}


if "token" not in st.session_state:
    st.warning("Please sign in from the main page.")
    st.stop()

st.sidebar.title("Platform Manager")
if st.sidebar.button("Sign out"):
    del st.session_state["token"]
    st.rerun()

st.title("Audit Log")
st.caption("Every tenant-boundary-crossing action recorded with actor and timestamp.")

limit = st.slider("Show last N entries", 10, 500, 100, step=10)

_SAMPLE_LOGS = [
    {"action": "tenant.provisioned", "actor_id": "aa00aa00-0000-0000-0000-000000000000", "actor_role": "platform_manager",
     "tenant_id": "11111111-1111-1111-1111-111111111111", "created_at": "2026-06-12T09:14:03", "metadata": {"name": "Beirut Municipality", "plan": "enterprise"}},
    {"action": "tenant.suspended", "actor_id": "aa00aa00-0000-0000-0000-000000000000", "actor_role": "platform_manager",
     "tenant_id": "33333333-3333-3333-3333-333333333333", "created_at": "2026-06-10T16:42:51", "metadata": {"reason": "payment overdue"}},
    {"action": "tenant.erased", "actor_id": "aa00aa00-0000-0000-0000-000000000000", "actor_role": "platform_manager",
     "tenant_id": "44444444-4444-4444-4444-444444444444", "created_at": "2026-06-08T11:05:18", "metadata": {"confirmed": True, "vectors_removed": 1284}},
]

if st.session_state["token"] == "preview":
    logs: list[dict] = _SAMPLE_LOGS[:limit]
else:
    try:
        resp = httpx.get(
            f"{API_BASE}/platform/audit-logs",
            params={"limit": limit},
            headers=_headers(),
            timeout=10,
        )
        if resp.status_code == 401:
            del st.session_state["token"]
            st.rerun()
        resp.raise_for_status()
        logs = resp.json()
    except httpx.HTTPStatusError as exc:
        st.error(f"Failed to load audit logs: {exc}")
        st.stop()
    except httpx.RequestError as exc:
        st.error(f"Cannot reach API: {exc}")
        st.stop()

if not logs:
    st.info("No audit entries yet.")
    st.stop()

ACTION_ICON = {
    "tenant.provisioned": "🏗️",
    "tenant.suspended": "⏸️",
    "tenant.erased": "🗑️",
}

for entry in logs:
    icon = ACTION_ICON.get(entry["action"], "📋")
    ts = entry["created_at"][:19].replace("T", " ")
    tenant_label = f"`{entry['tenant_id'][:8]}…`" if entry["tenant_id"] else "—"
    with st.expander(f"{icon} **{entry['action']}** — {ts}"):
        col1, col2 = st.columns(2)
        col1.markdown(f"**Actor:** `{entry['actor_id'][:8]}…` ({entry['actor_role']})")
        col1.markdown(f"**Tenant:** {tenant_label}")
        col2.markdown(f"**Timestamp:** {ts}")
        if entry.get("metadata"):
            st.json(entry["metadata"])
