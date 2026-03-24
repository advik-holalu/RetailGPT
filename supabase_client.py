"""
supabase_client.py
Supabase connection, data fetching (with caching), and data upload utilities.
Supports both Supabase REST API (default) and direct PostgreSQL (via SUPABASE_DB_URL).
"""

import os
import re
import math
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
SUPABASE_DB_URL = os.environ.get("SUPABASE_DB_URL", "")

_supabase_client = None


def get_supabase():
    """Return (and cache) the Supabase client."""
    global _supabase_client
    if _supabase_client is None:
        from supabase import create_client
        _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase_client


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600, show_spinner=False)
def load_outlet_data() -> pd.DataFrame:
    """
    Load all rows from outlet_data table.
    Tries direct PostgreSQL first (fast), falls back to paginated REST API.
    Returns an empty DataFrame only if both methods fail.
    """
    if SUPABASE_DB_URL:
        try:
            return _load_via_sqlalchemy("outlet_data")
        except Exception:
            pass  # fall through to REST
    try:
        return _load_via_rest("outlet_data")
    except Exception as e:
        st.error(f"Failed to load sales data: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=3600, show_spinner=False)
def load_targets() -> pd.DataFrame:
    """
    Load all rows from targets table.
    Tries direct PostgreSQL first (fast), falls back to paginated REST API.
    """
    if SUPABASE_DB_URL:
        try:
            return _load_via_sqlalchemy("targets")
        except Exception:
            pass  # fall through to REST
    try:
        return _load_via_rest("targets")
    except Exception as e:
        st.error(f"Failed to load targets: {e}")
        return pd.DataFrame()


def _load_via_sqlalchemy(table: str) -> pd.DataFrame:
    """
    Fast direct PostgreSQL fetch using SQLAlchemy.
    Raises on failure so callers can fall back to the REST API.
    """
    from sqlalchemy import create_engine, text
    engine = create_engine(SUPABASE_DB_URL)
    try:
        with engine.connect() as conn:
            df = pd.read_sql(text(f'SELECT * FROM "{table}"'), conn)
    finally:
        engine.dispose()
    return _coerce_types(df, table)


def _load_via_rest(table: str, page_size: int = 1000) -> pd.DataFrame:
    """
    Paginated REST API fetch.
    Supabase's PostgREST server caps each response at 1000 rows by default.
    page_size must be <= that server limit or the loop breaks too early.
    offset advances by the number of rows actually received so nothing is skipped.
    """
    client = get_supabase()
    all_rows = []
    offset = 0
    while True:
        resp = (
            client.table(table)
            .select("*")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        rows = resp.data or []
        if not rows:
            break
        all_rows.extend(rows)
        offset += len(rows)          # advance by actual rows received
        if len(rows) < page_size:    # last page — server had no more rows
            break

    if not all_rows:
        return pd.DataFrame()
    df = pd.DataFrame(all_rows)
    return _coerce_types(df, table)


def _coerce_types(df: pd.DataFrame, table: str) -> pd.DataFrame:
    """Ensure correct column dtypes after loading."""
    if df.empty:
        return df
    if table == "outlet_data":
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
        for col in ["net_value_order", "order_in_unit"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        for col in ["year", "month"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        # Normalise text columns
        for col in ["sales_officer", "asm", "rsm", "beats_or_route", "outlet",
                    "area", "state", "zone", "distributor"]:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip()
    if table == "targets":
        for col in ["secondary_tgt", "upc_target"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        for col in ["year", "month"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        for col in ["rsm_name", "asm_name", "so_name"]:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip()
    return df


def clear_data_cache():
    """Clear the Streamlit data cache (call after upload to force reload)."""
    load_outlet_data.clear()
    load_targets.clear()


# ---------------------------------------------------------------------------
# Upload helpers
# ---------------------------------------------------------------------------

OUTLET_COLUMN_MAP = {
    # Direct lowercase mappings
    "Area": "area",
    "Distributor": "distributor",
    "Zone": "zone",
    "State": "state",
    "Outlet": "outlet",
    "Date": "date",
    "Day": "day",
    "Year": "year",
    "Month": "month",
    "Week": "week",
    "RSM": "rsm",
    "ASM": "asm",
    # Exact names from the file
    "Sales Officer (SO)": "sales_officer",
    "Sales Officer / SO": "sales_officer",
    "Sales Officer": "sales_officer",
    "SO": "sales_officer",
    "Distributor ErpId": "distributor_erpid",
    "Distributor ERPID": "distributor_erpid",
    "Beats or Route": "beats_or_route",
    "Beat": "beats_or_route",
    "Shop ERPID": "shop_erpid",
    "Product Name": "product_name",
    "Month Week": "month_week",
    "Order In Unit": "order_in_unit",
    "Net Value (Order)": "net_value_order",
    "Net Value Order": "net_value_order",
    "L1 - Parent Category": "l1_parent_category",
    "L1- Parent Category": "l1_parent_category",
    "L1-Parent Category": "l1_parent_category",
}

TARGET_COLUMN_MAP = {
    "RSM Name": "rsm_name",
    "RSM": "rsm_name",
    "ASM Name": "asm_name",
    "ASM": "asm_name",
    "SO Name": "so_name",
    "SO": "so_name",
    "Sales Officer": "so_name",
    "Secondary TGT": "secondary_tgt",
    "Secondary Target": "secondary_tgt",
    "UPC (target)": "upc_target",
    "UPC": "upc_target",
    "UPC Target": "upc_target",
    "Month": "month",
    "Year": "year",
}


def parse_outlet_excel(file, fy: str) -> pd.DataFrame:
    """
    Parse an OutletFY25.xlsx (or FY26, etc.) file into a clean DataFrame
    ready for Supabase upload.
    """
    df = pd.read_excel(file, engine="openpyxl")
    # Strip pandas auto-suffixes like ".1", ".2" from duplicate column names
    df.columns = [re.sub(r'\.\d+$', '', col) for col in df.columns]
    # Now dedup — keeping first occurrence
    df = df.loc[:, ~df.columns.duplicated(keep='first')]
    df = df.dropna(axis=1, how='all')
    df = df.rename(columns={c: OUTLET_COLUMN_MAP.get(c, c) for c in df.columns})
    # Dedup again in case two differently-named source cols map to the same target
    df = df.loc[:, ~df.columns.duplicated(keep='first')]

    # Keep only known columns + add fy
    known_cols = list(OUTLET_COLUMN_MAP.values())
    existing = [c for c in known_cols if c in df.columns]
    df = df[existing].copy()

    # Ensure date is string for JSON serialisation
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d")

    # Convert month from "Mar-25" format to integer
    if "month" in df.columns:
        month_map = {
            'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
            'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
        }
        df["month"] = df["month"].astype(str).str[:3].map(month_map).fillna(0).astype(int)

    # Convert week from "Week_1" format to integer
    if "week" in df.columns:
        df["week"] = pd.to_numeric(
            df["week"].astype(str).str.extract(r'(\d+)')[0], errors='coerce'
        ).fillna(0).astype(int)

    # Add FY column
    df["fy"] = str(fy)

    # Fill NaN with None for JSON
    df = df.where(pd.notna(df), None)
    return df


def parse_target_excel(file) -> pd.DataFrame:
    """Parse a TargetMMYY.xlsx file into a clean DataFrame."""
    df = pd.read_excel(file, engine="openpyxl")
    df = df.rename(columns={c: TARGET_COLUMN_MAP.get(c, c) for c in df.columns})
    known_cols = list(set(TARGET_COLUMN_MAP.values()))
    existing = [c for c in known_cols if c in df.columns]
    df = df[existing].copy()

    # Convert month from "Mar" format to integer
    if "month" in df.columns:
        month_map = {
            'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
            'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
        }
        df["month"] = df["month"].astype(str).str[:3].map(month_map).fillna(0).astype(int)

    df = df.where(pd.notna(df), None)
    return df


def upload_dataframe(
    df: pd.DataFrame,
    table: str,
    mode: str = "append",
    batch_size: int = 500,
    progress_callback=None,
) -> tuple[int, str]:
    """
    Upload a DataFrame to a Supabase table.
    mode: 'replace' (delete all rows first) or 'append'.
    Returns (rows_uploaded, error_message_or_None).
    """
    client = get_supabase()

    if mode == "replace":
        try:
            # Delete all rows — use a filter that matches everything
            client.table(table).delete().neq("id", -1).execute()
        except Exception:
            # Table might not have 'id'; try alternative
            try:
                client.table(table).delete().gte("id", 0).execute()
            except Exception:
                pass  # Will be overwritten anyway

    # Final safety dedup — strip pandas auto-suffixes then drop duplicate columns
    df.columns = [re.sub(r'\.\d+$', '', col) for col in df.columns]
    df = df.loc[:, ~df.columns.duplicated(keep='first')]

    import numpy as np
    df = df.replace({np.nan: None, float('inf'): None, float('-inf'): None})
    records = df.where(pd.notnull(df), None).to_dict(orient='records')
    total = len(records)
    uploaded = 0
    n_batches = math.ceil(total / batch_size)

    for i in range(n_batches):
        batch = records[i * batch_size: (i + 1) * batch_size]
        try:
            client.table(table).insert(batch).execute()
            uploaded += len(batch)
        except Exception as e:
            return uploaded, str(e)
        if progress_callback:
            progress_callback(uploaded / total)

    return uploaded, None


def upsert_dataframe(
    df: pd.DataFrame,
    table: str,
    batch_size: int = 500,
    progress_callback=None,
) -> tuple[int, str]:
    """Upsert records (insert or update on conflict)."""
    client = get_supabase()
    records = df.to_dict(orient="records")
    total = len(records)
    uploaded = 0
    n_batches = math.ceil(total / batch_size)

    for i in range(n_batches):
        batch = records[i * batch_size: (i + 1) * batch_size]
        try:
            client.table(table).upsert(batch).execute()
            uploaded += len(batch)
        except Exception as e:
            return uploaded, str(e)
        if progress_callback:
            progress_callback(uploaded / total)

    return uploaded, None


def get_table_row_count(table: str) -> int:
    """Return the number of rows in a table (fast HEAD request)."""
    try:
        client = get_supabase()
        resp = client.table(table).select("id", count="exact").limit(1).execute()
        return resp.count or 0
    except Exception:
        return 0
