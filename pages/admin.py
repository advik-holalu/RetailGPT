"""
pages/admin.py
Master-only admin panel: Manage Access + Upload Data in one page.
"""

import sys
import re
import os
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from page_utils import render_header  # noqa: E402

st.set_page_config(
    page_title="DESi Field AI - Admin",
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
[data-testid="stFormSubmitButton"] > button {
    border-radius: 10px !important; min-height: 42px !important;
}
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
.info-box {
    border: 1px solid #333; border-radius: 8px;
    padding: 0.9rem 1.2rem; margin: 0.75rem 0; font-size: 0.88rem; color: #AAAAAA;
}
.success-box {
    background: #1b2e1b; border: 1px solid #2e7d32;
    border-radius: 8px; padding: 0.9rem 1.2rem; color: #81c784;
}
.error-box {
    background: #2e1b1b; border: 1px solid #c62828;
    border-radius: 8px; padding: 0.9rem 1.2rem; color: #ef9a9a;
}
.badge-role {
    display: inline-block; border-radius: 6px;
    padding: 0.15rem 0.55rem; font-size: 0.76rem; font-weight: 600;
}
.badge-rsm  { background: #1a2e1a; color: #81c784; border: 1px solid #2e7d32; }
.badge-asm  { background: #1a1f2e; color: #90caf9; border: 1px solid #1565c0; }
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
# Header + back
# ---------------------------------------------------------------------------
render_header()

if st.button("Back to DESi Field AI", key="admin_back"):
    st.switch_page("app.py")

st.markdown("<div style='height:0.25rem'></div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Tabs: Manage Access | Upload Data
# ---------------------------------------------------------------------------
from supabase_client import (
    load_names, add_approved_user, remove_approved_user, get_all_approved_users,
    parse_outlet_excel, parse_target_excel, upload_dataframe,
    delete_rows, get_table_row_count, clear_data_cache,
)

UPLOAD_PASSWORD = os.environ.get("UPLOAD_PASSWORD", "")

_tab_access, _tab_upload = st.tabs(["Manage Access", "Upload Data"])

# ============================================================
# TAB 1 — Manage Access
# ============================================================
with _tab_access:
    st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

    # -- Add New User --
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
                "Name (no names found in data - enter manually)", key="add_name_manual"
            )

    _add_email    = st.text_input("Work email", placeholder="user@company.com", key="add_email")
    _add_password = st.text_input("Set Password", type="password", key="add_password",
                                  placeholder="Set a password for this user")

    if st.button("Add User", key="add_user_btn", type="primary"):
        if not _add_email.strip():
            st.error("Please enter an email address.")
        elif not str(_add_name).strip():
            st.error("Please select or enter a name.")
        elif not _add_password.strip():
            st.error("Please set a password for this user.")
        else:
            _ok, _err = add_approved_user(_add_email.strip(), _add_role, str(_add_name).strip(), _add_password)
            if _ok:
                st.success(f"User added: {_add_email.strip()} ({_add_role} - {_add_name})")
                st.rerun()
            else:
                st.error(_err or "Failed to add user.")

    st.markdown("</div>", unsafe_allow_html=True)

    # -- Current Users --
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Current Users</div>', unsafe_allow_html=True)

    _users = get_all_approved_users()
    if not _users:
        st.markdown(
            '<p style="color:#AAAAAA;font-size:0.88rem;">No active users found.</p>',
            unsafe_allow_html=True,
        )
    else:
        _hcols = st.columns([3, 1.2, 2.5, 2, 1.5])
        for _col, _lbl in zip(_hcols, ["Email", "Role", "Name", "Added On", "Action"]):
            _col.markdown(
                f'<div style="font-size:0.78rem;font-weight:600;color:#AAAAAA;'
                f'padding:0.3rem 0;border-bottom:1px solid #333;">{_lbl}</div>',
                unsafe_allow_html=True,
            )
        for _u in _users:
            _rc  = {"RSM": "badge-rsm", "ASM": "badge-asm", "Master": "badge-master"}.get(
                _u.get("role", ""), "badge-asm"
            )
            _dt  = str(_u.get("created_at", ""))[:10]
            _rc2 = st.columns([3, 1.2, 2.5, 2, 1.5])
            _rc2[0].markdown(
                f'<div style="font-size:0.85rem;padding:0.4rem 0;">{_u.get("email","")}</div>',
                unsafe_allow_html=True,
            )
            _rc2[1].markdown(
                f'<div style="padding:0.4rem 0;">'
                f'<span class="badge-role {_rc}">{_u.get("role","")}</span></div>',
                unsafe_allow_html=True,
            )
            _rc2[2].markdown(
                f'<div style="font-size:0.85rem;padding:0.4rem 0;">{_u.get("name","")}</div>',
                unsafe_allow_html=True,
            )
            _rc2[3].markdown(
                f'<div style="font-size:0.82rem;color:#AAAAAA;padding:0.4rem 0;">{_dt}</div>',
                unsafe_allow_html=True,
            )
            if _rc2[4].button("Remove", key=f"rm_{_u.get('id', _u.get('email',''))}", use_container_width=True):
                _rm_ok, _rm_err = remove_approved_user(_u["id"])
                if _rm_ok:
                    st.success(f"Access removed for {_u['email']} ({_u.get('role','')} - {_u.get('name','')})")
                    st.rerun()
                else:
                    st.error(_rm_err or "Failed to remove access.")

    st.markdown("</div>", unsafe_allow_html=True)

# ============================================================
# TAB 2 — Upload Data
# ============================================================
with _tab_upload:
    st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

    # Password gate
    if "upload_authenticated" not in st.session_state:
        st.session_state.upload_authenticated = False

    if not st.session_state.upload_authenticated:
        st.markdown("### Enter upload password")
        _pwd = st.text_input("Password", type="password", key="upload_pwd")
        if st.button("Login", key="upload_login"):
            if _pwd == UPLOAD_PASSWORD:
                st.session_state.upload_authenticated = True
                st.rerun()
            else:
                st.error("Incorrect password.")
    else:
        if st.button("Logout", key="upload_logout"):
            st.session_state.upload_authenticated = False
            st.rerun()

        # Data status
        st.markdown("### Current Data Status")
        _sc1, _sc2 = st.columns(2)
        with _sc1:
            _oc = get_table_row_count("outlet_data")
            st.metric("outlet_data rows", f"{_oc:,}" if _oc else "0 (empty)")
        with _sc2:
            _tc = get_table_row_count("targets")
            st.metric("targets rows", f"{_tc:,}" if _tc else "0 (empty)")

        st.markdown("---")

        # -- Outlet upload --
        st.markdown("### 1. Upload Outlet Sales Data")
        st.markdown("""
<div class="info-box">
Upload <b>OutletFY25.xlsx</b> or <b>OutletFY26.xlsx</b>.
FY is auto-detected from the filename.
</div>
""", unsafe_allow_html=True)

        outlet_file = st.file_uploader(
            "Select OutletFY*.xlsx file", type=["xlsx", "xls"], key="outlet_upload"
        )
        _ofy_col, _omode_col = st.columns(2)
        with _ofy_col:
            fy_input = st.text_input(
                "Financial Year (e.g. FY26)",
                placeholder="Leave blank to auto-detect",
                key="fy_input",
            )
        with _omode_col:
            outlet_mode = st.selectbox(
                "Upload mode",
                ["APPEND - add to existing data", "REPLACE - delete all existing rows first"],
                key="outlet_mode",
            )
        outlet_mode_key = "append" if outlet_mode.startswith("APPEND") else "replace"

        if outlet_mode_key == "replace":
            st.warning("REPLACE mode will permanently delete ALL existing outlet data before uploading.")

        if outlet_file and st.button("Upload Outlet Data", key="upload_outlet_btn", use_container_width=True):
            fy = fy_input.strip() or (
                re.search(r"FY\d{2}", outlet_file.name, re.IGNORECASE).group(0).upper()
                if re.search(r"FY\d{2}", outlet_file.name, re.IGNORECASE) else "FY25"
            )
            st.info(f"Detected FY: **{fy}** | Mode: **{outlet_mode_key.upper()}**")
            progress_bar = st.progress(0, text="Parsing Excel file...")
            try:
                with st.spinner("Parsing Excel..."):
                    df = parse_outlet_excel(outlet_file, fy)
                import re as _re
                df.columns = [_re.sub(r'\.\d+$', '', str(c)).strip() for c in df.columns]
                df = df.loc[:, ~df.columns.duplicated(keep='first')]
                df = df.dropna(axis=1, how='all')
                st.success(f"Parsed **{len(df):,}** rows from {outlet_file.name}")
                with st.expander("Preview first 5 rows"):
                    st.dataframe(df.head(5), use_container_width=True)
                required = ["sales_officer", "net_value_order", "shop_erpid", "date"]
                missing  = [c for c in required if c not in df.columns]
                if missing:
                    st.error(f"Missing required columns: {missing}")
                    st.stop()
                if outlet_mode_key == "replace":
                    _ds = st.empty()
                    _ds.info(f"Deleting existing rows for {fy}...")
                    _dc, _de = delete_rows("outlet_data", {"fy": fy})
                    if _de:
                        _ds.error(f"Delete failed: {_de}")
                        st.stop()
                    _ds.success(f"Deleted **{_dc:,}** existing rows. Uploading...")
                progress_bar.progress(0.1, text="Uploading to Supabase...")
                _rc = st.empty()
                def _upd(uploaded, total):
                    frac = uploaded / total if total else 0
                    progress_bar.progress(0.1 + frac * 0.9,
                        text=f"Uploading... {uploaded:,} of {total:,} rows")
                    _rc.markdown(f"**{uploaded:,}** of **{total:,}** rows uploaded...")
                rows_done, err = upload_dataframe(
                    df, table="outlet_data", mode="append",
                    batch_size=100, progress_callback=_upd
                )
                _rc.empty()
                progress_bar.progress(1.0, text="Done!")
                if err and err.startswith("Upload complete."):
                    st.warning(err)
                elif err:
                    st.markdown(f'<div class="error-box">Upload failed at {rows_done:,} rows. {err}</div>',
                                unsafe_allow_html=True)
                else:
                    st.markdown(
                        f'<div class="success-box">Uploaded <b>{rows_done:,}</b> rows ({outlet_mode_key.upper()} mode).</div>',
                        unsafe_allow_html=True)
                clear_data_cache()
            except Exception as e:
                st.markdown(f'<div class="error-box">Error: {e}</div>', unsafe_allow_html=True)

        st.markdown("---")

        # -- Target upload --
        st.markdown("### 2. Upload Monthly Targets")
        st.markdown("""
<div class="info-box">
Upload the monthly target file (e.g. <b>TargetMar26.xlsx</b>).
Columns needed: RSM Name, ASM Name, SO Name, Secondary TGT, UPC (target), Month, Year.
</div>
""", unsafe_allow_html=True)

        target_file = st.file_uploader(
            "Select Target*.xlsx file", type=["xlsx", "xls"], key="target_upload"
        )
        _tm_col, _ = st.columns([2, 2])
        with _tm_col:
            target_mode = st.selectbox(
                "Upload mode",
                ["APPEND - add to existing targets", "REPLACE - delete all existing targets first"],
                key="target_mode",
            )
        target_mode_key = "append" if target_mode.startswith("APPEND") else "replace"
        if target_mode_key == "replace":
            st.warning("REPLACE mode will delete ALL existing target data.")

        if target_file and st.button("Upload Target Data", key="upload_target_btn", use_container_width=True):
            progress_bar_t = st.progress(0, text="Parsing Excel file...")
            try:
                with st.spinner("Parsing Excel..."):
                    df_t = parse_target_excel(target_file)
                st.success(f"Parsed **{len(df_t):,}** rows from {target_file.name}")
                with st.expander("Preview first 5 rows"):
                    st.dataframe(df_t.head(5), use_container_width=True)
                missing_t = [c for c in ["so_name", "secondary_tgt"] if c not in df_t.columns]
                if missing_t:
                    st.error(f"Missing required columns: {missing_t}")
                    st.stop()
                if target_mode_key == "replace":
                    _dts = st.empty()
                    if "month" in df_t.columns and "year" in df_t.columns:
                        _tm = int(df_t["month"].iloc[0]); _ty = int(df_t["year"].iloc[0])
                        _dts.info(f"Deleting targets for {_tm}/{_ty}...")
                        _dtc, _dte = delete_rows("targets", {"month": _tm, "year": _ty})
                    else:
                        _dts.info("Deleting all existing targets...")
                        _dtc, _dte = delete_rows("targets")
                    if _dte:
                        _dts.error(f"Delete failed: {_dte}")
                        st.stop()
                    _dts.success(f"Deleted **{_dtc:,}** rows. Uploading...")
                progress_bar_t.progress(0.1, text="Uploading...")
                _rct = st.empty()
                def _updt(uploaded, total):
                    frac = uploaded / total if total else 0
                    progress_bar_t.progress(0.1 + frac * 0.9,
                        text=f"Uploading... {uploaded:,} of {total:,} rows")
                    _rct.markdown(f"**{uploaded:,}** of **{total:,}** rows uploaded...")
                rows_done_t, err_t = upload_dataframe(
                    df_t, table="targets", mode="append",
                    batch_size=100, progress_callback=_updt
                )
                _rct.empty()
                progress_bar_t.progress(1.0, text="Done!")
                if err_t and err_t.startswith("Upload complete."):
                    st.warning(err_t)
                elif err_t:
                    st.markdown(f'<div class="error-box">Upload failed. {err_t}</div>',
                                unsafe_allow_html=True)
                else:
                    st.markdown(
                        f'<div class="success-box">Uploaded <b>{rows_done_t:,}</b> target rows.</div>',
                        unsafe_allow_html=True)
                clear_data_cache()
            except Exception as e:
                st.markdown(f'<div class="error-box">Error: {e}</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.markdown("""
<div style="text-align:center;color:#444;font-size:0.78rem;padding:1.5rem 0 0.5rem;">
DESi Field AI - Admin Panel - Master Only
</div>
""", unsafe_allow_html=True)
