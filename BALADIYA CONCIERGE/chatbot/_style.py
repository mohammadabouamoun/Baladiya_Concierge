"""Shared brand styling for the Tenant Admin Streamlit app.

`inject()` does two things on every page:
  1. injects the Baladiya Concierge design system (deep green + copper) as CSS
  2. renders the logo + brand block at the top of the sidebar

Palette is derived from the logo: deep green #1a3a2a, copper #b5651d, stone #f4f0ea.
"""
from __future__ import annotations

import base64
import functools
import os

import streamlit as st

_LOGO_PATH = os.path.join(os.path.dirname(__file__), "assets", "logo.png")


@functools.lru_cache(maxsize=1)
def _logo_b64() -> str:
    """Read the logo once and cache its base64 string (so it can live inside CSS/HTML)."""
    try:
        with open(_LOGO_PATH, "rb") as fh:
            return base64.b64encode(fh.read()).decode("ascii")
    except OSError:
        return ""


# Islamic-star tessellation, URL-encoded — the same signature texture as the public site.
_STAR_SVG = (
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='56' height='56'%3E"
    "%3Cpath d='M28 6 L32 16 L42 11 L37 21 L47 25 L37 29 L42 39 L32 34 L28 44 L24 34 L14 39 "
    "L19 29 L9 25 L19 21 L14 11 L24 16 Z' fill='none' stroke='rgba(255,255,255,0.06)' "
    "stroke-width='0.7'/%3E%3Cpath d='M28 14 L31 21 L38 18 L35 25 L42 28 L35 31 L38 38 L31 35 "
    "L28 42 L25 35 L18 38 L21 31 L14 28 L21 25 L18 18 L25 21 Z' fill='none' "
    "stroke='rgba(181,101,29,0.08)' stroke-width='0.5'/%3E%3C/svg%3E"
)


def inject() -> None:
    """Inject brand CSS, then render the sidebar brand header."""
    logo = _logo_b64()

    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,600;0,700;1,400&family=Source+Sans+3:wght@300;400;500;600;700&family=Noto+Sans+Arabic:wght@400;500;600;700&display=swap');

        :root {{
            --green:        #1a3a2a;
            --green-2:      #2d6a4f;
            --light-green:  #d4e8df;
            --copper:       #b5651d;
            --copper-dark:  #8b4513;
            --copper-light: #f0d9c8;
            --stone:        #f4f0ea;
            --sand:         #ede8de;
            --border:       #d8d2c8;
            --text:         #1c1c1c;
            --muted:        #6a665f;
            --ease:         cubic-bezier(0.22, 1, 0.36, 1);
        }}

        /* ── Base ──────────────────────────────────────────────── */
        html, body, [class*="css"], .stApp, [data-testid="stMarkdownContainer"] {{
            font-family: 'Source Sans 3', 'Noto Sans Arabic', system-ui, sans-serif !important;
        }}
        .stApp {{ background: var(--stone) !important; }}

        /* page content fades up on each load */
        .main .block-container {{
            animation: bc-rise 0.5s var(--ease) both;
            padding-top: 2.4rem !important;
            max-width: 1200px;
        }}
        @keyframes bc-rise {{ from {{ opacity: 0; transform: translateY(16px); }} to {{ opacity: 1; transform: translateY(0); }} }}
        @keyframes bc-fade {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}

        /* ── Top header bar ────────────────────────────────────── */
        [data-testid="stHeader"] {{
            background: var(--green) !important;
            background-image: url("{_STAR_SVG}") !important;
            background-size: 56px 56px !important;
            border-bottom: 2px solid var(--copper);
        }}

        /* ── Sidebar ───────────────────────────────────────────── */
        [data-testid="stSidebar"] {{
            background-color: var(--green) !important;
            background-image: url("{_STAR_SVG}") !important;
            background-size: 56px 56px !important;
            border-right: 1px solid rgba(181,101,29,0.4);
        }}
        [data-testid="stSidebar"] * {{ color: #eef2ee !important; }}

        /* brand block at top of sidebar (rendered below) */
        .bc-brand {{
            display: flex; align-items: center; gap: 12px;
            padding: 4px 4px 18px;
            margin-bottom: 14px;
            border-bottom: 1px solid rgba(255,255,255,0.12);
            animation: bc-fade 0.7s var(--ease) both;
        }}
        .bc-brand img {{
            width: 52px; height: 52px; border-radius: 50%;
            object-fit: cover;
            border: 2px solid rgba(181,101,29,0.55);
            box-shadow: 0 0 0 3px rgba(181,101,29,0.14);
            transition: transform 0.4s var(--ease);
        }}
        .bc-brand:hover img {{ transform: scale(1.06) rotate(3deg); }}
        .bc-brand .bc-name {{
            font-family: 'Source Sans 3', sans-serif !important;
            font-size: 15px; font-weight: 700; line-height: 1.2; color: #fff !important;
        }}
        .bc-brand .bc-role {{
            font-size: 10px; letter-spacing: 0.14em; text-transform: uppercase;
            color: var(--copper-light) !important; margin-top: 3px;
        }}

        /* auto multipage nav links */
        [data-testid="stSidebarNav"] a {{
            border-radius: 8px !important;
            transition: background 0.25s var(--ease), padding 0.2s var(--ease) !important;
        }}
        [data-testid="stSidebarNav"] a:hover {{
            background: rgba(255,255,255,0.09) !important;
            padding-inline-start: 18px !important;
        }}
        [data-testid="stSidebarNav"] a[aria-current="page"] {{
            background: var(--copper) !important;
        }}

        /* sidebar buttons (e.g. Sign out) */
        [data-testid="stSidebar"] .stButton > button {{
            background: transparent !important;
            border: 1px solid rgba(181,101,29,0.7) !important;
            color: var(--copper-light) !important;
            width: 100%;
            border-radius: 8px !important;
            transition: all 0.22s var(--ease) !important;
        }}
        [data-testid="stSidebar"] .stButton > button:hover {{
            background: var(--copper) !important;
            border-color: var(--copper) !important;
            color: #fff !important;
            transform: translateY(-1px);
        }}

        /* ── Headings ──────────────────────────────────────────── */
        h1 {{
            color: var(--green) !important;
            font-family: 'Playfair Display', Georgia, serif !important;
            font-weight: 700 !important;
            letter-spacing: -0.01em;
            padding-inline-start: 0.8rem !important;
            border-inline-start: 5px solid var(--copper) !important;
            margin-bottom: 1.4rem !important;
        }}
        h2 {{ color: var(--green) !important; font-weight: 700 !important; }}
        h3 {{ color: var(--green-2) !important; font-weight: 600 !important; }}

        /* ── Buttons ───────────────────────────────────────────── */
        .stButton > button, .stFormSubmitButton > button, .stDownloadButton > button {{
            border-radius: 9px !important;
            font-weight: 600 !important;
            border: 1px solid var(--border) !important;
            transition: all 0.2s var(--ease) !important;
        }}
        .stButton > button:hover, .stDownloadButton > button:hover {{
            border-color: var(--green-2) !important;
            color: var(--green) !important;
            transform: translateY(-1px);
        }}
        .stButton > button[kind="primary"],
        .stFormSubmitButton > button[kind="primary"],
        .stFormSubmitButton > button {{
            background: var(--copper) !important;
            color: #fff !important;
            border: none !important;
            box-shadow: 0 3px 12px rgba(181,101,29,0.28) !important;
        }}
        .stButton > button[kind="primary"]:hover,
        .stFormSubmitButton > button[kind="primary"]:hover,
        .stFormSubmitButton > button:hover {{
            background: var(--copper-dark) !important;
            color: #fff !important;
            transform: translateY(-2px);
            box-shadow: 0 6px 18px rgba(181,101,29,0.38) !important;
        }}

        /* ── Metrics ───────────────────────────────────────────── */
        [data-testid="stMetric"], [data-testid="metric-container"] {{
            background: #fff !important;
            border: 1px solid var(--border) !important;
            border-inline-start: 4px solid var(--copper) !important;
            border-radius: 12px !important;
            padding: 1rem 1.25rem !important;
            box-shadow: 0 1px 3px rgba(26,58,42,0.05);
            transition: transform 0.25s var(--ease), box-shadow 0.25s var(--ease);
        }}
        [data-testid="stMetric"]:hover, [data-testid="metric-container"]:hover {{
            transform: translateY(-3px);
            box-shadow: 0 10px 26px rgba(26,58,42,0.1);
        }}
        [data-testid="stMetricValue"] {{ color: var(--green) !important; font-weight: 700 !important; }}

        /* ── Containers / expanders / forms ────────────────────── */
        [data-testid="stExpander"], [data-testid="stForm"],
        [data-testid="stVerticalBlockBorderWrapper"] {{
            border: 1px solid var(--border) !important;
            border-radius: 12px !important;
            background: #fff !important;
            transition: border-color 0.25s var(--ease), box-shadow 0.25s var(--ease);
        }}
        [data-testid="stExpander"] {{ margin-bottom: 0.6rem !important; }}
        [data-testid="stExpander"]:hover,
        [data-testid="stVerticalBlockBorderWrapper"]:hover {{
            border-color: rgba(181,101,29,0.5) !important;
            box-shadow: 0 6px 22px rgba(26,58,42,0.08) !important;
        }}
        [data-testid="stForm"] {{ padding: 1.5rem !important; }}

        /* ── Inputs ────────────────────────────────────────────── */
        .stTextInput input, .stTextArea textarea, .stNumberInput input,
        [data-baseweb="select"] > div, [data-baseweb="input"] {{
            border-radius: 8px !important;
            transition: border-color 0.2s var(--ease), box-shadow 0.2s var(--ease) !important;
        }}
        .stTextInput input:focus, .stTextArea textarea:focus, .stNumberInput input:focus {{
            border-color: var(--green-2) !important;
            box-shadow: 0 0 0 3px rgba(45,106,79,0.15) !important;
        }}

        /* ── Tabs ──────────────────────────────────────────────── */
        .stTabs [data-baseweb="tab-list"] {{ gap: 4px; border-bottom: 1px solid var(--border); }}
        .stTabs [data-baseweb="tab"] {{ border-radius: 8px 8px 0 0 !important; transition: background 0.2s var(--ease); }}
        .stTabs [aria-selected="true"] {{ color: var(--green) !important; border-bottom-color: var(--copper) !important; }}

        /* ── Alerts ────────────────────────────────────────────── */
        [data-testid="stAlert"] {{ border-radius: 10px !important; border-inline-start-width: 4px !important; }}

        /* ── Tables / dataframes ───────────────────────────────── */
        [data-testid="stDataFrame"], [data-testid="stTable"] {{
            border-radius: 10px !important; overflow: hidden; border: 1px solid var(--border);
        }}

        /* ── Scrollbar ─────────────────────────────────────────── */
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

    # Brand block at the very top of the sidebar (logo + role label).
    if logo:
        st.sidebar.markdown(
            f"""
            <div class="bc-brand">
                <img src="data:image/png;base64,{logo}" alt="Baladiya Concierge" />
                <div>
                    <div class="bc-name">Baladiya Concierge</div>
                    <div class="bc-role">Tenant Admin</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def login_hero(title: str, subtitle: str) -> None:
    """Centered branded header for sign-in screens. Call inside the login block."""
    logo = _logo_b64()
    img = (
        f'<img src="data:image/png;base64,{logo}" alt="" '
        f'style="width:96px;height:96px;border-radius:50%;object-fit:cover;'
        f'border:2px solid rgba(181,101,29,0.5);box-shadow:0 0 0 4px rgba(181,101,29,0.12);" />'
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
            <div style="width:54px; height:3px; background:#b5651d; border-radius:2px;
                        margin:18px auto 0;"></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
