from __future__ import annotations

import logging
import pandas as pd
import streamlit as st

from apple_health_dashboard.db import default_db_path
from apple_health_dashboard.logging_config import configure_logging
from apple_health_dashboard.web.page_utils import (
    inject_global_css,
    sidebar_nav,
    load_all_records,
    load_all_workouts,
    load_all_activity_summaries,
    ring_dots_html,
    trend_pill,
    page_footer,
)
from apple_health_dashboard.services.insights import daily_readiness_score
from apple_health_dashboard.services.heart import heart_summary_stats
from apple_health_dashboard.services.workouts import summarize_workouts_by_week

logger = logging.getLogger(__name__)


def _sparkline_svg(values: list[float], color: str = "#2E7D6E", width: int = 80, height: int = 28) -> str:
    """Generate a tiny inline SVG sparkline."""
    if not values or len(values) < 2:
        return ""
    mn, mx = min(values), max(values)
    rng = mx - mn or 1
    n = len(values)
    step = width / (n - 1)
    pts = []
    for i, v in enumerate(values):
        x = i * step
        y = height - ((v - mn) / rng) * (height - 4) - 2
        pts.append(f"{x:.1f},{y:.1f}")
    poly = " ".join(pts)
    return (
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        f'xmlns="http://www.w3.org/2000/svg" style="display:inline-block;vertical-align:middle;">'
        f'<polyline points="{poly}" fill="none" stroke="{color}" stroke-width="2" '
        f'stroke-linecap="round" stroke-linejoin="round"/>'
        f"</svg>"
    )


def _kpi_card(label: str, value: str, sparkline_svg: str = "", pill_html: str = "", icon: str = "") -> str:
    """Return a styled KPI card as HTML."""
    return f"""
<div class="ahd-card" style="padding:14px 18px;">
  <div style="font-size:0.75rem;font-weight:600;opacity:0.55;text-transform:uppercase;
              letter-spacing:0.06em;margin-bottom:6px;">{icon} {label}</div>
  <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
    <span style="font-size:1.6rem;font-weight:800;color:#0D2822;letter-spacing:-0.02em;">{value}</span>
    {pill_html}
  </div>
  {sparkline_svg}
</div>"""


def main() -> None:
    configure_logging()

    st.set_page_config(
        page_title="Apple Health Dashboard",
        page_icon="🍎",
        layout="wide",
    )
    inject_global_css()

    with st.sidebar:
        sidebar_nav(current="Home")
        st.divider()
        st.caption(f"Database: `{default_db_path().name}`")
        st.page_link("pages/10_⚙️_Settings.py", label="⚙️ Manage Data")

    db_path = default_db_path()

    with st.spinner("Loading data…"):
        df = load_all_records(str(db_path))
        wdf = load_all_workouts(str(db_path))
        adf = load_all_activity_summaries(str(db_path))

    if df.empty:
        st.markdown("""
<div class="ahd-card" style="text-align:center;padding:40px 20px;">
  <div style="font-size:3rem;margin-bottom:12px;">🍎</div>
  <div style="font-size:1.2rem;font-weight:700;color:#0D2822;margin-bottom:8px;">No data yet</div>
  <div style="opacity:0.6;margin-bottom:16px;">Import your Apple Health export to get started.</div>
</div>""", unsafe_allow_html=True)
        st.page_link("pages/10_⚙️_Settings.py", label="Go to Settings →", icon="⚙️")
        st.stop()

    # ── Hero banner ───────────────────────────────────────────────────────────
    latest_date = df["start_at"].max().floor("D")
    db_size_mb = db_path.stat().st_size / 1_048_576 if db_path.exists() else 0
    total_records = len(df)

    st.markdown(f"""
<div class="ahd-hero">
  <div class="ahd-hero-title">🍎 Daily Dashboard</div>
  <div class="ahd-hero-sub">
    Latest data: <strong style="color:white;">{latest_date.date()}</strong>
    &nbsp;·&nbsp; {total_records:,} records
    &nbsp;·&nbsp; DB: {db_size_mb:.1f} MB
  </div>
</div>""", unsafe_allow_html=True)

    # ── Readiness + Rings row ─────────────────────────────────────────────────
    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("#### 🏆 Today's Readiness Score")
        readiness = daily_readiness_score(df)
        if not readiness.empty:
            latest_r = readiness.iloc[-1]
            score = latest_r["score"]
            color = "#10B981" if score >= 60 else ("#F59E0B" if score >= 40 else "#EF4444")
            badge_cls = "ahd-score-green" if score >= 60 else ("ahd-score-yellow" if score >= 40 else "ahd-score-red")
            label_txt = "🟢 Ready to train" if score >= 60 else ("🟡 Take it easy" if score >= 40 else "🔴 Rest recommended")

            # 7-day trend
            scores_7d = readiness["score"].tail(7).tolist()
            spark = _sparkline_svg(scores_7d, color=color)
            prev_score = readiness["score"].iloc[-2] if len(readiness) >= 2 else score
            pill = trend_pill(score - prev_score)

            st.markdown(f"""
<div class="ahd-card">
  <div style="display:flex;align-items:center;gap:16px;">
    <div class="ahd-score-badge {badge_cls}">{score:.0f}</div>
    <div>
      <div style="font-weight:700;font-size:0.95rem;color:#0D2822;">{label_txt}</div>
      <div style="margin-top:4px;display:flex;align-items:center;gap:8px;">
        {pill}
        <span style="font-size:0.8rem;opacity:0.5;">vs yesterday</span>
        {spark}
      </div>
    </div>
  </div>
  {"<div style='margin-top:8px;font-size:0.8rem;opacity:0.6;'>HRV: " + f"{latest_r['hrv']:.0f} ms" + " · RHR: " + f"{latest_r['rhr']:.0f} bpm" + " · Sleep: " + f"{latest_r['sleep_h']:.1f} h</div>" if all(c in readiness.columns for c in ['hrv','rhr','sleep_h']) else ""}
</div>""", unsafe_allow_html=True)
            st.page_link("pages/9_💡_Insights.py", label="View Readiness Details →")

            # Rest-day recommendation banner
            if score < 40:
                st.warning("😴 **Rest day recommended.** Your readiness is low — prioritise sleep and recovery today.")
            elif score >= 75:
                st.success("💪 **High readiness!** Great day for an intense workout or PB attempt.")
        else:
            st.info("Not enough data to calculate readiness.")

    with col_b:
        st.markdown("#### 🔥 Activity Rings — Last 7 Days")
        if not adf.empty:
            last7_adf = adf.tail(7)
            latest_adf = adf.iloc[-1]

            # Ring dots
            RING_DEFS = [
                ("active_energy_burned_kcal", "active_energy_burned_goal_kcal", "🔴 Move"),
                ("apple_exercise_time_min", "apple_exercise_time_goal_min", "🟢 Exercise"),
                ("apple_stand_hours", "apple_stand_hours_goal", "🔵 Stand"),
            ]
            ring_html = ""
            for actual_col, goal_col, ring_name in RING_DEFS:
                if actual_col in last7_adf.columns:
                    if goal_col in last7_adf.columns:
                        closed = [
                            bool(row[actual_col] >= row[goal_col]) if (row.get(goal_col, 0) or 0) > 0 else None
                            for _, row in last7_adf.iterrows()
                        ]
                    else:
                        closed = [None] * len(last7_adf)
                    ring_html += f"<div style='margin-bottom:4px;'><span style='font-size:0.75rem;font-weight:600;opacity:0.6;width:80px;display:inline-block;'>{ring_name}</span> {ring_dots_html(closed)}</div>"

            if ring_html:
                st.markdown(f"""
<div class="ahd-card">
  <div style="font-size:0.75rem;opacity:0.45;margin-bottom:8px;font-weight:500;">7-day ring history (most recent →)</div>
  {ring_html}
</div>""", unsafe_allow_html=True)

            # Today's values
            c1, c2, c3 = st.columns(3)
            c1.metric("🔴 Move", f"{latest_adf.get('active_energy_burned_kcal', 0):.0f} kcal")
            c2.metric("🟢 Exercise", f"{latest_adf.get('apple_exercise_time_min', 0):.0f} min")
            c3.metric("🔵 Stand", f"{latest_adf.get('apple_stand_hours', 0):.0f} h")
            st.page_link("pages/6_🔥_Rings.py", label="View Activity Rings →")
        else:
            st.info("No Activity Ring data found.")

    st.divider()

    # ── Heart + Workouts row ──────────────────────────────────────────────────
    col_c, col_d = st.columns(2)

    with col_c:
        st.markdown("#### ❤️ Heart Summary")
        stats = heart_summary_stats(df)
        if stats:
            # 7-day RHR trend sparkline
            from apple_health_dashboard.services.heart import resting_hr_trend
            rhr_df = resting_hr_trend(df)
            rhr_spark = ""
            rhr_pill = ""
            if not rhr_df.empty and len(rhr_df) >= 2:
                vals = rhr_df["rhr"].tail(7).tolist()
                rhr_spark = _sparkline_svg(vals, "#EF4444")
                delta_rhr = vals[-1] - vals[0] if len(vals) >= 2 else 0
                rhr_pill = trend_pill(delta_rhr, " bpm", lower_is_better=True)

            sc1, sc2 = st.columns(2)
            sc1.metric("Avg Resting HR", f"{stats.get('avg_resting_hr', '—')} bpm")
            sc2.metric("Avg HRV", f"{stats.get('avg_hrv', '—')} ms")
            if rhr_spark:
                st.markdown(
                    f"<div style='display:flex;align-items:center;gap:8px;margin-top:4px;'>"
                    f"<span style='font-size:0.8rem;opacity:0.5;'>7-day RHR:</span> {rhr_spark} {rhr_pill}</div>",
                    unsafe_allow_html=True,
                )
            vo2 = stats.get("latest_vo2max")
            vo2_class = stats.get("vo2max_classification", "")
            if vo2:
                st.metric("VO₂ Max", f"{vo2}", delta=str(vo2_class) if vo2_class else None)
        st.page_link("pages/2_❤️_Heart.py", label="View Heart Health →")

    with col_d:
        st.markdown("#### 🏋️ Recent Workouts")
        if not wdf.empty:
            recent = wdf[wdf["start_at"] >= latest_date - pd.Timedelta(days=7)]
            prev_7 = wdf[
                (wdf["start_at"] >= latest_date - pd.Timedelta(days=14))
                & (wdf["start_at"] < latest_date - pd.Timedelta(days=7))
            ]
            count_now = len(recent)
            count_prev = len(prev_7)
            delta_w = count_now - count_prev

            col_w1, col_w2 = st.columns(2)
            col_w1.metric(
                "Workouts (7 days)",
                f"{count_now}",
                delta=f"{delta_w:+d} vs prev week" if count_prev > 0 else None,
            )
            if not recent.empty:
                col_w2.metric("Total duration", f"{recent['duration_s'].sum() / 3600:.1f} h")

            # Workout type mini-breakdown
            if not recent.empty:
                label_col = "activity_label" if "activity_label" in recent.columns else "workout_activity_type"
                counts = recent[label_col].value_counts().head(3)
                types_str = " · ".join([f"{v}× {k}" for k, v in counts.items()])
                st.caption(f"Types: {types_str}")
        else:
            st.info("No workouts logged.")
        st.page_link("pages/5_🏋️_Workouts.py", label="View All Workouts →")

    st.divider()

    # ── Navigation cards ──────────────────────────────────────────────────────
    st.markdown(
        "<div style='font-size:1.05rem;font-weight:700;color:#0D2822;"
        "letter-spacing:-0.01em;margin-bottom:4px;'>Explore your health data</div>",
        unsafe_allow_html=True,
    )

    # Count records per category for live counts
    type_counts: dict[str, int] = {}
    if not df.empty:
        type_counts = df["type"].value_counts().to_dict()

    HEART_TYPES = {"HKQuantityTypeIdentifierHeartRate", "HKQuantityTypeIdentifierHeartRateVariabilitySDNN",
                   "HKQuantityTypeIdentifierRestingHeartRate", "HKQuantityTypeIdentifierVO2Max"}
    ACTIVITY_TYPES = {"HKQuantityTypeIdentifierStepCount", "HKQuantityTypeIdentifierDistanceWalkingRunning",
                      "HKQuantityTypeIdentifierActiveEnergyBurned"}
    SLEEP_TYPES = {"HKCategoryTypeIdentifierSleepAnalysis"}
    BODY_TYPES = {"HKQuantityTypeIdentifierBodyMass", "HKQuantityTypeIdentifierBodyFatPercentage"}

    def _count(types: set[str]) -> int:
        return sum(type_counts.get(t, 0) for t in types)

    nav = [
        ("📊", "Overview", "pages/1_📊_Overview.py",
         "Key metrics, trends & highlights at a glance.", ""),
        ("❤️", "Heart", "pages/2_❤️_Heart.py",
         "HR, HRV, VO₂ max, blood pressure & SpO₂.", f"{_count(HEART_TYPES):,} records"),
        ("🏃", "Activity", "pages/3_🏃_Activity.py",
         "Steps, distance, calories & active minutes.", f"{_count(ACTIVITY_TYPES):,} records"),
        ("😴", "Sleep", "pages/4_😴_Sleep.py",
         "Sleep stages, duration & consistency.", f"{_count(SLEEP_TYPES):,} records"),
        ("🏋️", "Workouts", "pages/5_🏋️_Workouts.py",
         "All workout types, personal records & streaks.", f"{len(wdf):,} workouts"),
        ("🔥", "Rings", "pages/6_🔥_Rings.py",
         "Activity ring completion, goals & streaks.", f"{len(adf):,} days"),
        ("⚖️", "Body", "pages/7_⚖️_Body.py",
         "Weight, BMI, body fat & composition trends.", f"{_count(BODY_TYPES):,} records"),
        ("🔬", "Explorer", "pages/8_🔬_Explorer.py",
         "Browse & filter all raw health data.", f"{len(df):,} records"),
        ("💡", "Insights", "pages/9_💡_Insights.py",
         "Cross-metric analysis that connects the dots.", ""),
        ("📈", "Trends", "pages/11_📈_Trends.py",
         "Year-over-year comparisons & long-term trends.", ""),
    ]

    for i in range(0, len(nav), 3):
        row_items = nav[i: i + 3]
        cols = st.columns(len(row_items))
        for col, (icon, name, page, desc, count_str) in zip(cols, row_items):
            with col:
                count_html = f'<div class="ahd-nav-card-count">{count_str}</div>' if count_str else ""
                st.markdown(
                    f"""<div class="ahd-nav-card">
  <div class="ahd-nav-card-title">{icon} {name}</div>
  <div class="ahd-nav-card-desc">{desc}</div>
  {count_html}
</div>""",
                    unsafe_allow_html=True,
                )
                st.page_link(page, label=f"Open {name} →")

    page_footer(db_path)


if __name__ == "__main__":
    main()
