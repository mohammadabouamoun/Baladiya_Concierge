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
    {"id": "p1", "title": "Building permit — requirements and fees",
     "body": ("To apply for a building permit you must submit stamped architectural plans, "
              "structural drawings, proof of land ownership, and the municipal application form. "
              "The processing fee for a commercial building permit is LBP 1,200,000; a residential "
              "permit is LBP 600,000. Standard processing takes 15 working days from the date all "
              "documents are received."),
     "category": "permits", "lang": "en", "embedding_status": "done"},
    {"id": "p2", "title": "Household waste collection schedule",
     "body": ("Household waste is collected three times a week — Monday, Wednesday, and Friday — "
              "before 7:00 AM in residential neighbourhoods, and daily in the central market area. "
              "Place bins at the curb the night before. Bulky items (furniture, appliances) are "
              "collected on the first Saturday of each month by prior request."),
     "category": "waste", "lang": "en", "embedding_status": "done"},
    {"id": "p3", "title": "مواعيد جمع النفايات المنزلية",
     "body": ("تُجمع النفايات المنزلية ثلاث مرات أسبوعياً — الإثنين والأربعاء والجمعة — قبل الساعة "
              "السابعة صباحاً في الأحياء السكنية، ويومياً في منطقة السوق المركزي. يُرجى إخراج الحاويات "
              "في الليلة السابقة. تُجمع الأغراض الكبيرة (أثاث، أجهزة) في أول سبت من كل شهر بطلب مسبق."),
     "category": "waste", "lang": "ar", "embedding_status": "done"},
    {"id": "p4", "title": "Municipality office hours and contact",
     "body": ("The municipality is open Monday to Friday, 8:00 AM to 3:00 PM, and Saturday 8:00 AM "
              "to 1:00 PM. The Urban Planning and Permits desk closes at 1:00 PM. You can reach the "
              "main switchboard at 01-123456 or email info@beirut.gov.lb. The offices are closed on "
              "official public holidays."),
     "category": "general", "lang": "en", "embedding_status": "done"},
    {"id": "p5", "title": "Annual property tax (rental value tax)",
     "body": ("The annual municipal property tax is based on the assessed rental value of the "
              "property. Bills are issued in January and payable by 31 March. A 10% early-payment "
              "discount applies before 1 March; late payment after 31 March incurs a 5% penalty. "
              "Pay at the municipal cashier or via bank transfer using your property reference number."),
     "category": "taxes", "lang": "en", "embedding_status": "done"},
    {"id": "p6", "title": "Reporting a water cut or pipe leak",
     "body": ("To report a water outage or a burst pipe, provide the exact street and the nearest "
              "landmark. Emergency leaks affecting the public road are prioritised and addressed "
              "within 24 hours. Scheduled maintenance cuts are announced at least 48 hours in advance "
              "on the municipality website and SMS list."),
     "category": "water", "lang": "en", "embedding_status": "done"},
    {"id": "p7", "title": "الإبلاغ عن انقطاع المياه أو تسرّب",
     "body": ("للإبلاغ عن انقطاع المياه أو انفجار أنبوب، يُرجى تحديد الشارع وأقرب معلم بارز. تُعالَج "
              "التسربات الطارئة التي تؤثّر على الطريق العام خلال 24 ساعة. يُعلَن عن انقطاعات الصيانة "
              "المجدولة قبل 48 ساعة على الأقل عبر موقع البلدية وقائمة الرسائل النصية."),
     "category": "water", "lang": "ar", "embedding_status": "done"},
    {"id": "p8", "title": "Reporting street faults — potholes and lighting",
     "body": ("Report potholes, damaged pavements, or broken streetlights with the street name and a "
              "nearby landmark; a photo helps. Streetlight repairs are typically completed within five "
              "working days. Potholes on main roads are assessed within 48 hours and scheduled for "
              "patching based on severity and traffic."),
     "category": "roads", "lang": "en", "embedding_status": "done"},
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
            c1, c2 = st.columns([5, 1])
            with c1:
                st.markdown(f"**{entry['title']}**  \n`{entry['category']}` · `{entry['lang']}`")
                body = entry.get("body", "")
                st.caption(body[:200] + ("…" if len(body) > 200 else ""))
                # CMS entries are published information, not tasks — no done/in-progress status.
                # The only signal worth surfacing is when an entry failed to index for search.
                if entry.get("embedding_status") == "failed":
                    st.caption("⚠️ Not yet searchable — re-save this entry to re-index it.")
            with c2:
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
