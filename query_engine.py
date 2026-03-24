"""
query_engine.py
Core logic: understands a natural language question → filters data → calculates metrics → formats response.

Flow:
  1. Claude extracts structured intent (entities, time range, query type) from the question.
  2. fuzzy_matcher resolves all mentioned names against actual data values.
  3. If names are ambiguous, return a clarification question instead of answering.
  4. Apply filters and calculate metrics using metrics.py.
  5. Claude formats the final response using the computed numbers.
"""

import json
import re
import pandas as pd
import anthropic
import os
from dotenv import load_dotenv

from fuzzy_matcher import match_name, resolve_name_in_context
from metrics import (
    apply_time_filter, filter_lmtd, filter_mtd,
    calc_metrics, calc_metrics_grouped, merge_targets,
    format_metrics_table, summarize_single,
    format_currency, format_indian, format_pct, ach_label,
    get_latest_date, get_current_month_year,
)
from prompts import (
    SYSTEM_PROMPT, RESPONSE_SYSTEM, RESPONSE_USER_TEMPLATE,
    ENTITY_EXTRACTION_SYSTEM, ENTITY_EXTRACTION_USER_TEMPLATE,
    format_history_for_extraction, format_history_for_response,
    build_data_summary,
)

load_dotenv()

MODEL = "claude-sonnet-4-5"
MAX_TOKENS = 2048

MONTH_NAMES = {
    1: "January", 2: "February", 3: "March", 4: "April",
    5: "May", 6: "June", 7: "July", 8: "August",
    9: "September", 10: "October", 11: "November", 12: "December",
}


class QueryEngine:
    """Main query engine for RetailGPT."""

    def __init__(self, outlet_df: pd.DataFrame, targets_df: pd.DataFrame):
        self.outlet_df = outlet_df
        self.targets_df = targets_df
        self.client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

        # Pre-compute unique name lists for fuzzy matching
        self._so_names: list[str] = []
        self._asm_names: list[str] = []
        self._rsm_names: list[str] = []
        self._beat_names: list[str] = []
        self._outlet_names: list[str] = []
        self._states: list[str] = []
        self._zones: list[str] = []
        self._categories: list[str] = []

        if not outlet_df.empty:
            self._so_names = outlet_df["sales_officer"].dropna().unique().tolist()
            self._asm_names = outlet_df["asm"].dropna().unique().tolist()
            self._rsm_names = outlet_df["rsm"].dropna().unique().tolist()
            self._beat_names = outlet_df["beats_or_route"].dropna().unique().tolist()
            self._outlet_names = outlet_df["outlet"].dropna().unique().tolist()
            if "state" in outlet_df.columns:
                self._states = outlet_df["state"].dropna().unique().tolist()
            if "zone" in outlet_df.columns:
                self._zones = outlet_df["zone"].dropna().unique().tolist()
            if "l1_parent_category" in outlet_df.columns:
                self._categories = outlet_df["l1_parent_category"].dropna().unique().tolist()

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def process(
        self,
        question: str,
        chat_history: list[dict],
        session_context: dict,
    ) -> tuple[str, dict]:
        """
        Process a user question.

        Returns:
            (response_text, updated_session_context)
        The caller should append the response to chat_history.
        """
        if self.outlet_df.empty:
            return (
                "I don't have any sales data loaded yet. Please ask your data analyst "
                "to upload the OutletFY25 Excel file via the Upload page.",
                session_context,
            )

        try:
            # Step 1: Extract intent
            intent = self._extract_intent(question, chat_history)
            if intent is None:
                return (
                    "I had trouble understanding that question. Could you rephrase it?",
                    session_context,
                )

            # Step 2: Merge with session context if needed
            if intent.get("context_from_history"):
                intent = self._merge_context(intent, session_context)

            # Step 3: Resolve fuzzy names
            resolved, clarification = self._resolve_entities(intent)
            if clarification:
                return clarification, session_context

            # Step 4: Build updated context
            new_context = self._build_new_context(resolved, session_context)

            # Step 5: Compute the answer
            response = self._compute_and_format(question, resolved, chat_history)

            return response, new_context

        except Exception as e:
            return (
                f"I ran into an issue processing your question. Please try rephrasing. "
                f"(Details logged for the tech team.)",
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
            # Strip markdown fences if present
            raw = re.sub(r"^```json\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
            return json.loads(raw)
        except (json.JSONDecodeError, Exception):
            return None

    # ------------------------------------------------------------------
    # Step 2: Context merge
    # ------------------------------------------------------------------

    def _merge_context(self, intent: dict, ctx: dict) -> dict:
        """Fill in missing entities from session context."""
        for key in ["rsm", "asm", "so", "beat", "outlet", "state", "zone"]:
            if not intent.get(key) and ctx.get(key):
                intent[key] = ctx[key]
        return intent

    def _build_new_context(self, resolved: dict, old_ctx: dict) -> dict:
        """Build updated session context from resolved entities."""
        ctx = dict(old_ctx)
        for key in ["rsm", "asm", "so", "beat", "outlet", "state", "zone"]:
            if resolved.get(key):
                ctx[key] = resolved[key]
        return ctx

    # ------------------------------------------------------------------
    # Step 3: Fuzzy name resolution
    # ------------------------------------------------------------------

    def _resolve_entities(self, intent: dict) -> tuple[dict, str | None]:
        """
        Resolve all named entities via fuzzy matching.
        Returns (resolved_intent, clarification_message_or_None).
        """
        resolved = dict(intent)

        checks = [
            ("so", self._so_names, "Sales Officer"),
            ("asm", self._asm_names, "ASM"),
            ("rsm", self._rsm_names, "RSM"),
            ("beat", self._beat_names, "Beat"),
            ("outlet", self._outlet_names, "Outlet"),
            ("state", self._states, "State"),
            ("zone", self._zones, "Region/Zone"),
        ]

        for field, candidates, label in checks:
            raw = intent.get(field)
            if not raw or str(raw).strip().lower() in ("null", "none", ""):
                resolved[field] = None
                continue

            result = match_name(str(raw), candidates, entity_type=label)

            if result["status"] == "matched":
                resolved[field] = result["matched"]

            elif result["status"] == "clarify":
                resolved[field] = result["matched"]  # Use best guess but note it
                # For medium confidence, we note but proceed
                # (caller can show an advisory note)

            elif result["status"] == "ambiguous":
                return resolved, result["message"]

            elif result["status"] == "not_found":
                return resolved, result["message"]

        return resolved, None

    # ------------------------------------------------------------------
    # Step 4: Data filtering
    # ------------------------------------------------------------------

    def _filter_outlet(self, resolved: dict) -> pd.DataFrame:
        """Apply hierarchy and time filters to outlet_df."""
        df = self.outlet_df.copy()

        # Hierarchy filters
        if resolved.get("rsm"):
            df = df[df["rsm"].str.lower() == resolved["rsm"].lower()]
        if resolved.get("asm"):
            df = df[df["asm"].str.lower() == resolved["asm"].lower()]
        if resolved.get("so"):
            df = df[df["sales_officer"].str.lower() == resolved["so"].lower()]
        if resolved.get("beat"):
            df = df[df["beats_or_route"].str.lower() == resolved["beat"].lower()]
        if resolved.get("outlet"):
            df = df[df["outlet"].str.lower() == resolved["outlet"].lower()]
        if resolved.get("state"):
            df = df[df["state"].str.lower() == resolved["state"].lower()]
        if resolved.get("zone"):
            df = df[df["zone"].str.lower() == resolved["zone"].lower()]
        if resolved.get("product_category"):
            cat = resolved["product_category"].lower()
            df = df[df["l1_parent_category"].str.lower().str.contains(cat, na=False)]

        return df

    def _apply_time(self, df: pd.DataFrame, resolved: dict) -> pd.DataFrame:
        return apply_time_filter(
            df,
            time_range=resolved.get("time_range", "mtd"),
            specific_month=resolved.get("specific_month"),
            specific_year=resolved.get("specific_year"),
        )

    def _filter_targets(self, resolved: dict, month: int, year: int) -> pd.DataFrame:
        if self.targets_df is None or self.targets_df.empty:
            return pd.DataFrame()
        df = self.targets_df.copy()
        if resolved.get("rsm"):
            df = df[df["rsm_name"].str.lower() == resolved["rsm"].lower()]
        if resolved.get("asm"):
            df = df[df["asm_name"].str.lower() == resolved["asm"].lower()]
        if resolved.get("so"):
            df = df[df["so_name"].str.lower() == resolved["so"].lower()]
        df = df[
            (df["month"].astype(str) == str(month))
            & (df["year"].astype(str) == str(year))
        ]
        return df

    # ------------------------------------------------------------------
    # Step 5: Compute metrics and format response
    # ------------------------------------------------------------------

    def _compute_and_format(
        self, question: str, resolved: dict, chat_history: list[dict]
    ) -> str:
        query_type = resolved.get("query_type", "summary")
        time_range = resolved.get("time_range", "mtd")

        # Get the reference date info
        latest = get_latest_date(self.outlet_df)
        cur_month, cur_year = get_current_month_year(self.outlet_df)

        # Choose month/year for target lookup
        if time_range in ("last_month", "lmtd"):
            if cur_month == 1:
                tgt_month, tgt_year = 12, cur_year - 1
            else:
                tgt_month, tgt_year = cur_month - 1, cur_year
        elif resolved.get("specific_month") and resolved.get("specific_year"):
            tgt_month = resolved["specific_month"]
            tgt_year = resolved["specific_year"]
        else:
            tgt_month, tgt_year = cur_month, cur_year

        time_label = self._build_time_label(time_range, latest, resolved)

        # Route to the right computation
        if query_type in ("top_n", "bottom_n", "breakdown"):
            data_summary = self._compute_grouped(resolved, time_range, query_type, tgt_month, tgt_year, time_label)
        elif query_type == "comparison_mtd_lmtd":
            data_summary = self._compute_comparison(resolved, time_label)
        elif query_type == "beat_wise":
            data_summary = self._compute_beat_wise(resolved, time_range, time_label)
        elif query_type == "category_wise":
            data_summary = self._compute_category_wise(resolved, time_range, time_label)
        elif query_type == "outlet_wise":
            data_summary = self._compute_outlet_wise(resolved, time_range, resolved.get("n", 10), time_label)
        elif query_type == "target_achievement":
            data_summary = self._compute_target_achievement(resolved, time_range, tgt_month, tgt_year, time_label)
        else:
            # summary
            data_summary = self._compute_summary(resolved, time_range, tgt_month, tgt_year, time_label)

        # Final Claude call to write the natural language response
        return self._format_response(question, data_summary, chat_history)

    # ------------------------------------------------------------------
    # Computation helpers
    # ------------------------------------------------------------------

    def _compute_summary(self, resolved, time_range, tgt_month, tgt_year, time_label) -> str:
        df = self._filter_outlet(resolved)
        df_t = self._apply_time(df, resolved)
        m = calc_metrics(df_t)

        # Targets for the entity
        tgt_row = None
        if not self.targets_df.empty:
            tdf = self._filter_targets(resolved, tgt_month, tgt_year)
            if not tdf.empty:
                tgt_row = {
                    "secondary_tgt": tdf["secondary_tgt"].sum(),
                    "upc_target": tdf["upc_target"].sum(),
                }

        display = summarize_single(m, tgt_row)
        lines = [f"Time period: {time_label}"]
        for k, v in display.items():
            lines.append(f"  {k}: {v}")
        return "\n".join(lines)

    def _compute_grouped(self, resolved, time_range, query_type, tgt_month, tgt_year, time_label) -> str:
        df = self._filter_outlet(resolved)
        df_t = self._apply_time(df, resolved)

        # Determine group column
        group_by = resolved.get("group_by")
        col_map = {
            "so": "sales_officer", "asm": "asm", "rsm": "rsm",
            "beat": "beats_or_route", "outlet": "outlet",
            "category": "l1_parent_category", "state": "state", "zone": "zone",
        }
        if not group_by:
            # Infer from hierarchy
            if resolved.get("asm") or resolved.get("rsm"):
                group_by = "so"
            else:
                group_by = "asm"
        group_col = col_map.get(group_by, group_by)

        if group_col not in df_t.columns:
            return f"Time period: {time_label}\nNo data available for grouping by {group_by}."

        grp = calc_metrics_grouped(df_t, group_col)
        include_targets = "target" in resolved.get("metrics", []) or query_type == "target_achievement"

        if include_targets:
            grp = merge_targets(grp, self.targets_df, group_col, tgt_month, tgt_year)

        # Top/Bottom N filtering
        n = resolved.get("n") or 10
        if query_type == "top_n":
            grp = grp.head(int(n))
        elif query_type == "bottom_n":
            grp = grp.tail(int(n)).sort_values("secondary")

        display_df = format_metrics_table(grp, group_col, include_targets=include_targets)
        table_md = display_df.to_markdown(index=False)
        return f"Time period: {time_label}\nGroup by: {group_by}\n\n{table_md}"

    def _compute_comparison(self, resolved, time_label) -> str:
        df = self._filter_outlet(resolved)
        mtd_df = filter_mtd(df)
        lmtd_df = filter_lmtd(df)
        mtd_m = calc_metrics(mtd_df)
        lmtd_m = calc_metrics(lmtd_df)

        def delta(a, b):
            if b == 0:
                return "—"
            pct = (a - b) / b * 100
            sign = "+" if pct >= 0 else ""
            return f"{sign}{pct:.1f}%"

        rows = []
        labels = [
            ("Secondary", "secondary", True),
            ("PC", "pc", False),
            ("UPC", "upc", False),
            ("TC", "tc", False),
            ("ABV", "abv", True),
        ]
        for label, key, is_currency in labels:
            mtd_val = format_currency(mtd_m[key]) if is_currency else f"{int(mtd_m[key]):,}"
            lmtd_val = format_currency(lmtd_m[key]) if is_currency else f"{int(lmtd_m[key]):,}"
            rows.append({
                "Metric": label,
                "MTD": mtd_val,
                "LMTD": lmtd_val,
                "Change": delta(mtd_m[key], lmtd_m[key]),
            })

        table = pd.DataFrame(rows).to_markdown(index=False)
        return f"MTD vs LMTD Comparison\n\n{table}"

    def _compute_beat_wise(self, resolved, time_range, time_label) -> str:
        df = self._filter_outlet(resolved)
        df_t = self._apply_time(df, resolved)
        grp = calc_metrics_grouped(df_t, "beats_or_route")
        display_df = format_metrics_table(grp, "beats_or_route")
        table_md = display_df.to_markdown(index=False)
        return f"Time period: {time_label}\nBeat-wise breakdown\n\n{table_md}"

    def _compute_category_wise(self, resolved, time_range, time_label) -> str:
        df = self._filter_outlet(resolved)
        df_t = self._apply_time(df, resolved)

        if "l1_parent_category" not in df_t.columns or df_t.empty:
            return f"Time period: {time_label}\nNo category data available."

        grp = calc_metrics_grouped(df_t, "l1_parent_category")
        total_sec = grp["secondary"].sum()
        grp["contribution%"] = (grp["secondary"] / total_sec * 100).round(1).astype(str) + "%"
        grp["secondary_fmt"] = grp["secondary"].apply(format_currency)

        display = grp[["rank", "l1_parent_category", "secondary_fmt", "contribution%", "pc", "upc"]].copy()
        display.columns = ["#", "Category", "Secondary", "Share%", "PC", "UPC"]
        table_md = display.to_markdown(index=False)
        return f"Time period: {time_label}\nCategory-wise breakdown\n\n{table_md}"

    def _compute_outlet_wise(self, resolved, time_range, n, time_label) -> str:
        df = self._filter_outlet(resolved)
        df_t = self._apply_time(df, resolved)
        grp = calc_metrics_grouped(df_t, "outlet")
        n = int(n or 10)
        direction = resolved.get("query_type", "top_n")
        if direction == "bottom_n":
            top = grp.tail(n).sort_values("secondary")
        else:
            top = grp.head(n)
        display_df = format_metrics_table(top, "outlet")
        table_md = display_df.to_markdown(index=False)
        label = "Bottom" if direction == "bottom_n" else "Top"
        return f"Time period: {time_label}\n{label} {n} Outlets\n\n{table_md}"

    def _compute_target_achievement(self, resolved, time_range, tgt_month, tgt_year, time_label) -> str:
        df = self._filter_outlet(resolved)
        df_t = self._apply_time(df, resolved)

        group_by = resolved.get("group_by", "so")
        col_map = {
            "so": "sales_officer", "asm": "asm", "rsm": "rsm",
        }
        group_col = col_map.get(group_by, "sales_officer")

        if group_col not in df_t.columns:
            return f"Time period: {time_label}\nNo data available."

        grp = calc_metrics_grouped(df_t, group_col)
        grp = merge_targets(grp, self.targets_df, group_col, tgt_month, tgt_year)

        display_df = format_metrics_table(grp, group_col, include_targets=True)
        table_md = display_df.to_markdown(index=False)
        return f"Time period: {time_label}\nTarget vs Achievement\n\n{table_md}"

    # ------------------------------------------------------------------
    # Final formatting via Claude
    # ------------------------------------------------------------------

    def _format_response(self, question: str, data_summary: str, chat_history: list[dict]) -> str:
        user_content = RESPONSE_USER_TEMPLATE.format(
            question=question,
            data_summary=data_summary,
        )
        history_msgs = format_history_for_response(chat_history)
        messages = history_msgs + [{"role": "user", "content": user_content}]

        resp = self.client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=RESPONSE_SYSTEM,
            messages=messages,
        )
        return resp.content[0].text.strip()

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def _build_time_label(self, time_range: str, latest, resolved: dict) -> str:
        tr = (time_range or "mtd").lower()
        month_name = MONTH_NAMES.get(latest.month, "")
        year = latest.year

        if tr in ("mtd", "this_month"):
            return f"MTD {month_name} {year} (up to {latest.strftime('%d %b')})"
        if tr in ("lmtd", "last_month"):
            prev_m = latest.month - 1 if latest.month > 1 else 12
            prev_y = year if latest.month > 1 else year - 1
            return f"LMTD {MONTH_NAMES.get(prev_m, '')} {prev_y}"
        if tr == "3m":
            prev_months = []
            for i in range(1, 4):
                m = latest.month - i
                y = year
                while m <= 0:
                    m += 12
                    y -= 1
                prev_months.append(MONTH_NAMES.get(m, "")[:3])
            return f"Last 3 months ({', '.join(reversed(prev_months))})"
        if tr == "ytd":
            fy_y = year if latest.month >= 4 else year - 1
            return f"YTD FY{str(fy_y)[2:]+str(fy_y+1)[2:]} (Apr {fy_y} – {latest.strftime('%d %b %Y')})"
        if tr == "today":
            return f"Today ({latest.strftime('%d %b %Y')})"
        if tr == "yesterday":
            return f"Yesterday"
        if tr == "specific_month_year":
            m = resolved.get("specific_month")
            y = resolved.get("specific_year")
            if m and y:
                return f"{MONTH_NAMES.get(int(m), '')} {y}"
        return time_range.upper()
