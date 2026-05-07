from __future__ import annotations

import streamlit as st

from apple_health_dashboard.db import default_db_path
from apple_health_dashboard.services.filters import apply_date_filter
from apple_health_dashboard.services.heart import (
    HR_ZONES,
    blood_pressure_trend,
    heart_summary_stats,
    hr_daily_stats,
    hr_zone_distribution,
    hrv_trend,
    resting_hr_trend,
    spo2_trend,
    vo2max_trend,
    classify_vo2max,
    HEART_RATE_TYPE,
    RESTING_HR_TYPE,
    HRV_TYPE,
    VO2MAX_TYPE,
    SYSTOLIC_TYPE,
    DIASTOLIC_TYPE,
    SPO2_TYPE,
)
from apple_health_dashboard.services.streaks import daily_streak, longest_streak
from apple_health_dashboard.web.charts import area_chart, bar_chart, donut_chart, line_chart
from apple_health_dashboard.web.page_utils import (
    load_all_records,
    page_header,
    sidebar_date_filter,
    sidebar_nav,
)

st.set_page_config(
    page_title="Heart Health · Apple Health Dashboard",
    page_icon="❤️",
    layout="wide",
)

page_header("❤️", "Heart Health", "Heart rate, HRV, VO₂ max, blood pressure & blood oxygen.")

db_path = default_db_path()

with st.sidebar:
    sidebar_nav(current="Heart")
    st.divider()

with st.spinner("Loading heart data…"):
    df = load_all_records(str(db_path))

if df.empty:
    st.warning("No data found. Please import your Apple Health export on the Home page.")
    st.page_link("app.py", label="Go to Home →", icon="🏠")
    st.stop()

# ── Date filter ───────────────────────────────────────────────────────────────
date_filter = sidebar_date_filter(df, current="Heart")
if date_filter is None:
    st.warning("Could not determine date range.")
    st.stop()

df_f = apply_date_filter(df, date_filter)

# ── Available heart types ─────────────────────────────────────────────────────
available_types = set(df_f["type"].unique()) if not df_f.empty else set()
HEART_TYPES = {
    HEART_RATE_TYPE, RESTING_HR_TYPE, HRV_TYPE, VO2MAX_TYPE,
    SYSTOLIC_TYPE, DIASTOLIC_TYPE, SPO2_TYPE,
}
has_any_heart = bool(available_types & HEART_TYPES)

if not has_any_heart:
    st.info("No heart-related data found in the selected period.")
    st.stop()

# ── Summary stats ─────────────────────────────────────────────────────────────
stats = heart_summary_stats(df_f)

c1, c2, c3, c4 = st.columns(4)
c1.metric(
    "Avg Resting HR",
    f"{stats['avg_resting_hr']} bpm" if "avg_resting_hr" in stats else "—",
    help="Mean resting heart rate over the selected period.",
)
c2.metric(
    "Avg HRV (SDNN)",
    f"{stats['avg_hrv']} ms" if "avg_hrv" in stats else "—",
    help="Mean heart rate variability. Higher is generally better.",
)
c3.metric(
    "Latest VO₂ Max",
    f"{stats['latest_vo2max']} mL/kg/min" if "latest_vo2max" in stats else "—",
    delta=str(stats.get("vo2max_classification", "")) or None,
)
c4.metric(
    "Latest Resting HR",
    f"{stats['latest_resting_hr']} bpm" if "latest_resting_hr" in stats else "—",
)

st.divider()

tabs = st.tabs(["Heart Rate", "HRV", "VO₂ Max", "Blood Pressure", "Blood Oxygen", "ECG"])

# ── Heart Rate ────────────────────────────────────────────────────────────────
with tabs[0]:
    st.subheader("Heart Rate Analysis")

    daily_hr = hr_daily_stats(df_f)
    rhr = resting_hr_trend(df_f)

    if not daily_hr.empty:
        col_chart, col_stats = st.columns([2, 1])
        with col_chart:
            st.markdown("**Daily HR Range (min / mean / max)**")
            st.altair_chart(
                line_chart(daily_hr, x="day", y=["hr_min", "hr_mean", "hr_max"], y_title="bpm", height=260),
                use_container_width=True,
            )

        with col_stats:
            st.markdown("**Statistics**")
            st.metric("Overall Mean HR", f"{daily_hr['hr_mean'].mean():.1f} bpm")
            st.metric("Lowest recorded", f"{daily_hr['hr_min'].min():.0f} bpm")
            st.metric("Highest recorded", f"{daily_hr['hr_max'].max():.0f} bpm")
            st.metric("Days with data", f"{len(daily_hr):,}")

        st.markdown("**Resting Heart Rate Trend**")
        if not rhr.empty:
            st.altair_chart(
                line_chart(rhr, x="day", y="rhr", y_title="bpm", height=200, rolling_avg_days=7),
                use_container_width=True,
            )
            st.caption("Dashed line = 7-day rolling average. A declining trend indicates improving fitness.")
    else:
        st.info("No heart rate data in this period.")

    # ── HR Zone Distribution ──────────────────────────────────────────────────
    st.markdown("**Heart Rate Zone Distribution**")
    with st.sidebar:
        max_hr = st.slider(
            "Estimated Max HR (bpm)",
            min_value=150,
            max_value=220,
            value=185,
            step=1,
            help="220 minus your age is a common estimate.",
            key="hr_max_slider",
        )

    zones = hr_zone_distribution(df_f, max_hr=max_hr)
    if not zones.empty and zones["minutes"].sum() > 0:
        col_donut, col_table = st.columns([1, 1])
        with col_donut:
            st.altair_chart(
                donut_chart(zones, theta="minutes", color="zone", title="Time in Zone (minutes)"),
                use_container_width=True,
            )
        with col_table:
            display_zones = zones.copy()
            display_zones["minutes"] = display_zones["minutes"].round(1)
            display_zones["pct"] = display_zones["pct"].apply(lambda x: f"{x:.1f}%")
            st.dataframe(display_zones, use_container_width=True, hide_index=True)
    else:
        st.info("Not enough heart rate duration data to compute zone distribution.")

# ── HRV ───────────────────────────────────────────────────────────────────────
with tabs[1]:
    st.subheader("Heart Rate Variability (HRV)")
    st.caption(
        "SDNN measures the variation in time between heartbeats. "
        "Higher values generally indicate better recovery and cardiovascular health."
    )

    hrv = hrv_trend(df_f)
    if hrv.empty:
        st.info("No HRV data found. HRV requires Apple Watch with a supported OS version.")
    else:
        col_chart, col_stats = st.columns([2, 1])
        with col_chart:
            st.altair_chart(
                area_chart(hrv, x="day", y="hrv", y_title="ms (SDNN)", color="#7C3AED", height=260),
                use_container_width=True,
            )

        with col_stats:
            st.metric("Average HRV", f"{hrv['hrv'].mean():.1f} ms")
            st.metric("Latest HRV", f"{hrv['hrv'].iloc[-1]:.1f} ms")
            st.metric("Best HRV", f"{hrv['hrv'].max():.1f} ms")
            st.metric("Days with data", f"{len(hrv):,}")

            # Trend direction
            if len(hrv) >= 14:
                first_half = hrv["hrv"].iloc[: len(hrv) // 2].mean()
                second_half = hrv["hrv"].iloc[len(hrv) // 2 :].mean()
                direction = "↑ Improving" if second_half > first_half else "↓ Declining"
                st.info(f"Trend: **{direction}**")

        with st.expander("What is HRV?"):
            st.markdown(
                """
**Heart Rate Variability (SDNN)** measures the standard deviation of time intervals
between heartbeats. Despite the name "variability," *higher* values are better —
they indicate your autonomic nervous system is adapting well.

| HRV Range | Interpretation |
|-----------|---------------|
| < 20 ms   | Low — may indicate stress, fatigue or overtraining |
| 20–50 ms  | Normal for most adults |
| 50–100 ms | Good — indicates good recovery capacity |
| > 100 ms  | Excellent — typical of well-trained athletes |

*Values vary significantly by age, fitness level, and measurement method.*
"""
            )

# ── VO₂ Max ───────────────────────────────────────────────────────────────────
with tabs[2]:
    st.subheader("VO₂ Max (Cardiorespiratory Fitness)")
    st.caption(
        "VO₂ max is the maximum amount of oxygen your body can use during exercise. "
        "Apple Watch estimates this from outdoor runs and walks."
    )

    vo2 = vo2max_trend(df_f)
    if vo2.empty:
        st.info(
            "No VO₂ max data found. "
            "VO₂ max requires Apple Watch with GPS and is recorded during outdoor runs/walks."
        )
    else:
        col_chart, col_classify = st.columns([2, 1])
        with col_chart:
            st.altair_chart(
                line_chart(vo2, x="day", y="vo2max", y_title="mL/kg/min", height=260),
                use_container_width=True,
            )

        with col_classify:
            latest = float(vo2["vo2max"].iloc[-1])
            classification = classify_vo2max(latest)
            st.metric("Latest VO₂ Max", f"{latest:.1f} mL/kg/min")
            st.metric("Classification", classification)

            if len(vo2) > 1:
                improvement = latest - float(vo2["vo2max"].iloc[0])
                arrow = "↑" if improvement >= 0 else "↓"
                st.metric("Change in period", f"{arrow} {abs(improvement):.1f}")

        with st.expander("VO₂ Max Classifications"):
            st.markdown(
                """
| Classification | VO₂ Max (mL/kg/min) |
|---------------|---------------------|
| Very Poor      | < 28               |
| Poor           | 28–34              |
| Fair           | 34–42              |
| Good           | 42–50              |
| Excellent      | 50–60              |
| Superior       | > 60               |

*These thresholds are approximate and vary by age and sex.*
"""
            )

# ── Blood Pressure ────────────────────────────────────────────────────────────
with tabs[3]:
    st.subheader("Blood Pressure")

    bp = blood_pressure_trend(df_f)
    if bp.empty or (len(bp.columns) < 2):
        st.info(
            "No blood pressure data found. "
            "Connect a blood pressure monitor to Apple Health to see this data."
        )
    else:
        available_bp_cols = [c for c in ["systolic", "diastolic"] if c in bp.columns]
        col_chart, col_stats = st.columns([2, 1])
        with col_chart:
            if len(available_bp_cols) == 2:
                st.altair_chart(
                    line_chart(bp, x="day", y=available_bp_cols, y_title="mmHg", height=260),
                    use_container_width=True,
                )
            else:
                col = available_bp_cols[0]
                st.altair_chart(
                    line_chart(bp, x="day", y=col, y_title="mmHg", height=260),
                    use_container_width=True,
                )

        with col_stats:
            if "systolic" in bp.columns:
                st.metric("Avg Systolic", f"{bp['systolic'].mean():.1f} mmHg")
            if "diastolic" in bp.columns:
                st.metric("Avg Diastolic", f"{bp['diastolic'].mean():.1f} mmHg")
            st.metric("Readings", f"{len(bp):,}")

        with st.expander("Blood Pressure Guide"):
            st.markdown(
                """
| Category         | Systolic      | Diastolic    |
|-----------------|---------------|-------------|
| Normal           | < 120         | < 80        |
| Elevated         | 120–129       | < 80        |
| High Stage 1     | 130–139       | 80–89       |
| High Stage 2     | ≥ 140         | ≥ 90        |
| Crisis           | > 180         | > 120       |
"""
            )

# ── Blood Oxygen ──────────────────────────────────────────────────────────────
with tabs[4]:
    st.subheader("Blood Oxygen (SpO₂)")
    st.caption("Normal SpO₂ is 95–100%. Values below 90% require medical attention.")

    spo2 = spo2_trend(df_f)
    if spo2.empty:
        st.info(
            "No SpO₂ data found. "
            "Blood oxygen monitoring requires Apple Watch Series 6 or later."
        )
    else:
        col_chart, col_stats = st.columns([2, 1])
        with col_chart:
            st.altair_chart(
                area_chart(spo2, x="day", y="spo2", y_title="SpO₂ (%)", color="#0EA5E9", height=260),
                use_container_width=True,
            )
        with col_stats:
            st.metric("Average SpO₂", f"{spo2['spo2'].mean():.1f}%")
            st.metric("Minimum SpO₂", f"{spo2['spo2'].min():.1f}%")
            st.metric("Readings", f"{len(spo2):,}")

            low_readings = (spo2["spo2"] < 95).sum()
            if low_readings > 0:
                st.warning(f"⚠️ {low_readings} readings below 95%")

# ── ECG ───────────────────────────────────────────────────────────────────────
with tabs[5]:
    st.subheader("Electrocardiogram (ECG)")
    st.info("Apple Watch ECG recordings are typically stored as high-frequency samples. This view shows a summary of your recent recordings.")
    
    ecg_records = df_f[df_f["type"] == "HKDataTypeIdentifierElectrocardiogram"]
    if ecg_records.empty:
        st.info("No ECG recordings found in the selected period. Ensure you have recorded ECGs using the ECG app on your Apple Watch.")
    else:
        st.write(f"Found {len(ecg_records)} ECG recordings.")
        st.dataframe(ecg_records[["start_at", "value"]].rename(columns={"value": "Classification"}), hide_index=True)
        
        st.markdown("### Waveform Simulation")
        st.caption("Note: Raw waveform data is often contained in separate XML files in the export. Below is a representative heartbeat visualization.")
        
        import numpy as np
        t = np.linspace(0, 1, 500)
        # Simple simulated ECG-like pulse
        pulse = np.exp(-100 * (t - 0.2)**2) * 0.8 + \
                np.exp(-5000 * (t - 0.4)**2) * 1.5 + \
                np.exp(-500 * (t - 0.45)**2) * -0.5 + \
                np.exp(-100 * (t - 0.7)**2) * 0.6
        ecg_sim = pd.DataFrame({"t": t, "mV": pulse})
        
        sim_chart = alt.Chart(ecg_sim).mark_line(color="#EF4444", strokeWidth=1.5).encode(
            x=alt.X("t:Q", axis=None),
            y=alt.Y("mV:Q", axis=None)
        ).properties(height=150, title="Simulated Single Heartbeat Cycle")
        st.altair_chart(sim_chart, use_container_width=True)
