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
from apple_health_dashboard.services.stats import to_dataframe
from apple_health_dashboard.storage.sqlite_store import init_db, iter_records, open_db
from apple_health_dashboard.web.charts import area_chart, line_chart, scatter_chart
from apple_health_dashboard.web.page_utils import sidebar_date_filter

st.set_page_config(
    page_title="Body · Apple Health Dashboard",
    page_icon="⚖️",
    layout="wide",
)

st.markdown("<style>.block-container{padding-top:1.5rem}</style>", unsafe_allow_html=True)
st.title("⚖️ Body")
st.caption("Weight, BMI, body fat percentage, lean mass and composition trends.")

db_path = default_db_path()

with st.spinner("Loading body metrics…"):
    con = open_db(db_path)
    try:
        init_db(con)
        df = to_dataframe(list(iter_records(con)))
    finally:
        con.close()

if df.empty:
    st.warning("No data found. Please import your Apple Health export on the Home page.")
    st.page_link("app.py", label="Go to Home →", icon="🏠")
    st.stop()

date_filter = sidebar_date_filter(df)
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
            st.altair_chart(
                line_chart(
                    w_trend,
                    x="day",
                    y="weight_kg",
                    y_title="kg",
                    title="Daily Weight",
                    height=280,
                    rolling_avg_days=7,
                ),
                use_container_width=True,
            )
            st.caption("Dashed line = 7-day rolling average.")

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

    # Weekly averages
    if not w_trend.empty and len(w_trend) >= 7:
        st.markdown("**Weekly Average Weight**")
        weekly = w_trend.copy()
        weekly["week"] = pd.to_datetime(weekly["day"]).dt.to_period("W").dt.start_time
        weekly_avg = weekly.groupby("week")["weight_kg"].mean().reset_index()
        from apple_health_dashboard.web.charts import bar_chart
        st.altair_chart(
            bar_chart(weekly_avg, x="week", y="weight_kg", y_title="kg", height=200),
            use_container_width=True,
        )

    # Rate of change
    if not w_trend.empty and len(w_trend) >= 2:
        st.markdown("**Rate of Change**")
        rate_df = w_trend.copy()
        rate_df["day_dt"] = pd.to_datetime(rate_df["day"])
        rate_df = rate_df.sort_values("day_dt")

        # Compare weeks
        if len(rate_df) >= 14:
            n = len(rate_df)
            half = n // 2
            first_half_avg = rate_df["weight_kg"].iloc[:half].mean()
            second_half_avg = rate_df["weight_kg"].iloc[half:].mean()
            weekly_change = (second_half_avg - first_half_avg) / max(half / 7, 1)

            if abs(weekly_change) > 0.01:
                direction = "gaining" if weekly_change > 0 else "losing"
                st.info(
                    f"📊 Trend: You're **{direction}** approximately "
                    f"**{abs(weekly_change):.2f} kg per week** on average."
                )

        # Goal calculator
        st.markdown("**Goal Calculator**")
        target_weight = st.number_input(
            "Target weight (kg)",
            min_value=30.0,
            max_value=300.0,
            value=float(latest_weight) if latest_weight else _DEFAULT_TARGET_WEIGHT_KG,
            step=0.5,
        )
        current_w = latest_weight or float(w_trend["weight_kg"].mean())
        diff = target_weight - current_w

        if abs(diff) > 0.1:
            # Weekly rates
            for weekly_rate in [0.25, 0.5, 0.75]:
                weeks = abs(diff) / weekly_rate
                direction = "lose" if diff < 0 else "gain"
                st.write(
                    f"To **{direction} {abs(diff):.1f} kg** at {weekly_rate} kg/week: "
                    f"approximately **{weeks:.0f} weeks** ({weeks / 4.3:.1f} months)."
                )
        else:
            st.success("You're at your target weight! 🎉")
