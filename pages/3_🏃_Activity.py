from __future__ import annotations

import pandas as pd
import streamlit as st

from apple_health_dashboard.db import default_db_path
from apple_health_dashboard.services.filters import apply_date_filter
from apple_health_dashboard.services.stats import summarize_by_day_agg
from apple_health_dashboard.services.streaks import daily_streak, longest_streak, personal_bests
from apple_health_dashboard.services.units import normalize_units
from apple_health_dashboard.web.charts import area_chart, line_chart
from apple_health_dashboard.web.heatmaps import calendar_heatmap
from apple_health_dashboard.web.page_utils import (
    sidebar_nav,
    load_all_records,
    page_header,
    sidebar_date_filter,
)

st.set_page_config(
    page_title="Activity · Apple Health Dashboard",
    page_icon="🏃",
    layout="wide",
)

page_header("🏃", "Activity", "Steps, distance, active energy, exercise time & more.")

with st.sidebar:
    sidebar_nav(current="Activity")

db_path = default_db_path()

ACTIVITY_METRICS = [
    ("HKQuantityTypeIdentifierStepCount", "Steps", "count", "sum"),
    ("HKQuantityTypeIdentifierDistanceWalkingRunning", "Walking + Running Distance", "km", "sum"),
    ("HKQuantityTypeIdentifierDistanceCycling", "Cycling Distance", "km", "sum"),
    ("HKQuantityTypeIdentifierActiveEnergyBurned", "Active Energy", "kcal", "sum"),
    ("HKQuantityTypeIdentifierBasalEnergyBurned", "Basal Energy", "kcal", "sum"),
    ("HKQuantityTypeIdentifierAppleExerciseTime", "Exercise Time", "min", "sum"),
    ("HKQuantityTypeIdentifierAppleStandTime", "Stand Time", "min", "sum"),
    ("HKQuantityTypeIdentifierFlightsClimbed", "Flights Climbed", "count", "sum"),
    ("HKQuantityTypeIdentifierWalkingSpeed", "Walking Speed", "km/h", "mean"),
    ("HKQuantityTypeIdentifierRunningSpeed", "Running Speed", "km/h", "mean"),
    ("HKQuantityTypeIdentifierRunningPower", "Running Power", "W", "mean"),
]

with st.spinner("Loading activity data…"):
    df = load_all_records(str(db_path))

if df.empty:
    st.warning("No data found. Please import your Apple Health export on the Home page.")
    st.page_link("app.py", label="Go to Home →", icon="🏠")
    st.stop()

date_filter = sidebar_date_filter(df)
if date_filter is None:
    st.warning("Could not determine date range.")
    st.stop()

df_f = apply_date_filter(df, date_filter)
available_types = set(df_f["type"].unique()) if not df_f.empty else set()

# Filter to only available metrics
available_metrics = [(rt, label, unit, agg) for rt, label, unit, agg in ACTIVITY_METRICS if rt in available_types]

if not available_metrics:
    st.info("No activity data found in the selected period.")
    st.stop()

# ── Metric selector ───────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 📊 Metric")
    metric_labels = [label for _, label, _, _ in available_metrics]
    selected_label = st.selectbox("Choose metric", metric_labels, index=0)
    selected_idx = metric_labels.index(selected_label)
    selected_rt, _, selected_unit, selected_agg = available_metrics[selected_idx]

# ── Load selected metric data ─────────────────────────────────────────────────
metric_df = df_f[df_f["type"] == selected_rt].copy()
metric_df = normalize_units(metric_df, record_type=selected_rt)
daily = summarize_by_day_agg(metric_df, agg=selected_agg)

# ── KPIs ──────────────────────────────────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)

if not daily.empty:
    if selected_agg == "sum":
        c1.metric("Total", f"{daily['value'].sum():,.1f} {selected_unit}")
        c2.metric("Daily Average", f"{daily['value'].mean():,.1f} {selected_unit}")
        c3.metric("Best Day", f"{daily['value'].max():,.1f} {selected_unit}")
    else:
        c1.metric("Mean", f"{daily['value'].mean():,.1f} {selected_unit}")
        c2.metric("Max", f"{daily['value'].max():,.1f} {selected_unit}")
        c3.metric("Min", f"{daily['value'].min():,.1f} {selected_unit}")

    st.divider()
    st.subheader("🗓️ Activity Consistency")
    st.caption(f"Daily {selected_label} intensity over the last year.")
    with st.spinner("Generating heatmap..."):
        h_chart = calendar_heatmap(daily, "day", "value", color_scheme="greens")
        if h_chart:
            st.altair_chart(h_chart, use_container_width=True)
        else:
            st.info("Not enough data to generate consistency heatmap.")

    streak = daily_streak(daily.rename(columns={"value": "v"}), threshold=0)
    best_streak = longest_streak(daily.rename(columns={"value": "v"}), threshold=0)
    c4.metric("Current Streak", f"{streak} days", help="Consecutive days with data.")
    c5.metric("Best Streak", f"{best_streak} days", help="Longest ever consecutive streak.")

# Step goal tracker (shown when Steps is selected)
if "Step" in selected_label and not daily.empty:
    with st.sidebar:
        st.markdown("### 🎯 Step Goal")
        step_goal = st.number_input("Daily step goal", min_value=1000, max_value=30000, value=10000, step=500, key="step_goal")
    today_val = float(daily["value"].iloc[-1]) if not daily.empty else 0
    pct = min(today_val / step_goal * 100, 100)
    days_hit = (daily["value"] >= step_goal).sum()
    pct_days = days_hit / len(daily) * 100
    g1, g2, g3 = st.columns(3)
    g1.metric("Latest day steps", f"{today_val:,.0f}", delta=f"{today_val - step_goal:+,.0f} vs goal")
    g2.metric("Goal progress", f"{pct:.0f}%")
    g3.metric(f"Days hitting {step_goal:,}", f"{days_hit} ({pct_days:.0f}%)")

if selected_agg == "sum" and not daily.empty:
    st.markdown("#### 🏃 Annual Pacing Projection")
    daily_avg = daily["value"].mean()
    annual_proj = daily_avg * 365
    p1, p2 = st.columns(2)
    p1.metric(f"Projected 365-Day {selected_label}", f"{annual_proj:,.0f} {selected_unit}")
    
    msg = f"Based on your current average of **{daily_avg:,.1f} {selected_unit}** per day, this is what a full year would look like."
    if "Step" in selected_label:
        if annual_proj >= 3650000:
            msg += " 🌟 That's over 10,000 steps a day average!"
        elif annual_proj >= 1000000:
            msg += " 👏 Over a million steps!"
    elif "Distance" in selected_label:
        if annual_proj >= 1000:
            msg += " 🌍 Over 1,000 km in a year!"
    p2.info(msg)

st.divider()

# ── Main chart ────────────────────────────────────────────────────────────────
col_chart, col_info = st.columns([3, 1])

with col_chart:
    if not daily.empty:
        st.altair_chart(
            area_chart(
                daily,
                x="day",
                y="value",
                y_title=f"{selected_label} ({selected_unit})",
                title=f"{selected_label} per Day",
                height=280,
            ),
            width="stretch",
        )
    else:
        st.info("No data for this metric in the selected period.")

with col_info:
    if not daily.empty:
        pb = personal_bests(daily.rename(columns={"value": "v"}))
        if pb:
            st.markdown("**Personal Best**")
            st.metric(
                "Best day value",
                f"{pb['max_value']:,.1f} {selected_unit}",
            )
            best_day = pb.get("max_day")
            if best_day is not None:
                st.caption(f"Achieved: {pd.Timestamp(best_day).date()}")
            st.metric("Total days", f"{pb['total_days']:,}")

# ── Rolling average chart ──────────────────────────────────────────────────────
if not daily.empty and len(daily) >= 7:
    st.markdown("**7-Day & 30-Day Rolling Average**")
    roll_df = daily.copy()
    roll_df["7d_avg"] = roll_df["value"].rolling(7, min_periods=1).mean()
    if len(roll_df) >= 30:
        roll_df["30d_avg"] = roll_df["value"].rolling(30, min_periods=1).mean()
        y_cols = ["7d_avg", "30d_avg"]
    else:
        y_cols = ["7d_avg"]

    st.altair_chart(
        line_chart(roll_df, x="day", y=y_cols, y_title=selected_unit, height=200),
        width="stretch",
    )

st.divider()

# ── Advanced Activity Heatmap ──────────────────────────────────────────────────
st.subheader("🔥 Time-of-Day Heatmap")
st.caption(f"When are you most active? Average {selected_label} by hour and day of the week.")

if not metric_df.empty and "start_at" in metric_df.columns:
    hm_df = metric_df.dropna(subset=["start_at"]).copy()
    if not hm_df.empty:
        hm_df["hour"] = hm_df["start_at"].dt.hour
        hm_df["dow"] = hm_df["start_at"].dt.day_name()
        hm_df["dow_num"] = hm_df["start_at"].dt.dayofweek
        
        # We need the number of unique weeks to calculate the true average per hour-day slot
        num_weeks = max(1, (hm_df["start_at"].max() - hm_df["start_at"].min()).days / 7)
        
        if selected_agg == "sum":
            hm_agg = hm_df.groupby(["dow", "dow_num", "hour"])["value"].sum().reset_index()
            hm_agg["value"] = hm_agg["value"] / num_weeks
        else:
            hm_agg = hm_df.groupby(["dow", "dow_num", "hour"])["value"].mean().reset_index()
            
        days_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        
        import altair as alt
        heatmap = (
            alt.Chart(hm_agg)
            .mark_rect()
            .encode(
                x=alt.X("hour:O", title="Hour of Day (0-23)", axis=alt.Axis(labelAngle=0)),
                y=alt.Y("dow:O", sort=days_order, title=""),
                color=alt.Color("value:Q", scale=alt.Scale(scheme="oranges"), legend=alt.Legend(title=f"Avg {selected_unit}")),
                tooltip=[
                    alt.Tooltip("dow:O", title="Day"),
                    alt.Tooltip("hour:O", title="Hour"),
                    alt.Tooltip("value:Q", title=f"Avg {selected_label}", format=".1f"),
                ]
            )
            .properties(height=300)
        )
        st.altair_chart(heatmap, width="stretch")
    else:
        st.info("Not enough data with timestamps to generate a heatmap.")
else:
    st.info("Not enough data with timestamps to generate a heatmap.")

st.divider()

# ── All activity metrics overview ──────────────────────────────────────────────
st.subheader("All Activity Metrics Summary")
st.caption("Quick overview of all available activity metrics for the selected period.")

summary_rows = []
for rt, label, unit, agg in available_metrics:
    m_df = df_f[df_f["type"] == rt].copy()
    m_df = normalize_units(m_df, record_type=rt)
    d = summarize_by_day_agg(m_df, agg=agg)
    if d.empty:
        continue

    row = {"Metric": label, "Unit": unit, "Days": len(d)}
    if agg == "sum":
        row["Total"] = f"{d['value'].sum():,.1f}"
        row["Daily Average"] = f"{d['value'].mean():,.1f}"
        row["Best Day"] = f"{d['value'].max():,.1f}"
    else:
        row["Total"] = "—"
        row["Daily Average"] = f"{d['value'].mean():,.1f}"
        row["Best Day"] = f"{d['value'].max():,.1f}"
    summary_rows.append(row)

if summary_rows:
    summary_df = pd.DataFrame(summary_rows)
    st.dataframe(summary_df, width="stretch", hide_index=True)

# ── Monthly breakdown ────────────────────────────────────────────────────────
if not daily.empty and len(daily) >= 30:
    st.divider()
    st.subheader("Monthly Breakdown")
    monthly = daily.copy()
    monthly["month"] = pd.to_datetime(monthly["day"]).dt.to_period("M").dt.start_time

    if selected_agg == "sum":
        monthly_agg = monthly.groupby("month")["value"].sum().reset_index()
        monthly_agg = monthly_agg.rename(columns={"value": f"total_{selected_unit}"})
    else:
        monthly_agg = monthly.groupby("month")["value"].mean().reset_index()
        monthly_agg = monthly_agg.rename(columns={"value": f"avg_{selected_unit}"})

    val_col = monthly_agg.columns[1]
    from apple_health_dashboard.web.charts import bar_chart as _bar
    st.altair_chart(
        _bar(
            monthly_agg,
            x="month",
            y=val_col,
            y_title=f"{selected_label} ({selected_unit})",
            height=220,
        ),
        width="stretch",
    )
    st.dataframe(monthly_agg, width="stretch", hide_index=True)
