"""Streamlit Guardrails config page — Tenant Admin.

Allows Tenant Admins to configure their tenant rail overlay:
  - blocked topics
  - refusal tone / custom refusal message
  - enabled agent tools

Platform rails (injection, jailbreak, cross-tenant, PII) are NOT shown
here — they cannot be viewed or modified by tenants.
"""
from __future__ import annotations

import os

import httpx
import streamlit as st

API_BASE = os.environ.get("API_BASE_URL", "http://api:8000")

st.set_page_config(page_title="Guardrails — Baladiya Concierge", layout="wide")


def _auth_headers() -> dict:
    token = st.session_state.get("token", "")
    return {"Authorization": f"Bearer {token}"}


# ── Login ──────────────────────────────────────────────────────────────────

if "token" not in st.session_state:
    st.title("Baladiya Concierge — Guardrail Settings")
    st.subheader("Sign in")
    with st.form("login"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in")
    if submitted:
        try:
            resp = httpx.post(
                f"{API_BASE}/auth/token",
                json={"email": email, "password": password},
                timeout=10,
            )
            if resp.status_code == 200:
                st.session_state["token"] = resp.json()["access_token"]
                st.rerun()
            else:
                st.error(f"Login failed: {resp.json().get('detail', resp.status_code)}")
        except httpx.RequestError as exc:
            st.error(f"Cannot reach API: {exc}")
    st.stop()


# ── Load current settings ──────────────────────────────────────────────────

st.title("Guardrail Settings")
st.caption("Configure your tenant's content rails. Platform safety rails (injection, jailbreak, cross-tenant) are mandatory and cannot be modified here.")

try:
    resp = httpx.get(f"{API_BASE}/admin/settings", headers=_auth_headers(), timeout=10)
    resp.raise_for_status()
    tenant_settings: dict = resp.json()
except httpx.HTTPStatusError as exc:
    if exc.response.status_code == 401:
        del st.session_state["token"]
        st.rerun()
    st.error(f"Failed to load settings: {exc}")
    st.stop()
except httpx.RequestError as exc:
    st.error(f"Cannot reach API: {exc}")
    st.stop()

guardrail_config: dict = tenant_settings.get("guardrail_config") or {}

# ── Edit form ──────────────────────────────────────────────────────────────

with st.form("guardrail_form"):
    st.subheader("Blocked Topics")
    st.caption("Messages mentioning these topics will be refused. One topic per line.")
    raw_topics = "\n".join(guardrail_config.get("blocked_topics", []))
    blocked_topics_text = st.text_area("Blocked topics", value=raw_topics, height=120)

    st.subheader("Refusal Message")
    st.caption("Shown to residents when a blocked topic is triggered. Leave blank to use the default.")
    custom_msg = st.text_input(
        "Custom refusal message",
        value=guardrail_config.get("custom_refusal_message", ""),
        placeholder="e.g. We cannot assist with that topic. Please contact us directly.",
    )

    st.subheader("Enabled Agent Tools")
    all_tools = ["rag_search", "capture_request", "escalate"]
    enabled_tools = guardrail_config.get("allowed_tools", all_tools)
    selected_tools = st.multiselect(
        "Allowed tools",
        options=all_tools,
        default=[t for t in enabled_tools if t in all_tools],
    )

    save = st.form_submit_button("Save guardrail settings")

if save:
    new_config = {
        "blocked_topics": [t.strip() for t in blocked_topics_text.splitlines() if t.strip()],
        "allowed_tools": selected_tools,
        "custom_refusal_message": custom_msg.strip() or None,
    }
    try:
        resp = httpx.patch(
            f"{API_BASE}/admin/settings",
            json={"guardrail_config": new_config},
            headers=_auth_headers(),
            timeout=10,
        )
        resp.raise_for_status()
        st.success("Guardrail settings saved.")
    except httpx.HTTPStatusError as exc:
        st.error(f"Save failed: {exc.response.json().get('detail', exc)}")
    except httpx.RequestError as exc:
        st.error(f"Cannot reach API: {exc}")
