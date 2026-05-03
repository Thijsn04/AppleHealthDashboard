from __future__ import annotations

import pandas as pd
import streamlit as st

from apple_health_dashboard.db import default_db_path
from apple_health_dashboard.services.activity_summary import activity_summaries_to_dataframe
from apple_health_dashboard.services.streaks import ring_streak
from apple_health_dashboard.storage.sqlite_store import init_db, iter_activity_summaries, open_db
from apple_health_dashboard.web.charts import area_chart, bar_chart, line_chart
from apple_health_dashboard.web.page_utils import sidebar_date_filter

st.set_page_config(
    page_title="Rings · Apple Health Dashboard",
    page_icon="🔥",
    layout="wide",
)

st.markdown("<style>.block-container{padding-top:1.5rem}</style>", unsafe_allow_html=True)
st.title("🔥 Activity Rings")
st.caption("Move, Exercise, and Stand ring progress, goals and streaks.")

db_path = default_db_path()

with st.spinner("Loading activity rings…"):
    con = open_db(db_path)
    try:
        init_db(con)
        adf = activity_summaries_to_dataframe(list(iter_activity_summaries(con)))
    finally:
        con.close()

if adf.empty:
    st.warning(
        "No ActivitySummary data found. "
        "This requires an Apple Watch — make sure you exported from a device with ring history."
    )
    st.page_link("app.py", label="Go to Home →", icon="🏠")
    st.stop()

# ── Date filter ───────────────────────────────────────────────────────────────
# Build proxy df for date filter
proxy_df = adf.rename(columns={"day": "start_at"})[["start_at"]].copy()
proxy_df["type"] = "ring"

from apple_health_dashboard.services.filters import infer_date_filter, DateFilter

with st.sidebar:
    st.markdown("### 📅 Date Range")
    preset = st.selectbox("Preset", ["All", "7D", "30D", "90D", "180D", "1Y"], index=3)
    preset_filter = infer_date_filter(proxy_df, preset=preset)
    if preset_filter is None:
        st.warning("No dates found.")
        st.stop()

    use_custom = st.checkbox("Custom range", value=False)
    if use_custom:
        min_d = preset_filter.start.date()
        max_d = preset_filter.end.date()
        dates = st.date_input("Date range", value=(min_d, max_d), min_value=min_d, max_value=max_d)
        if isinstance(dates, (list, tuple)) and len(dates) == 2:
            start_d, end_d = dates
            date_filter = DateFilter(
                start=pd.Timestamp(start_d, tz="UTC"),
                end=pd.Timestamp(end_d, tz="UTC") + pd.Timedelta(days=1) - pd.Timedelta(seconds=1),
            )
        else:
            date_filter = preset_filter
    else:
        date_filter = preset_filter

# Filter by date (day column is tz-naive)
adf_f = adf[
    (adf["day"] >= pd.Timestamp(date_filter.start.date()))
    & (adf["day"] <= pd.Timestamp(date_filter.end.date()))
].copy()

with st.sidebar:
    st.caption(f"{date_filter.start.date()} → {date_filter.end.date()}")

if adf_f.empty:
    st.info("No ring data in the selected period.")
    st.stop()

# ── Streaks ───────────────────────────────────────────────────────────────────
streaks = ring_streak(adf)  # use full history for streak
streaks_period = ring_streak(adf_f)

# ── KPIs ──────────────────────────────────────────────────────────────────────
c1, c2, c3, c4, c5, c6 = st.columns(6)

# Compute goal completion rates
def _completion_rate(df: pd.DataFrame, actual_col: str, goal_col: str) -> float:
    if goal_col not in df.columns or actual_col not in df.columns:
        return 0.0
    valid = df[(df[goal_col].fillna(0) > 0)]
    if valid.empty:
        return 0.0
    closed = (valid[actual_col].fillna(0) >= valid[goal_col]).sum()
    return closed / len(valid)

move_rate = _completion_rate(adf_f, "active_energy_burned_kcal", "active_energy_burned_goal_kcal")
exercise_rate = _completion_rate(adf_f, "apple_exercise_time_min", "apple_exercise_time_goal_min")
stand_rate = _completion_rate(adf_f, "apple_stand_hours", "apple_stand_hours_goal")

avg_move = adf_f["active_energy_burned_kcal"].mean() if "active_energy_burned_kcal" in adf_f.columns else None
avg_exercise = adf_f["apple_exercise_time_min"].mean() if "apple_exercise_time_min" in adf_f.columns else None
avg_stand = adf_f["apple_stand_hours"].mean() if "apple_stand_hours" in adf_f.columns else None

c1.metric("🔴 Avg Move", f"{avg_move:.0f} kcal" if avg_move is not None else "—")
c2.metric("🟢 Avg Exercise", f"{avg_exercise:.0f} min" if avg_exercise is not None else "—")
c3.metric("🔵 Avg Stand", f"{avg_stand:.1f}h" if avg_stand is not None else "—")
c4.metric("Move Goal %", f"{move_rate * 100:.0f}%", help="% of days move goal was reached.")
c5.metric("Current Streak", f"{streaks.get('current_streak', 0)} days", help="All 3 rings closed.")
c6.metric("Best Streak", f"{streaks.get('longest_streak', 0)} days")

st.divider()

tabs = st.tabs(["Trends", "Goal Completion", "Monthly", "Raw Data"])

# ── Trends tab ────────────────────────────────────────────────────────────────
with tabs[0]:
    st.subheader("Ring Trends")

    ring_cols = {
        "active_energy_burned_kcal": ("🔴 Move (kcal)", "#FF6B6B"),
        "apple_exercise_time_min": ("🟢 Exercise (min)", "#10B981"),
        "apple_stand_hours": ("🔵 Stand (hours)", "#3B82F6"),
    }

    for col, (label, color) in ring_cols.items():
        if col in adf_f.columns and adf_f[col].notna().any():
            st.markdown(f"**{label}**")
            plot_df = adf_f[["day", col]].dropna().rename(columns={col: "value"})

            # Add goal line if available
            goal_col = col.replace("_kcal", "_goal_kcal").replace("_min", "_goal_min").replace("_hours", "_goal")
            if goal_col in adf_f.columns and adf_f[goal_col].notna().any():
                avg_goal = adf_f[goal_col].median()
                import altair as alt
                base = alt.Chart(plot_df).encode(
                    x=alt.X("day:T", axis=alt.Axis(labelAngle=-30, title="")),
                )
                area = base.mark_area(
                    line={"color": color, "strokeWidth": 2},
                    color=alt.Gradient(
                        gradient="linear",
                        stops=[
                            alt.GradientStop(color=color, offset=0),
                            alt.GradientStop(color="rgba(255,255,255,0)", offset=1),
                        ],
                        x1=1, x2=1, y1=1, y2=0,
                    ),
                ).encode(
                    y=alt.Y("value:Q"),
                    tooltip=[alt.Tooltip("day:T"), alt.Tooltip("value:Q", format=".0f")],
                )
                goal_line = (
                    alt.Chart(pd.DataFrame({"g": [avg_goal]}))
                    .mark_rule(strokeDash=[5, 3], strokeWidth=1.5, color="#94A3B8")
                    .encode(y=alt.Y("g:Q"))
                )
                st.altair_chart((area + goal_line).properties(height=180).interactive(), use_container_width=True)
            else:
                st.altair_chart(
                    area_chart(plot_df, x="day", y="value", y_title=label, color=color, height=180),
                    use_container_width=True,
                )

# ── Goal Completion tab ────────────────────────────────────────────────────────
with tabs[1]:
    st.subheader("Goal Completion")
    st.caption("How often you closed each ring.")

    comp_data = []
    ring_defs = [
        ("active_energy_burned_kcal", "active_energy_burned_goal_kcal", "🔴 Move"),
        ("apple_exercise_time_min", "apple_exercise_time_goal_min", "🟢 Exercise"),
        ("apple_stand_hours", "apple_stand_hours_goal", "🔵 Stand"),
    ]

    for actual_col, goal_col, ring_name in ring_defs:
        if actual_col not in adf_f.columns or goal_col not in adf_f.columns:
            continue
        valid = adf_f[adf_f[goal_col].fillna(0) > 0].copy()
        if valid.empty:
            continue

        valid["closed"] = valid[actual_col].fillna(0) >= valid[goal_col]
        valid["pct"] = valid[actual_col].fillna(0) / valid[goal_col] * 100
        rate = valid["closed"].mean() * 100

        comp_data.append({
            "Ring": ring_name,
            "Days closed": int(valid["closed"].sum()),
            "Total days": int(len(valid)),
            "Completion rate": f"{rate:.1f}%",
            "Avg % of goal": f"{valid['pct'].mean():.0f}%",
        })

    if comp_data:
        st.dataframe(pd.DataFrame(comp_data), use_container_width=True, hide_index=True)

    # Daily completion streak chart
    st.markdown("**All-Three-Rings Completion Over Time**")
    adf_streak = adf_f.copy()

    def _all_closed(row: pd.Series) -> int:
        checks = []
        for actual_col, goal_col, _ in ring_defs:
            if actual_col in row and goal_col in row:
                goal = row.get(goal_col, 0) or 0
                actual = row.get(actual_col, 0) or 0
                checks.append(goal > 0 and actual >= goal)
        return int(all(checks)) if checks else 0

    adf_streak["all_closed"] = adf_streak.apply(_all_closed, axis=1)
    import altair as alt
    closed_chart = (
        alt.Chart(adf_streak)
        .mark_bar(color="#10B981")
        .encode(
            x=alt.X("day:T", axis=alt.Axis(labelAngle=-30, title="")),
            y=alt.Y("all_closed:Q", axis=alt.Axis(title="Ring Closed (1=yes)"), scale=alt.Scale(domain=[0, 1])),
            color=alt.condition(
                alt.datum.all_closed == 1,
                alt.value("#10B981"),
                alt.value("#FCA5A5"),
            ),
            tooltip=[alt.Tooltip("day:T"), alt.Tooltip("all_closed:Q")],
        )
        .properties(title="All Rings Closed per Day (green = closed)", height=180)
        .interactive()
    )
    st.altair_chart(closed_chart, use_container_width=True)

# ── Monthly tab ────────────────────────────────────────────────────────────────
with tabs[2]:
    st.subheader("Monthly Averages")

    adf_f["month"] = pd.to_datetime(adf_f["day"]).dt.to_period("M").dt.start_time
    month_agg_cols = {}
    for col in ["active_energy_burned_kcal", "apple_exercise_time_min", "apple_stand_hours"]:
        if col in adf_f.columns:
            month_agg_cols[col] = "mean"

    if month_agg_cols:
        monthly = adf_f.groupby("month").agg(month_agg_cols).reset_index()
        monthly.columns = ["Month"] + [
            c.replace("active_energy_burned_kcal", "Avg Move (kcal)")
            .replace("apple_exercise_time_min", "Avg Exercise (min)")
            .replace("apple_stand_hours", "Avg Stand (h)")
            for c in list(month_agg_cols.keys())
        ]
        for c in monthly.columns[1:]:
            monthly[c] = monthly[c].round(1)
        st.dataframe(monthly, use_container_width=True, hide_index=True)

        # Bar charts for each ring
        ring_monthly = [
            ("Avg Move (kcal)", "#FF6B6B"),
            ("Avg Exercise (min)", "#10B981"),
            ("Avg Stand (h)", "#3B82F6"),
        ]
        for col, color in ring_monthly:
            if col in monthly.columns:
                st.altair_chart(
                    bar_chart(monthly, x="Month", y=col, y_title=col, color=color, height=180),
                    use_container_width=True,
                )

# ── Raw Data tab ───────────────────────────────────────────────────────────────
with tabs[3]:
    st.subheader("Raw Activity Summary Data")
    raw = adf_f.drop(columns=["month"], errors="ignore")
    st.dataframe(raw.sort_values("day", ascending=False), use_container_width=True, hide_index=True)
    st.caption(f"Total rows: {len(raw):,}")
