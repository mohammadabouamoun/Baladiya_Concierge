"""Streamlit CMS page — Tenant Admin content management.

Allows Tenant Admins to create, edit, and delete CMS entries.
Displays embedding status badge (pending / done / failed).
Talks to the API via httpx (not direct DB access).
"""
from __future__ import annotations

import os

import httpx
import streamlit as st

import sys, os as _os
sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "../.."))
from chatbot._style import inject as _inject_css, login_hero

API_BASE = os.environ.get("API_BASE_URL", "http://localhost:8000")
# Local design-preview only. Never set in docker-compose, so the bypass cannot exist in deployment.
PREVIEW_ENABLED = os.environ.get("CHATBOT_PREVIEW") == "1"

st.set_page_config(page_title="CMS — Baladiya Concierge", layout="wide")
_inject_css()


def _auth_headers() -> dict:
    token = st.session_state.get("token", "")
    return {"Authorization": f"Bearer {token}"}


def _status_badge(status: str) -> str:
    colors = {"done": "🟢", "pending": "🟡", "failed": "🔴"}
    return f"{colors.get(status, '⚪')} {status}"


# ── Login ──────────────────────────────────────────────────────────────────

if "token" not in st.session_state:
    _, mid, _ = st.columns([1, 1.4, 1])
    with mid:
        login_hero("Tenant Admin", "Sign in to manage your municipality's assistant")
        with st.form("login"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign in", use_container_width=True, type="primary")
        if PREVIEW_ENABLED:
            if st.button("Preview the design (no API)", use_container_width=True):
                st.session_state["token"] = "preview"
                st.rerun()
            st.caption("Preview mode loads sample data so you can explore the UI without the backend.")
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


# ── Sidebar ────────────────────────────────────────────────────────────────

st.sidebar.title("CMS")
if st.sidebar.button("Sign out"):
    del st.session_state["token"]
    st.rerun()

# ── Load entries ───────────────────────────────────────────────────────────

_PREVIEW_ENTRIES = [
    {"id": "p1", "title": "Pothole reporting on main roads", "body": "Residents can report potholes and road damage with a photo and location.",
     "category": "roads", "lang": "en", "embedding_status": "done"},
    {"id": "p2", "title": "مواعيد جمع النفايات", "body": "جدول جمع النفايات لكل حي في المدينة، محدّث أسبوعياً.",
     "category": "waste", "lang": "ar", "embedding_status": "done"},
    {"id": "p3", "title": "Building permit requirements", "body": "Documents and fees required to apply for a residential building permit.",
     "category": "permits", "lang": "en", "embedding_status": "pending"},
    {"id": "p4", "title": "انقطاع المياه المجدول", "body": "إشعارات بانقطاع المياه المخطط له لأعمال الصيانة.",
     "category": "water", "lang": "ar", "embedding_status": "failed"},
]


@st.cache_data(ttl=10, show_spinner=False)
def _load_entries(token: str) -> list[dict]:
    if token == "preview":
        return _PREVIEW_ENTRIES
    try:
        resp = httpx.get(
            f"{API_BASE}/cms/entries",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        st.error(f"Failed to load entries: {exc}")
        return []


token = st.session_state["token"]
entries = _load_entries(token)

# ── Create / Edit form ─────────────────────────────────────────────────────

st.title("Content Entries")

with st.expander("➕ New entry", expanded=False):
    with st.form("create_entry"):
        title = st.text_input("Title")
        body = st.text_area("Body", height=200)
        col1, col2 = st.columns(2)
        category = col1.selectbox(
            "Category",
            ["general", "roads", "water", "electricity", "waste", "permits", "taxes", "environment"],
        )
        lang = col2.selectbox("Language", ["en", "ar"])
        if st.form_submit_button("Save"):
            if not title or not body:
                st.warning("Title and body are required.")
            elif token == "preview":
                st.info("Preview mode — connect the API to save entries.")
            else:
                resp = httpx.post(
                    f"{API_BASE}/cms/entries",
                    headers=_auth_headers(),
                    json={"title": title, "body": body, "category": category, "lang": lang},
                    timeout=30,
                )
                if resp.status_code == 201:
                    st.success(f"Created. Embedding status: {resp.json()['embedding_status']}")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error(f"Error: {resp.json().get('detail', resp.status_code)}")

# ── Entry table ────────────────────────────────────────────────────────────

if not entries:
    st.info("No entries yet. Create one above.")
else:
    for entry in entries:
        with st.container(border=True):
            c1, c2, c3 = st.columns([4, 1, 1])
            c1.markdown(f"**{entry['title']}**  \n`{entry['category']}` · `{entry['lang']}`")
            c2.markdown(_status_badge(entry["embedding_status"]))

            with c3:
                if st.button("Edit", key=f"edit_{entry['id']}"):
                    st.session_state["editing"] = entry["id"]
                if st.button("Delete", key=f"del_{entry['id']}"):
                    st.session_state["deleting"] = entry["id"]

            # Inline edit form
            if st.session_state.get("editing") == entry["id"]:
                with st.form(f"edit_form_{entry['id']}"):
                    new_title = st.text_input("Title", value=entry["title"])
                    new_body = st.text_area("Body", value=entry["body"], height=150)
                    col1, col2 = st.columns(2)
                    new_cat = col1.selectbox(
                        "Category",
                        ["general", "roads", "water", "electricity", "waste", "permits", "taxes", "environment"],
                        index=["general", "roads", "water", "electricity", "waste", "permits", "taxes", "environment"].index(entry["category"]),
                    )
                    new_lang = col2.selectbox("Language", ["en", "ar"], index=["en", "ar"].index(entry["lang"]))
                    s1, s2 = st.columns(2)
                    if s1.form_submit_button("Save changes"):
                        if token == "preview":
                            st.info("Preview mode — connect the API to save changes.")
                            st.stop()
                        resp = httpx.put(
                            f"{API_BASE}/cms/entries/{entry['id']}",
                            headers=_auth_headers(),
                            json={"title": new_title, "body": new_body, "category": new_cat, "lang": new_lang},
                            timeout=30,
                        )
                        if resp.status_code == 200:
                            st.success("Updated.")
                            del st.session_state["editing"]
                            st.cache_data.clear()
                            st.rerun()
                        else:
                            st.error(f"Error: {resp.json().get('detail', resp.status_code)}")
                    if s2.form_submit_button("Cancel"):
                        del st.session_state["editing"]
                        st.rerun()

            # Delete confirmation
            if st.session_state.get("deleting") == entry["id"]:
                st.warning(f"Delete **{entry['title']}**? This also removes all vectors.")
                d1, d2 = st.columns(2)
                if d1.button("Confirm delete", key=f"confirm_del_{entry['id']}"):
                    if token == "preview":
                        st.info("Preview mode — connect the API to delete entries.")
                        st.stop()
                    resp = httpx.delete(
                        f"{API_BASE}/cms/entries/{entry['id']}",
                        headers=_auth_headers(),
                        timeout=10,
                    )
                    if resp.status_code == 204:
                        st.success("Deleted.")
                        del st.session_state["deleting"]
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error(f"Error: {resp.status_code}")
                if d2.button("Cancel delete", key=f"cancel_del_{entry['id']}"):
                    del st.session_state["deleting"]
                    st.rerun()
