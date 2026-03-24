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
import pandas as pd
from supabase_client import load_outlet_data, load_targets
from query_engine import QueryEngine
from prompts import STARTER_QUESTIONS
from metrics import get_latest_date, get_current_month_year, MONTH_NAMES

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

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def get_engine():
    outlet_df = load_outlet_data()
    targets_df = load_targets()
    engine = QueryEngine(outlet_df, targets_df)
    return engine, outlet_df, targets_df


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
col1, col2, col3 = st.columns([6, 2, 2])

with col2:
    if st.button("🔄 New Conversation", use_container_width=True):
        st.session_state.messages = []
        st.session_state.session_context = {}
        st.rerun()

with col3:
    if st.button("⟳ Refresh Data", use_container_width=True):
        get_engine.clear()
        st.rerun()

# ---------------------------------------------------------------------------
# Load data and engine
# ---------------------------------------------------------------------------
with st.spinner("Loading sales data…"):
    try:
        engine, outlet_df, targets_df = get_engine()
        data_ok = not outlet_df.empty
    except Exception as e:
        engine = None
        outlet_df = pd.DataFrame()
        targets_df = pd.DataFrame()
        data_ok = False
        st.error(f"Could not connect to database: {e}")

# Data status bar
if data_ok:
    latest = get_latest_date(outlet_df)
    row_count = f"{len(outlet_df):,}"
    month_name = MONTH_NAMES.get(latest.month, "")
    st.markdown(
        f'<div class="status-bar">'
        f'<span class="status-ok">●</span> Data loaded &nbsp;|&nbsp; '
        f'{row_count} rows &nbsp;|&nbsp; '
        f'Latest date: <b>{latest.strftime("%d %b %Y")}</b> &nbsp;|&nbsp; '
        f'MTD reference: <b>{month_name} {latest.year}</b>'
        f'</div>',
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        '<div class="status-bar"><span class="status-warn">●</span> '
        'No data loaded. Upload files via the <b>Upload</b> page.</div>',
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Chat history display
# ---------------------------------------------------------------------------
st.markdown('<div class="chat-container">', unsafe_allow_html=True)

if not st.session_state.messages:
    # Welcome screen with suggested questions
    st.markdown("""
<div class="welcome-box">
    <h2>How can I help you today?</h2>
    <p>Ask me anything about your sales data — secondary, targets, rankings, trends, and more.</p>
</div>
""", unsafe_allow_html=True)

    # Starter question buttons
    cols = st.columns(2)
    for i, q in enumerate(STARTER_QUESTIONS):
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

    if engine is None or outlet_df.empty:
        response = (
            "I don't have any sales data to work with yet. "
            "Please ask your data analyst to upload the data via the **Upload** page."
        )
    else:
        with st.spinner("Analysing…"):
            try:
                response, new_ctx = engine.process(
                    question=question,
                    chat_history=st.session_state.messages[:-1],
                    session_context=st.session_state.session_context,
                )
                st.session_state.session_context = new_ctx
            except Exception:
                response = (
                    "I encountered an issue processing your question. "
                    "Please try rephrasing, or check the data has been uploaded correctly."
                )

    st.session_state.messages.append({"role": "assistant", "content": response})
    st.rerun()
