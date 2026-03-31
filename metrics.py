"""
metrics.py
All metric calculations for RetailGPT.
Metrics: Secondary, TC, PC, UPC, ABV, and their target/achievement variants.
Time periods: MTD, LMTD, 3M, YTD, specific month.
Indian number formatting.
"""

import pandas as pd
import numpy as np
from datetime import datetime, date

MONTH_NAMES = {
    1: "January", 2: "February", 3: "March", 4: "April",
    5: "May", 6: "June", 7: "July", 8: "August",
    9: "September", 10: "October", 11: "November", 12: "December",
}


# ---------------------------------------------------------------------------
# Indian Number Formatting
# ---------------------------------------------------------------------------

def format_indian(n, decimals: int = 2) -> str:
    """Format a number in Indian number system (lakhs/crores)."""
    if n is None or (isinstance(n, float) and np.isnan(n)):
        return "—"
    n = float(n)
    if n == 0:
        return "0"

    neg = n < 0
    n = abs(n)

    if n >= 1_00_00_000:
        val = n / 1_00_00_000
        return ("-" if neg else "") + f"{val:,.{decimals}f} Cr"
    if n >= 1_00_000:
        val = n / 1_00_000
        return ("-" if neg else "") + f"{val:,.{decimals}f} L"
    if n >= 1_000:
        # Indian grouping: 1,00,000 style
        return ("-" if neg else "") + _indian_group(int(round(n)))
    return ("-" if neg else "") + f"{n:.{decimals}f}"


def _indian_group(n: int) -> str:
    """Apply Indian grouping (2-2-3) to an integer."""
    s = str(abs(n))
    if len(s) <= 3:
        return s
    # Last 3 digits
    result = s[-3:]
    s = s[:-3]
    while s:
        result = s[-2:] + "," + result
        s = s[:-2]
    return result


def format_currency(n, decimals: int = 2) -> str:
    """Format as ₹ + Indian number."""
    if n is None or (isinstance(n, float) and np.isnan(n)):
        return "—"
    return f"₹{format_indian(n, decimals)}"


def format_pct(n, decimals: int = 1) -> str:
    """Format as percentage string."""
    if n is None or (isinstance(n, float) and np.isnan(n)):
        return "—"
    return f"{float(n):.{decimals}f}%"


def ach_label(pct: float) -> str:
    """Return achievement label with emoji."""
    if pct is None or (isinstance(pct, float) and np.isnan(pct)):
        return "—"
    if pct >= 100:
        return f"{pct:.1f}% ✅"
    if pct >= 90:
        return f"{pct:.1f}% ⚠️"
    return f"{pct:.1f}% 🔴"


# ---------------------------------------------------------------------------
# Latest Date Helpers
# ---------------------------------------------------------------------------

def get_latest_date(df: pd.DataFrame) -> pd.Timestamp:
    """Return the latest date in the dataset (used as reference, NOT system date)."""
    return pd.to_datetime(df["date"]).max()


def get_current_month_year(df: pd.DataFrame) -> tuple[int, int]:
    """Return (month, year) of the latest date in the dataset."""
    latest = get_latest_date(df)
    return latest.month, latest.year


# ---------------------------------------------------------------------------
# Date Range Filters
# ---------------------------------------------------------------------------

def filter_mtd(df: pd.DataFrame) -> pd.DataFrame:
    """Filter to MTD: 1st of latest month → latest date in data."""
    latest = get_latest_date(df)
    start = latest.replace(day=1)
    mask = (pd.to_datetime(df["date"]) >= start) & (pd.to_datetime(df["date"]) <= latest)
    return df[mask].copy()


def filter_lmtd(df: pd.DataFrame) -> pd.DataFrame:
    """
    Filter to LMTD: 1st of previous month → same day-of-month as latest date
    but in the previous month.
    """
    latest = get_latest_date(df)
    # Previous month
    if latest.month == 1:
        prev_month = 12
        prev_year = latest.year - 1
    else:
        prev_month = latest.month - 1
        prev_year = latest.year

    start = latest.replace(year=prev_year, month=prev_month, day=1)
    # Same day-of-month cap (handle month-end edge cases)
    import calendar
    max_day = calendar.monthrange(prev_year, prev_month)[1]
    end_day = min(latest.day, max_day)
    end = latest.replace(year=prev_year, month=prev_month, day=end_day)

    mask = (pd.to_datetime(df["date"]) >= start) & (pd.to_datetime(df["date"]) <= end)
    return df[mask].copy()


def filter_nm(df: pd.DataFrame, n: int) -> pd.DataFrame:
    """Filter to last N complete calendar months based on latest date."""
    latest = get_latest_date(df)
    months = []
    for i in range(1, n + 1):
        m, y = latest.month - i, latest.year
        while m <= 0:
            m += 12; y -= 1
        months.append((m, y))
    mask = pd.Series(False, index=df.index)
    dates = pd.to_datetime(df["date"])
    for m, y in months:
        mask |= (dates.dt.month == m) & (dates.dt.year == y)
    return df[mask].copy()


def filter_3m(df: pd.DataFrame) -> pd.DataFrame:
    """Filter to last 3 complete calendar months based on latest date."""
    return filter_nm(df, 3)


def filter_6m(df: pd.DataFrame) -> pd.DataFrame:
    """Filter to last 6 complete calendar months based on latest date."""
    return filter_nm(df, 6)


def filter_ytd(df: pd.DataFrame) -> pd.DataFrame:
    """Filter to YTD: April 1st of current FY to latest date."""
    latest = get_latest_date(df)
    # Indian FY starts April 1
    fy_start_year = latest.year if latest.month >= 4 else latest.year - 1
    fy_start = pd.Timestamp(year=fy_start_year, month=4, day=1)
    mask = (pd.to_datetime(df["date"]) >= fy_start) & (pd.to_datetime(df["date"]) <= latest)
    return df[mask].copy()


def filter_specific_month(df: pd.DataFrame, month: int, year: int) -> pd.DataFrame:
    """Filter to a specific month and year."""
    mask = (pd.to_datetime(df["date"]).dt.month == month) & (pd.to_datetime(df["date"]).dt.year == year)
    return df[mask].copy()


def filter_today(df: pd.DataFrame) -> pd.DataFrame:
    """Filter to the latest date in data (proxy for 'today')."""
    latest = get_latest_date(df)
    mask = pd.to_datetime(df["date"]) == latest
    return df[mask].copy()


def filter_yesterday(df: pd.DataFrame) -> pd.DataFrame:
    """Filter to the second-latest date in data."""
    dates = sorted(pd.to_datetime(df["date"]).unique())
    if len(dates) < 2:
        return df.iloc[0:0].copy()
    yesterday = dates[-2]
    mask = pd.to_datetime(df["date"]) == yesterday
    return df[mask].copy()


def apply_time_filter(df: pd.DataFrame, time_range: str, specific_month: int = None, specific_year: int = None) -> pd.DataFrame:
    """Dispatch to the right time filter based on time_range string."""
    tr = (time_range or "mtd").lower()
    if tr == "mtd" or tr == "this_month":
        return filter_mtd(df)
    if tr == "lmtd" or tr == "last_month":
        return filter_lmtd(df)
    if tr == "3m":
        return filter_3m(df)
    if tr == "6m":
        return filter_6m(df)
    if tr == "ytd":
        return filter_ytd(df)
    if tr == "today":
        return filter_today(df)
    if tr == "yesterday":
        return filter_yesterday(df)
    if tr == "specific_month_year" and specific_month and specific_year:
        return filter_specific_month(df, specific_month, specific_year)
    if tr == "all":
        return df.copy()
    # Default to MTD
    return filter_mtd(df)


# ---------------------------------------------------------------------------
# Core Metric Calculations
# ---------------------------------------------------------------------------

def calc_metrics(df: pd.DataFrame) -> dict:
    """
    Calculate all core metrics from a (pre-filtered) outlet_data DataFrame.
    Returns a flat dict of metric values (numeric).
    """
    if df.empty:
        return {
            "secondary": 0.0,
            "tc": 0,
            "pc": 0,
            "upc": 0,
            "abv": 0.0,
        }

    secondary = df["net_value_order"].sum()
    tc = len(df)
    pc_df = df[df["net_value_order"] > 0]
    pc = len(pc_df)
    upc = pc_df["shop_erpid"].nunique()
    abv = secondary / pc if pc > 0 else 0.0

    return {
        "secondary": float(secondary),
        "tc": int(tc),
        "pc": int(pc),
        "upc": int(upc),
        "abv": float(abv),
    }


def calc_metrics_grouped(df: pd.DataFrame, group_col: str) -> pd.DataFrame:
    """
    Calculate all core metrics grouped by a column.
    Returns a DataFrame with columns: [group_col, secondary, tc, pc, upc, abv].
    """
    if df.empty or group_col not in df.columns:
        return pd.DataFrame(columns=[group_col, "secondary", "tc", "pc", "upc", "abv"])

    df = df.copy()
    df["_is_pc"] = (df["net_value_order"] > 0).astype(int)
    df["_pc_shop"] = df.apply(
        lambda r: r["shop_erpid"] if r["net_value_order"] > 0 else None, axis=1
    )

    grouped = df.groupby(group_col).agg(
        secondary=("net_value_order", "sum"),
        tc=(group_col, "count"),
        pc=("_is_pc", "sum"),
    ).reset_index()

    # UPC: distinct shop_erpid where net_value_order > 0
    upc_df = (
        df[df["net_value_order"] > 0]
        .groupby(group_col)["shop_erpid"]
        .nunique()
        .reset_index()
        .rename(columns={"shop_erpid": "upc"})
    )

    grouped = grouped.merge(upc_df, on=group_col, how="left")
    grouped["upc"] = grouped["upc"].fillna(0).astype(int)
    grouped["abv"] = grouped.apply(
        lambda r: r["secondary"] / r["pc"] if r["pc"] > 0 else 0.0, axis=1
    )
    grouped = grouped.sort_values("secondary", ascending=False).reset_index(drop=True)
    grouped["rank"] = range(1, len(grouped) + 1)
    return grouped


def merge_targets(
    metrics_df: pd.DataFrame,
    targets_df: pd.DataFrame,
    group_col: str,
    month: int,
    year: int,
) -> pd.DataFrame:
    """
    Merge calculated metrics with target data.
    group_col should be one of: 'sales_officer', 'asm', 'rsm'.
    Matches target col names: so_name, asm_name, rsm_name.
    """
    target_col_map = {
        "sales_officer": "so_name",
        "asm": "asm_name",
        "rsm": "rsm_name",
    }
    t_col = target_col_map.get(group_col)
    if t_col is None or targets_df is None or targets_df.empty:
        return metrics_df

    tgt_filtered = targets_df[
        (targets_df["month"].astype(str) == str(month))
        & (targets_df["year"].astype(str) == str(year))
    ].copy()

    if tgt_filtered.empty:
        return metrics_df

    tgt_filtered = tgt_filtered[[t_col, "secondary_tgt", "upc_target"]].copy()
    tgt_filtered = tgt_filtered.rename(columns={t_col: group_col})

    merged = metrics_df.merge(tgt_filtered, on=group_col, how="left")
    merged["secondary_tgt"] = merged.get("secondary_tgt", pd.Series(dtype=float))
    merged["upc_target"] = merged.get("upc_target", pd.Series(dtype=float))

    merged["secondary_ach"] = merged.apply(
        lambda r: (r["secondary"] / r["secondary_tgt"] * 100)
        if pd.notna(r.get("secondary_tgt")) and r.get("secondary_tgt", 0) > 0
        else None,
        axis=1,
    )
    merged["upc_ach"] = merged.apply(
        lambda r: (r["upc"] / r["upc_target"] * 100)
        if pd.notna(r.get("upc_target")) and r.get("upc_target", 0) > 0
        else None,
        axis=1,
    )
    return merged


# ---------------------------------------------------------------------------
# Formatted Summary Tables
# ---------------------------------------------------------------------------

def format_metrics_table(df: pd.DataFrame, group_col: str, include_targets: bool = False) -> pd.DataFrame:
    """Return a display-ready DataFrame with Indian-formatted values."""
    display = pd.DataFrame()
    display["#"] = df.get("rank", range(1, len(df) + 1))
    display[group_col.replace("_", " ").title()] = df[group_col]
    display["Secondary"] = df["secondary"].apply(format_currency)
    display["PC"] = df["pc"].apply(lambda x: f"{int(x):,}")
    display["UPC"] = df["upc"].apply(lambda x: f"{int(x):,}")
    display["TC"] = df["tc"].apply(lambda x: f"{int(x):,}")
    display["ABV"] = df["abv"].apply(format_currency)

    if include_targets and "secondary_tgt" in df.columns:
        display["Sec Target"] = df["secondary_tgt"].apply(
            lambda x: format_currency(x) if pd.notna(x) else "—"
        )
        display["Sec Ach%"] = df["secondary_ach"].apply(
            lambda x: ach_label(x) if pd.notna(x) else "—"
        )
    if include_targets and "upc_target" in df.columns:
        display["UPC Target"] = df["upc_target"].apply(
            lambda x: f"{int(x):,}" if pd.notna(x) else "—"
        )
        display["UPC Ach%"] = df["upc_ach"].apply(
            lambda x: ach_label(x) if pd.notna(x) else "—"
        )

    return display


def summarize_single(metrics: dict, targets: dict = None) -> dict:
    """Return a display-ready dict for a single-entity summary."""
    out = {
        "Secondary": format_currency(metrics["secondary"]),
        "TC": f"{metrics['tc']:,}",
        "PC": f"{metrics['pc']:,}",
        "UPC": f"{metrics['upc']:,}",
        "ABV": format_currency(metrics["abv"]),
    }
    if targets:
        sec_tgt = targets.get("secondary_tgt")
        upc_tgt = targets.get("upc_target")
        if sec_tgt:
            ach = metrics["secondary"] / sec_tgt * 100
            out["Secondary Target"] = format_currency(sec_tgt)
            out["Secondary Ach%"] = ach_label(ach)
        if upc_tgt:
            uach = metrics["upc"] / upc_tgt * 100
            out["UPC Target"] = f"{int(upc_tgt):,}"
            out["UPC Ach%"] = ach_label(uach)
    return out
