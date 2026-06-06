"""Streamlit Widget Management page — Tenant Admin.

Allows Tenant Admins to:
  - Create widgets with allowed_origins
  - Update allowed_origins and active status
  - Copy the one-line <script> embed snippet
"""
from __future__ import annotations

import os

import httpx
import streamlit as st

API_BASE = os.environ.get("API_BASE_URL", "http://api:8000")

st.set_page_config(page_title="Widget — Baladiya Concierge", layout="wide")


def _auth_headers() -> dict:
    return {"Authorization": f"Bearer {st.session_state.get('token', '')}"}


# ── Login ──────────────────────────────────────────────────────────────────

if "token" not in st.session_state:
    st.title("Baladiya Concierge — Widget Management")
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


# ── Load widgets ───────────────────────────────────────────────────────────

st.title("Widget Management")
st.caption("Create embeddable chat widgets for your municipality site.")

try:
    resp = httpx.get(f"{API_BASE}/widget/widgets", headers=_auth_headers(), timeout=10)
    resp.raise_for_status()
    widgets: list[dict] = resp.json()
except httpx.HTTPStatusError as exc:
    if exc.response.status_code == 401:
        del st.session_state["token"]
        st.rerun()
    st.error(f"Failed to load widgets: {exc}")
    st.stop()
except httpx.RequestError as exc:
    st.error(f"Cannot reach API: {exc}")
    st.stop()


# ── Existing widgets ───────────────────────────────────────────────────────

if widgets:
    st.subheader("Your Widgets")
    for w in widgets:
        with st.expander(f"Widget `{w['id']}` — {'Active' if w['is_active'] else 'Inactive'}"):
            st.markdown("**Embed snippet** — paste this into your municipality website:")
            snippet = f'<script src="{API_BASE}/widget.js" data-widget-id="{w["id"]}"></script>'
            st.code(snippet, language="html")
            st.markdown("**Allowed origins:**")
            st.code("\n".join(w.get("allowed_origins", [])))

            with st.form(f"update_{w['id']}"):
                new_origins = st.text_area(
                    "Allowed Origins (one per line)",
                    value="\n".join(w.get("allowed_origins", [])),
                )
                active = st.checkbox("Active", value=w["is_active"])
                if st.form_submit_button("Save"):
                    origins_list = [o.strip() for o in new_origins.splitlines() if o.strip()]
                    try:
                        patch_resp = httpx.patch(
                            f"{API_BASE}/widget/widgets/{w['id']}",
                            json={"allowed_origins": origins_list, "is_active": active},
                            headers=_auth_headers(),
                            timeout=10,
                        )
                        patch_resp.raise_for_status()
                        st.success("Widget updated.")
                        st.rerun()
                    except httpx.HTTPStatusError as exc:
                        st.error(f"Update failed: {exc.response.json().get('detail', exc)}")
else:
    st.info("No widgets yet. Create one below.")


# ── Create widget ──────────────────────────────────────────────────────────

st.subheader("Create New Widget")
with st.form("create_widget"):
    origins_raw = st.text_area(
        "Allowed Origins (one per line)",
        placeholder="https://municipality.gov\nhttps://www.municipality.gov",
        help="The widget token exchange will reject requests from any origin not in this list.",
    )
    if st.form_submit_button("Create Widget"):
        origins_list = [o.strip() for o in origins_raw.splitlines() if o.strip()]
        if not origins_list:
            st.error("At least one allowed origin is required.")
        else:
            try:
                create_resp = httpx.post(
                    f"{API_BASE}/widget/widgets",
                    json={"allowed_origins": origins_list},
                    headers=_auth_headers(),
                    timeout=10,
                )
                create_resp.raise_for_status()
                new_widget = create_resp.json()
                st.success(f"Widget created! ID: `{new_widget['id']}`")
                st.code(
                    f'<script src="{API_BASE}/widget.js" data-widget-id="{new_widget["id"]}"></script>',
                    language="html",
                )
                st.rerun()
            except httpx.HTTPStatusError as exc:
                st.error(f"Create failed: {exc.response.json().get('detail', exc)}")
