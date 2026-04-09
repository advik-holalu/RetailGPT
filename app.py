"""
app.py
RetailGPT — Main Streamlit chat interface.
Open to all users (ASMs and RSMs). No login required.
"""

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# Page config — must be first Streamlit call
st.set_page_config(
    page_title="RetailGPT",
    page_icon="🏪",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Custom CSS — professional dark theme
# ---------------------------------------------------------------------------
st.markdown("""
<style>
/* Global */
html, body, [data-testid="stAppViewContainer"] {
    background-color: #0f1117;
    color: #e0e0e0;
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
}

/* Hide Streamlit default header/footer */
#MainMenu, footer, header { visibility: hidden; }

/* Main content */
[data-testid="stMain"] { padding-top: 0; }

/* Header */
.retailgpt-header {
    background: linear-gradient(135deg, #1a1f2e 0%, #242938 100%);
    border-bottom: 1px solid #2d3250;
    padding: 1rem 2rem 0.75rem;
    margin-bottom: 1rem;
}
.retailgpt-header h1 {
    font-size: 1.8rem;
    font-weight: 700;
    color: #ffffff;
    margin: 0;
}
.retailgpt-header p {
    color: #8892a4;
    font-size: 0.9rem;
    margin: 0.2rem 0 0;
}

/* Chat container */
.chat-container {
    max-width: 900px;
    margin: 0 auto;
    padding: 0 1rem;
}

/* User message bubble */
.msg-user {
    display: flex;
    justify-content: flex-end;
    margin: 0.75rem 0;
}
.bubble-user {
    background: #2d3250;
    color: #e8eaf6;
    padding: 0.75rem 1.1rem;
    border-radius: 18px 18px 4px 18px;
    max-width: 75%;
    font-size: 0.95rem;
    line-height: 1.5;
    box-shadow: 0 2px 8px rgba(0,0,0,0.3);
}

/* Bot message bubble */
.msg-bot {
    display: flex;
    justify-content: flex-start;
    margin: 0.75rem 0;
}
.bubble-bot {
    background: #1e2235;
    border: 1px solid #2d3250;
    color: #d4d9e8;
    padding: 0.9rem 1.2rem;
    border-radius: 18px 18px 18px 4px;
    max-width: 85%;
    font-size: 0.92rem;
    line-height: 1.6;
    box-shadow: 0 2px 8px rgba(0,0,0,0.3);
}
.bubble-bot table {
    border-collapse: collapse;
    margin: 0.5rem 0;
    font-size: 0.88rem;
    width: 100%;
}
.bubble-bot table th {
    background: #2d3250;
    padding: 0.4rem 0.7rem;
    text-align: left;
    color: #a0aec0;
    font-weight: 600;
    border-bottom: 1px solid #3d4466;
}
.bubble-bot table td {
    padding: 0.35rem 0.7rem;
    border-bottom: 1px solid #252a3d;
    color: #c8cfdf;
}
.bubble-bot table tr:last-child td { border-bottom: none; }
.bubble-bot table tr:hover td { background: #252a3d; }

/* Avatar icons */
.avatar {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1rem;
    flex-shrink: 0;
    margin-top: 4px;
}
.avatar-bot { background: #3949ab; margin-right: 10px; }
.avatar-user { background: #1565c0; margin-left: 10px; }

/* Suggested questions */
.starter-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 0.6rem;
    margin: 1.5rem 0;
}
.starter-card {
    background: #1a1f2e;
    border: 1px solid #2d3250;
    border-radius: 10px;
    padding: 0.75rem 1rem;
    cursor: pointer;
    color: #9fa8da;
    font-size: 0.88rem;
    transition: all 0.2s;
}
.starter-card:hover {
    background: #242938;
    border-color: #5c6bc0;
    color: #e8eaf6;
}

/* Input area */
.stTextInput > div > div > input {
    background: #1a1f2e !important;
    border: 1px solid #2d3250 !important;
    color: #e0e0e0 !important;
    border-radius: 12px !important;
    padding: 0.75rem 1rem !important;
    font-size: 0.95rem !important;
}
.stTextInput > div > div > input:focus {
    border-color: #5c6bc0 !important;
    box-shadow: 0 0 0 2px rgba(92,107,192,0.2) !important;
}

/* Buttons */
.stButton button {
    background: #3949ab;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 0.5rem 1rem;
    font-weight: 500;
    transition: background 0.2s;
}
.stButton button:hover { background: #5c6bc0; }

/* Data status bar */
.status-bar {
    background: #1a1f2e;
    border: 1px solid #2d3250;
    border-radius: 8px;
    padding: 0.5rem 1rem;
    font-size: 0.82rem;
    color: #8892a4;
    margin-bottom: 1rem;
}
.status-ok { color: #66bb6a; }
.status-warn { color: #ffa726; }

/* Spinner */
.stSpinner > div { color: #5c6bc0 !important; }

/* Scrollbar */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #0f1117; }
::-webkit-scrollbar-thumb { background: #2d3250; border-radius: 3px; }

/* Onboarding */
.onboarding-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 80vh;
    text-align: center;
    padding: 2rem;
}
/* Remove Streamlit's default top padding so onboarding sits at the true viewport top */
[data-testid="stMain"] > div:first-child { padding-top: 0 !important; }
section[data-testid="stSidebar"] + div [data-testid="stVerticalBlock"] { padding-top: 0 !important; }
.block-container { padding-top: 1rem !important; }
.onboarding-title { font-size: 2.4rem; font-weight: 800; color: #fff; margin: 0.3rem 0; }
.onboarding-sub { color: #8892a4; font-size: 1rem; margin-bottom: 2.5rem; }
.role-btn-row { display: flex; gap: 1.2rem; margin-bottom: 1.5rem; }
.role-card {
    background: #1a1f2e; border: 2px solid #2d3250; border-radius: 14px;
    padding: 1.4rem 2.2rem; cursor: pointer; text-align: center;
    transition: all 0.2s; min-width: 160px;
}
.role-card:hover, .role-card.active {
    border-color: #5c6bc0; background: #242938; color: #e8eaf6;
}
.role-card .role-icon { font-size: 2rem; display: block; margin-bottom: 0.4rem; }
.role-card .role-label { font-size: 1.05rem; font-weight: 600; color: #d0d5e8; }
.user-badge {
    background: #1a1f2e; border: 1px solid #3949ab; border-radius: 8px;
    padding: 0.3rem 0.75rem; font-size: 0.82rem; color: #9fa8da;
    display: inline-flex; align-items: center; gap: 0.4rem;
}

/* Welcome message */
.welcome-box {
    text-align: center;
    padding: 2rem 1rem;
    color: #8892a4;
}
.welcome-box h2 { color: #d0d5e8; font-size: 1.4rem; margin-bottom: 0.5rem; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Lazy imports (after page config)
# ---------------------------------------------------------------------------
from supabase_client import load_names, get_latest_date_str, get_categories
from query_engine import QueryEngine
from prompts import STARTER_QUESTIONS
from metrics import MONTH_NAMES

# ---------------------------------------------------------------------------
# Session state initialisation
# ---------------------------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []

if "session_context" not in st.session_state:
    st.session_state.session_context = {}

if "engine" not in st.session_state:
    st.session_state.engine = None

if "data_loaded" not in st.session_state:
    st.session_state.data_loaded = False

if "starter_clicked" not in st.session_state:
    st.session_state.starter_clicked = None

if "pending_question" not in st.session_state:
    st.session_state.pending_question = None

if "input_key" not in st.session_state:
    st.session_state.input_key = 0

if "user_role" not in st.session_state:
    st.session_state.user_role = None   # "RSM" | "ASM"

if "user_name" not in st.session_state:
    st.session_state.user_name = None   # primary display name (first selected)

if "user_names" not in st.session_state:
    st.session_state.user_names = []    # full list of selected names

if "selected_categories" not in st.session_state:
    st.session_state.selected_categories = []

if "onboarding_role" not in st.session_state:
    st.session_state.onboarding_role = None  # role selected but name not yet confirmed

# ---------------------------------------------------------------------------
# Onboarding / loading screen — shown once per session
# ---------------------------------------------------------------------------
if not st.session_state.user_role:

    # ── CSS first (always before any content) ──────────────────────────────
    # Scoped here: st.stop() prevents these styles leaking into the chat UI.
    st.markdown("""
<style>
.main > div:first-child { padding-top: 0rem !important; }
section.main > div { padding-top: 0rem !important; }
#root > div:nth-child(1) > div > div > div > div > section > div {
    padding-top: 0rem !important;
}
header { display: none !important; }
.block-container {
    padding-top: 0rem !important;
    padding-bottom: 0rem !important;
    max-width: 620px !important;
    margin-left: auto !important;
    margin-right: auto !important;
}
[data-testid="stVerticalBlock"] {
    min-height: 100vh;
    display: flex !important;
    flex-direction: column !important;
    align-items: center !important;
    justify-content: center !important;
}
[data-testid="stVerticalBlock"] > div { width: 100%; max-width: 520px; }
[data-testid="stRadio"] > div { justify-content: center; }
[data-testid="stRadio"] label { font-size: 1.05rem !important; }
[data-testid="stFormSubmitButton"] button,
[data-testid="stButton"] button { width: 100%; font-size: 1.05rem !important; }
@keyframes ob-pulse { 0%,100%{opacity:.25} 50%{opacity:1} }
.ob-dot { display:inline-block; animation: ob-pulse 1.4s ease-in-out infinite; }
.ob-dot:nth-child(2) { animation-delay:.2s; }
.ob-dot:nth-child(3) { animation-delay:.4s; }
[data-testid="collapsedControl"] {
    display: flex !important;
    visibility: visible !important;
    opacity: 1 !important;
}
section[data-testid="stSidebar"] {
    display: block !important;
}
</style>
""", unsafe_allow_html=True)

    # ── Step 1: show loading screen IMMEDIATELY (before any Supabase call) ─
    _screen = st.empty()
    _screen.markdown("""
<div style="display:flex;flex-direction:column;align-items:center;
            justify-content:center;min-height:100vh;text-align:center;gap:.9rem;">
  <div style="font-size:3.5rem;line-height:1;">🏪</div>
  <h1 style="font-size:2.2rem;font-weight:800;color:#fff;margin:0;">RetailGPT</h1>
  <p style="color:#8892a4;font-size:.95rem;margin:0;">
    Your AI-powered sales intelligence assistant
  </p>
  <div style="font-size:2rem;color:#5c6bc0;margin:.6rem 0;letter-spacing:.3rem;">
    <span class="ob-dot">●</span><span class="ob-dot">●</span><span class="ob-dot">●</span>
  </div>
  <div style="font-size:1.1rem;font-weight:700;color:#e0e0e0;">
    Loading, please wait...
  </div>
  <div style="font-size:.95rem;font-weight:600;color:#ef5350;">
    ⚠️ DO NOT refresh the page
  </div>
</div>
""", unsafe_allow_html=True)

    # ── Step 2: fetch names (blocks here; loading screen visible meanwhile) ─
    _ob_names = load_names()

    # ── Step 3: clear loading screen, show onboarding ──────────────────────
    _screen.empty()

    st.markdown("""
<div style="text-align:center;padding-bottom:1.5rem;">
  <div style="font-size:3.5rem;line-height:1.1;">🏪</div>
  <h1 style="font-size:2.3rem;font-weight:800;color:#fff;margin:.4rem 0 .2rem;">
    Welcome to RetailGPT
  </h1>
  <p style="color:#8892a4;font-size:1rem;margin:0 0 1.8rem;">
    Your AI-powered sales intelligence assistant
  </p>
  <h3 style="color:#d0d5e8;font-size:1.1rem;margin-bottom:.5rem;">Who are you?</h3>
</div>
""", unsafe_allow_html=True)

    _role_choice = st.radio(
        label="Role",
        options=["👔  I am an RSM", "🧑‍💼  I am an ASM"],
        index=(0 if st.session_state.onboarding_role == "RSM" else
               1 if st.session_state.onboarding_role == "ASM" else 0),
        horizontal=True,
        key="ob_role_radio",
        label_visibility="collapsed",
    )
    _role = "RSM" if _role_choice.startswith("👔") else "ASM"
    if _role != st.session_state.onboarding_role:
        st.session_state.onboarding_role = _role
        st.rerun()

    _name_list = (
        _ob_names.get("rsm_names", []) if _role == "RSM"
        else _ob_names.get("asm_names", [])
    )
    if not _name_list:
        st.warning("Name list not loaded yet — data may still be uploading. Try refreshing.")
    else:
        st.markdown(
            f'<p style="text-align:center;color:#9fa8da;margin:1rem 0 .3rem;">'
            f'Select your name(s) ({_role}):</p>',
            unsafe_allow_html=True,
        )
        _selected = st.multiselect(
            label="Your name(s)",
            options=sorted(_name_list),
            placeholder="Select one or more names…",
            key="ob_name_select",
            label_visibility="collapsed",
        )
        if _selected:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Enter RetailGPT →", key="ob_enter", type="primary"):
                st.session_state.user_role = _role
                st.session_state.user_names = _selected
                st.session_state.user_name = _selected[0]   # primary for badge
                st.session_state.onboarding_role = None
                st.rerun()

    st.stop()


# ---------------------------------------------------------------------------
# Engine initialisation — fast startup (names + latest date only, no full load)
# ---------------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def get_engine() -> QueryEngine:
    names           = load_names()
    latest_date_str = get_latest_date_str()
    return QueryEngine(names, latest_date_str)


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown("""
<div class="retailgpt-header">
    <h1>🏪 RetailGPT</h1>
    <p>Your AI-powered sales intelligence assistant</p>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Top toolbar
# ---------------------------------------------------------------------------
col1, col2, col3, col4 = st.columns([4, 2, 2, 2])

with col1:
    if st.session_state.user_names:
        role_icon = "👔" if st.session_state.user_role == "RSM" else "🧑‍💼"
        _names = st.session_state.user_names
        if len(_names) == 1:
            _badge_label = _names[0]
        elif len(_names) == 2:
            _badge_label = f"{_names[0]}, {_names[1]}"
        else:
            _badge_label = f"{_names[0]} +{len(_names)-1} others"
        if st.button(
            f"{role_icon} {_badge_label} ({st.session_state.user_role}) ✏️",
            key="badge_switch",
            help="Click to switch user",
        ):
            st.session_state.user_role = None
            st.session_state.user_name = None
            st.session_state.user_names = []
            st.session_state.selected_categories = []
            st.session_state.onboarding_role = None
            st.session_state.messages = []
            st.session_state.session_context = {}
            st.rerun()

with col2:
    if st.button("🔄 New Conversation", use_container_width=True):
        st.session_state.messages = []
        st.session_state.session_context = {}
        st.rerun()

with col3:
    if st.button("⟳ Refresh Data", use_container_width=True):
        get_engine.clear()
        st.rerun()

with col4:
    if st.button("↩ Switch User", use_container_width=True):
        st.session_state.user_role = None
        st.session_state.user_name = None
        st.session_state.user_names = []
        st.session_state.selected_categories = []
        st.session_state.onboarding_role = None
        st.session_state.messages = []
        st.session_state.session_context = {}
        st.rerun()

# ---------------------------------------------------------------------------
# Initialise engine (fast — only fetches names + latest date)
# ---------------------------------------------------------------------------
_init_banner = st.empty()
_init_banner.markdown(
    '<div style="background:#7c3a00;border:2px solid #ff8c00;border-radius:8px;'
    'padding:0.85rem 1.2rem;font-size:1rem;font-weight:600;color:#ffe0b2;'
    'text-align:center;margin-bottom:0.75rem;">'
    '⏳ &nbsp; Loading data, please wait... &nbsp; DO NOT refresh the page.'
    '</div>',
    unsafe_allow_html=True,
)

try:
    engine  = get_engine()
    data_ok = engine._latest_date is not None
except Exception as e:
    engine  = None
    data_ok = False
    _init_banner.error(f"Could not connect to database: {e}")

if data_ok:
    _init_banner.markdown(
        '<div style="background:#1b4332;border:2px solid #40916c;border-radius:8px;'
        'padding:0.85rem 1.2rem;font-size:1rem;font-weight:600;color:#b7e4c7;'
        'text-align:center;margin-bottom:0.75rem;">'
        '✅ &nbsp; Ready! Ask me anything about your sales data.'
        '</div>',
        unsafe_allow_html=True,
    )
    import time as _time; _time.sleep(2)
    _init_banner.empty()
else:
    _init_banner.markdown(
        '<div style="background:#4a0000;border:2px solid #e53935;border-radius:8px;'
        'padding:0.85rem 1.2rem;font-size:1rem;font-weight:600;color:#ffcdd2;'
        'text-align:center;margin-bottom:0.75rem;">'
        '⚠️ &nbsp; No data found. Please upload data via the Upload page.'
        '</div>',
        unsafe_allow_html=True,
    )

# Status bar
if data_ok:
    latest     = engine._latest_date
    month_name = MONTH_NAMES.get(latest.month, "")
    st.markdown(
        f'<div class="status-bar">'
        f'<span class="status-ok">●</span> Ready &nbsp;|&nbsp; '
        f'Latest date: <b>{latest.strftime("%d %b %Y")}</b> &nbsp;|&nbsp; '
        f'MTD reference: <b>{month_name} {latest.year}</b> &nbsp;|&nbsp; '
        f'<i>Data fetched per question</i>'
        f'</div>',
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        '<div class="status-bar"><span class="status-warn">●</span> '
        'No data found. Upload files via the <b>Upload</b> page.</div>',
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Category filter bar
# ---------------------------------------------------------------------------
_all_cats = get_categories()
if _all_cats:
    st.session_state.selected_categories = st.multiselect(
        label="Filter by Category (optional) — select one or more, or leave blank for all",
        options=_all_cats,
        default=st.session_state.selected_categories,
        key="cat_filter",
        placeholder="All categories",
    )

# ---------------------------------------------------------------------------
# Chat history display
# ---------------------------------------------------------------------------
st.markdown('<div class="chat-container">', unsafe_allow_html=True)

if not st.session_state.messages:
    _wnames = st.session_state.get("user_names", [])
    if len(_wnames) == 1:
        _scope_line = f"Showing data for <b>{_wnames[0]}</b>."
    elif len(_wnames) > 1:
        _scope_line = f"Showing data for <b>{', '.join(_wnames)}</b>."
    else:
        _scope_line = "Ask me anything about your sales data."
    st.markdown(
        f'<div class="welcome-box">'
        f'<h2>How can I help you today?</h2>'
        f'<p>{_scope_line}</p>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Dynamic starter questions based on logged-in role
    _role = st.session_state.get("user_role")
    if _role == "RSM":
        _starter_qs = [
            "What is the MTD secondary for my entire region?",
            "Show me top 5 SOs by secondary this month",
            "Which ASM has the highest UPC achievement?",
            "Give me target vs achievement for all ASMs",
            "Who are the bottom 3 SOs in my region?",
            "Category-wise sales contribution for my region",
            "MTD vs LMTD comparison for my team",
            "Top 10 outlets by secondary MTD",
            "What is the ABV trend over the last 3 months?",
            "Beat-wise secondary breakdown for my region",
        ]
    elif _role == "ASM":
        _starter_qs = [
            "What is the MTD secondary for my team?",
            "Show me top 5 SOs under me by secondary",
            "Give me target vs achievement for all my SOs",
            "Which of my SOs has the highest UPC this month?",
            "Who are the bottom 3 SOs under me?",
            "Category-wise sales for my team this month",
            "MTD vs LMTD comparison for my SOs",
            "Top 10 outlets under my ASM",
            "What is the ABV trend for my team?",
            "Beat-wise secondary breakdown for my territory",
        ]
    else:
        _starter_qs = STARTER_QUESTIONS

    cols = st.columns(2)
    for i, q in enumerate(_starter_qs):
        with cols[i % 2]:
            if st.button(q, key=f"starter_{i}", use_container_width=True):
                st.session_state.starter_clicked = q
                st.rerun()

else:
    # Render conversation
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            st.markdown(
                f'<div class="msg-user">'
                f'<div class="bubble-user">{msg["content"]}</div>'
                f'<div class="avatar avatar-user">👤</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        else:
            # Render bot message — support markdown tables
            import markdown
            try:
                html_content = markdown.markdown(
                    msg["content"],
                    extensions=["tables", "nl2br"],
                )
            except Exception:
                html_content = msg["content"].replace("\n", "<br>")

            st.markdown(
                f'<div class="msg-bot">'
                f'<div class="avatar avatar-bot">🤖</div>'
                f'<div class="bubble-bot">{html_content}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

st.markdown('</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Input area — fixed at bottom
# ---------------------------------------------------------------------------
st.markdown("<br>", unsafe_allow_html=True)

input_col, btn_col = st.columns([10, 1])

with input_col:
    user_input = st.text_input(
        label="",
        placeholder="Ask a sales question… e.g. 'Show me top 5 SOs by MTD secondary'",
        key=f"chat_input_{st.session_state.input_key}",
        label_visibility="collapsed",
    )

with btn_col:
    send = st.button("➤", key="send_btn", use_container_width=True)

# ---------------------------------------------------------------------------
# Phase 1 — Capture input (starter click or manual send)
# Only fires when the user actually submits something new.
# Increments input_key to clear the text box, then reruns into Phase 2.
# ---------------------------------------------------------------------------
if st.session_state.starter_clicked:
    st.session_state.pending_question = st.session_state.starter_clicked
    st.session_state.starter_clicked = None
    st.session_state.input_key += 1
    st.rerun()

if send and user_input.strip():
    st.session_state.pending_question = user_input.strip()
    st.session_state.input_key += 1
    st.rerun()

# ---------------------------------------------------------------------------
# Phase 2 — Process pending question (runs exactly once per question)
# pending_question is cleared before the rerun, so this block never fires twice.
# ---------------------------------------------------------------------------
if st.session_state.pending_question:
    question = st.session_state.pending_question
    st.session_state.pending_question = None  # Clear BEFORE any rerun

    st.session_state.messages.append({"role": "user", "content": question})

    if engine is None or not data_ok:
        response = (
            "I don't have any sales data to work with yet. "
            "Please ask your data analyst to upload the data via the **Upload** page."
        )
    else:
        with st.spinner("Analysing…"):
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
                    question=question,
                    chat_history=st.session_state.messages[:-1],
                    session_context=st.session_state.session_context,
                    user_scope=_user_scope,
                    category_filter=st.session_state.get("selected_categories") or None,
                )
                st.session_state.session_context = new_ctx
            except Exception:
                response = (
                    "I encountered an issue processing your question. "
                    "Please try rephrasing, or check the data has been uploaded correctly."
                )

    st.session_state.messages.append({"role": "assistant", "content": response})
    st.rerun()
