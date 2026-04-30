from __future__ import annotations

import pandas as pd
import streamlit as st

from apple_health_dashboard.db import default_db_path
from apple_health_dashboard.services.activity_summary import activity_summaries_to_dataframe
from apple_health_dashboard.services.body import body_summary_stats, weight_trend
from apple_health_dashboard.services.filters import apply_date_filter
from apple_health_dashboard.services.heart import heart_summary_stats, resting_hr_trend
from apple_health_dashboard.services.sleep import sleep_consistency_stats, sleep_duration_by_day, sleep_records
from apple_health_dashboard.services.stats import summarize_by_day_agg
from apple_health_dashboard.services.streaks import daily_streak, personal_bests
from apple_health_dashboard.services.workouts import workouts_to_dataframe
from apple_health_dashboard.storage.sqlite_store import (
    init_db,
    iter_activity_summaries,
    iter_records,
    iter_workouts,
    open_db,
)
from apple_health_dashboard.services.stats import to_dataframe
from apple_health_dashboard.web.charts import area_chart, line_chart
from apple_health_dashboard.web.page_utils import require_data, sidebar_date_filter

st.set_page_config(
    page_title="Overview · Apple Health Dashboard",
    page_icon="📊",
    layout="wide",
)

db_path = default_db_path()

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown(
    """
<style>
.block-container { padding-top: 1.5rem; }
.ahd-card {
  background: rgba(46,125,110,0.06);
  border: 1px solid rgba(46,125,110,0.18);
  padding: 14px 18px; border-radius: 14px; margin-bottom: 6px;
}
.ahd-big { font-size: 2rem; font-weight: 700; color: #2E7D6E; line-height: 1.1; }
.ahd-label { font-size: 0.8rem; opacity: 0.65; text-transform: uppercase; letter-spacing: 0.07em; }
</style>
""",
    unsafe_allow_html=True,
)

st.title("📊 Overview")
st.caption("Your key health metrics at a glance.")

# ── Load data ─────────────────────────────────────────────────────────────────
with st.spinner("Loading data…"):
    con = open_db(db_path)
    try:
        init_db(con)
        df = to_dataframe(list(iter_records(con)))
        wdf = workouts_to_dataframe(list(iter_workouts(con)))
        adf = activity_summaries_to_dataframe(list(iter_activity_summaries(con)))
    finally:
        con.close()

if df.empty:
    st.warning("No data imported yet. Please go to the **Home** page and import your Apple Health export.")
    st.page_link("app.py", label="Go to Home →", icon="🏠")
    st.stop()

# ── Date filter ───────────────────────────────────────────────────────────────
date_filter = sidebar_date_filter(df)
if date_filter is None:
    st.warning("Could not determine date range from the data.")
    st.stop()

df_f = apply_date_filter(df, date_filter)
period_label = f"{date_filter.start.date()} → {date_filter.end.date()}"

with st.sidebar:
    st.caption(f"Showing: **{period_label}**")
    st.caption(f"Records in range: **{len(df_f):,}**")

# ── Step count summary ────────────────────────────────────────────────────────
STEP_TYPE = "HKQuantityTypeIdentifierStepCount"
steps_df = df_f[df_f["type"] == STEP_TYPE].copy() if not df_f.empty else pd.DataFrame()
daily_steps = summarize_by_day_agg(steps_df, agg="sum") if not steps_df.empty else pd.DataFrame()

# ── Heart summary ─────────────────────────────────────────────────────────────
heart_stats = heart_summary_stats(df_f)

# ── Sleep summary ─────────────────────────────────────────────────────────────
srec = sleep_records(df_f)
sleep_stats = sleep_consistency_stats(srec)

# ── Body summary ──────────────────────────────────────────────────────────────
body_stats = body_summary_stats(df_f)

# ── Workouts in range ─────────────────────────────────────────────────────────
if not wdf.empty and "start_at" in wdf.columns:
    wdf_f = wdf[(wdf["start_at"] >= date_filter.start) & (wdf["start_at"] <= date_filter.end)].copy()
else:
    wdf_f = pd.DataFrame()

# ── Activity rings summary ────────────────────────────────────────────────────
if not adf.empty and "day" in adf.columns:
    adf_f = adf[
        (adf["day"] >= pd.Timestamp(date_filter.start.date()))
        & (adf["day"] <= pd.Timestamp(date_filter.end.date()))
    ].copy()
else:
    adf_f = pd.DataFrame()

# ── KPI row 1 ─────────────────────────────────────────────────────────────────
st.markdown("### Key Metrics")
c1, c2, c3, c4, c5, c6 = st.columns(6)

# Steps
if not daily_steps.empty:
    avg_steps = int(daily_steps["value"].mean())
    streak = daily_streak(daily_steps.rename(columns={"value": "steps"}), threshold=0)
    c1.metric("Avg Daily Steps", f"{avg_steps:,}", help="Average steps per day in selected period.")
    c2.metric("Steps Streak", f"{streak} days", help="Current consecutive days with steps recorded.")
else:
    c1.metric("Avg Daily Steps", "—")
    c2.metric("Steps Streak", "—")

# Heart
rhr = heart_stats.get("avg_resting_hr")
hrv = heart_stats.get("avg_hrv")
c3.metric("Avg Resting HR", f"{rhr} bpm" if rhr else "—", help="Average resting heart rate.")
c4.metric("Avg HRV", f"{hrv} ms" if hrv else "—", help="Average heart rate variability (SDNN).")

# Sleep
avg_sleep = sleep_stats.get("avg_hours")
nights_7 = sleep_stats.get("nights_gte_7h")
c5.metric(
    "Avg Sleep",
    f"{avg_sleep:.1f}h" if avg_sleep else "—",
    help="Average hours of sleep per night.",
)
c6.metric(
    "Nights ≥7h",
    f"{nights_7 * 100:.0f}%" if nights_7 is not None else "—",
    help="Percentage of nights with at least 7 hours of sleep.",
)

st.divider()

# ── KPI row 2 ─────────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)

# Workouts
c1.metric("Workouts", f"{len(wdf_f):,}" if not wdf_f.empty else "—")

# Activity rings
if not adf_f.empty and "active_energy_burned_kcal" in adf_f.columns:
    avg_cal = adf_f["active_energy_burned_kcal"].mean()
    c2.metric("Avg Move (kcal)", f"{avg_cal:.0f}" if not pd.isna(avg_cal) else "—")
else:
    c2.metric("Avg Move (kcal)", "—")

# VO2 max
vo2 = heart_stats.get("latest_vo2max")
vo2_class = heart_stats.get("vo2max_classification", "")
c3.metric("VO₂ Max", f"{vo2}" if vo2 else "—", delta=str(vo2_class) if vo2_class else None)

# Body
weight = body_stats.get("latest_weight_kg")
bmi = body_stats.get("latest_bmi")
c4.metric(
    "Weight / BMI",
    f"{weight} kg" if weight else "—",
    delta=f"BMI {bmi}" if bmi else None,
)

st.divider()

# ── Charts ────────────────────────────────────────────────────────────────────
col_l, col_r = st.columns(2)

with col_l:
    st.markdown("#### Steps per Day")
    if not daily_steps.empty:
        st.altair_chart(
            area_chart(
                daily_steps,
                x="day",
                y="value",
                y_title="Steps",
                color="#2E7D6E",
                height=200,
            ),
            use_container_width=True,
        )
        pb = personal_bests(daily_steps.rename(columns={"value": "steps"}))
        if pb:
            st.caption(
                f"Best day: **{pb['max_value']:,.0f} steps** on {pd.Timestamp(pb['max_day']).date()} · "
                f"Average: **{pb['avg_value']:,.0f}**"
            )
    else:
        st.info("No step data in this period.")

with col_r:
    st.markdown("#### Resting Heart Rate")
    rhr_df = resting_hr_trend(df_f)
    if not rhr_df.empty:
        st.altair_chart(
            line_chart(
                rhr_df,
                x="day",
                y="rhr",
                y_title="bpm",
                height=200,
                rolling_avg_days=7,
            ),
            use_container_width=True,
        )
        st.caption("Dashed line = 7-day rolling average.")
    else:
        st.info("No heart rate data in this period.")

col_l2, col_r2 = st.columns(2)

with col_l2:
    st.markdown("#### Sleep Duration")
    if not srec.empty:
        sleep_dur = sleep_duration_by_day(srec, stages="actual")
        if sleep_dur.empty:
            sleep_dur = sleep_duration_by_day(srec)
        if not sleep_dur.empty:
            st.altair_chart(
                area_chart(sleep_dur, x="day", y="hours", y_title="Hours", color="#4A90D9", height=200),
                use_container_width=True,
            )
            st.caption(
                f"Average: **{sleep_stats.get('avg_hours', 0):.1f}h** · "
                f"Median: **{sleep_stats.get('median_hours', 0):.1f}h**"
            )
    else:
        st.info("No sleep data in this period.")

with col_r2:
    st.markdown("#### Activity (Move Ring)")
    if not adf_f.empty and "active_energy_burned_kcal" in adf_f.columns:
        ring_data = adf_f[["day", "active_energy_burned_kcal"]].dropna().copy()
        ring_data = ring_data.rename(columns={"active_energy_burned_kcal": "kcal"})
        st.altair_chart(
            area_chart(ring_data, x="day", y="kcal", y_title="Active kcal", color="#FF6B6B", height=200),
            use_container_width=True,
        )
    else:
        st.info("No activity ring data in this period.")

# ── Weight trend ──────────────────────────────────────────────────────────────
w_trend = weight_trend(df_f)
if not w_trend.empty and len(w_trend) > 1:
    st.markdown("#### Weight Trend")
    st.altair_chart(
        line_chart(w_trend, x="day", y="weight_kg", y_title="kg", height=180, rolling_avg_days=7),
        use_container_width=True,
    )
    change = body_stats.get("weight_change_kg")
    if change is not None:
        arrow = "▲" if change > 0 else "▼"
        st.caption(
            f"Change in period: {arrow} **{abs(change):.1f} kg** · "
            f"Latest: **{body_stats.get('latest_weight_kg')} kg**"
        )

# ── Workouts summary ──────────────────────────────────────────────────────────
if not wdf_f.empty:
    st.divider()
    st.markdown("#### Workout Activity")
    label_col = "activity_label" if "activity_label" in wdf_f.columns else "workout_activity_type"
    type_counts = wdf_f[label_col].value_counts().reset_index()
    type_counts.columns = ["Type", "Count"]
    c_bar, c_info = st.columns([2, 1])
    with c_bar:
        from apple_health_dashboard.web.charts import bar_chart as _bar
        st.altair_chart(
            _bar(type_counts, x="Type", y="Count", horizontal=True, height=max(180, len(type_counts) * 28)),
            use_container_width=True,
        )
    with c_info:
        st.metric("Total workouts", len(wdf_f))
        total_h = wdf_f["duration_s"].fillna(0).sum() / 3600
        st.metric("Total hours", f"{total_h:.1f}h")
        total_kcal = wdf_f["total_energy_kcal"].fillna(0).sum()
        st.metric("Total calories", f"{total_kcal:,.0f} kcal")
