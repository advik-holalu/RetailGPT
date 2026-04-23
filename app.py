"""
app.py
RetailAI — Main Streamlit chat interface.
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
    page_title="RetailAI",
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
    ("_transitioning",      False),  # show loading screen between onboarding → chat
]:
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ---------------------------------------------------------------------------
# Lazy imports
# ---------------------------------------------------------------------------
from supabase_client import load_names, get_latest_date_str, get_categories, check_user_access, verify_user_login
from query_engine import QueryEngine


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

/* ── Base ── */
* { font-family: 'Inter', system-ui, sans-serif; box-sizing: border-box; }

/* Hide ALL Streamlit chrome — header tag + all known data-testid variants */
#MainMenu, footer, header,
[data-testid="stHeader"],
[data-testid="stDecoration"],
[data-testid="stToolbar"],
[data-testid="stStatusWidget"],
[data-testid="stAppDeployButton"],
[data-testid="stMainMenuPopover"] { display: none !important; }

html, body, [data-testid="stAppViewContainer"] { overflow-x: hidden !important; }

/* ── Page layout ── */
.block-container {
    padding-top: 0 !important;
    padding-bottom: 0 !important;
    max-width: 100% !important;
    padding-left: 3.5rem !important;
    padding-right: 3.5rem !important;
}

/* ── Onboarding screens: visual styling only, zero layout hacks ──────
   No height/overflow manipulation. Let Streamlit size naturally.
   Card is content-height → all 4 corners visible → no scroll needed.
───────────────────────────────────────────────────────────────────── */
[data-testid="stHorizontalBlock"]:has(.login-left-marker),
[data-testid="stHorizontalBlock"]:has(.loader-left-marker),
[data-testid="stHorizontalBlock"]:has(.master-left-marker),
[data-testid="stHorizontalBlock"]:has(.role-left-marker) {
    gap: 0 !important;
    border-radius: 20px !important;
    overflow: hidden !important;
    box-shadow: 0 24px 64px rgba(0,0,0,0.5) !important;
}
[data-testid="stColumn"]:has(.login-left-marker),
[data-testid="stColumn"]:has(.login-left-marker) > div,
[data-testid="stColumn"]:has(.login-left-marker) [data-testid="stVerticalBlockBorderWrapper"],
[data-testid="stColumn"]:has(.login-left-marker) [data-testid="stVerticalBlock"],
[data-testid="stColumn"]:has(.loader-left-marker),
[data-testid="stColumn"]:has(.loader-left-marker) > div,
[data-testid="stColumn"]:has(.loader-left-marker) [data-testid="stVerticalBlockBorderWrapper"],
[data-testid="stColumn"]:has(.loader-left-marker) [data-testid="stVerticalBlock"],
[data-testid="stColumn"]:has(.master-left-marker),
[data-testid="stColumn"]:has(.master-left-marker) > div,
[data-testid="stColumn"]:has(.master-left-marker) [data-testid="stVerticalBlockBorderWrapper"],
[data-testid="stColumn"]:has(.master-left-marker) [data-testid="stVerticalBlock"],
[data-testid="stColumn"]:has(.role-left-marker),
[data-testid="stColumn"]:has(.role-left-marker) > div,
[data-testid="stColumn"]:has(.role-left-marker) [data-testid="stVerticalBlockBorderWrapper"],
[data-testid="stColumn"]:has(.role-left-marker) [data-testid="stVerticalBlock"] {
    background: #F7941D !important;
}
[data-testid="stColumn"]:has(.login-left-marker) > div,
[data-testid="stColumn"]:has(.loader-left-marker) > div,
[data-testid="stColumn"]:has(.master-left-marker) > div,
[data-testid="stColumn"]:has(.role-left-marker) > div {
    padding: 2.5rem 3rem !important;
}
[data-testid="stColumn"]:has(.login-right-marker),
[data-testid="stColumn"]:has(.login-right-marker) > div,
[data-testid="stColumn"]:has(.login-right-marker) [data-testid="stVerticalBlockBorderWrapper"],
[data-testid="stColumn"]:has(.login-right-marker) [data-testid="stVerticalBlock"],
[data-testid="stColumn"]:has(.loader-right-marker),
[data-testid="stColumn"]:has(.loader-right-marker) > div,
[data-testid="stColumn"]:has(.loader-right-marker) [data-testid="stVerticalBlockBorderWrapper"],
[data-testid="stColumn"]:has(.loader-right-marker) [data-testid="stVerticalBlock"],
[data-testid="stColumn"]:has(.master-right-marker),
[data-testid="stColumn"]:has(.master-right-marker) > div,
[data-testid="stColumn"]:has(.master-right-marker) [data-testid="stVerticalBlockBorderWrapper"],
[data-testid="stColumn"]:has(.master-right-marker) [data-testid="stVerticalBlock"],
[data-testid="stColumn"]:has(.role-right-marker),
[data-testid="stColumn"]:has(.role-right-marker) > div,
[data-testid="stColumn"]:has(.role-right-marker) [data-testid="stVerticalBlockBorderWrapper"],
[data-testid="stColumn"]:has(.role-right-marker) [data-testid="stVerticalBlock"] {
    background: #2a2a2a !important;
    padding: 0 !important;
    overflow: hidden !important;
}
/* Nested columns inside left panels stay transparent */
[data-testid="stColumn"]:has(.login-left-marker) [data-testid="stColumn"],
[data-testid="stColumn"]:has(.login-left-marker) [data-testid="stColumn"] > div,
[data-testid="stColumn"]:has(.master-left-marker) [data-testid="stColumn"],
[data-testid="stColumn"]:has(.master-left-marker) [data-testid="stColumn"] > div,
[data-testid="stColumn"]:has(.role-left-marker) [data-testid="stColumn"],
[data-testid="stColumn"]:has(.role-left-marker) [data-testid="stColumn"] > div {
    background: transparent !important;
    padding: 0 !important;
}

/* ── Toolbar pills (owned HTML) ── */
.user-badge-pill {
    background: #F7941D;
    color: #fff;
    border-radius: 10px;
    padding: 0.55rem 1rem;
    font-size: 0.85rem;
    font-weight: 600;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    display: block;
}
.toolbar-status {
    background: #1A1A1A;
    border: 1px solid #2A2A2A;
    border-radius: 10px;
    padding: 0.55rem 1rem;
    font-size: 0.82rem;
    display: block;
}
/* ── Category filter label ── */
[data-testid="stMultiSelect"][data-key="cat_filter"] label {
    color: #F7941D !important;
    font-weight: 600 !important;
    font-size: 0.86rem !important;
}
.status-ok   { color: #4CAF50; }
.status-warn { color: #F7941D; }

/* ── Switch user button — yellow, scoped ── */
[data-testid="stColumn"]:has(.switch-user-marker) button {
    background: #E6FF00 !important;
    color: #1a1a1a !important;
    border: none !important;
    font-weight: 700 !important;
}

/* ── Suggested prompts ── */
.prompt-card-title {
    background: #F7941D;
    color: #fff;
    border-radius: 10px;
    padding: 0.55rem 1rem;
    font-size: 0.85rem;
    font-weight: 700;
    display: block;
    margin-bottom: 0.75rem;
}
.prompt-group-badge-sales {
    display: block;
    background: #954fc0;
    color: #fff;
    border-radius: 8px;
    padding: 0.4rem 1rem;
    font-size: 0.82rem;
    font-weight: 600;
    margin-bottom: 0.4rem;
    text-align: center;
}
.prompt-group-badge-prod {
    display: block;
    background: #2E7D32;
    color: #fff;
    border-radius: 8px;
    padding: 0.4rem 1rem;
    font-size: 0.82rem;
    font-weight: 600;
    margin-bottom: 0.4rem;
    text-align: center;
}
/* ── Prompt buttons: sales column (purple) ── */
[data-testid="stColumn"]:has(.prompt-group-badge-sales) button {
    text-align: left !important;
    border-left: 3px solid #954fc0 !important;
    font-size: 0.875rem !important;
    font-weight: 400 !important;
    transition: background 0.15s, color 0.15s !important;
}
[data-testid="stColumn"]:has(.prompt-group-badge-sales) button:hover {
    background: rgba(149, 79, 192, 0.18) !important;
    border-left-color: #b06dd4 !important;
    color: #ffffff !important;
}

/* ── Prompt buttons: productivity column (green) ── */
[data-testid="stColumn"]:has(.prompt-group-badge-prod) button {
    text-align: left !important;
    border-left: 3px solid #2E7D32 !important;
    font-size: 0.875rem !important;
    font-weight: 400 !important;
    transition: background 0.15s, color 0.15s !important;
}
[data-testid="stColumn"]:has(.prompt-group-badge-prod) button:hover {
    background: rgba(46, 125, 50, 0.18) !important;
    border-left-color: #43a047 !important;
    color: #ffffff !important;
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
.bubble-bot .table-wrapper {
    border-radius: 12px;
    overflow: hidden;
    overflow-x: auto;
    margin: 0.9rem 0;
    border: 1px solid #333;
    -webkit-overflow-scrolling: touch;
}
.bubble-bot table {
    border-collapse: collapse;
    width: 100%;
    font-size: 0.84rem;
}
.bubble-bot table th {
    background: #F7941D;
    color: #fff;
    padding: 0.5rem 1rem;
    text-align: left;
    font-weight: 700;
    font-size: 0.76rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    white-space: nowrap;
}
.bubble-bot table td {
    padding: 0.42rem 1rem;
    border-bottom: 1px solid #252525;
    color: #EEEEEE;
    white-space: nowrap;
}
.bubble-bot table tr:nth-child(even) td { background: #1C1C1C; }
.bubble-bot table tr:nth-child(odd) td  { background: #161616; }
.bubble-bot table tr:last-child td { border-bottom: none; }
.bubble-bot table tr:hover td { background: #2A2A2A !important; }

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

/* ── Welcome card ── */
.welcome-card-inner {
    padding: 2rem 2rem 1rem;
    text-align: center;
}
.welcome-card-title {
    font-size: 1.45rem;
    font-weight: 700;
    color: #FFFFFF;
    margin-bottom: 0.5rem;
}
.welcome-card-sub {
    font-size: 0.9rem;
    color: #888888;
}

/* Reset chat button — orange */
[data-testid="stColumn"]:has(.reset-chat-marker) button {
    background: #F7941D !important;
    color: #fff !important;
    border: none !important;
    font-weight: 600 !important;
}

/* ── Send button — orange ── */
[data-testid="stFormSubmitButton"] > button {
    background: #F7941D !important;
    color: #fff !important;
    border: none !important;
    font-weight: 700 !important;
}
[data-testid="stFormSubmitButton"] > button:hover {
    background: #e8820a !important;
    color: #fff !important;
}

/* ── Remove form's own border/padding so it blends into parent container ── */
[data-testid="stForm"] {
    border: none !important;
    padding: 0 !important;
    background: transparent !important;
}

/* ── Loading bar (onboarding) ── */
@keyframes bar-to-95 {
    0%   { width: 5%;  }
    30%  { width: 50%; }
    70%  { width: 80%; }
    100% { width: 95%; }
}
.loading-bar-fill {
    background: #ffffff; height: 100%; border-radius: 3px;
    animation: bar-to-95 15s ease-out forwards;
}

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-thumb { background: #2A2A2A; border-radius: 2px; }
::-webkit-scrollbar-thumb:hover { background: #F7941D; }

/* ── Multiselect chip color ── */
[data-testid="stMultiSelect"] span[data-baseweb="tag"] {
    background: #FF4B4B !important;
    color: #FFFFFF !important;
    border-radius: 8px !important;
    font-weight: 500 !important;
}

/* ═══════════════════════════════════
   RESPONSIVE — Tablet (≤ 900px)
═══════════════════════════════════ */
@media (max-width: 900px) {
    .block-container { padding-left: 1.2rem !important; padding-right: 1.2rem !important; }
    .bubble-user { max-width: 82%; }
    .bubble-bot  { max-width: 92%; }
}

/* ═══════════════════════════════════
   RESPONSIVE — Mobile (≤ 640px)
═══════════════════════════════════ */
@media (max-width: 640px) {
    .block-container { padding-left: 0.75rem !important; padding-right: 0.75rem !important; }
    .bubble-user, .bubble-bot { max-width: 96%; font-size: 0.88rem; }
    .prompts-section-label { font-size: 0.88rem; }
    .info-box-amber { font-size: 0.76rem; }
    .bubble-bot table { font-size: 0.78rem; }
    .bubble-bot table th, .bubble-bot table td { padding: 0.3rem 0.5rem; }
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

    # ── TRANSITION LOADING SCREEN ────────────────────────────────────────
    if st.session_state._transitioning:
        st.session_state._transitioning = False
        _tl, _tr = st.columns([55, 45])
        with _tl:
            st.markdown('<div class="loader-left-marker" style="display:none;"></div>', unsafe_allow_html=True)
            st.markdown("""
<div style="font-family:'Inter',sans-serif;">
  <div style="font-size:1rem;font-weight:700;color:#fff;margin-bottom:0.75rem;
      display:flex;align-items:center;gap:0.6rem;">
    Loading
    <span style="background:#fff;color:#1a1a1a;border-radius:20px;
        padding:0.2rem 0.75rem;font-size:0.78rem;font-weight:600;">
      just a moment...
    </span>
  </div>
  <div style="background:rgba(255,255,255,0.25);border-radius:4px;height:6px;overflow:hidden;">
    <div class="loading-bar-fill"></div>
  </div>
</div>
""", unsafe_allow_html=True)
        with _tr:
            st.markdown('<div class="loader-right-marker" style="display:none;"></div>', unsafe_allow_html=True)
        _time.sleep(0.35)
        st.rerun()
        return

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
[data-testid="stColumn"]:has(.role-left-marker) [data-testid="stBaseButton-primary"] {
    background: #FFFFFF !important; color: #1a1a1a !important;
    border: none !important; font-weight: 700 !important;
}
</style>
""", unsafe_allow_html=True)

        _rl_left, _rl_right = st.columns([55, 45])

        with _rl_left:
            st.markdown('<div class="role-left-marker" style="display:none;"></div>', unsafe_allow_html=True)

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
                st.session_state._transitioning = True
                st.rerun()

            # Logo + title (bottom)
            st.markdown(f"""
<div style="font-family:'Inter',system-ui,sans-serif;margin-top:1.5rem;">
  <div style="display:flex;align-items:center;gap:1.4rem;">
    {'<img src="data:image/png;base64,' + _LOGO_B64 + '" style="width:100px;height:100px;border-radius:50%;object-fit:cover;flex-shrink:0;">' if _LOGO_B64 else ''}
    <div>
      <div style="font-size:3.6rem;font-weight:800;color:#fff;line-height:1;letter-spacing:-0.02em;">RetailAI</div>
      <div style="font-size:1.05rem;font-weight:500;color:rgba(255,255,255,0.88);margin-top:0.3rem;">AI Powered Sales Intelligence</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

        with _rl_right:
            st.markdown('<div class="role-right-marker" style="display:none;"></div>', unsafe_allow_html=True)
            if _role_img_b64:
                st.markdown(
                    f'<img src="data:image/png;base64,{_role_img_b64}" '
                    f'style="width:100%;height:100%;height:100%;object-fit:cover;display:block;">',
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
            import base64 as _b64l
            _loader_img_b64 = ""
            try:
                with open(os.path.join(os.path.dirname(__file__), "assets", "LOGIN.png"), "rb") as _f:
                    _loader_img_b64 = _b64l.b64encode(_f.read()).decode()
            except Exception:
                pass

            _loader_css = ""  # all visual styling handled by global CSS

            def _render_loader(status_html):
                st.markdown(_loader_css, unsafe_allow_html=True)
                _ll, _lr = st.columns([55, 45])
                with _ll:
                    st.markdown('<div class="loader-left-marker" style="display:none;"></div>', unsafe_allow_html=True)

                    st.markdown(status_html, unsafe_allow_html=True)

                    # Logo + title (bottom)
                    st.markdown(f"""
<div style="font-family:'Inter',system-ui,sans-serif;margin-top:30rem;">
  <div style="display:flex;align-items:center;gap:1.4rem;">
    {'<img src="data:image/png;base64,' + _LOGO_B64 + '" style="width:100px;height:100px;border-radius:50%;object-fit:cover;flex-shrink:0;">' if _LOGO_B64 else ''}
    <div>
      <div style="font-size:3.6rem;font-weight:800;color:#fff;line-height:1;letter-spacing:-0.02em;">RetailAI</div>
      <div style="font-size:1.05rem;font-weight:500;color:rgba(255,255,255,0.88);margin-top:0.3rem;">AI Powered Sales Intelligence</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)
                with _lr:
                    st.markdown('<div class="loader-right-marker" style="display:none;"></div>', unsafe_allow_html=True)
                    if _loader_img_b64:
                        st.markdown(
                            f'<img src="data:image/png;base64,{_loader_img_b64}" '
                            f'style="width:100%;height:100%;object-fit:cover;display:block;">',
                            unsafe_allow_html=True,
                        )

            _screen = st.empty()
            with _screen.container():
                _render_loader("""
<div style="font-family:'Inter',sans-serif;">
  <div style="font-size:1rem;font-weight:700;color:#fff;margin-bottom:0.75rem;
      display:flex;align-items:center;gap:0.6rem;">
    Loading, please wait
    <span style="background:#FFE600;color:#1a1a1a;border-radius:20px;
        padding:0.2rem 0.75rem;font-size:0.78rem;font-weight:600;">
      do not refresh — takes up to 2 min
    </span>
  </div>
  <div style="background:#2A2A2A;border-radius:4px;height:6px;overflow:hidden;">
    <div class="loading-bar-fill"></div>
  </div>
</div>
""")

            st.session_state.ob_names = load_names()
            st.session_state.names_loaded = True

            with _screen.container():
                _render_loader("""
<div style="font-family:'Inter',sans-serif;">
  <div style="font-size:1rem;font-weight:700;color:#fff;margin-bottom:0.75rem;
      display:flex;align-items:center;gap:0.6rem;">
    Ready
    <span style="background:#4CAF50;color:#fff;border-radius:20px;
        padding:0.2rem 0.75rem;font-size:0.78rem;font-weight:600;">connected</span>
  </div>
  <div style="background:#2A2A2A;border-radius:4px;height:6px;overflow:hidden;">
    <div style="background:#fff;height:100%;width:100%;border-radius:4px;"></div>
  </div>
</div>
""")
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

        # Login: sign-in button white (screen-specific style only)
        st.markdown("""
<style>
[data-testid="stColumn"]:has(.login-left-marker) [data-testid="stBaseButton-secondary"] {
    background: #FFFFFF !important; color: #2a2a2a !important;
}
</style>
""", unsafe_allow_html=True)

        _lc_left, _lc_right = st.columns([55, 45])

        with _lc_left:
            st.markdown('<div class="login-left-marker" style="display:none;"></div>', unsafe_allow_html=True)

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

            # Logo + title (bottom)
            st.markdown(f"""
<div style="font-family:'Inter',system-ui,sans-serif;margin-top:24rem;">
  <div style="display:flex;align-items:center;gap:1.4rem;">
    {'<img src="data:image/png;base64,' + _LOGO_B64 + '" style="width:100px;height:100px;border-radius:50%;object-fit:cover;flex-shrink:0;">' if _LOGO_B64 else ''}
    <div>
      <div style="font-size:3.6rem;font-weight:800;color:#fff;line-height:1.05;letter-spacing:-0.03em;">RetailAI</div>
      <div style="font-size:1.05rem;font-weight:500;color:rgba(255,255,255,0.85);margin-top:0.3rem;letter-spacing:0.01em;">
        AI Powered Sales Intelligence
      </div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

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
                            st.session_state._transitioning = True
                            st.rerun()
                        else:
                            st.session_state.pending_roles = _matched
                            st.rerun()

        with _lc_right:
            st.markdown('<div class="login-right-marker" style="display:none;"></div>', unsafe_allow_html=True)
            if _login_img_b64:
                st.markdown(
                    f'<img src="data:image/png;base64,{_login_img_b64}" '
                    f'style="width:100%;height:100%;height:100%;'
                    f'object-fit:cover;display:block;">',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    '<div style="background:#f5f5f5;height:100%;width:100%;"></div>',
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
/* Master: Enter RetailAI button — white primary */
[data-testid="stColumn"]:has(.master-left-marker) [data-testid="stBaseButton-primary"] {
    background: #FFFFFF !important; color: #1a1a1a !important;
    border: none !important; font-weight: 700 !important;
}
/* RSM/ASM selected — black (inside stHorizontalBlock, overrides white above) */
[data-testid="stColumn"]:has(.master-left-marker) [data-testid="stHorizontalBlock"] [data-testid="stBaseButton-primary"] {
    background: #000000 !important; color: #fff !important;
}
[data-testid="stColumn"]:has(.master-left-marker) [data-testid="stHorizontalBlock"] [data-testid="stBaseButton-primary"]:hover {
    opacity: 0.85 !important;
}
/* RSM/ASM unselected — dark (inside stHorizontalBlock) */
[data-testid="stColumn"]:has(.master-left-marker) [data-testid="stHorizontalBlock"] [data-testid="stBaseButton-secondary"] {
    background: #2a2a2a !important; color: #fff !important;
    border: none !important; font-weight: 700 !important;
}
[data-testid="stColumn"]:has(.master-left-marker) [data-testid="stHorizontalBlock"] [data-testid="stBaseButton-secondary"]:hover {
    background: #3a3a3a !important;
}
/* Upload button — yellow secondary (not inside stHorizontalBlock) */
[data-testid="stColumn"]:has(.master-left-marker) [data-testid="stBaseButton-secondary"] {
    background: #FFE600 !important; color: #1a1a1a !important;
    border: none !important; font-weight: 700 !important;
}
[data-testid="stColumn"]:has(.master-left-marker) [data-testid="stBaseButton-secondary"]:hover {
    background: #f0d800 !important;
}
</style>
""", unsafe_allow_html=True)

        _ob_names = st.session_state.ob_names or {}
        _m_role = st.session_state.onboarding_role

        _mc_left, _mc_right = st.columns([55, 45])

        with _mc_left:
            st.markdown('<div class="master-left-marker" style="display:none;"></div>', unsafe_allow_html=True)

            st.subheader("Welcome, you are a master user")
            st.caption("Select an identity to enter as, or go straight to settings")

            # RSM / ASM buttons
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

            # Name selector — always visible, enabled only after role is picked
            _name_list = (
                _ob_names.get("rsm_names", []) if _m_role == "RSM"
                else _ob_names.get("asm_names", []) if _m_role == "ASM"
                else []
            )
            _m_selected = st.multiselect(
                label=f"Select {_m_role} name" if _m_role else "Select a name",
                options=sorted(_name_list),
                placeholder="Select one or more names...",
                key="master_name_select",
                disabled=not _m_role,
            )

            # Enter button — always visible, enabled only after names picked
            if st.button("Enter RetailAI →", key="master_enter",
                         type="primary", use_container_width=True,
                         disabled=not _m_selected):
                st.session_state.user_names          = _m_selected
                st.session_state.user_name           = _m_selected[0]
                st.session_state.selected_role       = _m_role
                st.session_state.master_identity_set = True
                st.session_state.onboarding_role     = None
                st.session_state._transitioning      = True
                st.rerun()

            # Yellow admin button
            if st.button("upload data / manage access?", key="master_admin",
                         use_container_width=True):
                st.switch_page("pages/admin.py")

            # Logo + title (bottom)
            st.markdown(f"""
<div style="font-family:'Inter',system-ui,sans-serif;margin-top:12rem;">
  <div style="display:flex;align-items:center;gap:1.4rem;">
    {'<img src="data:image/png;base64,' + _LOGO_B64 + '" style="width:100px;height:100px;border-radius:50%;object-fit:cover;flex-shrink:0;">' if _LOGO_B64 else ''}
    <div>
      <div style="font-size:3.6rem;font-weight:800;color:#fff;line-height:1;letter-spacing:-0.02em;">RetailAI</div>
      <div style="font-size:1.05rem;font-weight:500;color:rgba(255,255,255,0.88);margin-top:0.3rem;">AI Powered Sales Intelligence</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

        with _mc_right:
            st.markdown('<div class="master-right-marker" style="display:none;"></div>', unsafe_allow_html=True)
            if _master_img_b64:
                st.markdown(
                    f'<img src="data:image/png;base64,{_master_img_b64}" '
                    f'style="width:100%;height:100%;height:100%;'
                    f'object-fit:cover;display:block;">',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    '<div style="background:#2a2a2a;height:100%;width:100%;"></div>',
                    unsafe_allow_html=True,
                )

        return

    # ── CHAT UI ───────────────────────────────────────────────────────────

    render_header()

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

    # ── Engine ──────────────────────────────────────────────────────────
    try:
        engine  = get_engine()
        data_ok = engine._latest_date is not None
    except Exception as e:
        engine  = None
        data_ok = False
        st.error(f"Could not connect to database: {e}")

    # ── Toolbar row ──────────────────────────────────────────────────────
    _names = st.session_state.user_names or []
    if len(_names) == 1:
        _badge_text = f"Showing data for {_names[0]}"
    elif len(_names) > 1:
        _badge_text = f"Showing data for {_names[0]} +{len(_names)-1}"
    else:
        _badge_text = f"Showing data for {_effective_role}"

    _t1, _t2 = st.columns([6, 5], vertical_alignment="center")

    with _t1:
        _badge_c, _switch_c = st.columns([3, 1], vertical_alignment="center")
        with _badge_c:
            st.markdown(f'<div class="user-badge-pill">{_badge_text}</div>', unsafe_allow_html=True)
        with _switch_c:
            st.markdown('<div class="switch-user-marker" style="display:none;"></div>', unsafe_allow_html=True)
            if st.button("Switch user?", key="switch_user_btn", use_container_width=True):
                _reset_session()
                st.rerun()

    with _t2:
        if data_ok:
            _latest = engine._latest_date
            st.markdown(
                f'<div class="toolbar-status">'
                f'<span class="status-ok">&#9679;</span>&nbsp; Ready'
                f' &nbsp;|&nbsp; Latest date : <b>{_latest.strftime("%d %B %Y")}</b>'
                f'</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div class="toolbar-status"><span class="status-warn">&#9679;</span>'
                '&nbsp; No data found.</div>',
                unsafe_allow_html=True,
            )

    # ── Category filter row ─────────────────────────────────────────────
    _all_cats = get_categories()
    if _all_cats:
        st.session_state.selected_categories = st.multiselect(
            label="Filter category if needed",
            options=_all_cats,
            default=st.session_state.selected_categories,
            key="cat_filter",
            placeholder="Choose a category (Default – all categories)",
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

    st.markdown('<div class="prompt-card-title">Predefined prompts for ease of use</div>', unsafe_allow_html=True)

    _pc_left, _pc_right = st.columns(2)

    with _pc_left:
        st.markdown('<span class="prompt-group-badge-sales">Sales</span>', unsafe_allow_html=True)
        for _label, _query in _sales_btns:
            if st.button(_label, key=f"qs_{_label}", use_container_width=True):
                st.session_state.starter_clicked = (_label, _query)
                st.rerun()

    with _pc_right:
        st.markdown('<span class="prompt-group-badge-prod">Productivity</span>', unsafe_allow_html=True)
        for _label, _query in _prod_btns:
            if st.button(_label, key=f"qp_{_label}", use_container_width=True):
                st.session_state.starter_clicked = (_label, _query)
                st.rerun()

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

# ── Chat card ────────────────────────────────────────────────────────
    st.markdown('<div class="chat-wrapper">', unsafe_allow_html=True)

    st.markdown('<div id="chat-scroll-anchor"></div>', unsafe_allow_html=True)

    with st.container(border=True):

        st.markdown('<div class="chat-content">', unsafe_allow_html=True)

        if not st.session_state.messages and not _is_processing:
            st.markdown(
                '<div class="welcome-card-inner">'
                '<div class="welcome-card-title">Ask me anything about your sales data</div>'
                '<div class="welcome-card-sub">Explore performance, trends, and team insights</div>'
                '</div>',
                unsafe_allow_html=True,
            )
        else:
            import markdown as _md
            for msg in st.session_state.messages:
                if msg["role"] == "user":
                    _display_text = msg.get("display") or msg["content"]
                    st.markdown(
                        f'<div class="msg-user"><div class="bubble-user">{_display_text}</div></div>',
                        unsafe_allow_html=True,
                    )
                else:
                    try:
                        html_content = _md.markdown(msg["content"], extensions=["tables", "nl2br"])
                    except Exception:
                        html_content = msg["content"].replace("\n", "<br>")

                    html_content = html_content.replace(
                        "<table>", '<div class="table-wrapper"><table>'
                    ).replace("</table>", "</table></div>")

                    st.markdown(
                        f'<div class="msg-bot"><div class="bubble-bot">{html_content}</div></div>',
                        unsafe_allow_html=True,
                    )

        if _is_processing:
            st.markdown(
                '<div class="msg-bot"><div class="bubble-bot"><div class="loading-dots">'
                '<span></span><span></span><span></span>'
                '</div></div></div>',
                unsafe_allow_html=True,
            )

        st.markdown('</div>', unsafe_allow_html=True)  # CLOSE chat-content

        # ── Input form ──
        st.markdown('<div class="chat-input" style="padding-bottom: 2rem;">', unsafe_allow_html=True)

        with st.form(key="chat_form", clear_on_submit=True):
            _in_col, _btn_col = st.columns([10, 1])
            with _in_col:
                user_input = st.text_input(
                    label="",
                    placeholder="How can I help you today?",
                    label_visibility="collapsed",
                )
            with _btn_col:
                send_clicked = st.form_submit_button("Send", use_container_width=True)

        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)  # CLOSE chat-wrapper

    # ── Bottom strip ─────────────────────────────────────────────────────
    st.markdown("<div style='padding-bottom: 0rem;'>", unsafe_allow_html=True)

    _strip_l, _strip_r = st.columns([3, 1], vertical_alignment="center")

    with _strip_l:
        st.caption("Data is fetched live - responses may take a few seconds")

    with _strip_r:
        st.markdown('<div class="reset-chat-marker" style="display:none;"></div>', unsafe_allow_html=True)
        if st.button("Start a new conversation?", key="reset_chat_btn", use_container_width=True):
            st.session_state.messages = []
            st.session_state.session_context = {}
            st.session_state.pending_question = None
            st.session_state.pending_display = None
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

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
