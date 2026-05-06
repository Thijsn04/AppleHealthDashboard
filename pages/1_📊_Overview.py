from __future__ import annotations

import pandas as pd
import streamlit as st

from apple_health_dashboard.db import default_db_path
from apple_health_dashboard.services.filters import apply_date_filter
from apple_health_dashboard.services.body import body_summary_stats, weight_trend
from apple_health_dashboard.services.heart import heart_summary_stats, resting_hr_trend
from apple_health_dashboard.services.sleep import sleep_consistency_stats, sleep_duration_by_day, sleep_records
from apple_health_dashboard.services.insights import generate_insights
from apple_health_dashboard.services.stats import summarize_by_day_agg
from apple_health_dashboard.services.streaks import daily_streak, personal_bests
from apple_health_dashboard.web.charts import area_chart, line_chart
from apple_health_dashboard.services.readiness import calculate_readiness_score
from apple_health_dashboard.services.stats import detect_outliers_zscore
from apple_health_dashboard.storage.notes_store import load_notes, save_note
from apple_health_dashboard.web.page_utils import (
    sidebar_nav,
    load_all_activity_summaries,
    load_all_records,
    load_all_workouts,
    page_header,
    sidebar_date_filter,
)

st.set_page_config(
    page_title="Overview · Apple Health Dashboard",
    page_icon="📊",
    layout="wide",
)

with st.sidebar:
    sidebar_nav(current="Overview")
    st.divider()

db_path = default_db_path()

# ── Load data ─────────────────────────────────────────────────────────────────
with st.spinner("Loading data…"):
    df = load_all_records(str(db_path))
    wdf = load_all_workouts(str(db_path))
    adf = load_all_activity_summaries(str(db_path))

if df.empty:
    st.warning("No data imported yet. Please go to the **Home** page and import your Apple Health export.")
    st.page_link("app.py", label="Go to Home →", icon="🏠")
    st.stop()

# ── Readiness Score ───────────────────────────────────────────────────────────
readiness = calculate_readiness_score(df, pd.DataFrame(), adf) # Simplified sleep for now
score = readiness["score"]

st.markdown(
    f"""<div class="ahd-hero">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <div class="ahd-hero-title">Welcome back!</div>
                <div class="ahd-hero-sub">Your readiness is <b>{readiness['label']}</b> today. Based on your HRV, sleep, and activity.</div>
            </div>
            <div style="text-align: center; background: rgba(255,255,255,0.15); padding: 15px 25px; border-radius: 15px; backdrop-filter: blur(10px);">
                <div style="font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.1em; opacity: 0.8;">Readiness</div>
                <div style="font-size: 2.5rem; font-weight: 800;">{score}%</div>
            </div>
        </div>
    </div>""",
    unsafe_allow_html=True
)

# ── Anomaly Detection ──────────────────────────────────────────────────────────
hr_type = "HKQuantityTypeIdentifierHeartRate"
hr_data = df[df["type"] == hr_type].tail(1000) # Recent HR
if not hr_data.empty:
    hr_anomalies = detect_outliers_zscore(hr_data, "value", threshold=3.5)
    recent_anomalies = hr_anomalies[hr_anomalies["is_outlier"]].tail(3)
    if not recent_anomalies.empty:
        with st.expander("⚠️ Unusual Heart Rate Detected", expanded=False):
            st.warning("We detected some heart rate readings that are statistically unusual for you.")
            for _, row in recent_anomalies.iterrows():
                st.write(f"- **{row['value']:.0f} bpm** at {pd.to_datetime(row['start_at']).strftime('%H:%M on %b %d')}")
            st.info("Occasional spikes are normal during intense exercise or stress, but if you feel unwell, please consult a professional.")

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

# ── On This Day ───────────────────────────────────────────────────────────────
st.markdown("### 🕰️ On This Day")
if not df.empty and pd.notna(df["start_at"].max()):
    ref_date = pd.Timestamp.now().date()
    try:
        one_year_ago = ref_date.replace(year=ref_date.year - 1)
        
        # Steps
        df_1y_steps = df[(df["type"] == STEP_TYPE) & (df["start_at"].dt.date == one_year_ago)]
        steps_1y = int(df_1y_steps["value"].sum()) if not df_1y_steps.empty else 0
        
        # Workouts
        wdf_1y = wdf[wdf["start_at"].dt.date == one_year_ago] if not wdf.empty and "start_at" in wdf.columns else pd.DataFrame()
        
        if steps_1y > 0 or not wdf_1y.empty:
            st.caption(f"**Exactly 1 year ago today ({one_year_ago.strftime('%b %d, %Y')}):**")
            c1_1y, c2_1y, c3_1y = st.columns(3)
            c1_1y.metric("Steps", f"{steps_1y:,}" if steps_1y > 0 else "—")
            
            w_names = ", ".join(wdf_1y["activity_label"].tolist()) if not wdf_1y.empty and "activity_label" in wdf_1y.columns else "None"
            c2_1y.metric("Workouts", w_names if w_names else "—")
            
            # Move ring
            adf_1y = adf[adf["day"].dt.date == one_year_ago] if not adf.empty and "day" in adf.columns else pd.DataFrame()
            move_1y = int(adf_1y["active_energy_burned_kcal"].iloc[0]) if not adf_1y.empty and "active_energy_burned_kcal" in adf_1y.columns and pd.notna(adf_1y["active_energy_burned_kcal"].iloc[0]) else 0
            c3_1y.metric("Move (kcal)", f"{move_1y:,}" if move_1y > 0 else "—")
        else:
            st.info(f"No significant data recorded on {one_year_ago.strftime('%b %d, %Y')}.")
    except ValueError:
        pass # Leap year 29 Feb case

st.divider()

# ── Auto-insights strip ───────────────────────────────────────────────────────
st.markdown("### 💡 Key Insights")
st.caption("Auto-detected patterns across your health data. [See full analysis →](Insights)")

_insights = generate_insights(df_f, wdf_f)
_KIND_BG = {
    "positive": "rgba(16,185,129,0.08)",
    "negative": "rgba(239,68,68,0.08)",
    "neutral":  "rgba(245,158,11,0.08)",
    "info":     "rgba(59,130,246,0.08)",
}
_KIND_BORDER = {
    "positive": "#10B981",
    "negative": "#EF4444",
    "neutral":  "#F59E0B",
    "info":     "#3B82F6",
}
_top_insights = _insights[:3]
_cols = st.columns(len(_top_insights))
for _col, _ins in zip(_cols, _top_insights):
    _bg = _KIND_BG.get(_ins.get("kind", "info"), _KIND_BG["info"])
    _border = _KIND_BORDER.get(_ins.get("kind", "info"), _KIND_BORDER["info"])
    _col.markdown(
        f"""<div style="background:{_bg};border-left:4px solid {_border};
        padding:12px 14px;border-radius:10px;margin-bottom:6px;">
        <div style="font-weight:700;margin-bottom:4px;">{_ins['icon']} {_ins['title']}</div>
        <div style="font-size:0.85rem;opacity:0.82;">{_ins['body']}</div>
        </div>""",
        unsafe_allow_html=True,
    )

st.divider()

# ── Charts ────────────────────────────────────────────────────────────────────
tab_daily, tab_body, tab_workouts = st.tabs(["🚶 Daily Activity & Sleep", "❤️ Heart & Body Trends", "🏋️ Workouts Summary"])

with tab_daily:
    col_l, col_r = st.columns(2)
    
    with col_l:
        st.markdown("#### Steps per Day")
        if not daily_steps.empty:
            st.altair_chart(
                area_chart(daily_steps, x="day", y="value", y_title="Steps", color="#2E7D6E", height=200),
                width="stretch",
            )
            pb = personal_bests(daily_steps.rename(columns={"value": "steps"}))
            if pb:
                st.caption(f"Best: **{pb['max_value']:,.0f} steps** on {pd.Timestamp(pb['max_day']).date()} · Avg: **{pb['avg_value']:,.0f}**")
        else:
            st.info("No step data.")

    with col_r:
        st.markdown("#### Sleep Duration")
        if not srec.empty:
            sleep_dur = sleep_duration_by_day(srec, stages="actual")
            if sleep_dur.empty: sleep_dur = sleep_duration_by_day(srec)
            if not sleep_dur.empty:
                st.altair_chart(
                    area_chart(sleep_dur, x="day", y="hours", y_title="Hours", color="#4A90D9", height=200),
                    width="stretch",
                )
                st.caption(f"Avg: **{sleep_stats.get('avg_hours', 0):.1f}h** · Median: **{sleep_stats.get('median_hours', 0):.1f}h**")
        else:
            st.info("No sleep data.")

    st.markdown("#### Activity (Move Ring)")
    if not adf_f.empty and "active_energy_burned_kcal" in adf_f.columns:
        ring_data = adf_f[["day", "active_energy_burned_kcal"]].dropna().copy().rename(columns={"active_energy_burned_kcal": "kcal"})
        st.altair_chart(area_chart(ring_data, x="day", y="kcal", y_title="Active kcal", color="#FF6B6B", height=200), width="stretch")
    else:
        st.info("No activity ring data.")

with tab_body:
    col_bl, col_br = st.columns(2)
    with col_bl:
        st.markdown("#### Resting Heart Rate")
        rhr_df = resting_hr_trend(df_f)
        if not rhr_df.empty:
            st.altair_chart(line_chart(rhr_df, x="day", y="rhr", y_title="bpm", height=200, rolling_avg_days=7), width="stretch")
        else:
            st.info("No RHR data.")
            
    with col_br:
        w_trend = weight_trend(df_f)
        if not w_trend.empty and len(w_trend) > 1:
            st.markdown("#### Weight Trend")
            st.altair_chart(line_chart(w_trend, x="day", y="weight_kg", y_title="kg", height=200, rolling_avg_days=7), width="stretch")
        else:
            st.info("No Weight data.")

with tab_workouts:
    if not wdf_f.empty:
        label_col = "activity_label" if "activity_label" in wdf_f.columns else "workout_activity_type"
        type_counts = wdf_f[label_col].value_counts().reset_index()
        type_counts.columns = ["Type", "Count"]
        c_bar, c_info = st.columns([2, 1])
        with c_bar:
            from apple_health_dashboard.web.charts import bar_chart as _bar
            st.altair_chart(_bar(type_counts, x="Type", y="Count", horizontal=True, height=max(180, len(type_counts) * 28)), width="stretch")
        with c_info:
            st.metric("Total workouts", len(wdf_f))
            total_h = wdf_f["duration_s"].fillna(0).sum() / 3600
            st.metric("Total hours", f"{total_h:.1f}h")
            total_kcal = wdf_f["total_energy_kcal"].fillna(0).sum()
            st.metric("Total calories", f"{total_kcal:,.0f} kcal")
    else:
        st.info("No workout data.")

# ── Annotations & Notes ───────────────────────────────────────────────────────
with st.sidebar:
    st.divider()
    st.subheader("📝 Chart Annotations")
    note_date = st.date_input("Annotation Date", value=datetime.now())
    note_text = st.text_input("Note (e.g. 'Started diet')")
    if st.button("Add Annotation"):
        save_note(note_date, note_text, "Overview")
        st.success("Note added!")
        st.rerun()

# Helper to add annotations to Altair chart
def add_annotations(base_chart, notes):
    if notes.empty: return base_chart
    notes_df = notes.copy()
    notes_df["y"] = 0
    rules = alt.Chart(notes_df).mark_rule(color="red", strokeDash=[4,4]).encode(x="date:T")
    text = alt.Chart(notes_df).mark_text(align="left", dx=5, dy=-10, color="red", fontWeight="bold").encode(
        x="date:T", y=alt.value(20), text="note:N"
    )
    return base_chart + rules + text

notes_df_all = load_notes()
overview_notes = notes_df_all[notes_df_all["metric_context"] == "Overview"]
