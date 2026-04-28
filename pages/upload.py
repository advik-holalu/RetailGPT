"""
pages/upload.py
Password-protected data upload page for the data analyst.
File naming convention (mandatory):
  Outlet : claude_outlet_FY26.xlsx
  Target : claude_target_FY26APR.xlsx
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
    page_title="RetailAI — Data Upload",
    page_icon=None,
    layout="centered",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
* { font-family: 'Inter', sans-serif; }
#MainMenu, footer { visibility: hidden; }
.convention-box {
    background: #1a1a2e;
    border: 1px solid #F7941D;
    border-radius: 10px;
    padding: 1rem 1.4rem;
    margin: 0.75rem 0 1.2rem;
    font-size: 0.86rem;
    line-height: 1.7;
}
.convention-box code {
    background: rgba(247,148,29,0.15);
    color: #F7941D;
    padding: 0.1rem 0.4rem;
    border-radius: 4px;
    font-size: 0.85rem;
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
# Access guard
# ---------------------------------------------------------------------------
if not st.session_state.get("user_email") or st.session_state.get("user_role") != "Master":
    st.error("You don't have access to this page.")
    if st.button("Back to RetailAI", key="upload_back_guard"):
        st.switch_page("app.py")
    st.stop()

if st.button("Back to RetailAI", key="upload_back_top"):
    st.switch_page("app.py")

st.markdown("**Authenticated.** You can upload data files below.")
st.markdown("---")

if st.button("Logout", key="logout_btn"):
    st.session_state.upload_authenticated = False
    st.rerun()

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------
from supabase_client import (
    parse_outlet_excel,
    parse_target_excel,
    upload_dataframe,
    delete_rows,
    get_table_row_count,
    clear_data_cache,
    get_distinct_outlet_fy,
    get_distinct_target_fy_months,
)

MONTH_MAP = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4,  "MAY": 5,  "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}
MONTH_NUM_TO_NAME = {v: k for k, v in MONTH_MAP.items()}

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
# Section 1 — Outlet Data
# ---------------------------------------------------------------------------
st.markdown("### 1. Upload Outlet Sales Data")

st.markdown("""
<div class="convention-box">
<b>File naming convention (mandatory)</b><br>
Files must be named exactly: <code>claude_outlet_FY26.xlsx</code><br>
&bull; <code>FY26</code> is the financial year tag — it will be auto-detected from the filename.<br>
&bull; This tag is stored in the <code>fy</code> column for every row.<br>
&bull; To re-upload updated data for a year, use <b>Replace</b> — it only deletes that FY's rows.<br>
&bull; Use <b>Append</b> only the very first time you upload a brand new FY file.
</div>
""", unsafe_allow_html=True)

outlet_file = st.file_uploader(
    "Select claude_outlet_FY**.xlsx",
    type=["xlsx", "xls"],
    key="outlet_upload",
)

if outlet_file:
    # Auto-detect FY from filename
    fy_match = re.search(r"FY\d{2}", outlet_file.name, re.IGNORECASE)
    detected_fy = fy_match.group(0).upper() if fy_match else None

    if not detected_fy:
        st.error(
            f"Cannot detect FY from filename **{outlet_file.name}**. "
            "Rename it to match the convention: `claude_outlet_FY26.xlsx`"
        )
    else:
        st.success(f"Detected FY: **{detected_fy}** from `{outlet_file.name}`")

        existing_fys = get_distinct_outlet_fy()
        outlet_mode = st.radio(
            "Upload mode",
            ["Replace — update existing FY data", "Append — first-time upload of a new FY"],
            key="outlet_mode_radio",
            horizontal=True,
        )
        outlet_is_replace = outlet_mode.startswith("Replace")

        if outlet_is_replace:
            if existing_fys:
                replace_fy_options = existing_fys
                default_idx = replace_fy_options.index(detected_fy) if detected_fy in replace_fy_options else 0
                replace_fy = st.selectbox(
                    "Which FY do you want to replace?",
                    options=replace_fy_options,
                    index=default_idx,
                    key="outlet_replace_fy",
                )
                st.warning(
                    f"This will delete all **{replace_fy}** rows in outlet_data "
                    f"and replace them with the contents of `{outlet_file.name}`."
                )
            else:
                st.info("No existing FY data found in DB. Switching to Append automatically.")
                outlet_is_replace = False
                replace_fy = detected_fy
        else:
            replace_fy = detected_fy
            if detected_fy in existing_fys:
                st.warning(
                    f"**{detected_fy}** already exists in the database. "
                    "If you're re-uploading updated data, use **Replace** instead to avoid duplicates."
                )

        if st.button("Upload Outlet Data", key="upload_outlet_btn", use_container_width=True):
            progress_bar = st.progress(0, text="Parsing Excel file…")
            try:
                with st.spinner("Parsing Excel…"):
                    df = parse_outlet_excel(outlet_file, detected_fy)
                df.columns = [re.sub(r'\.\d+$', '', str(c)).strip() for c in df.columns]
                df = df.loc[:, ~df.columns.duplicated(keep='first')]
                df = df.dropna(axis=1, how='all')

                st.success(f"Parsed **{len(df):,}** rows from `{outlet_file.name}`")

                with st.expander("Preview first 5 rows"):
                    st.dataframe(df.head(5), use_container_width=True)

                required = ["sales_officer", "net_value_order", "shop_erpid", "date"]
                missing = [c for c in required if c not in df.columns]
                if missing:
                    st.error(f"Missing required columns: {missing}")
                    st.stop()

                if outlet_is_replace:
                    del_status = st.empty()
                    del_status.info(f"Deleting existing rows for **{replace_fy}**…")
                    del_count, del_err = delete_rows("outlet_data", {"fy": replace_fy})
                    if del_err:
                        del_status.error(f"Delete failed: {del_err}. No rows changed.")
                        st.stop()
                    del_status.success(f"Deleted **{del_count:,}** rows for {replace_fy}. Uploading fresh data…")

                progress_bar.progress(0.1, text="Uploading to Supabase…")
                row_counter = st.empty()

                def _outlet_progress(uploaded, total):
                    frac = uploaded / total if total else 0
                    progress_bar.progress(0.1 + frac * 0.9, text=f"Uploading… {uploaded:,}/{total:,} ({int(frac*100)}%)")
                    row_counter.markdown(f"**{uploaded:,}** of **{total:,}** rows uploaded…")

                rows_done, err = upload_dataframe(df, table="outlet_data", mode="append",
                                                  batch_size=500, progress_callback=_outlet_progress)
                row_counter.empty()
                progress_bar.progress(1.0, text="Done!")

                if err and err.startswith("Upload complete."):
                    st.warning(err)
                elif err:
                    st.markdown(f'<div class="error-box">Upload failed at {rows_done:,} rows. Error: {err}</div>', unsafe_allow_html=True)
                else:
                    mode_label = "REPLACE" if outlet_is_replace else "APPEND"
                    st.markdown(f'<div class="success-box">Successfully uploaded <b>{rows_done:,}</b> rows ({mode_label} — {detected_fy}).</div>', unsafe_allow_html=True)
                clear_data_cache()
                st.info("App data cache cleared.")
            except Exception as e:
                st.markdown(f'<div class="error-box">Error processing file: {e}</div>', unsafe_allow_html=True)

st.markdown("---")

# ---------------------------------------------------------------------------
# Section 2 — Target Data
# ---------------------------------------------------------------------------
st.markdown("### 2. Upload Monthly Targets")

st.markdown("""
<div class="convention-box">
<b>File naming convention (mandatory)</b><br>
Files must be named exactly: <code>claude_target_FY26APR.xlsx</code><br>
&bull; <code>FY26</code> = financial year, <code>APR</code> = month (3-letter abbreviation).<br>
&bull; Both values are auto-detected from the filename and stamped as <code>fy</code> and <code>month</code> columns.<br>
&bull; The Excel itself does NOT need month/year columns — they come from the filename.<br>
&bull; Valid month codes: JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC
</div>
""", unsafe_allow_html=True)

target_file = st.file_uploader(
    "Select claude_target_FY**XXX.xlsx",
    type=["xlsx", "xls"],
    key="target_upload",
)

if target_file:
    # Auto-detect FY and month from filename
    t_fy_match  = re.search(r"FY\d{2}", target_file.name, re.IGNORECASE)
    t_mon_match = re.search(r"FY\d{2}([A-Za-z]{3})", target_file.name, re.IGNORECASE)

    detected_tfy   = t_fy_match.group(0).upper()  if t_fy_match  else None
    detected_tmon  = t_mon_match.group(1).upper()  if t_mon_match else None
    detected_tmon_int = MONTH_MAP.get(detected_tmon) if detected_tmon else None

    errors = []
    if not detected_tfy:
        errors.append("Cannot detect FY from filename.")
    if not detected_tmon or not detected_tmon_int:
        errors.append(f"Cannot detect month from filename (got `{detected_tmon}`). Use a 3-letter month code like APR.")

    if errors:
        st.error(" | ".join(errors) + f" Filename: **{target_file.name}** — rename to `claude_target_FY26APR.xlsx`")
    else:
        st.success(f"Detected: FY **{detected_tfy}** | Month **{detected_tmon}** ({detected_tmon_int})")

        existing_tm = get_distinct_target_fy_months()
        existing_fys_t = sorted({x["fy"] for x in existing_tm})

        target_mode = st.radio(
            "Upload mode",
            [
                "Replace — update existing target data",
                "Append — first-time upload",
            ],
            key="target_mode_radio",
            horizontal=True,
        )
        target_is_replace = target_mode.startswith("Replace")

        replace_scope = None
        if target_is_replace:
            replace_scope = st.radio(
                "What to replace",
                [
                    f"This month only — {detected_tfy} {detected_tmon} (recommended)",
                    f"Entire FY — all months of {detected_tfy}",
                    "Everything — all target data",
                ],
                key="target_replace_scope",
            )
            if "This month only" in replace_scope:
                st.warning(f"Will delete all targets for **{detected_tfy} — {detected_tmon}** and replace with this file.")
            elif "Entire FY" in replace_scope:
                st.warning(f"Will delete ALL months of **{detected_tfy}** targets and replace with this file.")
            else:
                st.error("Will delete **ALL target data** across all FYs and months. Use with caution.")

        if st.button("Upload Target Data", key="upload_target_btn", use_container_width=True):
            progress_bar_t = st.progress(0, text="Parsing Excel file…")
            try:
                with st.spinner("Parsing Excel…"):
                    df_t = parse_target_excel(target_file, detected_tfy, detected_tmon_int)

                st.success(f"Parsed **{len(df_t):,}** rows | FY={detected_tfy} | month={detected_tmon_int}")

                with st.expander("Preview first 5 rows"):
                    st.dataframe(df_t.head(5), use_container_width=True)

                required_t = ["so_name", "secondary_tgt"]
                missing_t = [c for c in required_t if c not in df_t.columns]
                if missing_t:
                    st.error(f"Missing required columns: {missing_t}")
                    st.stop()

                if target_is_replace:
                    del_status_t = st.empty()
                    if "This month only" in replace_scope:
                        del_filters = {"fy": detected_tfy, "month": detected_tmon_int}
                        del_status_t.info(f"Deleting targets for {detected_tfy} {detected_tmon}…")
                    elif "Entire FY" in replace_scope:
                        del_filters = {"fy": detected_tfy}
                        del_status_t.info(f"Deleting all {detected_tfy} targets…")
                    else:
                        del_filters = None
                        del_status_t.info("Deleting ALL target data…")

                    del_count_t, del_err_t = delete_rows("targets", del_filters)
                    if del_err_t:
                        del_status_t.error(f"Delete failed: {del_err_t}. No rows changed.")
                        st.stop()
                    del_status_t.success(f"Deleted **{del_count_t:,}** target rows. Uploading fresh data…")

                progress_bar_t.progress(0.1, text="Uploading…")
                row_counter_t = st.empty()

                def _target_progress(uploaded, total):
                    frac = uploaded / total if total else 0
                    progress_bar_t.progress(0.1 + frac * 0.9, text=f"Uploading… {uploaded:,}/{total:,} ({int(frac*100)}%)")
                    row_counter_t.markdown(f"**{uploaded:,}** of **{total:,}** rows uploaded…")

                rows_done_t, err_t = upload_dataframe(df_t, table="targets", mode="append",
                                                      batch_size=500, progress_callback=_target_progress)
                row_counter_t.empty()
                progress_bar_t.progress(1.0, text="Done!")

                if err_t and err_t.startswith("Upload complete."):
                    st.warning(err_t)
                elif err_t:
                    st.markdown(f'<div class="error-box">Upload failed at {rows_done_t:,} rows. Error: {err_t}</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="success-box">Successfully uploaded <b>{rows_done_t:,}</b> target rows ({detected_tfy} {detected_tmon}).</div>', unsafe_allow_html=True)
                clear_data_cache()
                st.info("App data cache cleared.")
            except Exception as e:
                st.markdown(f'<div class="error-box">Error processing file: {e}</div>', unsafe_allow_html=True)

st.markdown("---")

# ---------------------------------------------------------------------------
# Section 3 — First-time Setup SQL
# ---------------------------------------------------------------------------
st.markdown("### 3. First-time Setup: Create / Migrate Tables")
st.markdown("Run this SQL in the **Supabase SQL Editor** if setting up for the first time, or if adding the new `fy` column to targets.")

with st.expander("Show Setup SQL"):
    st.code("""
-- outlet_data table
CREATE TABLE IF NOT EXISTS outlet_data (
    id                BIGSERIAL PRIMARY KEY,
    area              TEXT,
    sales_officer     TEXT,
    distributor       TEXT,
    distributor_erpid TEXT,
    zone              TEXT,
    state             TEXT,
    beats_or_route    TEXT,
    shop_erpid        TEXT,
    outlet            TEXT,
    product_name      TEXT,
    date              DATE,
    day               INTEGER,
    year              INTEGER,
    month             INTEGER,
    week              INTEGER,
    month_week        TEXT,
    order_in_unit     NUMERIC(12,2),
    net_value_order   NUMERIC(14,2),
    rsm               TEXT,
    asm               TEXT,
    l1_parent_category TEXT,
    fy                TEXT
);

CREATE INDEX IF NOT EXISTS idx_outlet_date       ON outlet_data(date);
CREATE INDEX IF NOT EXISTS idx_outlet_so         ON outlet_data(sales_officer);
CREATE INDEX IF NOT EXISTS idx_outlet_asm        ON outlet_data(asm);
CREATE INDEX IF NOT EXISTS idx_outlet_rsm        ON outlet_data(rsm);
CREATE INDEX IF NOT EXISTS idx_outlet_month_year ON outlet_data(year, month);
CREATE INDEX IF NOT EXISTS idx_outlet_fy         ON outlet_data(fy);

-- targets table (with fy column)
CREATE TABLE IF NOT EXISTS targets (
    id            BIGSERIAL PRIMARY KEY,
    rsm_name      TEXT,
    asm_name      TEXT,
    so_name       TEXT,
    secondary_tgt NUMERIC(14,2),
    upc_target    NUMERIC(10,2),
    month         INTEGER,
    year          INTEGER,
    fy            TEXT
);

CREATE INDEX IF NOT EXISTS idx_targets_so  ON targets(so_name);
CREATE INDEX IF NOT EXISTS idx_targets_asm ON targets(asm_name);
CREATE INDEX IF NOT EXISTS idx_targets_my  ON targets(month, year);
CREATE INDEX IF NOT EXISTS idx_targets_fy  ON targets(fy);

-- If targets table already exists, just add the fy column:
ALTER TABLE targets ADD COLUMN IF NOT EXISTS fy TEXT;
""", language="sql")

st.markdown("""
<br>
<div style="text-align:center; color:#444; font-size:0.8rem;">
RetailAI · Data Upload · Restricted Access
</div>
""", unsafe_allow_html=True)
