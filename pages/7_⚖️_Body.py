from __future__ import annotations

import pandas as pd
import streamlit as st

from apple_health_dashboard.db import default_db_path

# Default target weight shown in the goal calculator when no current weight is available
_DEFAULT_TARGET_WEIGHT_KG = 70.0
from apple_health_dashboard.services.body import (
    bmi_category,
    bmi_trend,
    body_fat_trend,
    body_summary_stats,
    lean_mass_trend,
    weight_trend,
)
from apple_health_dashboard.services.filters import apply_date_filter
from apple_health_dashboard.web.charts import area_chart, line_chart, scatter_chart
from apple_health_dashboard.services.forecasting import forecast_metric, predict_goal_date
from apple_health_dashboard.web.body_map import render_body_map
from apple_health_dashboard.web.page_utils import (
    load_all_records,
    page_header,
    sidebar_date_filter,
    sidebar_nav,
)

st.set_page_config(
    page_title="Body · Apple Health Dashboard",
    page_icon="⚖️",
    layout="wide",
)

page_header("⚖️", "Body", "Weight, BMI, body fat percentage, lean mass and composition trends.")

with st.sidebar:
    sidebar_nav(current="Body")

db_path = default_db_path()

with st.spinner("Loading body metrics…"):
    df = load_all_records(str(db_path))

if df.empty:
    st.warning("No data found. Please import your Apple Health export on the Home page.")
    st.page_link("app.py", label="Go to Home →", icon="🏠")
    st.stop()

date_filter = sidebar_date_filter(df, current="Body")
if date_filter is None:
    st.warning("Could not determine date range.")
    st.stop()

df_f = apply_date_filter(df, date_filter)

# ── Compute trends ────────────────────────────────────────────────────────────
w_trend = weight_trend(df_f)
b_trend = bmi_trend(df_f)
bf_trend = body_fat_trend(df_f)
lm_trend = lean_mass_trend(df_f)
stats = body_summary_stats(df_f)

has_any_body = not (w_trend.empty and b_trend.empty and bf_trend.empty and lm_trend.empty)

if not has_any_body:
    st.info(
        "No body metrics found in the selected period. "
        "Connect a smart scale or log weight in Apple Health to see this data."
    )
    st.stop()

# ── KPIs ──────────────────────────────────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)

latest_weight = stats.get("latest_weight_kg")
weight_change = stats.get("weight_change_kg")
latest_bmi = stats.get("latest_bmi")
bmi_cat = stats.get("bmi_category", "")
latest_bf = stats.get("latest_body_fat_pct")

c1.metric(
    "Latest Weight",
    f"{latest_weight} kg" if latest_weight else "—",
    delta=f"{weight_change:+.1f} kg" if weight_change is not None else None,
    help="Change from first to last measurement in the selected period.",
)
c2.metric("Latest BMI", f"{latest_bmi}" if latest_bmi else "—", delta=str(bmi_cat) if bmi_cat else None)
c3.metric("Body Fat %", f"{latest_bf}%" if latest_bf else "—")

if not w_trend.empty:
    c4.metric("Measurements", f"{len(w_trend):,}")
    c5.metric("Period span",
              f"{(pd.to_datetime(w_trend['day'].max()) - pd.to_datetime(w_trend['day'].min())).days} days")

st.divider()

tabs = st.tabs(["Weight", "BMI", "Body Composition", "Analysis"])

# ── Weight tab ────────────────────────────────────────────────────────────────
with tabs[0]:
    st.subheader("Weight Trend")

    if w_trend.empty:
        st.info("No weight data in the selected period.")
    else:
        col_chart, col_stats = st.columns([3, 1])
        with col_chart:
            import altair as alt
            height_m = st.sidebar.number_input("Your height (cm)", min_value=100, max_value=250, value=175, step=1, key="body_height_cm") / 100.0
            ideal_low = 18.5 * height_m ** 2
            ideal_high = 24.9 * height_m ** 2
            band_df = w_trend.copy()
            band_df["ideal_low"] = ideal_low
            band_df["ideal_high"] = ideal_high
            roll_df = w_trend.copy()
            roll_df["roll7"] = roll_df["weight_kg"].rolling(7, min_periods=1).mean()
            weight_line = alt.Chart(w_trend).mark_line(strokeWidth=2, color="#2E7D6E").encode(
                x=alt.X("day:T", axis=alt.Axis(labelAngle=-30, title="")),
                y=alt.Y("weight_kg:Q", scale=alt.Scale(zero=False), axis=alt.Axis(title="kg")),
                tooltip=[alt.Tooltip("day:T", title="Date"), alt.Tooltip("weight_kg:Q", title="Weight (kg)", format=".1f")],
            )
            ideal_band = alt.Chart(band_df).mark_area(opacity=0.15, color="#10B981").encode(
                x=alt.X("day:T"), y=alt.Y("ideal_high:Q"), y2=alt.Y2("ideal_low:Q"),
            )
            roll_line = alt.Chart(roll_df).mark_line(color="#FF6B6B", strokeWidth=1.5, strokeDash=[4, 3]).encode(
                x=alt.X("day:T"), y=alt.Y("roll7:Q"),
            )
            st.altair_chart(
                (ideal_band + weight_line + roll_line).properties(
                    title=f"Weight with Ideal Range ({ideal_low:.1f}-{ideal_high:.1f} kg for {height_m*100:.0f}cm)", height=280
                ).interactive(),
                use_container_width=True,
            )
            st.caption("Green band = BMI 18.5-24.9 normal range. Red dashed = 7-day rolling avg.")

        with col_stats:
            st.metric("Current", f"{w_trend['weight_kg'].iloc[-1]:.1f} kg")
            st.metric("Starting", f"{w_trend['weight_kg'].iloc[0]:.1f} kg")
            change = w_trend['weight_kg'].iloc[-1] - w_trend['weight_kg'].iloc[0]
            arrow = "↑" if change > 0 else "↓"
            st.metric("Change", f"{arrow} {abs(change):.1f} kg")
            st.metric("Min", f"{w_trend['weight_kg'].min():.1f} kg")
            st.metric("Max", f"{w_trend['weight_kg'].max():.1f} kg")
            st.metric("Avg", f"{w_trend['weight_kg'].mean():.1f} kg")

        # Monthly average
        if len(w_trend) >= 30:
            st.markdown("**Monthly Average Weight**")
            monthly = w_trend.copy()
            monthly["month"] = pd.to_datetime(monthly["day"]).dt.to_period("M").dt.start_time
            monthly_avg = monthly.groupby("month")["weight_kg"].mean().reset_index()
            from apple_health_dashboard.web.charts import bar_chart
            st.altair_chart(
                bar_chart(monthly_avg, x="month", y="weight_kg", y_title="kg", height=200),
                use_container_width=True,
            )

        # Weight Forecast
        st.divider()
        st.subheader("🔮 30-Day Forecast")
        with st.spinner("Calculating forecast..."):
            forecast_df = forecast_metric(w_trend, "day", "weight_kg")
            if not forecast_df.empty:
                f_chart = alt.Chart(forecast_df).mark_line(strokeWidth=2).encode(
                    x=alt.X("day:T", title=""),
                    y=alt.Y("value:Q", scale=alt.Scale(zero=False), title="kg"),
                    color=alt.Color("is_forecast:N", scale=alt.Scale(range=["#2E7D6E", "#F59E0B"]), legend=None),
                    strokeDash=alt.condition(alt.datum.is_forecast, alt.value([5, 5]), alt.value([0])),
                    tooltip=["day:T", "value:Q"]
                ).properties(height=250)
                st.altair_chart(f_chart.interactive(), use_container_width=True)
                st.caption("Orange dashed line = AI-generated forecast (Holt-Winters)")

# ── BMI tab ───────────────────────────────────────────────────────────────────
with tabs[1]:
    st.subheader("Body Mass Index (BMI)")

    if b_trend.empty:
        # Try to compute from weight if we have height
        from apple_health_dashboard.services.body import HEIGHT_TYPE, WEIGHT_TYPE
        height_df = df_f[df_f["type"] == HEIGHT_TYPE].copy()
        if not height_df.empty and not w_trend.empty:
            latest_height_m = height_df["value"].dropna().iloc[-1]
            # Normalize height if in cm
            if latest_height_m > 3:
                latest_height_m = latest_height_m / 100.0
            bmi_computed = w_trend.copy()
            bmi_computed["bmi"] = bmi_computed["weight_kg"] / (latest_height_m ** 2)
            b_trend = bmi_computed[["day", "bmi"]]

    if b_trend.empty:
        st.info(
            "No BMI data found. BMI can be calculated automatically if both weight and height "
            "are available in your Apple Health data."
        )
    else:
        col_chart, col_info = st.columns([3, 1])

        with col_chart:
            import altair as alt
            bmi_chart_df = b_trend.copy()
            bmi_line = (
                alt.Chart(bmi_chart_df)
                .mark_line(color="#7C3AED", strokeWidth=2)
                .encode(
                    x=alt.X("day:T", axis=alt.Axis(labelAngle=-30, title="")),
                    y=alt.Y("bmi:Q", scale=alt.Scale(zero=False), axis=alt.Axis(title="BMI")),
                    tooltip=[alt.Tooltip("day:T"), alt.Tooltip("bmi:Q", format=".1f")],
                )
            )
            # Reference bands
            ref_lines = [
                (18.5, "Underweight", "#60A5FA"),
                (25.0, "Overweight", "#F59E0B"),
                (30.0, "Obese", "#EF4444"),
            ]
            layers = [bmi_line]
            for threshold, label, color in ref_lines:
                layers.append(
                    alt.Chart(pd.DataFrame({"y": [threshold], "label": [label]}))
                    .mark_rule(strokeDash=[4, 3], strokeWidth=1, color=color)
                    .encode(y=alt.Y("y:Q"))
                )
            st.altair_chart(
                alt.layer(*layers).properties(title="BMI Trend", height=280).interactive(),
                use_container_width=True,
            )
            st.caption("Blue = 18.5 (underweight threshold) · Yellow = 25 · Red = 30")

        with col_info:
            latest = float(b_trend["bmi"].iloc[-1])
            cat = bmi_category(latest)
            st.metric("Current BMI", f"{latest:.1f}")
            st.metric("Category", cat)

            bmi_colors = {
                "Underweight": "🔵",
                "Normal weight": "🟢",
                "Overweight": "🟡",
                "Obese": "🔴",
            }
            st.markdown(f"### {bmi_colors.get(cat, '⚪')} {cat}")

            with st.expander("BMI Classification"):
                st.markdown(
                    """
| BMI        | Category      |
|-----------|---------------|
| < 18.5    | Underweight   |
| 18.5–24.9 | Normal weight |
| 25–29.9   | Overweight    |
| ≥ 30      | Obese         |
"""
                )

# ── Body Composition tab ───────────────────────────────────────────────────────
with tabs[2]:
    st.subheader("Body Composition")

    has_bf = not bf_trend.empty
    has_lm = not lm_trend.empty

    if not has_bf and not has_lm:
        st.info(
            "No body composition data found. "
            "Connect a smart scale that measures body fat percentage (e.g. Withings, Garmin) "
            "and sync it to Apple Health."
        )
    else:
        col_bf, col_lm = st.columns(2)

        with col_bf:
            st.markdown("**Body Fat %**")
            if has_bf:
                st.altair_chart(
                    area_chart(
                        bf_trend,
                        x="day",
                        y="body_fat_pct",
                        y_title="%",
                        color="#F59E0B",
                        height=220,
                    ),
                    use_container_width=True,
                )
                st.metric("Latest", f"{bf_trend['body_fat_pct'].iloc[-1]:.1f}%")
                change_bf = float(bf_trend['body_fat_pct'].iloc[-1]) - float(bf_trend['body_fat_pct'].iloc[0])
                st.metric("Change", f"{change_bf:+.1f}%")
            else:
                st.info("No body fat data.")

        with col_lm:
            st.markdown("**Lean Body Mass (kg)**")
            if has_lm:
                st.altair_chart(
                    area_chart(
                        lm_trend,
                        x="day",
                        y="lean_mass_kg",
                        y_title="kg",
                        color="#10B981",
                        height=220,
                    ),
                    use_container_width=True,
                )
                st.metric("Latest", f"{lm_trend['lean_mass_kg'].iloc[-1]:.1f} kg")
            else:
                st.info("No lean mass data.")

        # Combined weight vs body fat scatter
        if has_bf and not w_trend.empty:
            st.markdown("**Weight vs Body Fat %**")
            merged = pd.merge(
                w_trend,
                bf_trend,
                on="day",
                how="inner",
            )
            if not merged.empty:
                st.altair_chart(
                    scatter_chart(
                        merged,
                        x="weight_kg",
                        y="body_fat_pct",
                        x_title="Weight (kg)",
                        y_title="Body Fat (%)",
                        title="Weight vs Body Fat Correlation",
                        height=280,
                    ),
                    use_container_width=True,
                )

# ── Analysis tab ───────────────────────────────────────────────────────────────
with tabs[3]:
    st.subheader("Body Metrics Analysis")

    # Interactive Body Map for muscle/pain tracking
    st.markdown("#### 🧍 Interactive Body Map")
    st.caption("Track muscle soreness or log symptom locations.")
    render_body_map()

    # Goal Prediction
    st.divider()
    st.subheader("🏁 Goal Prediction")
    target_w = st.number_input(
        "Target weight (kg)",
        min_value=30.0,
        max_value=200.0,
        value=float(w_trend["weight_kg"].iloc[-1]),
        key="goal_target_input"
    )
    predicted_date = predict_goal_date(w_trend, "day", "weight_kg", target_w)
    if predicted_date:
        st.success(f"At your current trend, you will reach **{target_w} kg** around **{predicted_date.date().strftime('%B %d, %Y')}**.")
    else:
        st.info("Current trend is not moving towards your target, or not enough data to predict.")
