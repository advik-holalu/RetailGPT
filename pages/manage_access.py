"""
pages/manage_access.py
Master-only page for managing approved user access.
Add new users, remove existing users.
"""

import sys
import os
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from page_utils import render_header  # noqa: E402

st.set_page_config(
    page_title="DESi Field AI - Manage Access",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
* { font-family: 'Inter', system-ui, sans-serif; box-sizing: border-box; }
#MainMenu, footer, header { visibility: hidden; }
[data-testid="stMain"], [data-testid="stMainBlockContainer"] {
    padding-top: 0 !important; max-width: 100% !important;
    padding-left: 0 !important; padding-right: 0 !important;
}
.block-container {
    padding-top: 0 !important; max-width: 100% !important;
    padding-left: 3.5rem !important; padding-right: 3.5rem !important;
    position: static !important;
}
button, [data-testid="stBaseButton-primary"], [data-testid="stBaseButton-secondary"],
[data-testid="stFormSubmitButton"] > button { border-radius: 10px !important; min-height: 42px !important; }
[data-testid="stBaseButton-primary"], [data-testid="stFormSubmitButton"] > button {
    background: #F7941D !important; color: #FFFFFF !important;
    border: none !important; font-weight: 600 !important;
}
[data-testid="stDecoration"] { display: none !important; }
.section-card {
    background: #1A1A1A; border: 1px solid #2A2A2A;
    border-radius: 12px; padding: 1.5rem 1.75rem; margin-bottom: 1.5rem;
}
.section-title {
    font-size: 1rem; font-weight: 700; color: #FFFFFF;
    margin: 0 0 1.2rem; padding-bottom: 0.6rem;
    border-bottom: 2px solid #F7941D;
}
.user-table { width: 100%; border-collapse: collapse; font-size: 0.88rem; }
.user-table th {
    background: #222; color: #AAAAAA; font-weight: 600;
    padding: 0.5rem 0.8rem; text-align: left;
    border-bottom: 1px solid #333;
}
.user-table td {
    padding: 0.45rem 0.8rem; border-bottom: 1px solid #222; color: #EEEEEE;
}
.user-table tr:last-child td { border-bottom: none; }
.badge-role {
    display: inline-block; border-radius: 6px;
    padding: 0.15rem 0.55rem; font-size: 0.76rem; font-weight: 600;
}
.badge-rsm { background: #1a2e1a; color: #81c784; border: 1px solid #2e7d32; }
.badge-asm { background: #1a1f2e; color: #90caf9; border: 1px solid #1565c0; }
.badge-master { background: #2e1a1a; color: #ef9a9a; border: 1px solid #c62828; }
@media (max-width: 900px) {
    .block-container { padding-left: 1.2rem !important; padding-right: 1.2rem !important; }
}
@media (max-width: 640px) {
    .block-container { padding-left: 0.75rem !important; padding-right: 0.75rem !important; }
}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Access guard
# ---------------------------------------------------------------------------
if not st.session_state.get("user_email") or st.session_state.get("user_role") != "Master":
    st.error("You don't have access to this page.")
    if st.button("Back to DESi Field AI"):
        st.switch_page("app.py")
    st.stop()

# ---------------------------------------------------------------------------
# Header + back button
# ---------------------------------------------------------------------------
render_header()

if st.button("Back to DESi Field AI", key="back_btn"):
    st.switch_page("app.py")

st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
st.markdown("## Manage Access")
st.markdown("Add or remove user access to DESi Field AI.")

from supabase_client import add_approved_user, remove_approved_user, get_all_approved_users, load_names

# ---------------------------------------------------------------------------
# Section 1 — Add New User
# ---------------------------------------------------------------------------
st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.markdown('<div class="section-title">Add New User</div>', unsafe_allow_html=True)

_names_data = load_names()
_add_role   = st.selectbox("Role", ["ASM", "RSM", "Master"], key="add_role")

if _add_role == "Master":
    _add_name = st.text_input("Display name (e.g. Data Analyst)", key="add_name_text")
else:
    _name_pool = (
        sorted(_names_data.get("rsm_names", [])) if _add_role == "RSM"
        else sorted(_names_data.get("asm_names", []))
    )
    if _name_pool:
        _add_name = st.selectbox("Name", _name_pool, key="add_name_select")
    else:
        _add_name = st.text_input("Name (no names found in data, enter manually)", key="add_name_manual")

_add_email = st.text_input("Work email", placeholder="user@company.com", key="add_email")

if st.button("Add User", key="add_user_btn", type="primary"):
    if not _add_email.strip():
        st.error("Please enter an email address.")
    elif not _add_name or not str(_add_name).strip():
        st.error("Please select or enter a name.")
    else:
        _ok, _err = add_approved_user(_add_email.strip(), _add_role, str(_add_name).strip())
        if _ok:
            st.success(f"User added successfully: {_add_email.strip()} ({_add_role} - {_add_name})")
            st.rerun()
        else:
            st.error(_err or "Failed to add user.")

st.markdown("</div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Section 2 — Current Users
# ---------------------------------------------------------------------------
st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.markdown('<div class="section-title">Current Users</div>', unsafe_allow_html=True)

_users = get_all_approved_users()

if not _users:
    st.markdown(
        '<p style="color:#AAAAAA;font-size:0.88rem;">No active users found.</p>',
        unsafe_allow_html=True,
    )
else:
    # Table header
    _hcols = st.columns([3, 1.2, 2.5, 2, 1.5])
    for _col, _label in zip(_hcols, ["Email", "Role", "Name", "Added On", "Action"]):
        _col.markdown(
            f'<div style="font-size:0.78rem;font-weight:600;color:#AAAAAA;'
            f'padding:0.3rem 0;border-bottom:1px solid #333;">{_label}</div>',
            unsafe_allow_html=True,
        )

    for _u in _users:
        _role_cls = {"RSM": "badge-rsm", "ASM": "badge-asm", "Master": "badge-master"}.get(
            _u.get("role", ""), "badge-asm"
        )
        _added = str(_u.get("created_at", ""))[:10]
        _cols  = st.columns([3, 1.2, 2.5, 2, 1.5])
        _cols[0].markdown(
            f'<div style="font-size:0.85rem;padding:0.4rem 0;">{_u.get("email","")}</div>',
            unsafe_allow_html=True,
        )
        _cols[1].markdown(
            f'<div style="padding:0.4rem 0;">'
            f'<span class="badge-role {_role_cls}">{_u.get("role","")}</span></div>',
            unsafe_allow_html=True,
        )
        _cols[2].markdown(
            f'<div style="font-size:0.85rem;padding:0.4rem 0;">{_u.get("name","")}</div>',
            unsafe_allow_html=True,
        )
        _cols[3].markdown(
            f'<div style="font-size:0.82rem;color:#AAAAAA;padding:0.4rem 0;">{_added}</div>',
            unsafe_allow_html=True,
        )
        if _cols[4].button("Remove", key=f"rm_{_u.get('email','')}", use_container_width=True):
            _rm_ok, _rm_err = remove_approved_user(_u["email"])
            if _rm_ok:
                st.success(f"Access removed for {_u['email']}")
                st.rerun()
            else:
                st.error(_rm_err or "Failed to remove access.")

st.markdown("</div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.markdown("""
<div style="text-align:center;color:#444;font-size:0.78rem;padding:1rem 0;">
DESi Field AI - Manage Access - Master Only
</div>
""", unsafe_allow_html=True)
