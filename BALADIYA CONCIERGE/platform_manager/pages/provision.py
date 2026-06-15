"""Provision a new tenant."""
from __future__ import annotations

import os

import httpx
import streamlit as st

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from platform_manager._style import inject as _inject_css

API_BASE = os.environ.get("API_BASE_URL", "http://localhost:8000")

st.set_page_config(page_title="Provision Tenant — Baladiya", layout="wide")
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

st.title("Provision New Tenant")
st.caption("Creates an isolated tenant with a dedicated admin account.")

with st.form("provision"):
    name = st.text_input("Municipality Name", placeholder="City of Tripoli")
    admin_email = st.text_input("Admin Email", placeholder="admin@tripoli.gov.lb")
    admin_password = st.text_input("Admin Password", type="password")
    plan = st.selectbox("Plan", ["standard", "premium"])
    submitted = st.form_submit_button("Provision", type="primary")

if submitted:
    if not name or not admin_email or not admin_password:
        st.error("All fields are required.")
    elif st.session_state["token"] == "preview":
        st.info("Preview mode — connect the API to provision a real tenant.")
    else:
        try:
            resp = httpx.post(
                f"{API_BASE}/platform/tenants",
                json={
                    "name": name,
                    "admin_email": admin_email,
                    "admin_password": admin_password,
                    "plan": plan,
                },
                headers=_headers(),
                timeout=15,
            )
            if resp.status_code == 201:
                t = resp.json()
                st.success(f"Tenant **{t['name']}** provisioned successfully!")
                st.markdown(f"**Tenant ID:** `{t['id']}`")
                st.markdown(f"**Status:** {t['status']} | **Plan:** {t['plan']}")
                st.markdown(f"Admin can now log in at port 8501 with `{admin_email}`.")
            else:
                st.error(f"Provisioning failed: {resp.json().get('detail', resp.status_code)}")
        except httpx.RequestError as exc:
            st.error(f"Cannot reach API: {exc}")
