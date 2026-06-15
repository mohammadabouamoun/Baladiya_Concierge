"""Platform Manager Streamlit app — main page: tenant list + actions."""
from __future__ import annotations

import os

import httpx
import streamlit as st

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from platform_manager._style import inject as _inject_css, login_hero, status_pill

API_BASE = os.environ.get("API_BASE_URL", "http://localhost:8000")
# Local design-preview only. Never set in docker-compose, so the bypass cannot exist in deployment.
PREVIEW_ENABLED = os.environ.get("PLATFORM_PREVIEW") == "1"

st.set_page_config(page_title="Platform Manager — Baladiya", layout="wide")
_inject_css()


def _headers() -> dict:
    return {"Authorization": f"Bearer {st.session_state.get('token', '')}"}


# ── Login ──────────────────────────────────────────────────────────────────

if "token" not in st.session_state:
    _, mid, _ = st.columns([1, 1.4, 1])
    with mid:
        login_hero("Platform Manager", "Control plane — provision, suspend, and audit tenants")
        with st.form("login"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign in", use_container_width=True, type="primary")
        if PREVIEW_ENABLED:
            if st.button("Preview the design (no API)", use_container_width=True):
                st.session_state["token"] = "preview"
                st.rerun()
            st.caption("Preview mode loads sample tenants so you can explore the UI without the backend.")
    if submitted:
        try:
            resp = httpx.post(
                f"{API_BASE}/auth/token",
                json={"email": email, "password": password},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("role") != "platform_manager":
                    st.error("This portal is for Platform Managers only.")
                else:
                    st.session_state["token"] = data["access_token"]
                    st.rerun()
            else:
                st.error(f"Login failed: {resp.json().get('detail', resp.status_code)}")
        except httpx.RequestError as exc:
            st.error(f"Cannot reach API: {exc}")
    st.stop()


# ── Sidebar ────────────────────────────────────────────────────────────────

st.sidebar.title("Platform Manager")
if st.sidebar.button("Sign out"):
    del st.session_state["token"]
    st.rerun()


# ── Tenant List ────────────────────────────────────────────────────────────

st.title("Tenants")

token = st.session_state["token"]

_SAMPLE_TENANTS = [
    {"id": "11111111-1111-1111-1111-111111111111", "name": "Beirut Municipality", "status": "active", "plan": "enterprise", "created_at": "2025-09-12"},
    {"id": "22222222-2222-2222-2222-222222222222", "name": "Tripoli Municipality", "status": "active", "plan": "standard", "created_at": "2025-11-03"},
    {"id": "33333333-3333-3333-3333-333333333333", "name": "Sidon Municipality", "status": "suspended", "plan": "standard", "created_at": "2026-01-20"},
    {"id": "44444444-4444-4444-4444-444444444444", "name": "Zahle Municipality", "status": "erased", "plan": "trial", "created_at": "2026-02-15"},
]

if token == "preview":
    tenants: list[dict] = _SAMPLE_TENANTS
else:
    try:
        resp = httpx.get(f"{API_BASE}/platform/tenants", headers=_headers(), timeout=10)
        resp.raise_for_status()
        tenants = resp.json()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 401:
            del st.session_state["token"]
            st.rerun()
        st.error(f"Failed to load tenants: {exc}")
        st.stop()
    except httpx.RequestError as exc:
        st.error(f"Cannot reach API: {exc}")
        st.stop()

if not tenants:
    st.info("No tenants yet. Use Provision Tenant to create one.")
    st.stop()

# ── KPI summary ────────────────────────────────────────────────────────────
k1, k2, k3, k4 = st.columns(4)
k1.metric("Total tenants", len(tenants))
k2.metric("Active", sum(1 for t in tenants if t["status"] == "active"))
k3.metric("Suspended", sum(1 for t in tenants if t["status"] == "suspended"))
k4.metric("Erased", sum(1 for t in tenants if t["status"] == "erased"))
st.write("")

STATUS_ICON = {"active": "🟢", "suspended": "🟡", "erased": "🔴"}

for t in tenants:
    icon = STATUS_ICON.get(t["status"], "⚪")
    with st.expander(f"{icon}  {t['name']}  ·  {t['plan']}"):
        st.markdown(status_pill(t["status"]), unsafe_allow_html=True)
        st.write("")
        col1, col2 = st.columns(2)
        col1.markdown(f"**ID:** `{t['id']}`")
        col1.markdown(f"**Created:** {str(t['created_at'])[:10]}")
        col2.markdown(f"**Plan:** {t['plan']}")
        col2.markdown(f"**Status:** {t['status']}")

        if t["status"] == "active":
            if st.button("Suspend", key=f"suspend_{t['id']}"):
                if token == "preview":
                    st.info("Preview mode — connect the API to suspend tenants.")
                    st.stop()
                try:
                    r = httpx.post(
                        f"{API_BASE}/platform/tenants/{t['id']}/suspend",
                        headers=_headers(),
                        timeout=10,
                    )
                    r.raise_for_status()
                    st.success(f"Tenant {t['name']} suspended.")
                    st.rerun()
                except httpx.HTTPStatusError as exc:
                    st.error(f"Suspend failed: {exc.response.json().get('detail', exc)}")

        if t["status"] != "erased":
            st.warning("Erase is permanent and deletes all tenant data.")
            with st.form(f"erase_{t['id']}"):
                confirm = st.text_input("Type the tenant ID to confirm erase")
                if st.form_submit_button("Erase Tenant", type="primary"):
                    if confirm.strip() != str(t["id"]):
                        st.error("Tenant ID does not match.")
                    elif token == "preview":
                        st.info("Preview mode — connect the API to erase tenants.")
                    else:
                        try:
                            r = httpx.delete(
                                f"{API_BASE}/platform/tenants/{t['id']}",
                                params={"confirm_tenant_id": t["id"]},
                                headers=_headers(),
                                timeout=30,
                            )
                            r.raise_for_status()
                            st.success(f"Tenant {t['name']} erased.")
                            st.rerun()
                        except httpx.HTTPStatusError as exc:
                            st.error(f"Erase failed: {exc.response.json().get('detail', exc)}")
