"""
supabase_client.py
Supabase connection, on-demand data fetching, and upload utilities.

Startup  : Only fetches distinct name lists + latest date  (<3 seconds).
Per-query: Fetches only matching rows with pushed-down filters (1–3 seconds).
Upload   : Handles Excel parsing and batch upload to Supabase.
"""

import os
import re
import math
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL   = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY   = os.environ.get("SUPABASE_KEY", "")
SUPABASE_DB_URL = os.environ.get("SUPABASE_DB_URL", "")

_supabase_client = None


def get_supabase():
    """Return (and lazily initialise) the Supabase client."""
    global _supabase_client
    if _supabase_client is None:
        from supabase import create_client
        _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase_client


def _reset_connection():
    """Reset the Supabase client so the next call reconnects fresh."""
    global _supabase_client
    _supabase_client = None


# ---------------------------------------------------------------------------
# Startup helpers — called once, results cached for 2 hours
# ---------------------------------------------------------------------------

@st.cache_data(ttl=7200, show_spinner=False)
def load_names() -> dict:
    """
    Fetch unique name/value lists for fuzzy matching.
    Uses DISTINCT SQL when SUPABASE_DB_URL is set (instant).
    Falls back to sampling the first 10 k rows via the REST API (~10 calls).
    """
    col_to_key = {
        "sales_officer":      "so_names",
        "asm":                "asm_names",
        "rsm":                "rsm_names",
        "beats_or_route":     "beat_names",
        "outlet":             "outlet_names",
        "l1_parent_category": "categories",
        "state":              "states",
        "zone":               "zones",
    }
    result = {v: [] for v in col_to_key.values()}

    if SUPABASE_DB_URL:
        try:
            from sqlalchemy import create_engine, text as sa_text
            engine = create_engine(SUPABASE_DB_URL)
            with engine.connect() as conn:
                for col, key in col_to_key.items():
                    rows = conn.execute(
                        sa_text(
                            f'SELECT DISTINCT "{col}" FROM outlet_data '
                            f'WHERE "{col}" IS NOT NULL ORDER BY "{col}"'
                        )
                    ).fetchall()
                    result[key] = [str(r[0]).strip() for r in rows if r[0] and str(r[0]).strip()]
            engine.dispose()
            return result
        except Exception:
            pass  # fall through to REST

    # REST fallback: sample first 10 k rows and deduplicate
    try:
        client = get_supabase()
        select_cols = ",".join(col_to_key.keys())
        accumulator = {k: set() for k in col_to_key.values()}
        for offset in range(0, 10000, 1000):
            resp = (
                client.table("outlet_data")
                .select(select_cols)
                .range(offset, offset + 999)
                .execute()
            )
            rows = resp.data or []
            if not rows:
                break
            for row in rows:
                for col, key in col_to_key.items():
                    v = row.get(col)
                    if v and str(v).strip():
                        accumulator[key].add(str(v).strip())
            if len(rows) < 1000:
                break
        for key, values in accumulator.items():
            result[key] = sorted(values)
    except Exception:
        pass

    return result


@st.cache_data(ttl=7200, show_spinner=False)
def get_categories() -> list[str]:
    """Fetch distinct l1_parent_category values — used for the category filter bar."""
    if SUPABASE_DB_URL:
        try:
            from sqlalchemy import create_engine, text as sa_text
            engine = create_engine(SUPABASE_DB_URL)
            with engine.connect() as conn:
                rows = conn.execute(sa_text(
                    "SELECT DISTINCT l1_parent_category FROM outlet_data "
                    "WHERE l1_parent_category IS NOT NULL ORDER BY l1_parent_category"
                )).fetchall()
            engine.dispose()
            return [str(r[0]).strip() for r in rows if r[0] and str(r[0]).strip()]
        except Exception:
            pass
    try:
        client = get_supabase()
        resp = (
            client.table("outlet_data")
            .select("l1_parent_category")
            .not_.is_("l1_parent_category", "null")
            .execute()
        )
        return sorted({str(r["l1_parent_category"]).strip()
                       for r in (resp.data or [])
                       if r.get("l1_parent_category")})
    except Exception:
        return []


@st.cache_data(ttl=3600, show_spinner=False)
def get_latest_date_str() -> str | None:
    """
    Fetch the latest date in outlet_data — one fast query.
    Returns 'YYYY-MM-DD' string or None if the table is empty.
    """
    if SUPABASE_DB_URL:
        try:
            from sqlalchemy import create_engine, text as sa_text
            engine = create_engine(SUPABASE_DB_URL)
            with engine.connect() as conn:
                val = conn.execute(sa_text("SELECT MAX(date) FROM outlet_data")).scalar()
            engine.dispose()
            if val:
                return str(val)[:10]
        except Exception:
            pass

    try:
        client = get_supabase()
        resp = (
            client.table("outlet_data")
            .select("date")
            .order("date", desc=True)
            .limit(1)
            .execute()
        )
        if resp.data:
            return str(resp.data[0]["date"])[:10]
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Per-query: on-demand outlet data fetch with pushed-down filters
# ---------------------------------------------------------------------------

def fetch_outlet_data(
    date_start: str = None,
    date_end: str = None,
    rsm: str = None,
    asm: str = None,
    so: str = None,
    beat: str = None,
    outlet: str = None,
    state: str = None,
    zone: str = None,
    categories: list = None,
) -> pd.DataFrame:
    """
    Fetch outlet_data rows that match ALL supplied filters.
    Tries SQLAlchemy first; falls back to Supabase REST.
    Retries once on failure (FIX 7).
    """
    import time as _t
    cats = categories or []

    def _attempt():
        if SUPABASE_DB_URL:
            try:
                return _fetch_outlet_sql(date_start, date_end, rsm, asm, so, beat, outlet, state, zone, cats)
            except Exception:
                pass
        return _fetch_outlet_rest(date_start, date_end, rsm, asm, so, beat, outlet, state, zone, cats)

    try:
        return _attempt()
    except Exception:
        _reset_connection()
        _t.sleep(2)
        try:
            return _attempt()
        except Exception as e:
            raise ConnectionError(
                "Connection lost. Please click Refresh Data to reconnect."
            ) from e


def _sql_filter(conditions, params, col, val):
    """Append an = or IN condition for a column that may be a str or list."""
    if not val:
        return
    if isinstance(val, list):
        placeholders = ", ".join(f":{col}_{i}" for i in range(len(val)))
        conditions.append(f"LOWER({col}) IN ({placeholders})")
        for i, v in enumerate(val):
            params[f"{col}_{i}"] = v.lower()
    else:
        conditions.append(f"LOWER({col}) = LOWER(:{col})")
        params[col] = val


def _fetch_outlet_sql(
    date_start, date_end, rsm, asm, so, beat, outlet, state, zone, cats=None
) -> pd.DataFrame:
    from sqlalchemy import create_engine, text as sa_text

    conditions, params = [], {}
    if date_start:
        conditions.append("date >= :date_start");  params["date_start"] = date_start
    if date_end:
        conditions.append("date <= :date_end");    params["date_end"]   = date_end
    _sql_filter(conditions, params, "rsm",            rsm)
    _sql_filter(conditions, params, "asm",            asm)
    _sql_filter(conditions, params, "sales_officer",  so)
    _sql_filter(conditions, params, "beats_or_route", beat)
    _sql_filter(conditions, params, "outlet",         outlet)
    _sql_filter(conditions, params, "state",          state)
    _sql_filter(conditions, params, "zone",           zone)
    if cats:
        _sql_filter(conditions, params, "l1_parent_category", cats)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    sql   = sa_text(f'SELECT * FROM outlet_data {where}')

    engine = create_engine(SUPABASE_DB_URL)
    try:
        with engine.connect() as conn:
            df = pd.read_sql(sql, conn, params=params)
    finally:
        engine.dispose()
    return _coerce_types(df, "outlet_data")


def _fetch_outlet_rest(
    date_start, date_end, rsm, asm, so, beat, outlet, state, zone, cats=None
) -> pd.DataFrame:
    client = get_supabase()

    def _rest_filter(q, col, val):
        if not val:
            return q
        if isinstance(val, list):
            return q.in_(col, val)
        return q.ilike(col, val)

    def _build():
        q = client.table("outlet_data").select("*")
        if date_start: q = q.gte("date", date_start)
        if date_end:   q = q.lte("date", date_end)
        q = _rest_filter(q, "rsm",                rsm)
        q = _rest_filter(q, "asm",                asm)
        q = _rest_filter(q, "sales_officer",      so)
        q = _rest_filter(q, "beats_or_route",     beat)
        q = _rest_filter(q, "outlet",             outlet)
        q = _rest_filter(q, "state",              state)
        q = _rest_filter(q, "zone",               zone)
        if cats: q = q.in_("l1_parent_category",  cats)
        return q

    all_rows, offset = [], 0
    while True:
        resp = _build().range(offset, offset + 999).execute()
        rows = resp.data or []
        if not rows:
            break
        all_rows.extend(rows)
        offset += len(rows)
        if len(rows) < 1000:
            break

    if not all_rows:
        return pd.DataFrame()
    return _coerce_types(pd.DataFrame(all_rows), "outlet_data")


# ---------------------------------------------------------------------------
# Per-query: on-demand targets fetch
# ---------------------------------------------------------------------------

def fetch_targets(
    month: int = None,
    year: int = None,
    rsm: str = None,
    asm: str = None,
    so: str = None,
) -> pd.DataFrame:
    """Fetch target rows on demand with optional filters. Retries once on failure (FIX 7)."""
    import time as _t

    def _attempt():
        if SUPABASE_DB_URL:
            try:
                return _fetch_targets_sql(month, year, rsm, asm, so)
            except Exception:
                pass
        return _fetch_targets_rest(month, year, rsm, asm, so)

    try:
        return _attempt()
    except Exception:
        _reset_connection()
        _t.sleep(2)
        try:
            return _attempt()
        except Exception as e:
            raise ConnectionError(
                "Connection lost. Please click Refresh Data to reconnect."
            ) from e


def _fetch_targets_sql(month, year, rsm, asm, so) -> pd.DataFrame:
    from sqlalchemy import create_engine, text as sa_text

    conditions, params = [], {}
    if month: conditions.append("month = :month"); params["month"] = int(month)
    if year:  conditions.append("year = :year");   params["year"]  = int(year)
    _sql_filter(conditions, params, "rsm_name", rsm)
    _sql_filter(conditions, params, "asm_name", asm)
    _sql_filter(conditions, params, "so_name",  so)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    engine = create_engine(SUPABASE_DB_URL)
    try:
        with engine.connect() as conn:
            df = pd.read_sql(sa_text(f"SELECT * FROM targets {where}"), conn, params=params)
    finally:
        engine.dispose()
    return _coerce_types(df, "targets")


def _fetch_targets_rest(month, year, rsm, asm, so) -> pd.DataFrame:
    client = get_supabase()

    def _tf(q, col, val):
        if not val: return q
        return q.in_(col, val) if isinstance(val, list) else q.ilike(col, val)

    q = client.table("targets").select("*")
    if month: q = q.eq("month", int(month))
    if year:  q = q.eq("year",  int(year))
    q = _tf(q, "rsm_name", rsm)
    q = _tf(q, "asm_name", asm)
    q = _tf(q, "so_name",  so)
    rows = q.execute().data or []
    if not rows:
        return pd.DataFrame()
    return _coerce_types(pd.DataFrame(rows), "targets")


# ---------------------------------------------------------------------------
# Shared type coercion
# ---------------------------------------------------------------------------

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
    """Clear all Streamlit data caches (call after upload to force reload)."""
    load_names.clear()
    get_latest_date_str.clear()


# ---------------------------------------------------------------------------
# Row count helper (upload page)
# ---------------------------------------------------------------------------

def get_table_row_count(table: str) -> int:
    """Return the number of rows in a table (fast HEAD request)."""
    try:
        client = get_supabase()
        resp = client.table(table).select("id", count="exact").limit(1).execute()
        return resp.count or 0
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Column maps
# ---------------------------------------------------------------------------

OUTLET_COLUMN_MAP = {
    # Direct lowercase mappings
    "Area":       "area",
    "Distributor": "distributor",
    "Zone":       "zone",
    "State":      "state",
    "Outlet":     "outlet",
    "Date":       "date",
    "Day":        "day",
    "Year":       "year",
    "Month":      "month",
    "Week":       "week",
    "RSM":        "rsm",
    "ASM":        "asm",
    # Exact names from the file
    "Sales Officer (SO)":   "sales_officer",
    "Sales Officer / SO":   "sales_officer",
    "Sales Officer":        "sales_officer",
    "SO":                   "sales_officer",
    "Distributor ErpId":    "distributor_erpid",
    "Distributor ERPID":    "distributor_erpid",
    "Beats or Route":       "beats_or_route",
    "Beat":                 "beats_or_route",
    "Shop ERPID":           "shop_erpid",
    "Product Name":         "product_name",
    "Month Week":           "month_week",
    "Order In Unit":        "order_in_unit",
    "Net Value (Order)":    "net_value_order",
    "Net Value Order":      "net_value_order",
    "L1 - Parent Category": "l1_parent_category",
    "L1- Parent Category":  "l1_parent_category",
    "L1-Parent Category":   "l1_parent_category",
}

TARGET_COLUMN_MAP = {
    "RSM Name":        "rsm_name",
    "RSM":             "rsm_name",
    "ASM Name":        "asm_name",
    "ASM":             "asm_name",
    "SO Name":         "so_name",
    "SO":              "so_name",
    "Sales Officer":   "so_name",
    "Secondary TGT":   "secondary_tgt",
    "Secondary Target": "secondary_tgt",
    "UPC (target)":    "upc_target",
    "UPC":             "upc_target",
    "UPC Target":      "upc_target",
    "Month":           "month",
    "Year":            "year",
}


# ---------------------------------------------------------------------------
# Excel parsing helpers
# ---------------------------------------------------------------------------

def parse_outlet_excel(file, fy: str) -> pd.DataFrame:
    """
    Parse an OutletFY25.xlsx (or FY26, etc.) file into a clean DataFrame
    ready for Supabase upload.
    """
    df = pd.read_excel(file, engine="openpyxl")
    # Strip pandas auto-suffixes like ".1", ".2" from duplicate column names
    df.columns = [re.sub(r'\.\d+$', '', str(col)).strip() for col in df.columns]
    # Dedup — keep first occurrence
    df = df.loc[:, ~df.columns.duplicated(keep='first')]
    df = df.dropna(axis=1, how='all')
    df = df.rename(columns={c: OUTLET_COLUMN_MAP.get(c, c) for c in df.columns})
    # Dedup again in case two differently-named source cols map to the same target
    df = df.loc[:, ~df.columns.duplicated(keep='first')]

    # Keep only known columns
    known_cols = list(dict.fromkeys(OUTLET_COLUMN_MAP.values()))  # ordered, no dupes
    existing = [c for c in known_cols if c in df.columns]
    df = df[existing].copy()

    # Ensure date is string for JSON serialisation
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d")

    # Convert month from "Mar-25" format to integer
    if "month" in df.columns:
        month_map = {
            'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4,  'May': 5,  'Jun': 6,
            'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12,
        }
        df["month"] = df["month"].astype(str).str[:3].map(month_map).fillna(0).astype(int)

    # Convert week from "Week_1" format to integer
    if "week" in df.columns:
        df["week"] = (
            pd.to_numeric(df["week"].astype(str).str.extract(r'(\d+)')[0], errors='coerce')
            .fillna(0).astype(int)
        )

    # Add FY column
    df["fy"] = str(fy)

    # Fill NaN with None for JSON
    df = df.where(pd.notna(df), None)
    return df


def parse_target_excel(file, fy: str, month_int: int) -> pd.DataFrame:
    """Parse a claude_target_FY26APR.xlsx file. fy and month_int come from the filename."""
    df = pd.read_excel(file, engine="openpyxl")
    df = df.rename(columns={c: TARGET_COLUMN_MAP.get(c, c) for c in df.columns})
    # Keep only known columns (excluding month/year — we stamp from filename)
    known_cols = [c for c in TARGET_COLUMN_MAP.values() if c not in ("month", "year")]
    existing = [c for c in known_cols if c in df.columns]
    df = df[existing].copy()
    # Stamp FY and month from filename — source of truth
    df["fy"]    = str(fy)
    df["month"] = int(month_int)
    # Derive year from FY string: FY26 → 2026
    fy_digits = re.search(r"\d{2}", fy)
    df["year"] = (2000 + int(fy_digits.group())) if fy_digits else None
    df = df.where(pd.notna(df), None)
    return df


def get_distinct_outlet_fy() -> list[str]:
    """Return sorted list of distinct FY values in outlet_data."""
    try:
        if SUPABASE_DB_URL:
            from sqlalchemy import create_engine, text as sa_text
            engine = create_engine(SUPABASE_DB_URL)
            with engine.connect() as conn:
                rows = conn.execute(sa_text("SELECT DISTINCT fy FROM outlet_data ORDER BY fy")).fetchall()
                return [r[0] for r in rows if r[0]]
    except Exception:
        pass
    try:
        client = get_supabase()
        res = client.table("outlet_data").select("fy").execute()
        return sorted({r["fy"] for r in res.data if r.get("fy")})
    except Exception:
        return []


def get_distinct_target_fy_months() -> list[dict]:
    """Return list of {fy, month} dicts present in targets table."""
    try:
        if SUPABASE_DB_URL:
            from sqlalchemy import create_engine, text as sa_text
            engine = create_engine(SUPABASE_DB_URL)
            with engine.connect() as conn:
                rows = conn.execute(
                    sa_text("SELECT DISTINCT fy, month FROM targets ORDER BY fy, month")
                ).fetchall()
                return [{"fy": r[0], "month": r[1]} for r in rows if r[0]]
    except Exception:
        pass
    try:
        client = get_supabase()
        res = client.table("targets").select("fy,month").execute()
        seen, out = set(), []
        for r in res.data:
            key = (r.get("fy"), r.get("month"))
            if key not in seen and key[0]:
                seen.add(key)
                out.append({"fy": r["fy"], "month": r["month"]})
        return sorted(out, key=lambda x: (x["fy"], x["month"]))
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Upload helpers
# ---------------------------------------------------------------------------

def delete_rows(table: str, filters: dict = None) -> tuple[int, str]:
    """
    Delete rows from a Supabase table before a REPLACE-mode upload.
    filters: dict of {col: val} for targeted delete (all conditions ANDed).
             If None, deletes all rows in ID batches of 1000.
    Returns (rows_deleted, error_or_None).
    Raises nothing — errors are returned as the second tuple element.
    """
    import time as _time
    client = get_supabase()

    # Fast path: direct SQL DELETE (no timeout risk, instant for any table size)
    if SUPABASE_DB_URL:
        try:
            from sqlalchemy import create_engine, text as sa_text
            engine = create_engine(SUPABASE_DB_URL)
            with engine.connect() as conn:
                if filters:
                    conditions = " AND ".join(f"{col} = :{col}" for col in filters)
                    # Count first
                    count_row = conn.execute(
                        sa_text(f"SELECT COUNT(*) FROM {table} WHERE {conditions}"), filters
                    ).scalar()
                    conn.execute(
                        sa_text(f"DELETE FROM {table} WHERE {conditions}"), filters
                    )
                else:
                    count_row = conn.execute(sa_text(f"SELECT COUNT(*) FROM {table}")).scalar()
                    conn.execute(sa_text(f"DELETE FROM {table}"))
                conn.commit()
            return int(count_row or 0), None
        except Exception as e:
            return 0, str(e)

    # Fallback: ID-batch delete via REST API (safe for any table size)
    try:
        total_deleted = 0
        while True:
            q = client.table(table).select("id")
            if filters:
                for col, val in filters.items():
                    q = q.eq(col, val)
            res = q.limit(1000).execute()
            ids = [r["id"] for r in (res.data or [])]
            if not ids:
                break
            client.table(table).delete().in_("id", ids).execute()
            total_deleted += len(ids)
            _time.sleep(0.05)
        return total_deleted, None
    except Exception as e:
        return 0, str(e)


def upload_dataframe(
    df: pd.DataFrame,
    table: str,
    mode: str = "append",
    batch_size: int = 100,
    progress_callback=None,
) -> tuple[int, str]:
    """
    Upload a DataFrame to a Supabase table (insert only — delete is handled separately).
    mode parameter is accepted for backward compatibility but delete must be done beforehand.
    progress_callback: called as callback(uploaded_so_far, total_rows) after each batch.
    Returns (rows_uploaded, error_message_or_None).
    Retries each batch up to 3 times on failure; skips batches that exhaust retries.
    """
    import time as _time
    import numpy as np

    client = get_supabase()

    # Final safety dedup
    df.columns = [re.sub(r'\.\d+$', '', str(col)).strip() for col in df.columns]
    df = df.loc[:, ~df.columns.duplicated(keep='first')]

    df = df.replace({np.nan: None, float('inf'): None, float('-inf'): None})
    records = df.where(pd.notnull(df), None).to_dict(orient='records')
    total     = len(records)
    uploaded  = 0
    skipped   = 0
    n_batches = math.ceil(total / batch_size) if total else 0

    for i in range(n_batches):
        batch = records[i * batch_size: (i + 1) * batch_size]
        last_err = None
        for attempt in range(3):
            try:
                client.table(table).insert(batch).execute()
                uploaded += len(batch)
                last_err = None
                break
            except Exception as e:
                last_err = e
                if attempt < 2:
                    _time.sleep(2)
        if last_err is not None:
            skipped += len(batch)

        if progress_callback:
            progress_callback(uploaded, total)

        _time.sleep(0.1)

    if skipped:
        return uploaded, f"Upload complete. {uploaded:,} rows uploaded, {skipped:,} rows skipped after retries."
    return uploaded, None


# ---------------------------------------------------------------------------
# Access control — approved_users table
# ---------------------------------------------------------------------------

import hashlib


def hash_password(password: str) -> str:
    """Return SHA-256 hex digest of the given password string."""
    return hashlib.sha256(password.encode()).hexdigest()


def check_user_access(email: str) -> list[dict]:
    """
    Return all active approved_users rows for this email (case-insensitive).
    Used for step 1 of login (email existence check only, no password).
    Returns an empty list if no access.
    """
    try:
        client = get_supabase()
        resp = (
            client.table("approved_users")
            .select("*")
            .eq("email", email.lower().strip())
            .eq("active", True)
            .execute()
        )
        return resp.data or []
    except Exception:
        return []


def verify_user_login(email: str, password_hash: str) -> list[dict]:
    """
    Return active rows matching both email and password hash.
    Used for step 2 of login (password verification).
    """
    try:
        client = get_supabase()
        resp = (
            client.table("approved_users")
            .select("*")
            .eq("email", email.lower().strip())
            .eq("password", password_hash)
            .eq("active", True)
            .execute()
        )
        return resp.data or []
    except Exception:
        return []


def add_approved_user(email: str, role: str, name: str, password: str) -> tuple[bool, str]:
    """
    Insert a new row into approved_users with a hashed password.
    Blocks exact duplicates (same email + role + name + active).
    Same email with a different role or name is allowed (dual-role users).
    Returns (success, error_message).
    """
    try:
        client = get_supabase()
        dup = (
            client.table("approved_users")
            .select("id")
            .eq("email", email.lower().strip())
            .eq("role",  role)
            .eq("name",  name)
            .eq("active", True)
            .execute()
        )
        if dup.data:
            return False, "This user already has this role assigned."
        client.table("approved_users").insert({
            "email":    email.lower().strip(),
            "role":     role,
            "name":     name,
            "active":   True,
            "password": hash_password(password),
        }).execute()
        return True, None
    except Exception as e:
        return False, str(e)


def remove_approved_user(row_id: int) -> tuple[bool, str]:
    """
    Set active = false for the row with the given id.
    Verifies the update took effect before returning success.
    """
    try:
        client = get_supabase()
        client.table("approved_users").update({"active": False}).eq("id", row_id).execute()
        verify = (
            client.table("approved_users")
            .select("active")
            .eq("id", row_id)
            .execute()
        )
        if verify.data and verify.data[0].get("active") is False:
            return True, None
        return False, "Update did not take effect. Please try again."
    except Exception as e:
        return False, str(e)


def update_approved_user(
    row_id: int, email: str, role: str, name: str, password: str = None
) -> tuple[bool, str]:
    """
    Update an approved_users row by id.
    Only updates password if a new one is provided (non-empty string).
    Returns (success, error_message).
    """
    try:
        client = get_supabase()
        updates = {
            "email": email.lower().strip(),
            "role":  role,
            "name":  name,
        }
        if password and password.strip():
            updates["password"] = hash_password(password)
        client.table("approved_users").update(updates).eq("id", row_id).execute()
        return True, None
    except Exception as e:
        return False, str(e)


def get_all_approved_users() -> list[dict]:
    """Return all active rows from approved_users, ordered by created_at."""
    try:
        client = get_supabase()
        resp = (
            client.table("approved_users")
            .select("*")
            .eq("active", True)
            .order("created_at")
            .execute()
        )
        return resp.data or []
    except Exception:
        return []


def upsert_dataframe(
    df: pd.DataFrame,
    table: str,
    batch_size: int = 500,
    progress_callback=None,
) -> tuple[int, str]:
    """Upsert records (insert or update on conflict)."""
    client = get_supabase()
    records  = df.to_dict(orient="records")
    total    = len(records)
    uploaded = 0

    for i in range(math.ceil(total / batch_size)):
        batch = records[i * batch_size: (i + 1) * batch_size]
        try:
            client.table(table).upsert(batch).execute()
            uploaded += len(batch)
        except Exception as e:
            return uploaded, str(e)
        if progress_callback:
            progress_callback(uploaded / total)

    return uploaded, None
