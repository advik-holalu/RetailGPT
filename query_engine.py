"""
query_engine.py
Core logic: understands a natural language question → fetches only needed rows
→ calculates metrics → formats response.

Flow:
  1. Claude extracts structured intent (entities, time range, query type).
  2. fuzzy_matcher resolves all mentioned names against the pre-loaded name lists.
  3. If names are ambiguous, return a clarification instead of answering.
  4. Compute the date range for the question (pushed to DB as a filter).
  5. Fetch only the matching rows from Supabase (on demand, no full-table load).
  6. Calculate metrics on the small result set using metrics.py.
  7. Claude formats the final natural-language response.
"""

import json
import re
import calendar
import pandas as pd
import anthropic
import os
from dotenv import load_dotenv

from fuzzy_matcher import match_name
from metrics import (
    apply_time_filter, filter_lmtd, filter_mtd,
    calc_metrics, calc_metrics_grouped, merge_targets,
    format_metrics_table, summarize_single,
    format_currency, format_indian, format_pct, ach_label,
)
from supabase_client import fetch_outlet_data, fetch_targets
from prompts import (
    SYSTEM_PROMPT, RESPONSE_SYSTEM, RESPONSE_USER_TEMPLATE,
    ENTITY_EXTRACTION_SYSTEM, ENTITY_EXTRACTION_USER_TEMPLATE,
    format_history_for_extraction, format_history_for_response,
    build_data_summary,
)

load_dotenv()

MODEL      = "claude-sonnet-4-5"
MAX_TOKENS = 2048

MONTH_NAMES = {
    1: "January", 2: "February", 3: "March",    4: "April",
    5: "May",     6: "June",     7: "July",      8: "August",
    9: "September", 10: "October", 11: "November", 12: "December",
}


class QueryEngine:
    """Main query engine for RetailGPT."""

    def __init__(self, names_dict: dict, latest_date_str: str | None):
        """
        names_dict       : output of supabase_client.load_names()
        latest_date_str  : 'YYYY-MM-DD' string from supabase_client.get_latest_date_str()
        """
        self.client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

        # Latest reference date (used for time-range calculations)
        self._latest_date: pd.Timestamp | None = (
            pd.Timestamp(latest_date_str) if latest_date_str else None
        )

        # Name lists for fuzzy matching (populated from names_dict)
        self._so_names      = names_dict.get("so_names",    [])
        self._asm_names     = names_dict.get("asm_names",   [])
        self._rsm_names     = names_dict.get("rsm_names",   [])
        self._beat_names    = names_dict.get("beat_names",  [])
        self._outlet_names  = names_dict.get("outlet_names",[])
        self._states        = names_dict.get("states",      [])
        self._zones         = names_dict.get("zones",       [])
        self._categories    = names_dict.get("categories",  [])

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def process(
        self,
        question: str,
        chat_history: list[dict],
        session_context: dict,
        user_scope: dict | None = None,
        category_filter: list[str] | None = None,
    ) -> tuple[str, dict]:
        """
        Process a user question.
        user_scope: e.g. {"rsm": "Ravi Kumar"} or {"asm": "Puneeth"} — the
                    logged-in user's identity, applied as a default filter when
                    no explicit entity is mentioned in the question.
        Returns (response_text, updated_session_context).
        """
        if self._latest_date is None:
            return (
                "I don't have any sales data loaded yet. Please ask your data analyst "
                "to upload the OutletFY25 Excel file via the Upload page.",
                session_context,
            )

        try:
            intent = self._extract_intent(question, chat_history)
            if intent is None:
                return (
                    "I had trouble understanding that question. Could you rephrase it?",
                    session_context,
                )

            if intent.get("context_from_history"):
                intent = self._merge_context(intent, session_context)

            # Apply the logged-in user's scope as a last-resort default
            if user_scope:
                intent = self._apply_user_scope(intent, user_scope)

            resolved, clarification = self._resolve_entities(intent)
            if clarification:
                return clarification, session_context

            new_context = self._build_new_context(resolved, session_context)
            response    = self._compute_and_format(question, resolved, chat_history, category_filter)

            return response, new_context

        except Exception:
            return (
                "I ran into an issue processing your question. "
                "Please try rephrasing. (Details logged for the tech team.)",
                session_context,
            )

    # ------------------------------------------------------------------
    # Step 1: Intent extraction
    # ------------------------------------------------------------------

    def _extract_intent(self, question: str, chat_history: list[dict]) -> dict | None:
        history_text = format_history_for_extraction(chat_history)
        user_msg = ENTITY_EXTRACTION_USER_TEMPLATE.format(
            history=history_text, question=question
        )
        try:
            resp = self.client.messages.create(
                model=MODEL,
                max_tokens=512,
                system=ENTITY_EXTRACTION_SYSTEM,
                messages=[{"role": "user", "content": user_msg}],
            )
            raw = resp.content[0].text.strip()
            raw = re.sub(r"^```json\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
            return json.loads(raw)
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Step 2: Context merge / build
    # ------------------------------------------------------------------

    def _merge_context(self, intent: dict, ctx: dict) -> dict:
        for key in ["rsm", "asm", "so", "beat", "outlet", "state", "zone"]:
            if not intent.get(key) and ctx.get(key):
                intent[key] = ctx[key]
        return intent

    def _apply_user_scope(self, intent: dict, user_scope: dict) -> dict:
        """
        Fill in the logged-in user's identity for any entity fields that are
        still empty after intent extraction and context merge.
        Only fills — never overwrites an explicit mention.
        """
        for key, val in user_scope.items():
            if not intent.get(key):
                intent[key] = val
        return intent

    def _build_new_context(self, resolved: dict, old_ctx: dict) -> dict:
        ctx = dict(old_ctx)
        for key in ["rsm", "asm", "so", "beat", "outlet", "state", "zone"]:
            if resolved.get(key):
                ctx[key] = resolved[key]
        return ctx

    # ------------------------------------------------------------------
    # Step 3: Fuzzy name resolution
    # ------------------------------------------------------------------

    def _resolve_entities(self, intent: dict) -> tuple[dict, str | None]:
        resolved = dict(intent)
        checks = [
            ("so",     self._so_names,     "Sales Officer"),
            ("asm",    self._asm_names,    "ASM"),
            ("rsm",    self._rsm_names,    "RSM"),
            ("beat",   self._beat_names,   "Beat"),
            ("outlet", self._outlet_names, "Outlet"),
            ("state",  self._states,       "State"),
            ("zone",   self._zones,        "Region/Zone"),
        ]
        for field, candidates, label in checks:
            raw = intent.get(field)
            # Already a resolved list (from user_scope) — skip fuzzy matching
            if isinstance(raw, list):
                resolved[field] = raw
                continue
            if not raw or str(raw).strip().lower() in ("null", "none", ""):
                resolved[field] = None
                continue
            result = match_name(str(raw), candidates, entity_type=label)
            if result["status"] in ("matched", "clarify"):
                resolved[field] = result["matched"]
            elif result["status"] == "ambiguous":
                return resolved, result["message"]
            elif result["status"] == "not_found":
                return resolved, result["message"]
        return resolved, None

    # ------------------------------------------------------------------
    # Step 4: Date-range computation (for DB pushdown)
    # ------------------------------------------------------------------

    def _compute_date_range(
        self, time_range: str, resolved: dict
    ) -> tuple[str | None, str | None]:
        """
        Return (date_start, date_end) as 'YYYY-MM-DD' strings suitable for
        DB filtering.  Returns wider ranges where needed (e.g. MTD+LMTD);
        the in-memory apply_time_filter call that follows trims to exact bounds.
        """
        if self._latest_date is None:
            return None, None

        latest = self._latest_date
        fmt    = "%Y-%m-%d"
        tr     = (time_range or "mtd").lower()

        if tr in ("mtd", "this_month"):
            return latest.replace(day=1).strftime(fmt), latest.strftime(fmt)

        if tr in ("lmtd", "last_month"):
            prev_y, prev_m = (
                (latest.year - 1, 12) if latest.month == 1
                else (latest.year, latest.month - 1)
            )
            max_day = calendar.monthrange(prev_y, prev_m)[1]
            end_day = min(latest.day, max_day)
            start = latest.replace(year=prev_y, month=prev_m, day=1)
            end   = latest.replace(year=prev_y, month=prev_m, day=end_day)
            return start.strftime(fmt), end.strftime(fmt)

        if tr in ("3m", "6m"):
            n_months = 6 if tr == "6m" else 3
            months = []
            for i in range(1, n_months + 1):
                m, y = latest.month - i, latest.year
                while m <= 0:
                    m += 12; y -= 1
                months.append((m, y))
            min_m, min_y = min(months, key=lambda x: (x[1], x[0]))
            max_m, max_y = max(months, key=lambda x: (x[1], x[0]))
            last_day = calendar.monthrange(max_y, max_m)[1]
            start = pd.Timestamp(year=min_y, month=min_m, day=1)
            end   = pd.Timestamp(year=max_y, month=max_m, day=last_day)
            return start.strftime(fmt), end.strftime(fmt)

        if tr == "ytd":
            fy_y  = latest.year if latest.month >= 4 else latest.year - 1
            start = pd.Timestamp(year=fy_y, month=4, day=1)
            return start.strftime(fmt), latest.strftime(fmt)

        if tr == "today":
            d = latest.strftime(fmt)
            return d, d

        if tr == "yesterday":
            d = (latest - pd.Timedelta(days=1)).strftime(fmt)
            return d, d

        if tr == "specific_month_year":
            m = resolved.get("specific_month")
            y = resolved.get("specific_year")
            if m and y:
                last_day = calendar.monthrange(int(y), int(m))[1]
                return f"{y}-{int(m):02d}-01", f"{y}-{int(m):02d}-{last_day:02d}"

        if tr == "all":
            return None, None

        # Default: MTD
        return latest.replace(day=1).strftime(fmt), latest.strftime(fmt)

    # ------------------------------------------------------------------
    # Step 5: On-demand data fetching
    # ------------------------------------------------------------------

    def _fetch_outlet(
        self,
        resolved: dict,
        date_start: str = None,
        date_end: str = None,
        cats: list[str] = None,
    ) -> pd.DataFrame:
        """Push hierarchy + date + optional category filters to the DB."""
        return fetch_outlet_data(
            date_start=date_start,
            date_end=date_end,
            rsm=resolved.get("rsm"),
            asm=resolved.get("asm"),
            so=resolved.get("so"),
            beat=resolved.get("beat"),
            outlet=resolved.get("outlet"),
            state=resolved.get("state"),
            zone=resolved.get("zone"),
            categories=cats or [],
        )

    def _fetch_targets(self, resolved: dict, month: int, year: int) -> pd.DataFrame:
        """Fetch only the target rows needed for this query."""
        return fetch_targets(
            month=month,
            year=year,
            rsm=resolved.get("rsm"),
            asm=resolved.get("asm"),
            so=resolved.get("so"),
        )

    # ------------------------------------------------------------------
    # Step 6: Compute metrics and format response
    # ------------------------------------------------------------------

    @staticmethod
    def _wants_targets(question: str, resolved: dict) -> bool:
        """Return True only if the user explicitly asked for target/achievement data."""
        keywords = ("target", "tgt", "achievement", "ach%", "achiev", "vs target",
                    "against target", "attainment")
        q_lower = question.lower()
        if any(kw in q_lower for kw in keywords):
            return True
        if resolved.get("query_type") == "target_achievement":
            return True
        if "target" in [m.lower() for m in resolved.get("metrics", [])]:
            return True
        return False

    def _compute_and_format(
        self, question: str, resolved: dict, chat_history: list[dict],
        category_filter: list[str] | None = None,
    ) -> str:
        query_type = resolved.get("query_type", "summary")
        time_range = resolved.get("time_range", "mtd")

        latest    = self._latest_date
        cur_month = latest.month
        cur_year  = latest.year

        # Target month / year
        if time_range in ("last_month", "lmtd"):
            tgt_month = cur_month - 1 if cur_month > 1 else 12
            tgt_year  = cur_year if cur_month > 1 else cur_year - 1
        elif resolved.get("specific_month") and resolved.get("specific_year"):
            tgt_month = int(resolved["specific_month"])
            tgt_year  = int(resolved["specific_year"])
        else:
            tgt_month, tgt_year = cur_month, cur_year

        time_label = self._build_time_label(time_range, latest, resolved)

        cats         = category_filter or []
        want_targets = self._wants_targets(question, resolved)

        if query_type in ("top_n", "bottom_n", "breakdown"):
            data_summary = self._compute_grouped(
                resolved, time_range, query_type, tgt_month, tgt_year, time_label, cats, want_targets
            )
        elif query_type == "comparison_mtd_lmtd":
            data_summary = self._compute_comparison(resolved, time_label, cats)
        elif query_type == "beat_wise":
            data_summary = self._compute_beat_wise(resolved, time_range, time_label, cats)
        elif query_type == "category_wise":
            data_summary = self._compute_category_wise(resolved, time_range, time_label, cats)
        elif query_type == "outlet_wise":
            data_summary = self._compute_outlet_wise(
                resolved, time_range, resolved.get("n", 10), time_label, cats
            )
        elif query_type == "target_achievement":
            data_summary = self._compute_target_achievement(
                resolved, time_range, tgt_month, tgt_year, time_label, cats
            )
        else:
            data_summary = self._compute_summary(
                resolved, time_range, tgt_month, tgt_year, time_label, cats, want_targets
            )

        return self._format_response(question, data_summary, chat_history)

    # ------------------------------------------------------------------
    # Computation helpers
    # ------------------------------------------------------------------

    def _compute_summary(self, resolved, time_range, tgt_month, tgt_year, time_label, cats=None, want_targets=False) -> str:
        date_start, date_end = self._compute_date_range(time_range, resolved)
        df  = self._fetch_outlet(resolved, date_start, date_end, cats)
        df  = apply_time_filter(df, time_range,
                                resolved.get("specific_month"), resolved.get("specific_year"))
        m   = calc_metrics(df)

        tgt_row = None
        if want_targets:
            tdf = self._fetch_targets(resolved, tgt_month, tgt_year)
            if not tdf.empty:
                tgt_row = {
                    "secondary_tgt": tdf["secondary_tgt"].sum(),
                    "upc_target":    tdf["upc_target"].sum(),
                }

        display = summarize_single(m, tgt_row)
        lines   = [f"Time period: {time_label}"]
        for k, v in display.items():
            lines.append(f"  {k}: {v}")
        return "\n".join(lines)

    def _compute_grouped(
        self, resolved, time_range, query_type, tgt_month, tgt_year, time_label, cats=None, want_targets=False
    ) -> str:
        date_start, date_end = self._compute_date_range(time_range, resolved)
        df  = self._fetch_outlet(resolved, date_start, date_end, cats)
        df  = apply_time_filter(df, time_range,
                                resolved.get("specific_month"), resolved.get("specific_year"))

        col_map = {
            "so":       "sales_officer",
            "asm":      "asm",
            "rsm":      "rsm",
            "beat":     "beats_or_route",
            "outlet":   "outlet",
            "category": "l1_parent_category",
            "state":    "state",
            "zone":     "zone",
        }
        group_by = resolved.get("group_by")
        if not group_by:
            group_by = "so" if (resolved.get("asm") or resolved.get("rsm")) else "asm"
        group_col = col_map.get(group_by, group_by)

        if group_col not in df.columns:
            return f"Time period: {time_label}\nNo data available for grouping by {group_by}."

        grp             = calc_metrics_grouped(df, group_col)
        include_targets = want_targets or query_type == "target_achievement"

        if include_targets:
            tdf = self._fetch_targets(resolved, tgt_month, tgt_year)
            grp = merge_targets(grp, tdf, group_col, tgt_month, tgt_year)

        n = int(resolved.get("n") or 10)
        if query_type == "top_n":
            grp = grp.head(n)
        elif query_type == "bottom_n":
            grp = grp.tail(n).sort_values("secondary")

        display_df = format_metrics_table(grp, group_col, include_targets=include_targets)
        table_md   = display_df.to_markdown(index=False)
        return f"Time period: {time_label}\nGroup by: {group_by}\n\n{table_md}"

    def _compute_comparison(self, resolved, time_label, cats=None) -> str:
        # Fetch one range covering both MTD and LMTD, then split in memory
        latest = self._latest_date
        prev_y, prev_m = (
            (latest.year - 1, 12) if latest.month == 1
            else (latest.year, latest.month - 1)
        )
        date_start = latest.replace(year=prev_y, month=prev_m, day=1).strftime("%Y-%m-%d")
        date_end   = latest.strftime("%Y-%m-%d")

        df      = self._fetch_outlet(resolved, date_start, date_end, cats)
        mtd_df  = filter_mtd(df)
        lmtd_df = filter_lmtd(df)
        mtd_m   = calc_metrics(mtd_df)
        lmtd_m  = calc_metrics(lmtd_df)

        def delta(a, b):
            if b == 0:
                return "—"
            pct  = (a - b) / b * 100
            sign = "+" if pct >= 0 else ""
            return f"{sign}{pct:.1f}%"

        rows = []
        for label, key, is_currency in [
            ("Secondary", "secondary", True),
            ("PC",        "pc",        False),
            ("UPC",       "upc",       False),
            ("TC",        "tc",        False),
            ("ABV",       "abv",       True),
        ]:
            mtd_val  = format_currency(mtd_m[key])  if is_currency else f"{int(mtd_m[key]):,}"
            lmtd_val = format_currency(lmtd_m[key]) if is_currency else f"{int(lmtd_m[key]):,}"
            rows.append({
                "Metric": label,
                "MTD":    mtd_val,
                "LMTD":   lmtd_val,
                "Change": delta(mtd_m[key], lmtd_m[key]),
            })

        table = pd.DataFrame(rows).to_markdown(index=False)
        return f"MTD vs LMTD Comparison\n\n{table}"

    def _compute_beat_wise(self, resolved, time_range, time_label, cats=None) -> str:
        date_start, date_end = self._compute_date_range(time_range, resolved)
        df  = self._fetch_outlet(resolved, date_start, date_end, cats)
        df  = apply_time_filter(df, time_range,
                                resolved.get("specific_month"), resolved.get("specific_year"))
        grp        = calc_metrics_grouped(df, "beats_or_route")
        display_df = format_metrics_table(grp, "beats_or_route")
        table_md   = display_df.to_markdown(index=False)
        return f"Time period: {time_label}\nBeat-wise breakdown\n\n{table_md}"

    def _compute_category_wise(self, resolved, time_range, time_label, cats=None) -> str:
        date_start, date_end = self._compute_date_range(time_range, resolved)
        df = self._fetch_outlet(resolved, date_start, date_end, cats)
        df = apply_time_filter(df, time_range,
                               resolved.get("specific_month"), resolved.get("specific_year"))

        if "l1_parent_category" not in df.columns or df.empty:
            return f"Time period: {time_label}\nNo category data available."

        grp           = calc_metrics_grouped(df, "l1_parent_category")
        total_sec     = grp["secondary"].sum()
        grp["contribution%"]  = (grp["secondary"] / total_sec * 100).round(1).astype(str) + "%"
        grp["secondary_fmt"]  = grp["secondary"].apply(format_currency)

        display = grp[["rank", "l1_parent_category", "secondary_fmt", "contribution%", "pc", "upc"]].copy()
        display.columns = ["#", "Category", "Secondary", "Share%", "PC", "UPC"]
        return f"Time period: {time_label}\nCategory-wise breakdown\n\n{display.to_markdown(index=False)}"

    def _compute_outlet_wise(self, resolved, time_range, n, time_label, cats=None) -> str:
        date_start, date_end = self._compute_date_range(time_range, resolved)
        df  = self._fetch_outlet(resolved, date_start, date_end, cats)
        df  = apply_time_filter(df, time_range,
                                resolved.get("specific_month"), resolved.get("specific_year"))
        grp = calc_metrics_grouped(df, "outlet")
        n   = int(n or 10)
        direction = resolved.get("query_type", "top_n")
        top = grp.tail(n).sort_values("secondary") if direction == "bottom_n" else grp.head(n)
        display_df = format_metrics_table(top, "outlet")
        label = "Bottom" if direction == "bottom_n" else "Top"
        return f"Time period: {time_label}\n{label} {n} Outlets\n\n{display_df.to_markdown(index=False)}"

    def _compute_target_achievement(
        self, resolved, time_range, tgt_month, tgt_year, time_label, cats=None
    ) -> str:
        date_start, date_end = self._compute_date_range(time_range, resolved)
        df  = self._fetch_outlet(resolved, date_start, date_end, cats)
        df  = apply_time_filter(df, time_range,
                                resolved.get("specific_month"), resolved.get("specific_year"))

        col_map   = {"so": "sales_officer", "asm": "asm", "rsm": "rsm"}
        group_by  = resolved.get("group_by", "so")
        group_col = col_map.get(group_by, "sales_officer")

        if group_col not in df.columns:
            return f"Time period: {time_label}\nNo data available."

        grp  = calc_metrics_grouped(df, group_col)
        tdf  = self._fetch_targets(resolved, tgt_month, tgt_year)
        grp  = merge_targets(grp, tdf, group_col, tgt_month, tgt_year)

        display_df = format_metrics_table(grp, group_col, include_targets=True)
        return (
            f"Time period: {time_label}\nTarget vs Achievement\n\n"
            f"{display_df.to_markdown(index=False)}"
        )

    # ------------------------------------------------------------------
    # Final formatting via Claude
    # ------------------------------------------------------------------

    def _format_response(
        self, question: str, data_summary: str, chat_history: list[dict]
    ) -> str:
        user_content  = RESPONSE_USER_TEMPLATE.format(
            question=question, data_summary=data_summary
        )
        history_msgs  = format_history_for_response(chat_history)
        messages      = history_msgs + [{"role": "user", "content": user_content}]

        resp = self.client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=RESPONSE_SYSTEM,
            messages=messages,
        )
        return resp.content[0].text.strip()

    # ------------------------------------------------------------------
    # Time label helper
    # ------------------------------------------------------------------

    def _build_time_label(self, time_range: str, latest: pd.Timestamp, resolved: dict) -> str:
        tr         = (time_range or "mtd").lower()
        month_name = MONTH_NAMES.get(latest.month, "")
        year       = latest.year

        if tr in ("mtd", "this_month"):
            return f"MTD {month_name} {year} (up to {latest.strftime('%d %b')})"
        if tr in ("lmtd", "last_month"):
            prev_m = latest.month - 1 if latest.month > 1 else 12
            prev_y = year if latest.month > 1 else year - 1
            return f"LMTD {MONTH_NAMES.get(prev_m, '')} {prev_y}"
        if tr in ("3m", "6m"):
            n_months = 6 if tr == "6m" else 3
            prev_months = []
            for i in range(1, n_months + 1):
                m, y = latest.month - i, year
                while m <= 0:
                    m += 12; y -= 1
                prev_months.append(MONTH_NAMES.get(m, "")[:3])
            return f"Last {n_months} months ({', '.join(reversed(prev_months))})"
        if tr == "ytd":
            fy_y = year if latest.month >= 4 else year - 1
            return f"YTD FY{str(fy_y)[2:]+str(fy_y+1)[2:]} (Apr {fy_y} – {latest.strftime('%d %b %Y')})"
        if tr == "today":
            return f"Today ({latest.strftime('%d %b %Y')})"
        if tr == "yesterday":
            return "Yesterday"
        if tr == "specific_month_year":
            m = resolved.get("specific_month")
            y = resolved.get("specific_year")
            if m and y:
                return f"{MONTH_NAMES.get(int(m), '')} {y}"
        return time_range.upper()
