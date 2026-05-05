from __future__ import annotations

import pandas as pd
import streamlit as st

from apple_health_dashboard.db import default_db_path
from apple_health_dashboard.services.filters import apply_date_filter
from apple_health_dashboard.services.sleep import (
    SLEEP_RECORD_TYPE,
    sleep_consistency_stats,
    sleep_duration_by_day,
    sleep_records,
    sleep_stages_by_day,
    sleep_value_counts,
    SLEEP_STAGES,
    SLEEP_STAGES_ACTUAL,
)
from apple_health_dashboard.web.charts import area_chart, bar_chart, stacked_bar_chart
from apple_health_dashboard.web.page_utils import (
    load_all_records,
    page_header,
    sidebar_date_filter,
)

st.set_page_config(
    page_title="Sleep · Apple Health Dashboard",
    page_icon="😴",
    layout="wide",
)

page_header("😴", "Sleep", "Sleep duration, stages, consistency and trends.")

db_path = default_db_path()

with st.spinner("Loading sleep data…"):
    df = load_all_records(str(db_path))

if df.empty:
    st.warning("No data found. Please import your Apple Health export on the Home page.")
    st.page_link("app.py", label="Go to Home →", icon="🏠")
    st.stop()

date_filter = sidebar_date_filter(df, current="Sleep")
if date_filter is None:
    st.warning("Could not determine date range.")
    st.stop()

df_f = apply_date_filter(df, date_filter)
srec = sleep_records(df_f)

if srec.empty:
    st.info(
        f"No sleep records found in the selected period. "
        f"Sleep data is stored as `{SLEEP_RECORD_TYPE}` in Apple Health. "
        "Make sure you have an Apple Watch or third-party sleep tracker connected."
    )
    st.stop()

# ── Compute summaries ─────────────────────────────────────────────────────────
stats = sleep_consistency_stats(srec)
dur_actual = sleep_duration_by_day(srec, stages="actual")
dur_all = sleep_duration_by_day(srec, stages="all")
# Use actual sleep if available, else fall back to all
dur = dur_actual if not dur_actual.empty else dur_all

stages_wide = sleep_stages_by_day(srec)

# ── KPI row ───────────────────────────────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Avg Sleep", f"{stats.get('avg_hours', 0):.1f}h", help="Average sleep duration per night.")
c2.metric("Median Sleep", f"{stats.get('median_hours', 0):.1f}h")
c3.metric("Nights ≥7h", f"{stats.get('nights_gte_7h', 0) * 100:.0f}%", help="% of nights with at least 7 hours.")
c4.metric("Nights ≥8h", f"{stats.get('nights_gte_8h', 0) * 100:.0f}%")
c5.metric("Nights tracked", f"{stats.get('total_nights', 0):,}")

if stats.get("avg_hours", 0) < 7:
    st.warning("⚠️ Your average sleep is below the recommended 7 hours for adults.")
elif stats.get("avg_hours", 0) >= 8:
    st.success("✅ Great — your average sleep meets the recommended 7–9 hours.")

st.divider()

tabs = st.tabs(["Duration", "Sleep Stages", "Consistency", "Raw Data"])

# ── Duration tab ──────────────────────────────────────────────────────────────
with tabs[0]:
    st.subheader("Sleep Duration per Night")
    if not dur.empty:
        col_chart, col_stats = st.columns([3, 1])
        with col_chart:
            # Add 7h and 8h reference lines via Altair
            import altair as alt
            base = alt.Chart(dur).encode(
                x=alt.X("day:T", axis=alt.Axis(labelAngle=-30, title="")),
                y=alt.Y("hours:Q", axis=alt.Axis(title="Hours"), scale=alt.Scale(zero=False)),
                tooltip=[
                    alt.Tooltip("day:T", title="Date"),
                    alt.Tooltip("hours:Q", title="Hours", format=".2f"),
                ],
            )
            bars = base.mark_bar(color="#4A90D9", opacity=0.8)
            line_7h = (
                alt.Chart(pd.DataFrame({"y": [7]}))
                .mark_rule(color="#F59E0B", strokeDash=[4, 4], strokeWidth=1.5)
                .encode(y=alt.Y("y:Q"))
            )
            line_8h = (
                alt.Chart(pd.DataFrame({"y": [8]}))
                .mark_rule(color="#10B981", strokeDash=[4, 4], strokeWidth=1.5)
                .encode(y=alt.Y("y:Q"))
            )
            chart = (bars + line_7h + line_8h).properties(
                title="Sleep Duration (yellow = 7h, green = 8h)",
                height=280,
            ).interactive()
            st.altair_chart(chart, use_container_width=True)

        with col_stats:
            st.markdown("**Statistics**")
            st.metric("Average", f"{dur['hours'].mean():.2f}h")
            st.metric("Best night", f"{dur['hours'].max():.2f}h")
            st.metric("Shortest night", f"{dur['hours'].min():.2f}h")
            st.metric("Std deviation", f"{dur['hours'].std():.2f}h")

            if not dur_actual.empty and not dur_all.empty:
                avg_in_bed = dur_all["hours"].mean()
                avg_asleep = dur_actual["hours"].mean()
                efficiency = avg_asleep / avg_in_bed * 100 if avg_in_bed > 0 else 0
                st.metric("Sleep efficiency", f"{efficiency:.1f}%", help="Asleep / In Bed × 100")

        # 30-day rolling average
        if len(dur) >= 7:
            st.markdown("**Rolling Average**")
            roll_df = dur.copy()
            roll_df["7d_avg"] = roll_df["hours"].rolling(7, min_periods=1).mean()
            if len(roll_df) >= 30:
                roll_df["30d_avg"] = roll_df["hours"].rolling(30, min_periods=1).mean()
                y_cols = ["7d_avg", "30d_avg"]
            else:
                y_cols = ["7d_avg"]

            from apple_health_dashboard.web.charts import line_chart
            st.altair_chart(
                line_chart(roll_df, x="day", y=y_cols, y_title="Hours", height=180),
                use_container_width=True,
            )
    else:
        st.info("No sleep duration data could be computed for this period.")

# ── Stages tab ────────────────────────────────────────────────────────────────
with tabs[1]:
    st.subheader("Sleep Stages")
    st.caption(
        "Apple Watch (Series 4+) with watchOS 9+ records detailed sleep stages. "
        "Older devices only record In Bed / Asleep."
    )

    # Stage distribution (counts)
    stage_counts = sleep_value_counts(srec)
    if not stage_counts.empty:
        col_chart, col_table = st.columns([1, 1])
        with col_chart:
            import altair as alt
            donut = (
                alt.Chart(stage_counts)
                .mark_arc(innerRadius=55)
                .encode(
                    theta=alt.Theta("count:Q"),
                    color=alt.Color("stage:N", scale=alt.Scale(scheme="blues")),
                    tooltip=[alt.Tooltip("stage:N"), alt.Tooltip("count:Q")],
                )
                .properties(title="Stage Distribution (record count)", height=300)
            )
            st.altair_chart(donut, use_container_width=True)
        with col_table:
            st.markdown("**Stage Counts**")
            st.dataframe(stage_counts, use_container_width=True, hide_index=True)

    # Nightly breakdown by stage
    if not stages_wide.empty:
        stage_cols = [c for c in stages_wide.columns if c != "day"]
        if len(stage_cols) >= 2:
            st.markdown("**Nightly Stage Breakdown**")
            st.altair_chart(
                stacked_bar_chart(
                    stages_wide,
                    x="day",
                    y_cols=stage_cols,
                    y_title="Hours",
                    title="Sleep Stages per Night",
                    height=280,
                ),
                use_container_width=True,
            )
        else:
            st.info(
                "Only one sleep stage found. "
                "Detailed stages (Core, Deep, REM) require Apple Watch Series 4+ with watchOS 9+."
            )
    else:
        st.info("No stage breakdown data available.")

# ── Consistency tab ───────────────────────────────────────────────────────────
with tabs[2]:
    st.subheader("Sleep Consistency")
    st.caption("Regular sleep timing is as important as duration.")

    if not dur.empty:
        col_dist, col_heat = st.columns(2)

        with col_dist:
            st.markdown("**Distribution of Sleep Duration**")
            hist_df = dur.copy()
            hist_df["hours_bin"] = (hist_df["hours"] * 2).round() / 2  # 30-min bins
            bin_counts = hist_df["hours_bin"].value_counts().reset_index()
            bin_counts.columns = ["hours", "nights"]
            bin_counts = bin_counts.sort_values("hours")

            import altair as alt
            hist_chart = (
                alt.Chart(bin_counts)
                .mark_bar(color="#4A90D9", opacity=0.8)
                .encode(
                    x=alt.X("hours:Q", axis=alt.Axis(title="Hours")),
                    y=alt.Y("nights:Q", axis=alt.Axis(title="Nights")),
                    tooltip=[alt.Tooltip("hours:Q"), alt.Tooltip("nights:Q")],
                )
                .properties(title="Nights at Each Duration", height=260)
            )
            st.altair_chart(hist_chart, use_container_width=True)

        with col_heat:
            st.markdown("**Weekly Sleep Heatmap**")
            if len(dur) >= 7:
                heat_df = dur.copy()
                heat_df["day_dt"] = pd.to_datetime(heat_df["day"])
                heat_df["week"] = heat_df["day_dt"].dt.isocalendar().week.astype(str)
                heat_df["weekday"] = heat_df["day_dt"].dt.day_name()
                WEEKDAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
                heat_df["weekday"] = pd.Categorical(heat_df["weekday"], categories=WEEKDAY_ORDER, ordered=True)

                import altair as alt
                heat_chart = (
                    alt.Chart(heat_df)
                    .mark_rect()
                    .encode(
                        x=alt.X("week:O", axis=alt.Axis(title="Week")),
                        y=alt.Y("weekday:O", sort=WEEKDAY_ORDER, axis=alt.Axis(title="")),
                        color=alt.Color(
                            "hours:Q",
                            scale=alt.Scale(scheme="blues", domain=[4, 10]),
                            legend=alt.Legend(title="Hours"),
                        ),
                        tooltip=[
                            alt.Tooltip("day_dt:T", title="Date"),
                            alt.Tooltip("hours:Q", format=".1f"),
                        ],
                    )
                    .properties(title="Sleep by Day of Week & Week Number", height=240)
                )
                st.altair_chart(heat_chart, use_container_width=True)
            else:
                st.info("Need at least 7 days of data for the heatmap.")

        # Weekly averages
        st.markdown("**Weekly Average Sleep**")
        weekly = dur.copy()
        weekly["week"] = pd.to_datetime(weekly["day"]).dt.to_period("W").dt.start_time
        weekly_avg = weekly.groupby("week")["hours"].mean().reset_index()
        weekly_avg.columns = ["week", "avg_hours"]

        import altair as alt
        weekly_chart = (
            alt.Chart(weekly_avg)
            .mark_bar(color="#7C3AED", opacity=0.8)
            .encode(
                x=alt.X("week:T", axis=alt.Axis(labelAngle=-30, title="")),
                y=alt.Y("avg_hours:Q", axis=alt.Axis(title="Avg Hours")),
                tooltip=[alt.Tooltip("week:T", title="Week"), alt.Tooltip("avg_hours:Q", format=".2f")],
            )
            .properties(title="Weekly Average Sleep Duration", height=220)
            .interactive()
        )
        st.altair_chart(weekly_chart, use_container_width=True)

# ── Raw data tab ──────────────────────────────────────────────────────────────
with tabs[3]:
    st.subheader("Raw Sleep Records")
    display_cols = ["start_at", "end_at", "value_str", "source_name"]
    display_cols = [c for c in display_cols if c in srec.columns]
    display_df = srec[display_cols].copy()
    if "value_str" in display_df.columns:
        display_df["stage"] = display_df["value_str"].map(lambda v: SLEEP_STAGES.get(v, v))
        display_df = display_df.drop(columns=["value_str"])
    display_df = display_df.sort_values("start_at", ascending=False)

    page_size = st.selectbox("Rows per page", [100, 250, 500], index=0, key="sleep_ps")
    total = len(display_df)
    pages = max(1, (total + page_size - 1) // page_size)
    page = st.number_input("Page", min_value=1, max_value=pages, value=1, step=1, key="sleep_page")
    start = (page - 1) * page_size
    st.caption(f"Showing {start + 1}–{min(start + page_size, total)} of {total:,} records")
    st.dataframe(display_df.iloc[start : start + page_size], use_container_width=True)
