from __future__ import annotations

import pandas as pd
import streamlit as st

from apple_health_dashboard.db import default_db_path
from apple_health_dashboard.services.filters import apply_date_filter
from apple_health_dashboard.services.stats import summarize_by_day_agg
from apple_health_dashboard.services.streaks import daily_streak, longest_streak, personal_bests
from apple_health_dashboard.services.units import normalize_units
from apple_health_dashboard.web.charts import area_chart, line_chart
from apple_health_dashboard.web.page_utils import (
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

date_filter = sidebar_date_filter(df, current="Activity")
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

    streak = daily_streak(daily.rename(columns={"value": "v"}), threshold=0)
    best_streak = longest_streak(daily.rename(columns={"value": "v"}), threshold=0)
    c4.metric("Current Streak", f"{streak} days", help="Consecutive days with data.")
    c5.metric("Best Streak", f"{best_streak} days", help="Longest ever consecutive streak.")

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
            use_container_width=True,
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
        use_container_width=True,
    )

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
    st.dataframe(summary_df, use_container_width=True, hide_index=True)

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
        use_container_width=True,
    )
    st.dataframe(monthly_agg, use_container_width=True, hide_index=True)
