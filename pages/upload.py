"""
pages/upload.py
Password-protected data upload page for the data analyst.
Supports uploading OutletFY25 / OutletFY26 Excel files and Target Excel files.
Modes: REPLACE (delete all existing rows first) or APPEND (add to existing).
"""

import sys
import streamlit as st
import re
import os
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from page_utils import render_header  # noqa: E402

st.set_page_config(
    page_title="DESi Field AI — Data Upload",
    page_icon=None,
    layout="centered",
)

UPLOAD_PASSWORD = os.environ.get("UPLOAD_PASSWORD", "")

# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
* { font-family: 'Inter', sans-serif; }
#MainMenu, footer { visibility: hidden; }
.info-box {
    border: 1px solid #ccc;
    border-radius: 8px;
    padding: 0.9rem 1.2rem;
    margin: 0.75rem 0;
    font-size: 0.88rem;
}
.success-box {
    background: #1b2e1b;
    border: 1px solid #2e7d32;
    border-radius: 8px;
    padding: 0.9rem 1.2rem;
    color: #81c784;
}
.error-box {
    background: #2e1b1b;
    border: 1px solid #c62828;
    border-radius: 8px;
    padding: 0.9rem 1.2rem;
    color: #ef9a9a;
}
[data-testid="stBaseButton-secondary"], [data-testid="stBaseButton-primary"] {
    background: #F7941D !important;
    color: #0E0E0E !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
}
[data-testid="stBaseButton-secondary"]:hover, [data-testid="stBaseButton-primary"]:hover {
    background: #e0841a !important;
}
</style>
""", unsafe_allow_html=True)

render_header()

# ---------------------------------------------------------------------------
# Master access guard
# ---------------------------------------------------------------------------
if not st.session_state.get("user_email") or st.session_state.get("user_role") != "Master":
    st.error("You don't have access to this page.")
    if st.button("Back to DESi Field AI", key="upload_back_guard"):
        st.switch_page("app.py")
    st.stop()

if st.button("Back to DESi Field AI", key="upload_back_top"):
    st.switch_page("app.py")

# ---------------------------------------------------------------------------
# Password gate (secondary check kept for direct URL access safety)
# ---------------------------------------------------------------------------
if "upload_authenticated" not in st.session_state:
    st.session_state.upload_authenticated = False

if not st.session_state.upload_authenticated:
    st.markdown("### Enter upload password")
    pwd = st.text_input("Password", type="password", key="upload_pwd")
    if st.button("Login"):
        if pwd == UPLOAD_PASSWORD:
            st.session_state.upload_authenticated = True
            st.rerun()
        else:
            st.error("Incorrect password. Please try again.")
    st.stop()

# ---------------------------------------------------------------------------
# Authenticated — show upload UI
# ---------------------------------------------------------------------------
st.markdown("**Authenticated.** You can upload data files below.")
st.markdown("---")

if st.button("Logout", key="logout_btn"):
    st.session_state.upload_authenticated = False
    st.rerun()

# ---------------------------------------------------------------------------
# Import upload helpers
# ---------------------------------------------------------------------------
from supabase_client import (
    parse_outlet_excel,
    parse_target_excel,
    upload_dataframe,
    delete_rows,
    get_table_row_count,
    clear_data_cache,
)

# ---------------------------------------------------------------------------
# Current data status
# ---------------------------------------------------------------------------
st.markdown("### Current Data Status")
col1, col2 = st.columns(2)

with col1:
    outlet_count = get_table_row_count("outlet_data")
    st.metric("outlet_data rows", f"{outlet_count:,}" if outlet_count else "0 (empty)")

with col2:
    target_count = get_table_row_count("targets")
    st.metric("targets rows", f"{target_count:,}" if target_count else "0 (empty)")

st.markdown("---")

# ---------------------------------------------------------------------------
# Section 1: Outlet Data Upload
# ---------------------------------------------------------------------------
st.markdown("### 1. Upload Outlet Sales Data")
st.markdown("""
<div class="info-box">
Upload <b>OutletFY25.xlsx</b> or <b>OutletFY26.xlsx</b> (daily transactions file).
The FY is auto-detected from the filename or can be entered manually.
</div>
""", unsafe_allow_html=True)

outlet_file = st.file_uploader(
    "Select OutletFY*.xlsx file",
    type=["xlsx", "xls"],
    key="outlet_upload",
)

col_fy, col_mode_o = st.columns(2)
with col_fy:
    fy_input = st.text_input(
        "Financial Year (e.g. FY25 or FY26)",
        value="",
        placeholder="Leave blank to auto-detect from filename",
        key="fy_input",
    )
with col_mode_o:
    outlet_mode = st.selectbox(
        "Upload mode",
        ["APPEND — add to existing data", "REPLACE — delete all existing rows first"],
        key="outlet_mode",
    )

outlet_mode_key = "append" if outlet_mode.startswith("APPEND") else "replace"

if outlet_mode_key == "replace":
    st.warning(
        "⚠️ **REPLACE mode** will permanently delete ALL existing outlet data before uploading. "
        "Make sure the file is complete."
    )

if outlet_file and st.button("Upload Outlet Data", key="upload_outlet_btn", use_container_width=True):
    # Determine FY
    if fy_input.strip():
        fy = fy_input.strip()
    else:
        match = re.search(r"FY\d{2}", outlet_file.name, re.IGNORECASE)
        fy = match.group(0).upper() if match else "FY25"

    st.info(f"Detected FY: **{fy}** | Mode: **{outlet_mode_key.upper()}** | File: {outlet_file.name}")

    progress_bar = st.progress(0, text="Parsing Excel file…")

    try:
        with st.spinner("Parsing Excel…"):
            df = parse_outlet_excel(outlet_file, fy)
        # Nuclear dedup - force remove all duplicate columns right here
        import re as _re
        df.columns = [_re.sub(r'\.\d+$', '', str(col)).strip() for col in df.columns]
        df = df.loc[:, ~df.columns.duplicated(keep='first')]
        df = df.dropna(axis=1, how='all')

        st.success(f"Parsed **{len(df):,}** rows, **{len(df.columns)}** columns from {outlet_file.name}")

        # Show preview
        with st.expander("Preview first 5 rows"):
            st.dataframe(df.head(5), use_container_width=True)

        # DEBUG — remove once column issue is resolved
        with st.expander("DEBUG: columns after parsing", expanded=True):
            cols = df.columns.tolist()
            st.write(f"**Total columns:** {len(cols)}")
            st.write(cols)
            dupes = [c for c in cols if cols.count(c) > 1]
            if dupes:
                st.error(f"Duplicate column names still present: {list(set(dupes))}")
            else:
                st.success("No duplicate column names detected.")

        # Check required columns
        required = ["sales_officer", "net_value_order", "shop_erpid", "date"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            st.error(f"Missing required columns: {missing}. Please check the Excel file format.")
            st.stop()

        # ── REPLACE: delete existing rows first ────────────────────────────
        if outlet_mode_key == "replace":
            del_status = st.empty()
            del_status.info(f"Deleting existing rows for **{fy}**…")
            del_count, del_err = delete_rows("outlet_data", {"fy": fy})
            if del_err:
                del_status.error(f"Delete failed: {del_err}. Upload aborted — no rows were changed.")
                st.stop()
            del_status.success(f"Deleted **{del_count:,}** existing rows for {fy}. Now uploading fresh data…")

        # ── INSERT ──────────────────────────────────────────────────────────
        progress_bar.progress(0.1, text="Uploading to Supabase…")
        row_counter = st.empty()

        def update_progress(uploaded, total):
            frac = uploaded / total if total else 0
            progress_bar.progress(
                0.1 + frac * 0.9,
                text=f"Uploading… {uploaded:,} of {total:,} rows ({int(frac * 100)}%)",
            )
            row_counter.markdown(f"**{uploaded:,}** of **{total:,}** rows uploaded…")

        rows_done, err = upload_dataframe(
            df,
            table="outlet_data",
            mode="append",
            batch_size=100,
            progress_callback=update_progress,
        )
        row_counter.empty()

        progress_bar.progress(1.0, text="Done!")
        if err and err.startswith("Upload complete."):
            # Partial success — some batches skipped after retries
            st.warning(err)
            clear_data_cache()
            st.info("App data cache cleared. The chat page will reload fresh data on next query.")
        elif err:
            st.markdown(
                f'<div class="error-box">Upload failed at {rows_done:,} rows. Error: {err}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<div class="success-box">Successfully uploaded <b>{rows_done:,}</b> rows to outlet_data '
                f'({outlet_mode_key.upper()} mode).</div>',
                unsafe_allow_html=True,
            )
            clear_data_cache()
            st.info("App data cache cleared. The chat page will reload fresh data on next query.")

    except Exception as e:
        st.markdown(
            f'<div class="error-box">❌ Error processing file: {e}</div>',
            unsafe_allow_html=True,
        )

st.markdown("---")

# ---------------------------------------------------------------------------
# Section 2: Target Data Upload
# ---------------------------------------------------------------------------
st.markdown("### 2. Upload Monthly Targets")
st.markdown("""
<div class="info-box">
Upload the monthly target file (e.g. <b>TargetMar26.xlsx</b>).
Each row should have: RSM Name, ASM Name, SO Name, Secondary TGT, UPC (target), Month, Year.
</div>
""", unsafe_allow_html=True)

target_file = st.file_uploader(
    "Select Target*.xlsx file",
    type=["xlsx", "xls"],
    key="target_upload",
)

col_mode_t, _ = st.columns([2, 2])
with col_mode_t:
    target_mode = st.selectbox(
        "Upload mode",
        ["APPEND — add to existing targets", "REPLACE — delete all existing targets first"],
        key="target_mode",
    )

target_mode_key = "append" if target_mode.startswith("APPEND") else "replace"

if target_mode_key == "replace":
    st.warning("⚠️ **REPLACE mode** will delete ALL existing target data.")

if target_file and st.button("Upload Target Data", key="upload_target_btn", use_container_width=True):
    progress_bar_t = st.progress(0, text="Parsing Excel file…")

    try:
        with st.spinner("Parsing Excel…"):
            df_t = parse_target_excel(target_file)

        st.success(f"Parsed **{len(df_t):,}** rows from {target_file.name}")

        with st.expander("Preview first 5 rows"):
            st.dataframe(df_t.head(5), use_container_width=True)

        required_t = ["so_name", "secondary_tgt"]
        missing_t = [c for c in required_t if c not in df_t.columns]
        if missing_t:
            st.error(f"Missing required columns: {missing_t}. Please check the file format.")
            st.stop()

        # ── REPLACE: delete existing targets for this month/year ───────────
        if target_mode_key == "replace":
            del_status_t = st.empty()
            if "month" in df_t.columns and "year" in df_t.columns:
                t_month = int(df_t["month"].iloc[0])
                t_year  = int(df_t["year"].iloc[0])
                del_status_t.info(f"Deleting existing targets for **{t_month}/{t_year}**…")
                del_count_t, del_err_t = delete_rows("targets", {"month": t_month, "year": t_year})
            else:
                del_status_t.info("Deleting all existing targets…")
                del_count_t, del_err_t = delete_rows("targets")
            if del_err_t:
                del_status_t.error(f"Delete failed: {del_err_t}. Upload aborted — no rows were changed.")
                st.stop()
            del_status_t.success(f"Deleted **{del_count_t:,}** existing target rows. Now uploading fresh data…")

        # ── INSERT ──────────────────────────────────────────────────────────
        progress_bar_t.progress(0.1, text="Uploading…")
        row_counter_t = st.empty()

        def update_target_progress(uploaded, total):
            frac = uploaded / total if total else 0
            progress_bar_t.progress(
                0.1 + frac * 0.9,
                text=f"Uploading… {uploaded:,} of {total:,} rows ({int(frac * 100)}%)",
            )
            row_counter_t.markdown(f"**{uploaded:,}** of **{total:,}** rows uploaded…")

        rows_done_t, err_t = upload_dataframe(
            df_t,
            table="targets",
            mode="append",
            batch_size=100,
            progress_callback=update_target_progress,
        )
        row_counter_t.empty()

        progress_bar_t.progress(1.0, text="Done!")
        if err_t and err_t.startswith("Upload complete."):
            st.warning(err_t)
            clear_data_cache()
        elif err_t:
            st.markdown(
                f'<div class="error-box">Upload failed at {rows_done_t:,} rows. Error: {err_t}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<div class="success-box">Successfully uploaded <b>{rows_done_t:,}</b> target rows '
                f'({target_mode_key.upper()} mode).</div>',
                unsafe_allow_html=True,
            )
            clear_data_cache()

    except Exception as e:
        st.markdown(
            f'<div class="error-box">❌ Error processing file: {e}</div>',
            unsafe_allow_html=True,
        )

st.markdown("---")

# ---------------------------------------------------------------------------
# Section 3: Table Setup SQL
# ---------------------------------------------------------------------------
st.markdown("### 3. First-time Setup: Create Tables")
st.markdown("""
<div class="info-box">
If this is a fresh Supabase project, run the following SQL in the <b>Supabase SQL Editor</b>
to create the required tables.
</div>
""", unsafe_allow_html=True)

with st.expander("Show Setup SQL"):
    st.code("""
-- outlet_data table
CREATE TABLE IF NOT EXISTS outlet_data (
    id              BIGSERIAL PRIMARY KEY,
    area            TEXT,
    sales_officer   TEXT,
    distributor     TEXT,
    distributor_erpid TEXT,
    zone            TEXT,
    state           TEXT,
    beats_or_route  TEXT,
    shop_erpid      TEXT,
    outlet          TEXT,
    product_name    TEXT,
    date            DATE,
    day             INTEGER,
    year            INTEGER,
    month           INTEGER,
    week            INTEGER,
    month_week      TEXT,
    order_in_unit   NUMERIC(12,2),
    net_value_order NUMERIC(14,2),
    rsm             TEXT,
    asm             TEXT,
    l1_parent_category TEXT,
    fy              TEXT DEFAULT 'FY25'
);

-- Indexes for fast filtering
CREATE INDEX IF NOT EXISTS idx_outlet_date       ON outlet_data(date);
CREATE INDEX IF NOT EXISTS idx_outlet_so         ON outlet_data(sales_officer);
CREATE INDEX IF NOT EXISTS idx_outlet_asm        ON outlet_data(asm);
CREATE INDEX IF NOT EXISTS idx_outlet_rsm        ON outlet_data(rsm);
CREATE INDEX IF NOT EXISTS idx_outlet_month_year ON outlet_data(year, month);
CREATE INDEX IF NOT EXISTS idx_outlet_fy         ON outlet_data(fy);

-- targets table
CREATE TABLE IF NOT EXISTS targets (
    id            BIGSERIAL PRIMARY KEY,
    rsm_name      TEXT,
    asm_name      TEXT,
    so_name       TEXT,
    secondary_tgt NUMERIC(14,2),
    upc_target    NUMERIC(10,2),
    month         INTEGER,
    year          INTEGER
);

CREATE INDEX IF NOT EXISTS idx_targets_so       ON targets(so_name);
CREATE INDEX IF NOT EXISTS idx_targets_asm      ON targets(asm_name);
CREATE INDEX IF NOT EXISTS idx_targets_my       ON targets(month, year);
""", language="sql")

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.markdown("""
<br>
<div style="text-align:center; color:#444; font-size:0.8rem;">
DESi Field AI · Data Upload · Restricted Access
</div>
""", unsafe_allow_html=True)
