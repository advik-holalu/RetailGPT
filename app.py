"""
app.py
DESi Field AI — Main Streamlit chat interface.
Open to all users (ASMs and RSMs). No login required.
"""

import os
import time as _time
import streamlit as st
from dotenv import load_dotenv
from page_utils import _LOGO_B64, render_header

load_dotenv()


# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Retail AI",
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
    ("starter_clicked",     None),
    ("pending_question",    None),
    ("pending_display",     None),
    ("user_email",          None),   # set after email login
    ("user_role",           None),   # RSM | ASM | Master
    ("user_name",           None),   # pre-assigned name from approved_users
    ("user_names",          []),     # list form for query engine
    ("selected_role",       None),   # Master's chosen RSM/ASM role (for scope)
    ("master_identity_set", False),  # Master has selected their identity
    ("onboarding_role",     None),   # transient: role radio on Master screen
    ("selected_categories", []),
    ("ob_names",            None),
    ("names_loaded",        False),
    ("pending_roles",       []),     # list of user dicts when multiple roles found
    ("login_error",         None),   # persisted error message across reruns
]:
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ---------------------------------------------------------------------------
# Lazy imports
# ---------------------------------------------------------------------------
from supabase_client import load_names, get_latest_date_str, get_categories, check_user_access, verify_user_login
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
            
/* Default (unselected) buttons — dark like dropdown */
[data-testid="stColumn"]:has(.master-left-marker) 
[data-testid="stBaseButton-secondary"] {
    background: #2A2A2A !important;
    color: #FFFFFF !important;
    border: 1px solid #2A2A2A !important;
}

/* Selected button — white */
[data-testid="stColumn"]:has(.master-left-marker) 
[data-testid="stBaseButton-primary"] {
    background: #FFFFFF !important;
    color: #1a1a1a !important;
    border: none !important;
    font-weight: 700 !important;
}

/* Restore red chips in multiselect */
[data-testid="stMultiSelect"] span[data-baseweb="tag"] {
    background: #FF4B4B !important;
    color: #FFFFFF !important;
    border-radius: 8px !important;
    font-weight: 500 !important;
}

/* Optional: better hover */
[data-testid="stColumn"]:has(.master-left-marker) 
[data-testid="stBaseButton-secondary"]:hover {
    background: #333333 !important;
    border-color: #333333 !important;
}
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Main app
# ---------------------------------------------------------------------------
def main():  # noqa: C901

    _logo_large = (
        f'<img src="data:image/png;base64,{_LOGO_B64}" '
        f'style="width:90px;height:90px;object-fit:contain;flex-shrink:0;">'
        if _LOGO_B64 else ""
    )
    _logo_med = (
        f'<img src="data:image/png;base64,{_LOGO_B64}" '
        f'style="width:68px;height:68px;object-fit:contain;margin-bottom:0.75rem;">'
        if _LOGO_B64 else ""
    )

    # ── ROLE SELECTION SCREEN (dual-role users) ───────────────────────────
    if st.session_state.pending_roles and not st.session_state.user_email:
        _pr = st.session_state.pending_roles

        import base64 as _b64r
        _role_img_b64 = ""
        try:
            with open(os.path.join(os.path.dirname(__file__), "assets", "LOGIN.png"), "rb") as _f:
                _role_img_b64 = _b64r.b64encode(_f.read()).decode()
        except Exception:
            pass

        st.markdown("""
<style>
[data-testid="stHorizontalBlock"]:has(.role-left-marker) {
    gap: 0 !important; border-radius: 20px !important;
    overflow: hidden !important; box-shadow: 0 24px 64px rgba(0,0,0,0.5) !important;
}
[data-testid="stColumn"]:has(.role-left-marker),
[data-testid="stColumn"]:has(.role-left-marker) > div,
[data-testid="stColumn"]:has(.role-left-marker) [data-testid="stVerticalBlockBorderWrapper"],
[data-testid="stColumn"]:has(.role-left-marker) [data-testid="stVerticalBlock"] {
    background: #F7941D !important; min-height: 520px !important;
}
[data-testid="stColumn"]:has(.role-left-marker) > div {
    padding: 2.5rem 3rem 2rem !important;
}
[data-testid="stColumn"]:has(.role-right-marker),
[data-testid="stColumn"]:has(.role-right-marker) > div,
[data-testid="stColumn"]:has(.role-right-marker) [data-testid="stVerticalBlockBorderWrapper"],
[data-testid="stColumn"]:has(.role-right-marker) [data-testid="stVerticalBlock"] {
    background: #2a2a2a !important; min-height: 520px !important;
    padding: 0 !important; overflow: hidden !important;
}
[data-testid="stColumn"]:has(.role-left-marker) [data-testid="stHorizontalBlock"] {
    gap: 0 !important; box-shadow: none !important;
    border-radius: 0 !important; overflow: visible !important;
}
[data-testid="stColumn"]:has(.role-left-marker) [data-testid="stColumn"],
[data-testid="stColumn"]:has(.role-left-marker) [data-testid="stColumn"] > div,
[data-testid="stColumn"]:has(.role-left-marker) [data-testid="stColumn"] [data-testid="stVerticalBlockBorderWrapper"],
[data-testid="stColumn"]:has(.role-left-marker) [data-testid="stColumn"] [data-testid="stVerticalBlock"] {
    background: transparent !important; min-height: unset !important; padding: 0 !important;
}
[data-testid="stColumn"]:has(.role-left-marker) [data-testid="stBaseButton-primary"] {
    background: #FFFFFF !important; color: #1a1a1a !important;
    border: none !important; font-weight: 700 !important;
}
</style>
""", unsafe_allow_html=True)

        _rl_left, _rl_right = st.columns([55, 45])

        with _rl_left:
            st.markdown('<div class="role-left-marker" style="display:none;"></div>', unsafe_allow_html=True)
            # Logo + title
            st.markdown(f"""
<div style="font-family:'Inter',system-ui,sans-serif;">
  <div style="display:flex;align-items:center;gap:1.4rem;">
    {'<img src="data:image/png;base64,' + _LOGO_B64 + '" style="width:100px;height:100px;border-radius:50%;object-fit:cover;flex-shrink:0;">' if _LOGO_B64 else ''}
    <div>
      <div style="font-size:3.6rem;font-weight:800;color:#fff;line-height:1;letter-spacing:-0.02em;">Retail AI</div>
      <div style="font-size:1.05rem;font-weight:500;color:rgba(255,255,255,0.88);margin-top:0.3rem;">AI Powered Sales Intelligence</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

            st.markdown('<div style="height:240px;"></div>', unsafe_allow_html=True)

            st.markdown("""
<div style="font-family:'Inter',sans-serif;margin-bottom:1rem;">
  <div style="font-size:1.45rem;font-weight:800;color:#fff;margin-bottom:0.35rem;">
    Welcome, you have multiple roles assigned
  </div>
  <div style="font-size:0.88rem;color:rgba(255,255,255,0.75);">
    Select who you want to go forward as, can be changed later on too
  </div>
</div>
""", unsafe_allow_html=True)

            _role_options = [f"{u.get('role', '')} - {u.get('name', '')}" for u in _pr]
            _role_choice = st.selectbox(
                "Select your role",
                options=_role_options,
                index=0,
                key="role_select",
                label_visibility="collapsed",
            )
            st.markdown("<div style='height:0.6rem'></div>", unsafe_allow_html=True)
            if st.button("Continue", key="role_confirm", type="primary", use_container_width=True):
                _idx = _role_options.index(_role_choice)
                _pr_user = _pr[_idx]
                st.session_state.user_email    = _pr_user["email"]
                st.session_state.user_role     = _pr_user["role"]
                st.session_state.user_name     = _pr_user["name"]
                st.session_state.pending_roles = []
                if _pr_user["role"] in ("RSM", "ASM"):
                    st.session_state.user_names    = [_pr_user["name"]]
                    st.session_state.selected_role = _pr_user["role"]
                st.rerun()

        with _rl_right:
            st.markdown('<div class="role-right-marker" style="display:none;"></div>', unsafe_allow_html=True)
            if _role_img_b64:
                st.markdown(
                    f'<img src="data:image/png;base64,{_role_img_b64}" '
                    f'style="width:100%;height:100%;min-height:520px;object-fit:cover;display:block;">',
                    unsafe_allow_html=True,
                )
        return

    # ── LOGIN SCREEN ──────────────────────────────────────────────────────
    if not st.session_state.user_email:

        st.markdown("""
<style>
[data-testid="stRadio"] > div { justify-content: center !important; }
[data-testid="stRadio"] { display: flex; justify-content: center; }
</style>
""", unsafe_allow_html=True)

        # First load: show loading screen while fetching name lists
        if not st.session_state.names_loaded:
            _screen = st.empty()
            with _screen.container():
                st.markdown(f"""
<div style="display:flex;flex-direction:column;justify-content:space-between;
    min-height:88vh;font-family:'Inter',system-ui,sans-serif;">
  <div style="background:#F7941D;border-radius:20px;padding:2rem 2.5rem;
      display:flex;align-items:center;gap:1.5rem;margin-top:0.5rem;">
    {_logo_large}
    <div>
      <div style="font-size:3rem;font-weight:800;color:#fff;line-height:1.1;">Retail AI</div>
      <div style="font-size:1.05rem;font-weight:600;color:rgba(255,255,255,0.88);margin-top:0.3rem;">AI Powered Sales Intelligence</div>
    </div>
  </div>
  <div style="text-align:center;padding-bottom:3.5rem;">
    <div style="font-size:1.05rem;font-weight:700;color:#fff;margin-bottom:0.9rem;
        display:flex;align-items:center;justify-content:center;gap:0.6rem;">
      Loading, please wait
      <span style="background:#fff500;color:#1a1a1a;border-radius:20px;
          padding:0.25rem 0.85rem;font-size:0.82rem;font-weight:600;">
        do not refresh the page, takes upto two minute.
      </span>
    </div>
    <div style="width:80%;margin:0 auto;background:#2A2A2A;border-radius:4px;height:7px;overflow:hidden;">
      <div class="loading-bar-fill"></div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

            st.session_state.ob_names = load_names()
            st.session_state.names_loaded = True

            with _screen.container():
                st.markdown(f"""
<div style="display:flex;flex-direction:column;justify-content:space-between;
    min-height:88vh;font-family:'Inter',system-ui,sans-serif;">
  <div style="background:#F7941D;border-radius:20px;padding:2rem 2.5rem;
      display:flex;align-items:center;gap:1.5rem;margin-top:0.5rem;">
    {_logo_large}
    <div>
      <div style="font-size:3rem;font-weight:800;color:#fff;line-height:1.1;">Retail AI</div>
      <div style="font-size:1.05rem;font-weight:600;color:rgba(255,255,255,0.88);margin-top:0.3rem;">AI Powered Sales Intelligence</div>
    </div>
  </div>
  <div style="text-align:center;padding-bottom:3.5rem;">
    <div style="font-size:1.05rem;font-weight:700;color:#fff;margin-bottom:0.9rem;
        display:flex;align-items:center;justify-content:center;gap:0.6rem;">
      Ready
      <span style="background:#4CAF50;color:#fff;border-radius:20px;
          padding:0.25rem 0.85rem;font-size:0.82rem;font-weight:600;">connected</span>
    </div>
    <div style="width:80%;margin:0 auto;background:#2A2A2A;border-radius:4px;height:7px;overflow:hidden;">
      <div style="background:#F7941D;height:100%;width:100%;border-radius:4px;"></div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)
            _time.sleep(0.6)
            _screen.empty()

        # Load login illustration
        import base64 as _b64
        _login_img_b64 = ""
        try:
            with open(os.path.join(os.path.dirname(__file__), "assets", "LOGIN.png"), "rb") as _f:
                _login_img_b64 = _b64.b64encode(_f.read()).decode()
        except Exception:
            pass

        # Login card CSS
        st.markdown("""
<style>
/* ── Overall card ── */
[data-testid="stHorizontalBlock"]:has(.login-left-marker) {
    gap: 0 !important;
    border-radius: 20px !important;
    overflow: hidden !important;
    box-shadow: 0 24px 64px rgba(0,0,0,0.5) !important;
}
/* ── Left orange panel ── */
[data-testid="stColumn"]:has(.login-left-marker),
[data-testid="stColumn"]:has(.login-left-marker) > div,
[data-testid="stColumn"]:has(.login-left-marker) [data-testid="stVerticalBlockBorderWrapper"],
[data-testid="stColumn"]:has(.login-left-marker) [data-testid="stVerticalBlock"] {
    background: #F7941D !important;
    min-height: 520px !important;
}
[data-testid="stColumn"]:has(.login-left-marker) > div {
    padding: 2.5rem 3rem 2rem !important;
}
/* ── Right white panel ── */
[data-testid="stColumn"]:has(.login-right-marker),
[data-testid="stColumn"]:has(.login-right-marker) > div,
[data-testid="stColumn"]:has(.login-right-marker) [data-testid="stVerticalBlockBorderWrapper"],
[data-testid="stColumn"]:has(.login-right-marker) [data-testid="stVerticalBlock"] {
    background: #2a2a2a !important;
    min-height: 520px !important;
    padding: 0 !important;
    overflow: hidden !important;
}
/* ── Nested columns inside left panel stay transparent ── */
[data-testid="stColumn"]:has(.login-left-marker) [data-testid="stHorizontalBlock"] {
    gap: 0 !important; box-shadow: none !important;
    border-radius: 0 !important; overflow: visible !important;
}
[data-testid="stColumn"]:has(.login-left-marker) [data-testid="stColumn"],
[data-testid="stColumn"]:has(.login-left-marker) [data-testid="stColumn"] > div,
[data-testid="stColumn"]:has(.login-left-marker) [data-testid="stColumn"] [data-testid="stVerticalBlockBorderWrapper"],
[data-testid="stColumn"]:has(.login-left-marker) [data-testid="stColumn"] [data-testid="stVerticalBlock"] {
    background: transparent !important;
    min-height: unset !important;
    padding: 0 !important;
}
[data-testid="stColumn"]:has(.login-left-marker) [data-testid="stBaseButton-secondary"] {
    background: #FFFFFF !important;
    color: #2a2a2a !important;
}
</style>
""", unsafe_allow_html=True)

        _lc_left, _lc_right = st.columns([55, 45])

        with _lc_left:
            st.markdown('<div class="login-left-marker" style="display:none;"></div>', unsafe_allow_html=True)
            # Logo + title
            st.markdown(f"""
<div style="font-family:'Inter',system-ui,sans-serif;">
  <div style="display:flex;align-items:center;gap:1.4rem;">
    {'<img src="data:image/png;base64,' + _LOGO_B64 + '" style="width:100px;height:100px;border-radius:50%;object-fit:cover;flex-shrink:0;">' if _LOGO_B64 else ''}
    <div>
      <div style="font-size:3.6rem;font-weight:800;color:#fff;line-height:1.05;letter-spacing:-0.03em;">Retail AI</div>
      <div style="font-size:1.05rem;font-weight:500;color:rgba(255,255,255,0.85);margin-top:0.3rem;letter-spacing:0.01em;">
        AI Powered Sales Intelligence
      </div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

            # Spacer — pushes fields to the bottom of the panel
            st.markdown('<div style="height:400px;"></div>', unsafe_allow_html=True)

            # Email field
            _email_val = st.text_input(
                "email",
                placeholder="enter your GO DESi email ID (you@godesi.in)",
                key="login_email_input",
                label_visibility="collapsed",
            )

            # Password field
            _pwd_val = st.text_input(
                "password",
                type="password",
                placeholder="enter your assigned password",
                key="login_pwd_input",
                label_visibility="collapsed",
            )

            # Sign in button — full width
            _signin_clicked = st.button("sign in", key="login_signin", use_container_width=True)

            # Persisted error pill
            if st.session_state.login_error:
                st.markdown(
                    f'<div style="background:#F5D842;color:#1a1a1a;border-radius:20px;'
                    f'padding:0.35rem 1.1rem;font-size:0.84rem;font-weight:700;'
                    f'display:inline-block;margin-top:0.4rem;">'
                    f'{st.session_state.login_error}</div>',
                    unsafe_allow_html=True,
                )
                st.session_state.login_error = None

            if _signin_clicked:
                if not _email_val.strip():
                    st.session_state.login_error = "Please enter your email."
                    st.rerun()
                elif not _pwd_val.strip():
                    st.session_state.login_error = "Please enter your password."
                    st.rerun()
                else:
                    # Step 1: check email exists
                    _found = check_user_access(_email_val.strip())
                    if len(_found) == 0:
                        st.session_state.login_error = (
                            "Incorrect email ID, please try again or contact your manager."
                        )
                        st.rerun()
                    else:
                        # Step 2: verify password
                        from supabase_client import hash_password as _hp
                        _matched = verify_user_login(_email_val.strip(), _hp(_pwd_val))
                        if len(_matched) == 0:
                            st.session_state.login_error = "Incorrect password. Please try again."
                            st.rerun()
                        elif len(_matched) == 1:
                            _user = _matched[0]
                            st.session_state.user_email  = _user["email"]
                            st.session_state.user_role   = _user["role"]
                            st.session_state.user_name   = _user["name"]
                            if _user["role"] in ("RSM", "ASM"):
                                st.session_state.user_names    = [_user["name"]]
                                st.session_state.selected_role = _user["role"]
                            st.rerun()
                        else:
                            st.session_state.pending_roles = _matched
                            st.rerun()

        with _lc_right:
            st.markdown('<div class="login-right-marker" style="display:none;"></div>', unsafe_allow_html=True)
            if _login_img_b64:
                st.markdown(
                    f'<img src="data:image/png;base64,{_login_img_b64}" '
                    f'style="width:100%;height:100%;min-height:520px;'
                    f'object-fit:cover;display:block;">',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    '<div style="background:#f5f5f5;min-height:520px;width:100%;"></div>',
                    unsafe_allow_html=True,
                )
        return

    # ── MASTER SCREEN ─────────────────────────────────────────────────────
    if st.session_state.user_role == "Master" and not st.session_state.master_identity_set:

        import base64 as _b64m
        _master_img_b64 = ""
        try:
            with open(os.path.join(os.path.dirname(__file__), "assets", "LOGIN.png"), "rb") as _f:
                _master_img_b64 = _b64m.b64encode(_f.read()).decode()
        except Exception:
            pass

        st.markdown("""
<style>
/* ── Master card ── */
[data-testid="stHorizontalBlock"]:has(.master-left-marker) {
    gap: 0 !important;
    border-radius: 20px !important;
    overflow: hidden !important;
    box-shadow: 0 24px 64px rgba(0,0,0,0.5) !important;
}
[data-testid="stColumn"]:has(.master-left-marker),
[data-testid="stColumn"]:has(.master-left-marker) > div,
[data-testid="stColumn"]:has(.master-left-marker) [data-testid="stVerticalBlockBorderWrapper"],
[data-testid="stColumn"]:has(.master-left-marker) [data-testid="stVerticalBlock"] {
    background: #F7941D !important;
    min-height: 520px !important;
}
[data-testid="stColumn"]:has(.master-left-marker) > div {
    padding: 2.5rem 3rem 2rem !important;
}
[data-testid="stColumn"]:has(.master-right-marker),
[data-testid="stColumn"]:has(.master-right-marker) > div,
[data-testid="stColumn"]:has(.master-right-marker) [data-testid="stVerticalBlockBorderWrapper"],
[data-testid="stColumn"]:has(.master-right-marker) [data-testid="stVerticalBlock"] {
    background: #2a2a2a !important;
    min-height: 520px !important;
    padding: 0 !important;
    overflow: hidden !important;
}
[data-testid="stColumn"]:has(.master-left-marker) [data-testid="stHorizontalBlock"] {
    gap: 0 !important; box-shadow: none !important;
    border-radius: 0 !important; overflow: visible !important;
}
[data-testid="stColumn"]:has(.master-left-marker) [data-testid="stColumn"],
[data-testid="stColumn"]:has(.master-left-marker) [data-testid="stColumn"] > div,
[data-testid="stColumn"]:has(.master-left-marker) [data-testid="stColumn"] [data-testid="stVerticalBlockBorderWrapper"],
[data-testid="stColumn"]:has(.master-left-marker) [data-testid="stColumn"] [data-testid="stVerticalBlock"] {
    background: transparent !important;
    min-height: unset !important;
    padding: 0 !important;
}
/* Primary buttons inside master panel = white (selected RSM/ASM + Enter) */
[data-testid="stColumn"]:has(.master-left-marker) [data-testid="stBaseButton-primary"] {
    background: #FFFFFF !important;
    color: #1a1a1a !important;
    border: none !important;
    font-weight: 700 !important;
}
[data-testid="stColumn"]:has(.master-left-marker) [data-testid="stBaseButton-primary"]:hover {
    opacity: 0.9 !important;
}
/* Yellow admin button — :not(:has(.master-left-marker)) prevents bleeding to outer column */
[data-testid="stColumn"]:has(.master-admin-inner):not(:has(.master-left-marker)) [data-testid="stBaseButton-secondary"] {
    background: #FFE600 !important;
    color: #1a1a1a !important;
    border: none !important;
    font-weight: 700 !important;
    min-height: 48px !important;
}
[data-testid="stColumn"]:has(.master-admin-inner):not(:has(.master-left-marker)) [data-testid="stBaseButton-secondary"]:hover {
    background: #f0d800 !important;
    opacity: 1 !important;
}
</style>
""", unsafe_allow_html=True)

        _ob_names = st.session_state.ob_names or {}
        _m_role = st.session_state.onboarding_role

        _mc_left, _mc_right = st.columns([55, 45])

        with _mc_left:
            st.markdown('<div class="master-left-marker" style="display:none;"></div>', unsafe_allow_html=True)

            # Logo + title
            st.markdown(f"""
<div style="font-family:'Inter',system-ui,sans-serif;">
  <div style="display:flex;align-items:center;gap:1.4rem;">
    {'<img src="data:image/png;base64,' + _LOGO_B64 + '" style="width:100px;height:100px;border-radius:50%;object-fit:cover;flex-shrink:0;">' if _LOGO_B64 else ''}
    <div>
      <div style="font-size:3.6rem;font-weight:800;color:#fff;line-height:1;letter-spacing:-0.02em;">Retail AI</div>
      <div style="font-size:1.05rem;font-weight:500;color:rgba(255,255,255,0.88);margin-top:0.3rem;">AI Powered Sales Intelligence</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

            # Spacer — pushes content to bottom of panel
            st.markdown('<div style="height:360px;"></div>', unsafe_allow_html=True)

            # Welcome heading
            st.markdown("""
<div style="font-family:'Inter',sans-serif;margin-bottom:0.2rem;">
  <div style="font-size:1.45rem;font-weight:800;color:#fff;margin-bottom:0.35rem;">
    Welcome, you are a master user
  </div>
  <div style="font-size:0.88rem;color:rgba(255,255,255,0.75);">
    Select an identity to enter as, or go straight to settings
  </div>
</div>
""", unsafe_allow_html=True)

            # RSM / ASM buttons (secondary = dark by default in dark theme)
            _rb1, _spacer, _rb2 = st.columns([1, 0.04, 1])
            with _rb1:
                if st.button("RSM", key="master_rsm_btn",
                            type="primary" if _m_role == "RSM" else "secondary",
                            use_container_width=True):
                    st.session_state.onboarding_role = "RSM"
                    st.rerun()
            with _rb2:
                if st.button("ASM", key="master_asm_btn",
                            type="primary" if _m_role == "ASM" else "secondary",
                            use_container_width=True):
                    st.session_state.onboarding_role = "ASM"
                    st.rerun()

            st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)

            # Name selector
            _name_list = (
                _ob_names.get("rsm_names", []) if _m_role == "RSM"
                else _ob_names.get("asm_names", [])
            )

            if not _name_list:
                st.warning("Name list not loaded. Try Refresh Data.")
            else:
                st.markdown(
                    f'<p style="font-size:0.85rem;color:rgba(255,255,255,0.8);font-weight:500;margin:0 0 0.3rem;">Select an {_m_role}s name</p>',
                    unsafe_allow_html=True,
                )
                _m_selected = st.multiselect(
                    label="Name",
                    options=sorted(_name_list),
                    placeholder="Select one or more names...",
                    key="master_name_select",
                    label_visibility="collapsed",
                )
                if _m_selected:
                    st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
                    if st.button("Enter Retail AI →", key="master_enter",
                                 type="primary", use_container_width=True):
                        st.session_state.user_names          = _m_selected
                        st.session_state.user_name           = _m_selected[0]
                        st.session_state.selected_role       = _m_role
                        st.session_state.master_identity_set = True
                        st.session_state.onboarding_role     = None
                        st.rerun()

            # Yellow admin button — nested column so :has() targets it specifically
            _admin_col, _ = st.columns([1, 0.001])
            with _admin_col:
                st.markdown('<div class="master-admin-inner" style="display:none;"></div>', unsafe_allow_html=True)
                if st.button("upload data / manage access?", key="master_admin",
                             use_container_width=True):
                    st.switch_page("pages/admin.py")

        with _mc_right:
            st.markdown('<div class="master-right-marker" style="display:none;"></div>', unsafe_allow_html=True)
            if _master_img_b64:
                st.markdown(
                    f'<img src="data:image/png;base64,{_master_img_b64}" '
                    f'style="width:100%;height:100%;min-height:520px;'
                    f'object-fit:cover;display:block;">',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    '<div style="background:#2a2a2a;min-height:520px;width:100%;"></div>',
                    unsafe_allow_html=True,
                )

        return

    # ── CHAT UI ───────────────────────────────────────────────────────────

    render_header()

    # ── Toolbar ──────────────────────────────────────────────────────────
    t1, t2, t3, t4 = st.columns([5, 2, 2, 2])

    def _reset_session():
        for _k in ("user_email","user_role","user_name","user_names","selected_role",
                   "onboarding_role","messages","session_context","selected_categories",
                   "pending_question","pending_display","starter_clicked"):
            st.session_state[_k] = (
                [] if _k in ("user_names","selected_categories","messages") else
                {} if _k == "session_context" else
                None
            )
        st.session_state.master_identity_set = False
        st.session_state.names_loaded = False
        st.session_state.pending_roles = []
        st.session_state.login_error = None

    # Determine effective role (Master who chose RSM/ASM uses selected_role)
    _effective_role = st.session_state.get("selected_role") or st.session_state.get("user_role")

    with t1:
        _names = st.session_state.user_names or []
        if len(_names) == 1:
            _badge = f"{_names[0]} ({_effective_role})"
        elif len(_names) == 2:
            _badge = f"{_names[0]}, {_names[1]} ({_effective_role})"
        else:
            _badge = f"{_names[0]} +{len(_names)-1} others ({_effective_role})"
        if st.button(_badge, key="badge_switch", help="Click to switch user"):
            _reset_session()
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
            _reset_session()
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
    _names  = st.session_state.get("user_names", [])
    _nm_str = ", ".join(_names) if _names else "your team"
    if _effective_role == "RSM":
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
                    "rsm" if _effective_role == "RSM" else
                    "asm" if _effective_role == "ASM" else None
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
