from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from apple_health_dashboard.db import default_db_path
from apple_health_dashboard.services.filters import DateFilter, infer_date_filter
from apple_health_dashboard.services.metrics import (
    CATEGORY_EMOJI,
    METRICS,
    metric_description,
    metric_label,
    metrics_by_category,
)
from apple_health_dashboard.services.stats import summarize_by_day_agg
from apple_health_dashboard.services.units import normalize_units
from apple_health_dashboard.storage.duckdb_store import (
    count_records,
    init_db,
    list_record_types,
    open_db,
    query_records_page,
)
from apple_health_dashboard.web.charts import area_chart, bar_chart, line_chart
from apple_health_dashboard.web.page_utils import page_header, sidebar_nav

st.set_page_config(
    page_title="Explorer · Apple Health Dashboard",
    page_icon="🔬",
    layout="wide",
)

page_header("🔬", "Data Explorer", "Browse, filter and analyze any Apple Health record type.")

db_path = default_db_path()

# ── Load available record types ───────────────────────────────────────────────
with st.spinner("Loading record catalogue…"):
    con = open_db(db_path)
    try:
        init_db(con)
        all_types = list_record_types(con)
        total_records = con.execute("SELECT COUNT(*) FROM health_record").fetchone()[0]
    finally:
        con.close()

if not all_types:
    st.warning("No data found. Please import your Apple Health export on the Home page.")
    st.page_link("app.py", label="Go to Home →", icon="🏠")
    st.stop()

st.caption(f"**{total_records:,}** total records · **{len(all_types)}** distinct record types")

# ── Build enriched type labels ─────────────────────────────────────────────────
_METRIC_DICT = {m.record_type: m for m in METRICS}


def _type_display(rt: str) -> str:
    m = _METRIC_DICT.get(rt)
    if m:
        emoji = CATEGORY_EMOJI.get(m.category, "🔬")
        return f"{emoji} {m.label} ({rt})"
    return rt


type_display_map = {rt: _type_display(rt) for rt in all_types}
display_to_rt = {v: k for k, v in type_display_map.items()}

# ── Sidebar: record type picker ───────────────────────────────────────────────
with st.sidebar:
    sidebar_nav(current="Explorer")
    st.divider()
    st.markdown("### 🔬 Record Type")

    # Category filter
    all_categories = sorted({_METRIC_DICT[rt].category for rt in all_types if rt in _METRIC_DICT} | {"Other"})
    selected_cat = st.selectbox("Filter by category", ["All"] + all_categories, index=0)

    if selected_cat == "All":
        filtered_types = all_types
    else:
        filtered_types = [
            rt for rt in all_types
            if (_METRIC_DICT.get(rt) and _METRIC_DICT[rt].category == selected_cat)
            or (selected_cat == "Other" and rt not in _METRIC_DICT)
        ]

    # Search
    search = st.text_input("Search type name", value="")
    if search:
        search_lower = search.lower()
        filtered_types = [
            rt for rt in filtered_types
            if search_lower in rt.lower() or search_lower in metric_label(rt).lower()
        ]

    if not filtered_types:
        st.warning("No types match your filter.")
        st.stop()

    display_options = [type_display_map[rt] for rt in filtered_types]
    selected_display = st.selectbox("Record type", display_options, index=0)
    selected_rt = display_to_rt[selected_display]

    st.divider()
    st.markdown("### 📅 Date Range")
    preset = st.selectbox("Preset", ["All", "7D", "30D", "90D", "180D", "1Y"], index=3, key="exp_preset")
    use_custom = st.checkbox("Custom range", value=False, key="exp_custom")

# ── Determine date range from this record type's full history ─────────────────
con = open_db(db_path)
try:
    type_total = count_records(con, record_type=selected_rt)
    # Sample first/last for date range
    first_row = con.execute(
        "SELECT start_at FROM health_record WHERE type=? ORDER BY start_at ASC LIMIT 1",
        (selected_rt,),
    ).fetchone()
    last_row = con.execute(
        "SELECT start_at FROM health_record WHERE type=? ORDER BY start_at DESC LIMIT 1",
        (selected_rt,),
    ).fetchone()
finally:
    con.close()

if first_row and last_row:
    type_start = pd.Timestamp(first_row[0], tz="UTC")
    type_end = pd.Timestamp(last_row[0], tz="UTC")
else:
    type_start = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=90)
    type_end = pd.Timestamp.now(tz="UTC")

# Build date filter
days_map = {"7D": 7, "30D": 30, "90D": 90, "180D": 180, "1Y": 365}
if preset == "All":
    filter_start = type_start
    filter_end = type_end
elif preset in days_map:
    filter_start = type_end - pd.Timedelta(days=days_map[preset])
    filter_end = type_end
else:
    filter_start = type_start
    filter_end = type_end

with st.sidebar:
    if use_custom:
        dates = st.date_input(
            "Date range",
            value=(filter_start.date(), filter_end.date()),
            min_value=type_start.date(),
            max_value=type_end.date(),
            key="exp_dates",
        )
        if isinstance(dates, (list, tuple)) and len(dates) == 2:
            filter_start = pd.Timestamp(dates[0], tz="UTC")
            filter_end = pd.Timestamp(dates[1], tz="UTC") + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)

    order = st.selectbox("Sort", ["Newest first", "Oldest first"], index=0, key="exp_order")
    page_size = st.selectbox("Rows per page", [100, 250, 500, 1000, 2000], index=2, key="exp_ps")

order_sql = "start_at_desc" if order == "Newest first" else "start_at_asc"

# ── Load count and page ───────────────────────────────────────────────────────
con = open_db(db_path)
try:
    filtered_count = count_records(
        con,
        record_type=selected_rt,
        start_at=filter_start.to_pydatetime(),
        end_at=filter_end.to_pydatetime(),
    )
finally:
    con.close()

# ── Header info ───────────────────────────────────────────────────────────────
m = _METRIC_DICT.get(selected_rt)
col_title, col_meta = st.columns([2, 1])
with col_title:
    st.subheader(metric_label(selected_rt))
    desc = metric_description(selected_rt)
    if desc:
        st.caption(desc)
with col_meta:
    st.metric("Records in range", f"{filtered_count:,}")
    st.metric("Total records ever", f"{type_total:,}")
    if m:
        st.caption(f"Category: **{m.category}** · Aggregation: **{m.aggregation}**")
        if m.unit_hint:
            st.caption(f"Unit: **{m.unit_hint}**")

st.divider()

# ── Visualisation: daily aggregation ─────────────────────────────────────────
if filtered_count > 0:
    # Pull data for chart (up to 10k records)
    sample_limit = min(filtered_count, 10000)
    con = open_db(db_path)
    try:
        rows = query_records_page(
            con,
            record_type=selected_rt,
            start_at=filter_start.to_pydatetime(),
            end_at=filter_end.to_pydatetime(),
            order="start_at_asc",
            limit=sample_limit,
            offset=0,
        )
    finally:
        con.close()

    chart_df = pd.DataFrame(rows)
    if not chart_df.empty:
        for col in ["start_at", "end_at", "creation_at"]:
            if col in chart_df.columns:
                chart_df[col] = pd.to_datetime(chart_df[col], utc=True, errors="coerce")

        # Check if numeric
        is_numeric = (
            "value" in chart_df.columns
            and chart_df["value"].notna().any()
            and pd.to_numeric(chart_df["value"], errors="coerce").notna().any()
        )
        is_categorical = (
            "value_str" in chart_df.columns
            and chart_df["value_str"].notna().any()
        )

        col_chart, col_dist = st.columns([3, 1])

        with col_chart:
            if is_numeric and m:
                agg = m.aggregation
                from apple_health_dashboard.services.stats import summarize_by_day_agg
                chart_df = normalize_units(chart_df, record_type=selected_rt)
                daily = summarize_by_day_agg(chart_df, agg=agg)

                if not daily.empty:
                    unit_label = m.unit_hint or "value"
                    y_title = f"{metric_label(selected_rt)} ({unit_label})"
                    st.markdown(f"**Daily {agg.title()} — {metric_label(selected_rt)}**")

                    if agg == "sum":
                        st.altair_chart(
                            area_chart(daily, x="day", y="value", y_title=y_title, height=260),
                            width="stretch",
                        )
                    else:
                        st.altair_chart(
                            line_chart(daily, x="day", y="value", y_title=y_title,
                                       height=260, rolling_avg_days=7),
                            width="stretch",
                        )
            elif is_categorical:
                st.markdown("**Value Distribution**")
                val_counts = (
                    chart_df["value_str"].astype("string").fillna("(null)")
                    .value_counts().head(20).reset_index()
                )
                val_counts.columns = ["value", "count"]
                st.altair_chart(
                    bar_chart(val_counts, x="value", y="count", horizontal=True, height=300),
                    width="stretch",
                )
            else:
                st.info("No numeric or categorical values to chart for this record type.")

        with col_dist:
            if is_numeric and "value" in chart_df.columns:
                num_vals = pd.to_numeric(chart_df["value"], errors="coerce").dropna()
                if not num_vals.empty:
                    st.markdown("**Statistics**")
                    st.metric("Count", f"{len(num_vals):,}")
                    st.metric("Mean", f"{num_vals.mean():.2f}")
                    st.metric("Median", f"{num_vals.median():.2f}")
                    st.metric("Min", f"{num_vals.min():.2f}")
                    st.metric("Max", f"{num_vals.max():.2f}")
                    st.metric("Std Dev", f"{num_vals.std():.2f}")

            if is_categorical and "value_str" in chart_df.columns:
                top = chart_df["value_str"].value_counts().head(5)
                st.markdown("**Top values**")
                for val, cnt in top.items():
                    st.write(f"- {val}: **{cnt:,}**")

    st.divider()

    # CSV export
    if not chart_df.empty:
        csv_export = chart_df.to_csv(index=False)
        st.download_button('⬇️ Download sample as CSV', data=csv_export, file_name='explorer_export.csv', mime='text/csv')

    # ── Paginated raw data table ──────────────────────────────────────────────
    st.subheader("Raw Records")
    pages = max(1, (filtered_count + page_size - 1) // page_size)
    page = st.number_input("Page", min_value=1, max_value=pages, value=1, step=1, key="exp_page")
    offset = (page - 1) * page_size

    con = open_db(db_path)
    try:
        page_rows = query_records_page(
            con,
            record_type=selected_rt,
            start_at=filter_start.to_pydatetime(),
            end_at=filter_end.to_pydatetime(),
            order=order_sql,
            limit=page_size,
            offset=offset,
        )
    finally:
        con.close()

    st.caption(
        f"Records {offset + 1}–{min(offset + page_size, filtered_count):,} "
        f"of {filtered_count:,} · Page {page}/{pages}"
    )

    if page_rows:
        page_df = pd.DataFrame(page_rows)
        for col in ["start_at", "end_at", "creation_at"]:
            if col in page_df.columns:
                page_df[col] = pd.to_datetime(page_df[col], utc=True, errors="coerce")

        # Drop record_hash from display (technical field)
        display_df = page_df.drop(columns=["record_hash"], errors="ignore")
        st.dataframe(
            display_df,
            width="stretch",
            hide_index=True,
            column_config={
                "type": st.column_config.TextColumn("Type"),
                "start_at": st.column_config.DatetimeColumn("Start"),
                "end_at": st.column_config.DatetimeColumn("End"),
                "creation_at": st.column_config.DatetimeColumn("Created"),
                "value": st.column_config.NumberColumn("Value", format="%.4f"),
                "value_str": st.column_config.TextColumn("Value (text)"),
                "unit": st.column_config.TextColumn("Unit"),
                "source_name": st.column_config.TextColumn("Source"),
            },
        )

# ── Database overview ─────────────────────────────────────────────────────────
with st.expander("📊 Full Database Overview"):
    st.markdown("**All record types in your database**")

    # Build overview table
    overview_rows = []
    cat_by_type = {m.record_type: m.category for m in METRICS}
    label_by_type = {m.record_type: m.label for m in METRICS}

    for rt in all_types:
        overview_rows.append({
            "Type": rt,
            "Label": label_by_type.get(rt, metric_label(rt)),
            "Category": cat_by_type.get(rt, "Other"),
        })

    overview_df = pd.DataFrame(overview_rows)

    # Get counts per type
    con = open_db(db_path)
    try:
        type_counts = pd.read_sql_query(
            "SELECT type, COUNT(*) as count FROM health_record GROUP BY type ORDER BY count DESC",
            con,
        )
    finally:
        con.close()

    if not type_counts.empty:
        overview_df = overview_df.merge(type_counts, left_on="Type", right_on="type", how="left")
        overview_df = overview_df.drop(columns=["type"], errors="ignore")
        overview_df["count"] = overview_df["count"].fillna(0).astype(int)
        overview_df = overview_df.sort_values("count", ascending=False)

    st.dataframe(
        overview_df,
        width="stretch",
        hide_index=True,
        column_config={
            "count": st.column_config.NumberColumn("Records", format="%d"),
        },
    )
    st.caption(f"Total: **{total_records:,}** records across **{len(all_types)}** types")
