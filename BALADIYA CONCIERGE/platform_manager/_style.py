"""Brand styling for the Platform Manager Streamlit app.

Same Baladiya design DNA as the tenant admin (logo, green + copper, star texture,
Playfair headings, animations) — but a distinct *control-plane* identity: a darker,
near-black command-centre sidebar and copper-forward accents, so the oversight
console never gets mistaken for a tenant's own admin.
"""
from __future__ import annotations

import base64
import functools
import os

import streamlit as st

_LOGO_PATH = os.path.join(os.path.dirname(__file__), "assets", "logo.png")


@functools.lru_cache(maxsize=1)
def _logo_b64() -> str:
    try:
        with open(_LOGO_PATH, "rb") as fh:
            return base64.b64encode(fh.read()).decode("ascii")
    except OSError:
        return ""


_STAR_SVG = (
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='56' height='56'%3E"
    "%3Cpath d='M28 6 L32 16 L42 11 L37 21 L47 25 L37 29 L42 39 L32 34 L28 44 L24 34 L14 39 "
    "L19 29 L9 25 L19 21 L14 11 L24 16 Z' fill='none' stroke='rgba(255,255,255,0.05)' "
    "stroke-width='0.7'/%3E%3Cpath d='M28 14 L31 21 L38 18 L35 25 L42 28 L35 31 L38 38 L31 35 "
    "L28 42 L25 35 L18 38 L21 31 L14 28 L21 25 L18 18 L25 21 Z' fill='none' "
    "stroke='rgba(181,101,29,0.10)' stroke-width='0.5'/%3E%3C/svg%3E"
)

# Status colours for tenant lifecycle pills.
_PILL = {
    "active":    ("#1a3a2a", "#d4e8df", "#2d6a4f"),   # text, bg, dot
    "suspended": ("#8b4513", "#f0d9c8", "#b5651d"),
    "erased":    ("#7a1f1f", "#f3d9d9", "#b03a3a"),
}


def status_pill(status: str) -> str:
    """Return an inline HTML pill for a tenant lifecycle status."""
    txt, bg, dot = _PILL.get(status, ("#4a4a4a", "#e8e6e1", "#8a8680"))
    return (
        f'<span style="display:inline-flex;align-items:center;gap:7px;background:{bg};'
        f'color:{txt};font-size:12px;font-weight:700;letter-spacing:0.04em;'
        f'text-transform:uppercase;padding:4px 12px;border-radius:14px;">'
        f'<span style="width:7px;height:7px;border-radius:50%;background:{dot};"></span>'
        f'{status}</span>'
    )


def inject() -> None:
    logo = _logo_b64()

    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,600;0,700;1,400&family=Source+Sans+3:wght@300;400;500;600;700&family=Noto+Sans+Arabic:wght@400;500;600;700&display=swap');

        :root {{
            --green:        #1a3a2a;
            --green-2:      #2d6a4f;
            --control:      #11241a;   /* darker — command-centre */
            --light-green:  #d4e8df;
            --copper:       #b5651d;
            --copper-dark:  #8b4513;
            --copper-light: #f0d9c8;
            --stone:        #f3efe8;
            --sand:         #ece6db;
            --border:       #d8d2c8;
            --text:         #1c1c1c;
            --muted:        #6a665f;
            --ease:         cubic-bezier(0.22, 1, 0.36, 1);
        }}

        html, body, [class*="css"], .stApp, [data-testid="stMarkdownContainer"] {{
            font-family: 'Source Sans 3', 'Noto Sans Arabic', system-ui, sans-serif !important;
        }}
        .stApp {{ background: var(--stone) !important; }}

        .main .block-container {{
            animation: bc-rise 0.5s var(--ease) both;
            padding-top: 2.4rem !important;
            max-width: 1240px;
        }}
        @keyframes bc-rise {{ from {{ opacity: 0; transform: translateY(16px); }} to {{ opacity: 1; transform: translateY(0); }} }}
        @keyframes bc-fade {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}

        /* top header — copper underline marks the control plane */
        [data-testid="stHeader"] {{
            background: var(--control) !important;
            background-image: url("{_STAR_SVG}") !important;
            background-size: 56px 56px !important;
            border-bottom: 2px solid var(--copper);
        }}

        /* ── Command-centre sidebar (darker than tenant admin) ─── */
        [data-testid="stSidebar"] {{
            background-color: var(--control) !important;
            background-image: url("{_STAR_SVG}") !important;
            background-size: 56px 56px !important;
            border-right: 1px solid rgba(181,101,29,0.5);
        }}
        [data-testid="stSidebar"] * {{ color: #eef2ee !important; }}

        .bc-brand {{
            display: flex; align-items: center; gap: 12px;
            padding: 4px 4px 18px; margin-bottom: 14px;
            border-bottom: 1px solid rgba(181,101,29,0.3);
            animation: bc-fade 0.7s var(--ease) both;
        }}
        .bc-brand img {{
            width: 52px; height: 52px; border-radius: 50%; object-fit: cover;
            border: 2px solid rgba(181,101,29,0.7);
            box-shadow: 0 0 0 3px rgba(181,101,29,0.16);
            transition: transform 0.4s var(--ease);
        }}
        .bc-brand:hover img {{ transform: scale(1.06) rotate(3deg); }}
        .bc-brand .bc-name {{ font-size: 15px; font-weight: 700; line-height: 1.2; color: #fff !important; }}
        .bc-brand .bc-role {{
            font-size: 10px; letter-spacing: 0.16em; text-transform: uppercase;
            color: var(--copper-light) !important; margin-top: 3px;
        }}

        [data-testid="stSidebarNav"] a {{ border-radius: 8px !important; transition: background 0.25s var(--ease), padding 0.2s var(--ease) !important; }}
        [data-testid="stSidebarNav"] a:hover {{ background: rgba(255,255,255,0.08) !important; padding-inline-start: 18px !important; }}
        [data-testid="stSidebarNav"] a[aria-current="page"] {{ background: var(--copper) !important; }}

        [data-testid="stSidebar"] .stButton > button {{
            background: transparent !important;
            border: 1px solid rgba(181,101,29,0.75) !important;
            color: var(--copper-light) !important;
            width: 100%; border-radius: 8px !important;
            transition: all 0.22s var(--ease) !important;
        }}
        [data-testid="stSidebar"] .stButton > button:hover {{
            background: var(--copper) !important; border-color: var(--copper) !important;
            color: #fff !important; transform: translateY(-1px);
        }}

        /* ── Headings ──────────────────────────────────────────── */
        h1 {{
            color: var(--green) !important;
            font-family: 'Playfair Display', Georgia, serif !important;
            font-weight: 700 !important; letter-spacing: -0.01em;
            padding-inline-start: 0.8rem !important;
            border-inline-start: 5px solid var(--copper) !important;
            margin-bottom: 1.4rem !important;
        }}
        h2 {{ color: var(--green) !important; font-weight: 700 !important; }}
        h3 {{ color: var(--green-2) !important; font-weight: 600 !important; }}

        /* ── Buttons ───────────────────────────────────────────── */
        .stButton > button, .stFormSubmitButton > button, .stDownloadButton > button {{
            border-radius: 9px !important; font-weight: 600 !important;
            border: 1px solid var(--border) !important;
            transition: all 0.2s var(--ease) !important;
        }}
        .stButton > button:hover, .stDownloadButton > button:hover {{
            border-color: var(--green-2) !important; color: var(--green) !important; transform: translateY(-1px);
        }}
        /* primary = copper, but destructive forms (erase) read as copper-dark on hover */
        .stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {{
            background: var(--copper) !important; color: #fff !important; border: none !important;
            box-shadow: 0 3px 12px rgba(181,101,29,0.28) !important;
        }}
        .stButton > button[kind="primary"]:hover, .stFormSubmitButton > button[kind="primary"]:hover {{
            background: var(--copper-dark) !important; transform: translateY(-2px);
            box-shadow: 0 6px 18px rgba(181,101,29,0.4) !important;
        }}

        /* ── Metrics (KPI cards) ───────────────────────────────── */
        [data-testid="stMetric"], [data-testid="metric-container"] {{
            background: #fff !important; border: 1px solid var(--border) !important;
            border-top: 3px solid var(--copper) !important;
            border-radius: 12px !important; padding: 1.1rem 1.25rem !important;
            box-shadow: 0 1px 3px rgba(26,58,42,0.05);
            transition: transform 0.25s var(--ease), box-shadow 0.25s var(--ease);
        }}
        [data-testid="stMetric"]:hover, [data-testid="metric-container"]:hover {{
            transform: translateY(-3px); box-shadow: 0 10px 26px rgba(26,58,42,0.1);
        }}
        [data-testid="stMetricValue"] {{ color: var(--green) !important; font-weight: 700 !important; }}

        /* ── Containers / expanders / forms ────────────────────── */
        [data-testid="stExpander"], [data-testid="stForm"],
        [data-testid="stVerticalBlockBorderWrapper"] {{
            border: 1px solid var(--border) !important; border-radius: 12px !important;
            background: #fff !important;
            transition: border-color 0.25s var(--ease), box-shadow 0.25s var(--ease);
        }}
        [data-testid="stExpander"] {{ margin-bottom: 0.6rem !important; }}
        [data-testid="stExpander"]:hover, [data-testid="stVerticalBlockBorderWrapper"]:hover {{
            border-color: rgba(181,101,29,0.55) !important; box-shadow: 0 6px 22px rgba(26,58,42,0.08) !important;
        }}
        [data-testid="stForm"] {{ padding: 1.5rem !important; }}

        .stTextInput input:focus, .stTextArea textarea:focus, .stNumberInput input:focus {{
            border-color: var(--green-2) !important; box-shadow: 0 0 0 3px rgba(45,106,79,0.15) !important;
        }}

        [data-testid="stAlert"] {{ border-radius: 10px !important; border-inline-start-width: 4px !important; }}
        [data-testid="stDataFrame"], [data-testid="stTable"] {{ border-radius: 10px !important; overflow: hidden; border: 1px solid var(--border); }}

        ::-webkit-scrollbar {{ width: 9px; height: 9px; }}
        ::-webkit-scrollbar-thumb {{ background: var(--border); border-radius: 5px; }}
        ::-webkit-scrollbar-thumb:hover {{ background: var(--green-2); }}

        @media (prefers-reduced-motion: reduce) {{
            *, *::before, *::after {{ animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    if logo:
        st.sidebar.markdown(
            f"""
            <div class="bc-brand">
                <img src="data:image/png;base64,{logo}" alt="Baladiya Concierge" />
                <div>
                    <div class="bc-name">Baladiya Concierge</div>
                    <div class="bc-role">Platform · Control Plane</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def login_hero(title: str, subtitle: str) -> None:
    logo = _logo_b64()
    img = (
        f'<img src="data:image/png;base64,{logo}" alt="" '
        f'style="width:96px;height:96px;border-radius:50%;object-fit:cover;'
        f'border:2px solid rgba(181,101,29,0.6);box-shadow:0 0 0 4px rgba(181,101,29,0.14);" />'
        if logo else ""
    )
    st.markdown(
        f"""
        <div style="text-align:center; padding:56px 0 26px; animation: bc-rise 0.55s cubic-bezier(0.22,1,0.36,1) both;">
            {img}
            <div style="font-family:'Playfair Display',serif; font-size:30px; font-weight:700;
                        color:#1a3a2a; margin-top:18px;">{title}</div>
            <div style="font-family:'Source Sans 3',sans-serif; font-size:14px; color:#6a665f;
                        margin-top:6px; letter-spacing:0.02em;">{subtitle}</div>
            <div style="width:54px; height:3px; background:#b5651d; border-radius:2px; margin:18px auto 0;"></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
