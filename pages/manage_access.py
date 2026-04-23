"""
pages/manage_access.py
Master-only page for managing approved user access.
Add new users, remove or edit existing users.
"""

import sys
import os
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from page_utils import render_header  # noqa: E402

st.set_page_config(
    page_title="RetailAI - Manage Access",
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
.edit-form-card {
    background: #141414; border: 1px solid #F7941D;
    border-radius: 10px; padding: 1.2rem 1.5rem; margin: 0.5rem 0 0.75rem;
}
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
    if st.button("Back to RetailAI"):
        st.switch_page("app.py")
    st.stop()

# ---------------------------------------------------------------------------
# Header + back button
# ---------------------------------------------------------------------------
render_header()

if st.button("Back to RetailAI", key="back_btn"):
    st.switch_page("app.py")

st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
st.markdown("## Manage Access")
st.markdown("Add, edit, or remove user access to RetailAI.")

from supabase_client import (
    add_approved_user, remove_approved_user, get_all_approved_users,
    update_approved_user, load_names,
)

# Track which user row is being edited
if "editing_user_id" not in st.session_state:
    st.session_state.editing_user_id = None

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
        _add_name = st.text_input(
            "Name (no names found in data, enter manually)", key="add_name_manual"
        )

_add_email    = st.text_input("Work email", placeholder="user@company.com", key="add_email")
_add_password = st.text_input("Set Password", type="password", key="add_password",
                              placeholder="Set a password for this user")

if st.button("Add User", key="add_user_btn", type="primary"):
    if not _add_email.strip():
        st.error("Please enter an email address.")
    elif not _add_name or not str(_add_name).strip():
        st.error("Please select or enter a name.")
    elif not _add_password.strip():
        st.error("Please set a password for this user.")
    else:
        _ok, _err = add_approved_user(
            _add_email.strip(), _add_role, str(_add_name).strip(), _add_password
        )
        if _ok:
            st.success(
                f"User added: {_add_email.strip()} ({_add_role} - {_add_name})"
            )
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
    _hcols = st.columns([3, 1.2, 2.5, 1.8, 1, 1])
    for _col, _label in zip(_hcols, ["Email", "Role", "Name", "Added On", "Edit", "Remove"]):
        _col.markdown(
            f'<div style="font-size:0.78rem;font-weight:600;color:#AAAAAA;'
            f'padding:0.3rem 0;border-bottom:1px solid #333;">{_label}</div>',
            unsafe_allow_html=True,
        )

    for _u in _users:
        _uid      = _u.get("id")
        _role_cls = {"RSM": "badge-rsm", "ASM": "badge-asm", "Master": "badge-master"}.get(
            _u.get("role", ""), "badge-asm"
        )
        _added = str(_u.get("created_at", ""))[:10]
        _cols  = st.columns([3, 1.2, 2.5, 1.8, 1, 1])

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

        # Edit button
        if _cols[4].button("Edit", key=f"edit_{_uid}", use_container_width=True):
            st.session_state.editing_user_id = (
                None if st.session_state.editing_user_id == _uid else _uid
            )
            st.rerun()

        # Remove button
        if _cols[5].button("Remove", key=f"rm_{_uid}", use_container_width=True):
            _rm_ok, _rm_err = remove_approved_user(_uid)
            if _rm_ok:
                if st.session_state.editing_user_id == _uid:
                    st.session_state.editing_user_id = None
                st.success(
                    f"Access removed for {_u['email']} "
                    f"({_u.get('role','')} - {_u.get('name','')})"
                )
                st.rerun()
            else:
                st.error(_rm_err or "Failed to remove access.")

        # Inline edit form
        if st.session_state.editing_user_id == _uid:
            st.markdown('<div class="edit-form-card">', unsafe_allow_html=True)
            st.markdown(
                f'<div style="font-size:0.82rem;font-weight:700;color:#F7941D;'
                f'margin-bottom:0.8rem;">Editing: {_u.get("email","")}</div>',
                unsafe_allow_html=True,
            )

            _e_email = st.text_input(
                "Email", value=_u.get("email", ""), key=f"e_email_{_uid}"
            )
            _e_role  = st.selectbox(
                "Role", ["ASM", "RSM", "Master"],
                index=["ASM", "RSM", "Master"].index(_u.get("role", "ASM"))
                      if _u.get("role") in ["ASM", "RSM", "Master"] else 0,
                key=f"e_role_{_uid}",
            )

            # Name field depends on role
            if _e_role == "Master":
                _e_name = st.text_input(
                    "Display name", value=_u.get("name", ""), key=f"e_name_{_uid}"
                )
            else:
                _e_name_pool = (
                    sorted(_names_data.get("rsm_names", [])) if _e_role == "RSM"
                    else sorted(_names_data.get("asm_names", []))
                )
                if _e_name_pool:
                    _cur_name   = _u.get("name", "")
                    _e_name_idx = _e_name_pool.index(_cur_name) if _cur_name in _e_name_pool else 0
                    _e_name = st.selectbox(
                        "Name", _e_name_pool, index=_e_name_idx, key=f"e_name_{_uid}"
                    )
                else:
                    _e_name = st.text_input(
                        "Name", value=_u.get("name", ""), key=f"e_name_{_uid}"
                    )

            _e_pwd = st.text_input(
                "New Password (leave blank to keep current)",
                type="password", key=f"e_pwd_{_uid}",
                placeholder="Leave blank to keep unchanged",
            )

            _sa, _sc = st.columns([1, 1])
            with _sa:
                if st.button("Save Changes", key=f"save_{_uid}", type="primary",
                             use_container_width=True):
                    if not _e_email.strip():
                        st.error("Email cannot be empty.")
                    elif not str(_e_name).strip():
                        st.error("Name cannot be empty.")
                    else:
                        _upd_ok, _upd_err = update_approved_user(
                            _uid, _e_email.strip(), _e_role,
                            str(_e_name).strip(),
                            _e_pwd if _e_pwd.strip() else None,
                        )
                        if _upd_ok:
                            st.session_state.editing_user_id = None
                            st.success("Changes saved.")
                            st.rerun()
                        else:
                            st.error(_upd_err or "Failed to save changes.")
            with _sc:
                if st.button("Cancel", key=f"cancel_{_uid}", use_container_width=True):
                    st.session_state.editing_user_id = None
                    st.rerun()

            st.markdown("</div>", unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.markdown("""
<div style="text-align:center;color:#444;font-size:0.78rem;padding:1rem 0;">
RetailAI - Manage Access - Master Only
</div>
""", unsafe_allow_html=True)
