"""
app.py
DESi Field AI — Main Streamlit chat interface.
Open to all users (ASMs and RSMs). No login required.
"""

import os
import base64
import time as _time
import streamlit as st
from dotenv import load_dotenv

load_dotenv()


# ---------------------------------------------------------------------------
# Logo + header helpers
# ---------------------------------------------------------------------------

def get_logo_base64() -> str:
    """Return the GO DESi logo as a base64 string, or '' if not found."""
    logo_path = os.path.join(os.path.dirname(__file__), "assets", "godesi_logo.png")
    try:
        with open(logo_path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception:
        return ""


_LOGO_B64 = get_logo_base64()


def render_header() -> None:
    """Render the full-width orange DESi Field AI header on every screen."""
    logo_img = (
        f'<img src="data:image/png;base64,{_LOGO_B64}" '
        f'style="height:60px;width:60px;border-radius:50%;object-fit:cover;">'
        if _LOGO_B64 else ""
    )
    st.markdown(f"""
<style>
[data-testid="stAppViewContainer"] > .main > div:first-child,
[data-testid="stMain"],
[data-testid="stMainBlockContainer"],
.main .block-container,
section[data-testid="stMain"] > div:first-child {{
    padding-top: 0 !important;
    margin-top: 0 !important;
}}
[data-testid="stDecoration"] {{ display: none !important; }}
.desi-header {{
    background-color: #F7941D;
    padding: 20px 3.5rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-left: -3.5rem;
    margin-right: -3.5rem;
    margin-top: 0;
    margin-bottom: 1.2rem;
    font-family: 'Inter', system-ui, sans-serif;
    border-radius: 0 0 16px 16px;
}}
.desi-header-title {{
    font-size: 1.9rem;
    font-weight: 800;
    color: white;
    line-height: 1.2;
}}
.desi-header-subtitle {{
    font-size: 0.9rem;
    color: rgba(255,255,255,0.85);
    margin-top: 3px;
}}
@media (max-width: 900px) {{
    .desi-header {{ padding: 18px 2rem; margin-left: -1.2rem; margin-right: -1.2rem; }}
}}
@media (max-width: 640px) {{
    .desi-header {{ padding: 14px 1rem; margin-left: -0.75rem; margin-right: -0.75rem; }}
    .desi-header-title {{ font-size: 1.4rem; }}
    .desi-header-subtitle {{ font-size: 0.8rem; }}
}}
</style>
<div class="desi-header">
    <div>
        <div class="desi-header-title">DESi Field AI</div>
        <div class="desi-header-subtitle">AI-Powered Sales Intelligence</div>
    </div>
    {logo_img}
</div>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="DESi Field AI",
    page_icon="assets/godesi_logo.png" if os.path.exists("assets/godesi_logo.png") else None,
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
for _k, _v in [
    ("messages",            []),
    ("session_context",     {}),
    ("starter_clicked",     None),   # (display_label, full_query) or None
    ("pending_question",    None),
    ("pending_display",     None),   # short label to show in chat bubble
    ("user_role",           None),
    ("user_name",           None),
    ("user_names",          []),
    ("selected_categories", []),
    ("onboarding_role",     None),
    ("ob_names",            None),   # cached name list after first load
    ("names_loaded",        False),  # loading screen shown only once
]:
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ---------------------------------------------------------------------------
# Lazy imports
# ---------------------------------------------------------------------------
from supabase_client import load_names, get_latest_date_str, get_categories
from query_engine import QueryEngine
from metrics import MONTH_NAMES

# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def get_engine() -> QueryEngine:
    return QueryEngine(load_names(), get_latest_date_str())


# ---------------------------------------------------------------------------
# Global CSS
# ---------------------------------------------------------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

/* ── Reset & base ── */
* { font-family: 'Inter', system-ui, sans-serif; box-sizing: border-box; }
#MainMenu, footer, header { visibility: hidden; }
html, body, [data-testid="stAppViewContainer"] { overflow-x: hidden !important; }

/* ── Full-page layout: no max-width, controlled padding ── */
[data-testid="stMain"],
[data-testid="stMainBlockContainer"] {
    padding-top: 0 !important;
    padding-bottom: 0 !important;
    margin-top: 0 !important;
    max-width: 100% !important;
    padding-left: 0 !important;
    padding-right: 0 !important;
}
.block-container {
    padding-top: 0 !important;
    padding-bottom: 1rem !important;
    margin-top: 0 !important;
    max-width: 100% !important;
    padding-left: 3.5rem !important;
    padding-right: 3.5rem !important;
    /* Hard reset — prevents onboarding CSS leaking into chat */
    position: static !important;
    top: auto !important;
    left: auto !important;
    transform: none !important;
}

/* ── All buttons: rounded corners ── */
button,
[data-testid="stBaseButton-primary"],
[data-testid="stBaseButton-secondary"],
[data-testid="stFormSubmitButton"] > button {
    border-radius: 10px !important;
    min-height: 42px !important;
}

/* ── Primary buttons (orange) ── */
[data-testid="stBaseButton-primary"],
[data-testid="stFormSubmitButton"] > button {
    background: #F7941D !important;
    color: #FFFFFF !important;
    border: none !important;
    font-weight: 600 !important;
    transition: opacity 0.18s !important;
}
[data-testid="stBaseButton-primary"]:hover,
[data-testid="stFormSubmitButton"] > button:hover { opacity: 0.88 !important; }

/* ── Secondary buttons (toolbar) ── */
[data-testid="stBaseButton-secondary"] {
    font-size: 0.84rem !important;
}

/* ── Suggested prompt buttons ── */
.prompt-btn-wrap [data-testid="stBaseButton-secondary"] {
    border-left: 3px solid #F7941D !important;
    border-radius: 10px !important;
    text-align: left !important;
    padding: 0.6rem 0.9rem !important;
    font-size: 0.88rem !important;
    font-weight: 400 !important;
    margin-bottom: 0.35rem !important;
    width: 100% !important;
    transition: background 0.15s, color 0.15s !important;
}
.prompt-btn-wrap [data-testid="stBaseButton-secondary"]:hover {
    background: #F7941D !important;
    color: #FFFFFF !important;
    border-color: #F7941D !important;
}

/* ── Text input ── */
.stTextInput label { display: none !important; }
.stTextInput > div > div > input {
    border-radius: 10px !important;
    font-size: 0.95rem !important;
    padding: 0.6rem 1rem !important;
}

/* ── Category filter multiselect ── */
[data-testid="stMultiSelect"] > div { border-radius: 8px !important; }

/* ── Status bar ── */
.status-bar {
    border: 1px solid #333;
    border-radius: 8px;
    padding: 0.45rem 1rem;
    font-size: 0.82rem;
    margin-bottom: 0.6rem;
    background: #111;
}
.status-ok   { color: #4CAF50; }
.status-warn { color: #F7941D; }

/* ── Suggested prompts section label ── */
.prompts-section-label {
    font-size: 0.95rem;
    font-weight: 600;
    margin: 0.5rem 0 0.75rem;
    padding-bottom: 0.4rem;
    border-bottom: 2px solid #F7941D;
    color: #FFFFFF;
}
.prompt-col-header {
    color: #F7941D;
    font-size: 0.82rem;
    font-weight: 600;
    margin: 0 0 0.6rem;
}

/* ── Each prompts column as a card ── */
div:has(> .prompts-cols-marker) + div [data-testid="stColumn"] > div {
    background: #1A1A1A !important;
    border: 1px solid #2A2A2A !important;
    border-radius: 12px !important;
    padding: 16px 16px 10px !important;
    height: 100% !important;
}

/* ── Chat bubbles ── */
.msg-user { display: flex; justify-content: flex-end; margin: 0.5rem 0; }
.bubble-user {
    background: #2A2A2A; color: #FFFFFF;
    padding: 0.7rem 1.1rem;
    border-radius: 16px 16px 4px 16px;
    max-width: 70%; font-size: 0.93rem; line-height: 1.5;
}
.msg-bot { display: flex; justify-content: flex-start; margin: 0.5rem 0; }
.bubble-bot {
    background: #1A1A1A; border: 1px solid #2A2A2A; color: #FFFFFF;
    padding: 0.85rem 1.2rem;
    border-radius: 16px 16px 16px 4px;
    max-width: 82%; font-size: 0.93rem; line-height: 1.7;
}
.bubble-bot table {
    border-collapse: collapse; margin: 0.6rem 0;
    font-size: 0.85rem; width: 100%;
    display: block; overflow-x: auto; -webkit-overflow-scrolling: touch;
}
.bubble-bot table th { background: #2A2A2A; padding: 0.45rem 0.8rem; text-align: left; color: #AAAAAA; font-weight: 600; border-bottom: 1px solid #333; white-space: nowrap; }
.bubble-bot table td { padding: 0.35rem 0.8rem; border-bottom: 1px solid #222; color: #EEEEEE; white-space: nowrap; }
.bubble-bot table tr:last-child td { border-bottom: none; }
.bubble-bot table tr:hover td { background: #222; }

/* ── Loading dots ── */
@keyframes pulse-dot {
    0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
    40%            { transform: scale(1);   opacity: 1;   }
}
.loading-dots { display: flex; align-items: center; gap: 5px; padding: 2px 0; }
.loading-dots span {
    width: 7px; height: 7px; border-radius: 50%; background: #F7941D;
    display: inline-block; animation: pulse-dot 1.4s infinite ease-in-out;
}
.loading-dots span:nth-child(2) { animation-delay: 0.2s; }
.loading-dots span:nth-child(3) { animation-delay: 0.4s; }

/* ── Welcome box ── */
.welcome-box { text-align: center; padding: 1rem 1rem 0.5rem; }
.welcome-box h2 { font-size: 1.3rem; margin-bottom: 0.3rem; font-weight: 600; }

/* ── Amber info box below input ── */
.info-box-amber {
    background: #2A1F00;
    border: 1px solid #F7941D;
    border-radius: 10px;
    padding: 0.5rem 1rem;
    color: #F7941D;
    font-size: 0.8rem;
    text-align: center;
    margin: 0.35rem 0 0.5rem;
}

/* ── Input area wrapper (sticky) ── */
.input-area {
    position: sticky;
    bottom: 0;
    padding: 0.5rem 0 0;
    z-index: 100;
}

/* ── Loading bar (onboarding) ── */
@keyframes bar-to-95 {
    0%   { width: 5%;  }
    30%  { width: 50%; }
    70%  { width: 80%; }
    100% { width: 95%; }
}
.loading-bar-fill {
    background: #F7941D; height: 100%; border-radius: 3px;
    animation: bar-to-95 15s ease-out forwards;
}

/* ── Sidebar toggle ── */
[data-testid="collapsedControl"] { display: flex !important; visibility: visible !important; opacity: 1 !important; }

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-thumb { background: #2A2A2A; border-radius: 2px; }
::-webkit-scrollbar-thumb:hover { background: #F7941D; }

/* ── Toolbar gap tighten ── */
[data-testid="stHorizontalBlock"] { gap: 0.5rem !important; }

/* ═══════════════════════════════════
   RESPONSIVE — Tablet (≤ 900px)
═══════════════════════════════════ */
@media (max-width: 900px) {
    .block-container { padding-left: 1.2rem !important; padding-right: 1.2rem !important; }
    .bubble-user { max-width: 82% !important; }
    .bubble-bot  { max-width: 92% !important; }
    [data-testid="stBaseButton-secondary"] { font-size: 0.78rem !important; padding: 0.4rem 0.5rem !important; }
}

/* ═══════════════════════════════════
   RESPONSIVE — Mobile (≤ 640px)
═══════════════════════════════════ */
@media (max-width: 640px) {
    .block-container { padding-left: 0.75rem !important; padding-right: 0.75rem !important; }
    .bubble-user, .bubble-bot { max-width: 96% !important; font-size: 0.88rem !important; }
    .prompts-section-label { font-size: 0.88rem; }
    .prompt-btn-wrap [data-testid="stBaseButton-secondary"] { font-size: 0.84rem !important; padding: 0.55rem 0.75rem !important; }
    /* Stack toolbar buttons on mobile */
    .desi-header { padding: 16px 16px !important; }
    .desi-header-title { font-size: 1.4rem !important; }
    .info-box-amber { font-size: 0.76rem !important; }
    .bubble-bot table { font-size: 0.78rem !important; }
    .bubble-bot table th, .bubble-bot table td { padding: 0.3rem 0.5rem !important; }
}
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Main app
# ---------------------------------------------------------------------------
def main():  # noqa: C901

    # ── ONBOARDING ────────────────────────────────────────────────────────
    if not st.session_state.user_role:

        st.markdown("""
<style>
/* Center all onboarding content */
[data-testid="stRadio"] > div { justify-content: center !important; }
[data-testid="stRadio"] { display: flex; justify-content: center; }
[data-testid="stMultiSelect"] { max-width: 420px; margin: 0 auto; }
[data-testid="stFormSubmitButton"],
[data-testid="stBaseButton-primary"] { display: block; margin: 0 auto; }
</style>
""", unsafe_allow_html=True)

        _logo_html = (
            f'<img src="data:image/png;base64,{_LOGO_B64}" '
            f'style="width:72px;height:72px;object-fit:contain;">'
            if _LOGO_B64 else ""
        )

        if not st.session_state.names_loaded:
            # Show loading screen only on the very first load
            _screen = st.empty()
            with _screen.container():
                _, _lc, _ = st.columns([1, 2, 1])
                with _lc:
                    st.markdown(f"""
<div style="text-align:center;padding:3rem 0 2rem;font-family:'Inter',sans-serif;">
  {_logo_html}
  <div style="font-size:1.6rem;font-weight:800;margin:0.6rem 0 0.2rem;">DESi Field AI</div>
  <div style="font-size:0.9rem;color:#AAAAAA;margin-bottom:1.3rem;">AI-Powered Sales Intelligence</div>
  <div style="width:100%;margin:0 auto 0.7rem;">
    <div style="background:#2A2A2A;border-radius:3px;height:5px;overflow:hidden;">
      <div class="loading-bar-fill"></div>
    </div>
  </div>
  <div style="font-size:0.84rem;font-weight:500;">Connecting to your sales data...</div>
  <div style="font-size:0.79rem;color:#F7941D;font-weight:600;margin-top:0.3rem;">
    Please do not refresh the page
  </div>
</div>
""", unsafe_allow_html=True)

            st.session_state.ob_names = load_names()
            st.session_state.names_loaded = True

            with _screen.container():
                _, _lc, _ = st.columns([1, 2, 1])
                with _lc:
                    st.markdown(f"""
<div style="text-align:center;padding:3rem 0 2rem;font-family:'Inter',sans-serif;">
  {_logo_html}
  <div style="font-size:1.6rem;font-weight:800;margin:0.6rem 0 0.2rem;">DESi Field AI</div>
  <div style="font-size:0.9rem;color:#AAAAAA;margin-bottom:1.3rem;">AI-Powered Sales Intelligence</div>
  <div style="width:100%;margin:0 auto 0.7rem;">
    <div style="background:#2A2A2A;border-radius:3px;height:5px;overflow:hidden;">
      <div style="background:#F7941D;height:100%;width:100%;border-radius:3px;"></div>
    </div>
  </div>
  <div style="font-size:0.84rem;color:#4CAF50;font-weight:600;">Connected</div>
</div>
""", unsafe_allow_html=True)
            _time.sleep(0.5)
            _screen.empty()

        _ob_names = st.session_state.ob_names or {}

        # Onboarding form — centered using columns, no CSS position tricks
        _, _mid, _ = st.columns([1, 2, 1])
        with _mid:
            st.markdown(f"""
<div style="text-align:center;padding:1.5rem 0 0.8rem;font-family:'Inter',sans-serif;">
  {f'<img src="data:image/png;base64,{_LOGO_B64}" style="width:72px;height:72px;object-fit:contain;margin-bottom:0.75rem;">' if _LOGO_B64 else ''}
  <h2 style="font-size:1.6rem;font-weight:800;margin:0 0 0.2rem;">Welcome to DESi Field AI</h2>
  <p style="font-size:0.88rem;margin:0 0 1.2rem;opacity:0.7;">Select your role and name to continue</p>
  <p style="font-size:0.93rem;font-weight:600;margin-bottom:0.4rem;">Who are you?</p>
</div>
""", unsafe_allow_html=True)

            _role_choice = st.radio(
                label="Role",
                options=["I am an RSM", "I am an ASM"],
                index=(0 if st.session_state.onboarding_role == "RSM" else
                       1 if st.session_state.onboarding_role == "ASM" else 0),
                horizontal=True,
                key="ob_role_radio",
                label_visibility="collapsed",
            )
            _role = "RSM" if "RSM" in _role_choice else "ASM"
            if _role != st.session_state.onboarding_role:
                st.session_state.onboarding_role = _role
                st.rerun()

            _name_list = (
                _ob_names.get("rsm_names", []) if _role == "RSM"
                else _ob_names.get("asm_names", [])
            )

            if not _name_list:
                st.warning("Name list not loaded. Data may still be uploading. Try refreshing.")
            else:
                st.markdown(
                    f'<p style="text-align:center;font-size:0.85rem;opacity:0.7;'
                    f'margin:0.9rem 0 0.3rem;">Select your name as {_role}:</p>',
                    unsafe_allow_html=True,
                )
                _selected = st.multiselect(
                    label="Your name(s)",
                    options=sorted(_name_list),
                    placeholder="Select one or more names...",
                    key="ob_name_select",
                    label_visibility="collapsed",
                )
                if _selected:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("Enter DESi Field AI", key="ob_enter", type="primary",
                                 use_container_width=True):
                        st.session_state.user_role  = _role
                        st.session_state.user_names = _selected
                        st.session_state.user_name  = _selected[0]
                        st.session_state.onboarding_role = None
                        st.rerun()

            st.markdown("""
<div style="
    background: #1A1A1A;
    border: 1px solid #2A2A2A;
    border-radius: 10px;
    padding: 12px 24px;
    text-align: center;
    margin: 2rem 0 0;
">
    <span style="color:#AAAAAA;font-size:0.88rem;">Data Analyst?&nbsp;</span>
    <a href="/upload" style="color:#F7941D;text-decoration:none;font-size:0.88rem;font-weight:500;">
        Click here to upload data
    </a>
</div>
""", unsafe_allow_html=True)
        return

    # ── CHAT UI ───────────────────────────────────────────────────────────

    render_header()

    # ── Toolbar ──────────────────────────────────────────────────────────
    t1, t2, t3, t4 = st.columns([5, 2, 2, 2])

    with t1:
        _names = st.session_state.user_names or []
        if len(_names) == 1:
            _badge = f"{_names[0]} ({st.session_state.user_role})"
        elif len(_names) == 2:
            _badge = f"{_names[0]}, {_names[1]} ({st.session_state.user_role})"
        else:
            _badge = f"{_names[0]} +{len(_names)-1} others ({st.session_state.user_role})"
        if st.button(_badge, key="badge_switch", help="Click to switch user"):
            for _k in ("user_role","user_name","user_names","selected_categories",
                       "onboarding_role","messages","session_context"):
                st.session_state[_k] = (
                    [] if _k in ("user_names","selected_categories","messages")
                    else {} if _k == "session_context"
                    else None
                )
            st.session_state.names_loaded = False
            st.rerun()

    with t2:
        if st.button("New Conversation", use_container_width=True):
            st.session_state.messages        = []
            st.session_state.session_context = {}
            st.rerun()

    with t3:
        if st.button("Refresh Data", use_container_width=True):
            get_engine.clear()
            load_names.clear()
            get_latest_date_str.clear()
            st.rerun()

    with t4:
        if st.button("Switch User", use_container_width=True):
            for _k in ("user_role","user_name","user_names","selected_categories",
                       "onboarding_role","messages","session_context"):
                st.session_state[_k] = (
                    [] if _k in ("user_names","selected_categories","messages")
                    else {} if _k == "session_context"
                    else None
                )
            st.session_state.names_loaded = False
            st.rerun()

    # ── Engine ──────────────────────────────────────────────────────────
    try:
        engine  = get_engine()
        data_ok = engine._latest_date is not None
    except Exception as e:
        engine  = None
        data_ok = False
        st.error(f"Could not connect to database: {e}")

    # ── Status bar ──────────────────────────────────────────────────────
    if data_ok:
        latest     = engine._latest_date
        month_name = MONTH_NAMES.get(latest.month, "")
        st.markdown(
            f'<div class="status-bar">'
            f'<span class="status-ok">&#9679;</span> Ready'
            f' &nbsp;|&nbsp; Latest date: <b>{latest.strftime("%d %b %Y")}</b>'
            f' &nbsp;|&nbsp; MTD reference: <b>{month_name} {latest.year}</b>'
            f'</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="status-bar"><span class="status-warn">&#9679;</span> '
            'No data found. Upload files via the Upload page.</div>',
            unsafe_allow_html=True,
        )

    # ── Category filter ─────────────────────────────────────────────────
    _all_cats = get_categories()
    if _all_cats:
        st.session_state.selected_categories = st.multiselect(
            label="Filter by Category (optional)",
            options=_all_cats,
            default=st.session_state.selected_categories,
            key="cat_filter",
            placeholder="All categories",
        )

    # ── Suggested prompts (ABOVE chat history) ───────────────────────────
    _role   = st.session_state.get("user_role")
    _names  = st.session_state.get("user_names", [])
    _nm_str = ", ".join(_names) if _names else "your team"
    if _role == "RSM":
        _sub   = "ASM"
        _scope = f"RSM {_nm_str}"
    else:
        _sub   = "SO"
        _scope = f"ASM {_nm_str}"

    _sales_btns = [
        ("MTD Sales",
         f"Give me MTD secondary sales breakdown by each {_sub} for {_scope}. "
         f"Show Secondary, TC, PC, UPC, ABV."),
        ("YTD Sales",
         f"Give me YTD secondary sales breakdown by each {_sub} for {_scope}."),
        ("L3M Average Sales",
         f"Show average monthly secondary sales over last 3 complete months "
         f"for {_scope}. Show each month separately plus the 3-month average."),
        ("MTD Target vs Achievement",
         f"Give me MTD target vs achievement for each {_sub} under {_scope}."),
        ("CM vs LM vs LM Full",
         f"Compare current month MTD secondary vs last month same number of days "
         f"vs last month full month total for {_scope}. Show all three side by side."),
        ("Top Outlets: CM vs L3M Avg",
         f"Show top 10 outlets by current month secondary for {_scope}, "
         f"along with each outlet's last 3 month monthly average sales."),
        ("Unbilled Outlets",
         f"Show unbilled outlets for {_scope}: outlets that were active in last "
         f"3 months but have placed no orders this month MTD."),
    ]
    _prod_btns = [
        ("MTD TC, PC, UPC",
         f"Give me MTD TC, PC and UPC breakdown by each {_sub} for {_scope}."),
    ]

    st.markdown('<div class="prompts-section-label">Suggested Prompts</div>', unsafe_allow_html=True)
    st.markdown('<div class="prompts-cols-marker" style="display:none;"></div>', unsafe_allow_html=True)

    _left_col, _right_col = st.columns(2)

    with _left_col:
        st.markdown('<p class="prompt-col-header">Sales</p>', unsafe_allow_html=True)
        st.markdown('<div class="prompt-btn-wrap">', unsafe_allow_html=True)
        for _label, _query in _sales_btns:
            if st.button(_label, key=f"qs_{_label}", use_container_width=True):
                st.session_state.starter_clicked = (_label, _query)
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    with _right_col:
        st.markdown('<p class="prompt-col-header">Productivity</p>', unsafe_allow_html=True)
        st.markdown('<div class="prompt-btn-wrap">', unsafe_allow_html=True)
        for _label, _query in _prod_btns:
            if st.button(_label, key=f"qp_{_label}", use_container_width=True):
                st.session_state.starter_clicked = (_label, _query)
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    # Starter prompt capture — runs after buttons are rendered
    if st.session_state.starter_clicked:
        _s_label, _s_query = st.session_state.starter_clicked
        st.session_state.pending_question   = _s_query
        st.session_state.pending_display    = _s_label
        st.session_state.starter_clicked    = None
        st.rerun()

    # ── Capture pending question BEFORE rendering chat ───────────────────
    _is_processing = False
    _pending_q     = None

    if st.session_state.pending_question:
        _pending_q                        = st.session_state.pending_question
        _pending_display                  = st.session_state.pending_display or _pending_q
        st.session_state.pending_question = None
        st.session_state.pending_display  = None
        # Store the display label separately from the engine query
        st.session_state.messages.append({
            "role":    "user",
            "content": _pending_q,
            "display": _pending_display,
        })
        _is_processing = True

    # ── Chat history ─────────────────────────────────────────────────────
    if not st.session_state.messages and not _is_processing:
        _wnames = st.session_state.get("user_names", [])
        _scope_line = (
            f"Showing data for <b>{_wnames[0]}</b>." if len(_wnames) == 1 else
            f"Showing data for <b>{', '.join(_wnames)}</b>." if len(_wnames) > 1 else
            "Ask me anything about your sales data."
        )
        st.markdown(
            f'<div class="welcome-box"><h2>How can I help you today?</h2>'
            f'<p>{_scope_line}</p></div>',
            unsafe_allow_html=True,
        )
    else:
        for msg in st.session_state.messages:
            if msg["role"] == "user":
                # Show the short display label (button text) if available,
                # otherwise fall back to the full query text
                _display_text = msg.get("display") or msg["content"]
                st.markdown(
                    f'<div class="msg-user"><div class="bubble-user">'
                    f'{_display_text}</div></div>',
                    unsafe_allow_html=True,
                )
            else:
                import markdown as _md
                try:
                    html_content = _md.markdown(
                        msg["content"], extensions=["tables", "nl2br"]
                    )
                except Exception:
                    html_content = msg["content"].replace("\n", "<br>")
                st.markdown(
                    f'<div class="msg-bot"><div class="bubble-bot">'
                    f'{html_content}</div></div>',
                    unsafe_allow_html=True,
                )

    # Loading bubble while processing
    if _is_processing:
        st.markdown(
            '<div class="msg-bot"><div class="bubble-bot">'
            '<div class="loading-dots">'
            '<span></span><span></span><span></span>'
            '</div></div></div>',
            unsafe_allow_html=True,
        )

    # Spacer so last message isn't hidden behind sticky input
    st.markdown('<div style="height:70px;"></div>', unsafe_allow_html=True)

    # ── Sticky input area ────────────────────────────────────────────────
    st.markdown('<div class="input-area">', unsafe_allow_html=True)

    with st.form(key="chat_form", clear_on_submit=True):
        _in_col, _btn_col = st.columns([10, 1])
        with _in_col:
            user_input = st.text_input(
                label="",
                placeholder="Ask a sales question...",
                label_visibility="collapsed",
            )
        with _btn_col:
            send_clicked = st.form_submit_button("Send", use_container_width=True)

    st.markdown(
        '<div class="info-box-amber">'
        'Responses may take a few seconds as data is fetched live for each question'
        '</div>',
        unsafe_allow_html=True,
    )

    st.markdown('</div>', unsafe_allow_html=True)  # close .input-area

    # Form submission — typed text: display = content
    if send_clicked and user_input.strip():
        st.session_state.pending_question = user_input.strip()
        st.session_state.pending_display  = user_input.strip()
        st.rerun()

    # ── Process pending question ─────────────────────────────────────────
    if _is_processing and _pending_q:
        if engine is None or not data_ok:
            response = (
                "I don't have any sales data to work with yet. "
                "Please ask your data analyst to upload the data via the Upload page."
            )
        else:
            try:
                _scope_key = (
                    "rsm" if st.session_state.get("user_role") == "RSM" else
                    "asm" if st.session_state.get("user_role") == "ASM" else None
                )
                _unames = st.session_state.get("user_names", [])
                _user_scope = (
                    {_scope_key: _unames if len(_unames) > 1 else _unames[0]}
                    if _scope_key and _unames else None
                )
                response, new_ctx = engine.process(
                    question=_pending_q,
                    chat_history=st.session_state.messages[:-1],
                    session_context=st.session_state.session_context,
                    user_scope=_user_scope,
                    category_filter=st.session_state.get("selected_categories") or None,
                )
                st.session_state.session_context = new_ctx
            except ConnectionError as ce:
                response = str(ce)
            except Exception:
                response = (
                    "I encountered an issue processing your question. "
                    "Please try rephrasing, or click Refresh Data if the problem persists."
                )

        st.session_state.messages.append({"role": "assistant", "content": response})
        st.rerun()


main()
