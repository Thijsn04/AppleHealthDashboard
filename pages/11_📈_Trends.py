from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from apple_health_dashboard.db import default_db_path
from apple_health_dashboard.services.filters import DateFilter
from apple_health_dashboard.services.forecasting import forecast_metric
from apple_health_dashboard.web.page_utils import (
    load_all_records,
    load_all_workouts,
    page_header,
    sidebar_nav,
)

st.set_page_config(page_title="Trends · Apple Health Dashboard", page_icon="📈", layout="wide")
page_header("📈", "Trends", "Year-over-year comparisons and month-over-month change summaries.")

db_path = default_db_path()

with st.sidebar:
    sidebar_nav(current="Trends")
    st.divider()
    st.markdown("### 📅 Options")
    compare_years = st.checkbox("Year-over-year overlay", value=True)
    rolling_days = st.selectbox("Rolling average", [7, 14, 30], index=0)

with st.spinner("Loading data…"):
    df = load_all_records(str(db_path))
    wdf = load_all_workouts(str(db_path))

if df.empty:
    st.warning("No data found. Please import your Apple Health export.")
    st.page_link("app.py", label="Go to Home →", icon="🏠")
    st.stop()

# ── Helpers ───────────────────────────────────────────────────────────────────
def _daily_metric(df: pd.DataFrame, type_str: str, agg: str = "mean") -> pd.DataFrame:
    sub = df[df["type"] == type_str].copy()
    if sub.empty or "value" not in sub.columns:
        return pd.DataFrame()
    sub["value"] = pd.to_numeric(sub["value"], errors="coerce")
    sub = sub.dropna(subset=["value"])
    sub["day"] = sub["start_at"].dt.floor("D")
    if agg == "sum":
        out = sub.groupby("day")["value"].sum().reset_index()
    else:
        out = sub.groupby("day")["value"].mean().reset_index()
    return out


def _monthly(daily: pd.DataFrame, col: str = "value") -> pd.DataFrame:
    if daily.empty:
        return pd.DataFrame()
    d = daily.copy()
    d["month"] = pd.to_datetime(d["day"]).dt.to_period("M").dt.start_time
    return d.groupby("month")[col].mean().reset_index()


def _yoy_chart(daily: pd.DataFrame, title: str, y_title: str, color: str = "#2E7D6E") -> alt.Chart | None:
    if daily.empty:
        return None
    d = daily.copy()
    d["day"] = pd.to_datetime(d["day"])
    d["year"] = d["day"].dt.year.astype(str)
    d["day_of_year"] = d["day"].dt.dayofyear
    d["roll"] = d.groupby("year")["value"].transform(
        lambda s: s.rolling(rolling_days, min_periods=1).mean()
    )
    chart = (
        alt.Chart(d)
        .mark_line(strokeWidth=2, opacity=0.85)
        .encode(
            x=alt.X("day_of_year:Q", axis=alt.Axis(title="Day of year")),
            y=alt.Y("roll:Q", axis=alt.Axis(title=y_title)),
            color=alt.Color("year:N", scale=alt.Scale(scheme="tableau10")),
            tooltip=[
                alt.Tooltip("day:T", title="Date"),
                alt.Tooltip("year:N", title="Year"),
                alt.Tooltip("roll:Q", title=y_title, format=".1f"),
            ],
        )
        .properties(title=title, height=240)
        .interactive()
    )
    return chart


def _mom_chart(monthly: pd.DataFrame, title: str, y_title: str, color: str = "#2E7D6E") -> alt.Chart | None:
    if monthly.empty or len(monthly) < 2:
        return None
    m = monthly.copy()
    m["pct_change"] = m["value"].pct_change() * 100
    m = m.dropna(subset=["pct_change"])
    chart = (
        alt.Chart(m)
        .mark_bar()
        .encode(
            x=alt.X("month:T", axis=alt.Axis(labelAngle=-30, title="")),
            y=alt.Y("pct_change:Q", axis=alt.Axis(title="MoM change (%)")),
            color=alt.condition(
                alt.datum.pct_change >= 0,
                alt.value("#10B981"),
                alt.value("#EF4444"),
            ),
            tooltip=[
                alt.Tooltip("month:T", title="Month"),
                alt.Tooltip("pct_change:Q", title="MoM change %", format=".1f"),
                alt.Tooltip("value:Q", title=y_title, format=".1f"),
            ],
        )
        .properties(title=title, height=200)
        .interactive()
    )
    return chart


# ── Tabs ──────────────────────────────────────────────────────────────────────
tabs = st.tabs(["Steps", "Heart Rate", "Cardio Fitness", "Sleep", "Weight", "Workouts", "Monthly Summary"])

# ── Steps ─────────────────────────────────────────────────────────────────────
with tabs[0]:
    st.subheader("Step Count Trends")
    steps = _daily_metric(df, "HKQuantityTypeIdentifierStepCount", "sum")
    if steps.empty:
        st.info("No step data found.")
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("Avg daily steps", f"{steps['value'].mean():,.0f}")
        c2.metric("Best day", f"{steps['value'].max():,.0f}")
        c3.metric("Days with data", f"{len(steps):,}")

        if compare_years:
            chart = _yoy_chart(steps, "Daily Steps — Year-over-Year", "Steps/day")
            if chart:
                st.altair_chart(chart, width="stretch")
                st.caption(f"{rolling_days}-day rolling average per year.")

        st.markdown("**Month-over-Month Change**")
        monthly_steps = _monthly(steps)
        mom = _mom_chart(monthly_steps, "Steps MoM Change", "Steps/day")
        if mom:
            st.altair_chart(mom, width="stretch")

        st.markdown("**Monthly Averages**")
        if not monthly_steps.empty:
            monthly_steps_display = monthly_steps.copy()
            monthly_steps_display.columns = ["Month", "Avg Steps"]
            monthly_steps_display["Avg Steps"] = monthly_steps_display["Avg Steps"].round(0).astype(int)
            st.dataframe(monthly_steps_display, width="stretch", hide_index=True)

# ── Heart Rate ─────────────────────────────────────────────────────────────────
with tabs[1]:
    st.subheader("Resting Heart Rate Trends")
    rhr = _daily_metric(df, "HKQuantityTypeIdentifierRestingHeartRate", "mean")
    if rhr.empty:
        st.info("No resting heart rate data found.")
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("Avg RHR", f"{rhr['value'].mean():.0f} bpm")
        c2.metric("Best (lowest)", f"{rhr['value'].min():.0f} bpm")
        c3.metric("Trend", "↓ Improving" if rhr["value"].iloc[-1] < rhr["value"].iloc[0] else "↑ Rising")

        if compare_years:
            chart = _yoy_chart(rhr, "Resting Heart Rate — Year-over-Year", "bpm", "#EF4444")
            if chart:
                st.altair_chart(chart, width="stretch")

        st.markdown("**Month-over-Month Change**")
        monthly_rhr = _monthly(rhr)
        mom = _mom_chart(monthly_rhr, "RHR MoM Change", "bpm")
        if mom:
            st.altair_chart(mom, width="stretch")

    st.divider()
    st.subheader("HRV Trends")
    hrv = _daily_metric(df, "HKQuantityTypeIdentifierHeartRateVariabilitySDNN", "mean")
    if hrv.empty:
        st.info("No HRV data found.")
    else:
        if compare_years:
            chart = _yoy_chart(hrv, "HRV — Year-over-Year", "ms (SDNN)", "#7C3AED")
            if chart:
                st.altair_chart(chart, width="stretch")
        monthly_hrv = _monthly(hrv)
        mom = _mom_chart(monthly_hrv, "HRV MoM Change", "ms")
        if mom:
            st.altair_chart(mom, width="stretch")

# ── Cardio Fitness ─────────────────────────────────────────────────────────────
with tabs[2]:
    st.subheader("Cardiovascular Fitness (VO₂ Max)")
    vo2 = _daily_metric(df, "HKQuantityTypeIdentifierVO2Max", "last")
    if vo2.empty:
        st.info("No VO₂ Max data found.")
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("Current VO₂ Max", f"{vo2['value'].iloc[-1]:.1f}")
        c2.metric("Period Average", f"{vo2['value'].mean():.1f}")
        c3.metric("Trend", "↑ Improving" if vo2["value"].iloc[-1] > vo2["value"].iloc[0] else "↓ Declining")

        if compare_years:
            chart = _yoy_chart(vo2, "VO₂ Max — Year-over-Year", "mL/kg/min", "#06B6D4")
            if chart:
                st.altair_chart(chart, width="stretch")

        st.divider()
        st.subheader("🔮 60-Day VO₂ Max Forecast")
        with st.spinner("Calculating forecast..."):
            v_forecast = forecast_metric(vo2, "day", "value", days_to_forecast=60)
            if not v_forecast.empty:
                v_chart = alt.Chart(v_forecast).mark_line(strokeWidth=2).encode(
                    x=alt.X("day:T", title=""),
                    y=alt.Y("value:Q", scale=alt.Scale(zero=False), title="VO₂ Max"),
                    color=alt.Color("is_forecast:N", scale=alt.Scale(range=["#06B6D4", "#F59E0B"]), legend=None),
                    strokeDash=alt.condition(alt.datum.is_forecast, alt.value([5, 5]), alt.value([0])),
                    tooltip=["day:T", "value:Q"]
                ).properties(height=280)
                st.altair_chart(v_chart.interactive(), use_container_width=True)
                st.caption("Orange dashed line = Predictive trend (Holt-Winters)")

# ── Sleep ──────────────────────────────────────────────────────────────────────
with tabs[3]:
    st.subheader("Sleep Duration Trends")
    from apple_health_dashboard.services.sleep import sleep_duration_by_day, sleep_records
    srec_all = sleep_records(df)
    if srec_all.empty:
        st.info("No sleep data found.")
    else:
        dur_all = sleep_duration_by_day(srec_all, stages="actual")
        if dur_all.empty:
            dur_all = sleep_duration_by_day(srec_all, stages="all")

        if not dur_all.empty:
            dur_all = dur_all.rename(columns={"hours": "value"})
            c1, c2, c3 = st.columns(3)
            c1.metric("Avg sleep", f"{dur_all['value'].mean():.1f} h")
            c2.metric("Best night", f"{dur_all['value'].max():.1f} h")
            nights_7h = (dur_all["value"] >= 7).mean() * 100
            c3.metric("Nights ≥7h", f"{nights_7h:.0f}%")

            if compare_years:
                chart = _yoy_chart(dur_all, "Sleep Duration — Year-over-Year", "Hours", "#3B82F6")
                if chart:
                    st.altair_chart(chart, width="stretch")

            st.markdown("**Month-over-Month Change**")
            monthly_sleep = _monthly(dur_all)
            mom = _mom_chart(monthly_sleep, "Sleep Duration MoM Change", "h")
            if mom:
                st.altair_chart(mom, width="stretch")

# ── Weight ─────────────────────────────────────────────────────────────────────
with tabs[4]:
    st.subheader("Weight Trends")
    weight = _daily_metric(df, "HKQuantityTypeIdentifierBodyMass", "mean")
    if weight.empty:
        st.info("No weight data found.")
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("Current weight", f"{weight['value'].iloc[-1]:.1f} kg")
        total_change = weight['value'].iloc[-1] - weight['value'].iloc[0]
        c2.metric("Change over period", f"{total_change:+.1f} kg")
        c3.metric("Days with data", f"{len(weight):,}")

        if compare_years:
            chart = _yoy_chart(weight, "Weight — Year-over-Year", "kg", "#F97316")
            if chart:
                st.altair_chart(chart, width="stretch")

        st.markdown("**Month-over-Month Change**")
        monthly_weight = _monthly(weight)
        mom = _mom_chart(monthly_weight, "Weight MoM Change", "kg")
        if mom:
            st.altair_chart(mom, width="stretch")

# ── Workouts ───────────────────────────────────────────────────────────────────
with tabs[5]:
    st.subheader("Workout Frequency Trends")
    if wdf.empty:
        st.info("No workout data found.")
    else:
        label_col = "activity_label" if "activity_label" in wdf.columns else "workout_activity_type"
        wdf2 = wdf.copy()
        wdf2["day"] = wdf2["start_at"].dt.floor("D")
        wdf2["month"] = wdf2["start_at"].dt.to_period("M").dt.start_time
        wdf2["year"] = wdf2["start_at"].dt.year.astype(str)
        wdf2["week"] = wdf2["start_at"].dt.to_period("W").dt.start_time

        # Year-over-year weekly workout count
        if compare_years:
            weekly_counts = wdf2.groupby(["week", "year"]).size().reset_index(name="count")
            weekly_counts["day_of_year"] = pd.to_datetime(weekly_counts["week"]).dt.dayofyear
            yoy_chart = (
                alt.Chart(weekly_counts)
                .mark_line(strokeWidth=2)
                .encode(
                    x=alt.X("day_of_year:Q", axis=alt.Axis(title="Week of year")),
                    y=alt.Y("count:Q", axis=alt.Axis(title="Workouts/week")),
                    color=alt.Color("year:N", scale=alt.Scale(scheme="tableau10")),
                    tooltip=[alt.Tooltip("week:T"), alt.Tooltip("count:Q"), alt.Tooltip("year:N")],
                )
                .properties(title="Weekly Workout Count — Year-over-Year", height=240)
                .interactive()
            )
            st.altair_chart(yoy_chart, width="stretch")

        # Monthly breakdown by type
        st.markdown("**Monthly Workouts by Type**")
        monthly_type = wdf2.groupby(["month", label_col]).size().reset_index(name="count")
        stacked = (
            alt.Chart(monthly_type)
            .mark_bar()
            .encode(
                x=alt.X("month:T", axis=alt.Axis(labelAngle=-30, title="")),
                y=alt.Y("count:Q", stack="zero", axis=alt.Axis(title="Workouts")),
                color=alt.Color(f"{label_col}:N", scale=alt.Scale(scheme="tableau20")),
                tooltip=[alt.Tooltip("month:T"), alt.Tooltip(f"{label_col}:N"), alt.Tooltip("count:Q")],
            )
            .properties(title="Monthly Workouts by Type", height=260)
            .interactive()
        )
        st.altair_chart(stacked, width="stretch")

# ── Monthly Summary ────────────────────────────────────────────────────────────
with tabs[6]:
    st.subheader("Monthly Summary Table")
    st.caption("Key metrics averaged/summed per calendar month.")

    rows = []
    months = sorted(df["start_at"].dt.to_period("M").unique(), reverse=True)
    for period in months[:24]:  # last 24 months
        start = pd.Timestamp(period.start_time, tz="UTC")
        end = pd.Timestamp(period.end_time, tz="UTC")
        month_df = df[(df["start_at"] >= start) & (df["start_at"] <= end)]

        def _avg(t, col="value"):
            sub = month_df[month_df["type"] == t]
            if sub.empty or col not in sub.columns:
                return None
            v = pd.to_numeric(sub[col], errors="coerce").dropna()
            return round(float(v.mean()), 1) if not v.empty else None

        def _sum(t, col="value"):
            sub = month_df[month_df["type"] == t]
            if sub.empty or col not in sub.columns:
                return None
            v = pd.to_numeric(sub[col], errors="coerce").dropna()
            return round(float(v.sum()), 0) if not v.empty else None

        step_sum = _sum("HKQuantityTypeIdentifierStepCount")
        rhr_avg = _avg("HKQuantityTypeIdentifierRestingHeartRate")
        hrv_avg = _avg("HKQuantityTypeIdentifierHeartRateVariabilitySDNN")
        wt_avg = _avg("HKQuantityTypeIdentifierBodyMass")

        month_wdf = wdf[(wdf["start_at"] >= start) & (wdf["start_at"] <= end)] if not wdf.empty else pd.DataFrame()
        wo_count = len(month_wdf)
        wo_h = round(float(month_wdf["duration_s"].sum() / 3600), 1) if not month_wdf.empty else None

        rows.append({
            "Month": str(period),
            "Steps (total)": f"{step_sum:,.0f}" if step_sum else "—",
            "RHR (avg bpm)": f"{rhr_avg:.0f}" if rhr_avg else "—",
            "HRV (avg ms)": f"{hrv_avg:.0f}" if hrv_avg else "—",
            "Weight (avg kg)": f"{wt_avg:.1f}" if wt_avg else "—",
            "Workouts": wo_count or "—",
            "Workout hours": f"{wo_h:.1f}" if wo_h else "—",
        })

    if rows:
        summary_df = pd.DataFrame(rows)
        st.dataframe(summary_df, width="stretch", hide_index=True)
        csv_bytes = summary_df.to_csv(index=False)
        st.download_button("⬇️ Download Monthly Summary CSV", data=csv_bytes,
                           file_name="monthly_summary.csv", mime="text/csv")
    else:
        st.info("No monthly data available.")
