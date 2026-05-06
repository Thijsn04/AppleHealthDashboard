from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from apple_health_dashboard.db import default_db_path
from apple_health_dashboard.services.filters import apply_date_filter
from apple_health_dashboard.services.heart import hr_zone_distribution
from apple_health_dashboard.services.heart import hrv_trend as _hrv_trend
from apple_health_dashboard.services.insights import (
    active_energy_pairs,
    best_workout_type_for_hrv,
    blood_pressure_daily,
    circadian_profile,
    correlation_matrix,
    cross_metric_daily_table,
    daily_readiness_score,
    generate_insights,
    sleep_debt_daily,
    sleep_hrv_pairs,
    sleep_stages_daily,
    spo2_daily,
    steps_rolling,
    steps_sleep_pairs,
    walking_hr_daily,
    weight_bmi_daily,
    workout_duration_hrv_pairs,
    workout_duration_trend,
    workout_recovery_pairs,
)
from apple_health_dashboard.web.charts import scatter_chart
from apple_health_dashboard.web.page_utils import (
    load_all_records,
    load_all_workouts,
    page_header,
    sidebar_date_filter,
)

st.set_page_config(
    page_title="Insights · Apple Health Dashboard",
    page_icon="💡",
    layout="wide",
)

page_header(
    "💡",
    "Insights",
    "Cross-metric analysis — connecting sleep, heart, activity and workouts "
    "to surface patterns Apple Health doesn't show you.",
)

db_path = default_db_path()

with st.spinner("Loading data…"):
    df = load_all_records(str(db_path))
    wdf = load_all_workouts(str(db_path))

if df.empty:
    st.warning("No data imported yet. Please go to the **Home** page and import your Apple Health export.")
    st.page_link("app.py", label="Go to Home →", icon="🏠")
    st.stop()

date_filter = sidebar_date_filter(df, current="Insights")
if date_filter is None:
    st.warning("Could not determine date range from the data.")
    st.stop()

df_f = apply_date_filter(df, date_filter)
if not wdf.empty and "start_at" in wdf.columns:
    wdf_f = wdf[(wdf["start_at"] >= date_filter.start) & (wdf["start_at"] <= date_filter.end)].copy()
else:
    wdf_f = pd.DataFrame()

# ── Auto-generated insight cards ──────────────────────────────────────────────
st.markdown("## 🔍 Personalised Insights")
st.caption("Auto-detected patterns in your health data.")

insights = generate_insights(df_f, wdf_f)

_KIND_CSS = {
    "positive": "insight-positive",
    "negative": "insight-negative",
    "neutral": "insight-neutral",
    "info": "insight-info",
}

cols = st.columns(min(len(insights), 3))
for i, insight in enumerate(insights):
    css_class = _KIND_CSS.get(insight.get("kind", "info"), "insight-info")
    with cols[i % 3]:
        st.markdown(
            f"""
<div class="insight-card {css_class}">
  <div class="insight-title">{insight['icon']} {insight['title']}</div>
  <div class="insight-body">{insight['body']}</div>
</div>
""",
            unsafe_allow_html=True,
        )

st.divider()

# ── Daily Readiness Score ─────────────────────────────────────────────────────
st.markdown("## 🏅 Daily Readiness Score")
st.caption(
    "A composite 0–100 score combining your HRV (40%), resting heart rate (35%) "
    "and previous night's sleep (25%), each benchmarked against your personal 30-day baseline. "
    "Apple Health doesn't provide anything like this."
)

with st.sidebar:
    sleep_goal = st.slider(
        "Sleep goal (hours)", min_value=6.0, max_value=10.0, value=8.0, step=0.5,
        help="Your target sleep duration. Used to compute the sleep component of the readiness score.",
        key="sleep_goal_slider",
    )

readiness = daily_readiness_score(df_f, sleep_goal_h=sleep_goal)

if readiness.empty:
    st.info(
        "Not enough data to compute a readiness score. "
        "You need at least 7 days of HRV or resting HR + sleep data."
    )
else:
    col_chart, col_stats = st.columns([3, 1])
    with col_chart:
        import altair as alt

        # Colour-encode the score: red < 40, yellow 40-60, green > 60
        readiness_chart = readiness.copy()
        readiness_chart["day"] = pd.to_datetime(readiness_chart["day"])

        line = (
            alt.Chart(readiness_chart)
            .mark_line(strokeWidth=2, color="#7C3AED")
            .encode(
                x=alt.X("day:T", axis=alt.Axis(labelAngle=-30, title="")),
                y=alt.Y("score:Q", scale=alt.Scale(domain=[0, 100]), axis=alt.Axis(title="Readiness")),
                tooltip=[
                    alt.Tooltip("day:T", title="Date"),
                    alt.Tooltip("score:Q", title="Score", format=".1f"),
                    alt.Tooltip("hrv:Q", title="HRV (ms)", format=".1f"),
                    alt.Tooltip("rhr:Q", title="Resting HR (bpm)", format=".1f"),
                    alt.Tooltip("sleep_h:Q", title="Sleep (h)", format=".1f"),
                ],
            )
        )
        points = (
            alt.Chart(readiness_chart)
            .mark_circle(size=40)
            .encode(
                x=alt.X("day:T"),
                y=alt.Y("score:Q"),
                color=alt.condition(
                    alt.datum.score >= 60,
                    alt.value("#10B981"),
                    alt.condition(
                        alt.datum.score >= 40,
                        alt.value("#F59E0B"),
                        alt.value("#EF4444"),
                    ),
                ),
                tooltip=[
                    alt.Tooltip("day:T", title="Date"),
                    alt.Tooltip("score:Q", title="Score", format=".1f"),
                ],
            )
        )
        # Reference lines
        ref_60 = (
            alt.Chart(pd.DataFrame({"y": [60]}))
            .mark_rule(strokeDash=[4, 4], color="#10B981", strokeWidth=1)
            .encode(y=alt.Y("y:Q"))
        )
        ref_40 = (
            alt.Chart(pd.DataFrame({"y": [40]}))
            .mark_rule(strokeDash=[4, 4], color="#EF4444", strokeWidth=1)
            .encode(y=alt.Y("y:Q"))
        )
        chart = (
            (line + points + ref_60 + ref_40)
            .properties(title="Daily Readiness Score (green ≥ 60 · yellow 40-60 · red < 40)", height=280)
            .interactive()
        )
        st.altair_chart(chart, use_container_width=True)
        st.caption("Green line = 60 threshold · Red line = 40 threshold")

    with col_stats:
        latest_score = float(readiness["score"].iloc[-1])
        avg_score = float(readiness["score"].mean())
        great_days = int((readiness["score"] >= 60).sum())
        total_days = len(readiness)

        color = "green" if latest_score >= 60 else ("orange" if latest_score >= 40 else "red")
        st.markdown("**Today's readiness**")
        st.markdown(f"<h1 style='color:{color};margin:0'>{latest_score:.0f}</h1>", unsafe_allow_html=True)
        st.metric("Period average", f"{avg_score:.1f}")
        st.metric("Great days (≥60)", f"{great_days}/{total_days}")

        if "hrv_score" in readiness.columns and readiness["hrv_score"].notna().any():
            st.metric("HRV component", f"{readiness['hrv_score'].iloc[-1]:.0f}")
        if "rhr_score" in readiness.columns and readiness["rhr_score"].notna().any():
            st.metric("RHR component", f"{readiness['rhr_score'].iloc[-1]:.0f}")
        if "sleep_score" in readiness.columns and readiness["sleep_score"].notna().any():
            st.metric("Sleep component", f"{readiness['sleep_score'].iloc[-1]:.0f}")

st.divider()

# ── Sleep → next-day HRV ─────────────────────────────────────────────────────
st.markdown("## 😴 → ❤️ Sleep & Next-Morning HRV")
st.caption(
    "Does sleeping longer actually improve your HRV? "
    "Each dot is one day: x-axis = hours slept, y-axis = HRV measured the following morning."
)

pairs = sleep_hrv_pairs(df_f)
if pairs.empty or len(pairs) < 7:
    st.info("Need at least 7 days of both sleep and HRV data to show this analysis.")
else:
    corr = pairs["sleep_h"].corr(pairs["hrv"])
    col_scatter, col_info = st.columns([2, 1])
    with col_scatter:
        st.altair_chart(
            scatter_chart(
                pairs,
                x="sleep_h",
                y="hrv",
                x_title="Sleep duration (hours)",
                y_title="Next-morning HRV (ms)",
                title="Sleep Duration → Next-day HRV",
                height=300,
            ),
            use_container_width=True,
        )
    with col_info:
        st.metric("Pearson correlation", f"{corr:+.2f}")
        if corr > 0.3:
            st.success(
                f"✅ Positive link (r={corr:.2f}): longer sleep is associated "
                "with better recovery the next morning."
            )
        elif corr < -0.3:
            st.warning(
                f"⚠️ Negative link (r={corr:.2f}): something unusual — "
                "longer sleep may be compensating for stress or illness."
            )
        else:
            st.info(
                f"No strong link detected (r={corr:.2f}). "
                "Sleep duration alone may not be the main driver of your HRV."
            )
        st.metric("Nights analysed", f"{len(pairs):,}")

st.divider()

# ── Steps → sleep ─────────────────────────────────────────────────────────────
st.markdown("## 🏃 → 😴 Daily Activity & Sleep Duration")
st.caption(
    "Do more steps lead to longer sleep? "
    "Each dot represents one day: steps taken vs hours slept that night."
)

step_sleep = steps_sleep_pairs(df_f)
if step_sleep.empty or len(step_sleep) < 7:
    st.info("Need at least 7 days of both step and sleep data to show this analysis.")
else:
    corr_ss = step_sleep["steps"].corr(step_sleep["sleep_h"])
    col_s, col_si = st.columns([2, 1])
    with col_s:
        st.altair_chart(
            scatter_chart(
                step_sleep,
                x="steps",
                y="sleep_h",
                x_title="Daily Steps",
                y_title="Sleep that night (hours)",
                title="Daily Steps → Sleep Duration",
                height=300,
            ),
            use_container_width=True,
        )
    with col_si:
        st.metric("Pearson correlation", f"{corr_ss:+.2f}")
        if corr_ss > 0.2:
            st.success("More active days are associated with longer sleep. 🏃")
        elif corr_ss < -0.2:
            st.warning("More active days seem to come with shorter sleep — check if busy days cut into your sleep time.")
        else:
            st.info("No strong link between steps and sleep duration.")
        st.metric("Days analysed", f"{len(step_sleep):,}")

st.divider()

# ── Workout → next-day RHR ────────────────────────────────────────────────────
st.markdown("## 🏋️ → ❤️ Workout Days vs Rest-Day Heart Rate")
st.caption(
    "Compare your resting heart rate on the day after a workout vs days after rest. "
    "This reveals how well your cardiovascular system recovers from training."
)

recovery_df = workout_recovery_pairs(df_f, wdf_f)
if recovery_df.empty:
    st.info("Need both workout and resting heart rate data to show this analysis.")
elif not recovery_df["is_post_workout"].any() or not (~recovery_df["is_post_workout"]).any():
    st.info("Need a mix of post-workout and rest days to compare.")
else:
    post_rhr = recovery_df[recovery_df["is_post_workout"]]["rhr"]
    rest_rhr = recovery_df[~recovery_df["is_post_workout"]]["rhr"]

    col_a, col_b, col_c = st.columns([1, 1, 2])
    with col_a:
        st.metric("Post-workout avg RHR", f"{post_rhr.mean():.1f} bpm")
        st.metric("Post-workout days", f"{len(post_rhr):,}")
    with col_b:
        st.metric("Rest-day avg RHR", f"{rest_rhr.mean():.1f} bpm")
        st.metric("Rest days", f"{len(rest_rhr):,}")
    with col_c:
        delta = post_rhr.mean() - rest_rhr.mean()
        if delta > 1.5:
            st.warning(
                f"📈 Post-workout RHR is {delta:.1f} bpm higher than rest-day RHR. "
                "Normal recovery response — your heart is working to repair muscles."
            )
        elif delta < -1.5:
            st.success(
                f"📉 Post-workout RHR is actually {abs(delta):.1f} bpm *lower* than rest-day RHR. "
                "This is a sign of excellent cardiovascular adaptation."
            )
        else:
            st.info(f"Minimal difference ({delta:+.1f} bpm) between post-workout and rest days.")

    # Distribution chart
    import altair as alt

    rhr_compare = recovery_df.copy()
    rhr_compare["Category"] = rhr_compare["is_post_workout"].map(
        {True: "Day after workout", False: "Rest day"}
    )
    box_chart = (
        alt.Chart(rhr_compare)
        .mark_boxplot(extent="min-max")
        .encode(
            x=alt.X("Category:N", axis=alt.Axis(title="")),
            y=alt.Y("rhr:Q", axis=alt.Axis(title="Resting HR (bpm)"), scale=alt.Scale(zero=False)),
            color=alt.Color("Category:N", legend=None),
        )
        .properties(title="RHR Distribution: Post-workout vs Rest Day", height=280)
    )
    st.altair_chart(box_chart, use_container_width=True)

st.divider()

# ── Circadian profile ─────────────────────────────────────────────────────────
st.markdown("## 🌙 Circadian Profile — Sleep Timing by Day of Week")
st.caption(
    "When do you actually go to bed and wake up on different days of the week? "
    "Large differences between weekdays and weekends suggest social jet lag."
)

circ = circadian_profile(df_f)
if circ.empty or len(circ) < 3:
    st.info("Need sleep data across several different days of the week to show this analysis.")
else:
    DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    circ["day_name"] = circ["weekday"].map(lambda d: DAYS[d])

    def _format_hour(h: float) -> str:
        """Convert decimal hour (e.g. 23.5 or 25.5 for 01:30 next day) to HH:MM."""
        h_wrapped = h % 24
        hh = int(h_wrapped)
        mm = int((h_wrapped - hh) * 60)
        return f"{hh:02d}:{mm:02d}"

    circ["bedtime_label"] = circ["avg_bedtime_h"].apply(_format_hour)
    circ["waketime_label"] = circ["avg_waketime_h"].apply(_format_hour)

    import altair as alt

    col_bed, col_wake = st.columns(2)

    with col_bed:
        bed_chart = (
            alt.Chart(circ)
            .mark_bar(color="#7C3AED", opacity=0.8)
            .encode(
                x=alt.X("day_name:N", sort=DAYS, axis=alt.Axis(title="")),
                y=alt.Y(
                    "avg_bedtime_h:Q",
                    axis=alt.Axis(title="Bedtime (hour)"),
                    scale=alt.Scale(zero=False),
                ),
                tooltip=[
                    alt.Tooltip("day_name:N", title="Day"),
                    alt.Tooltip("bedtime_label:N", title="Avg bedtime"),
                    alt.Tooltip("n_nights:Q", title="Nights"),
                ],
            )
            .properties(title="Average Bedtime by Day of Week", height=260)
        )
        st.altair_chart(bed_chart, use_container_width=True)
        st.caption("Hours > 24 mean bedtime in the early hours of the next day (e.g. 25 = 01:00).")

    with col_wake:
        wake_chart = (
            alt.Chart(circ)
            .mark_bar(color="#F59E0B", opacity=0.8)
            .encode(
                x=alt.X("day_name:N", sort=DAYS, axis=alt.Axis(title="")),
                y=alt.Y(
                    "avg_waketime_h:Q",
                    axis=alt.Axis(title="Wake time (hour)"),
                    scale=alt.Scale(zero=False),
                ),
                tooltip=[
                    alt.Tooltip("day_name:N", title="Day"),
                    alt.Tooltip("waketime_label:N", title="Avg wake time"),
                    alt.Tooltip("n_nights:Q", title="Nights"),
                ],
            )
            .properties(title="Average Wake Time by Day of Week", height=260)
        )
        st.altair_chart(wake_chart, use_container_width=True)

    # Social jet lag metric
    weekday_bed = circ[circ["weekday"] < 5]["avg_bedtime_h"].mean()
    weekend_bed = circ[circ["weekday"] >= 5]["avg_bedtime_h"].mean()
    if not pd.isna(weekday_bed) and not pd.isna(weekend_bed):
        jet_lag_h = abs(weekend_bed - weekday_bed)
        if jet_lag_h >= 1:
            st.warning(
                f"🕰️ **Social jet lag: {jet_lag_h:.1f}h** — you go to bed "
                f"{'later' if weekend_bed > weekday_bed else 'earlier'} on weekends. "
                "Aligning your sleep schedule across the week can improve energy and focus."
            )
        else:
            st.success(
                f"✅ Low social jet lag ({jet_lag_h:.1f}h) — your sleep timing is "
                "consistent across the week. This supports a stable circadian rhythm."
            )

st.divider()

# ── Cross-metric correlation heatmap ─────────────────────────────────────────
st.markdown("## 🔗 Cross-Metric Correlation Heatmap")
st.caption(
    "Pearson correlations between your daily health metrics. "
    "Values near +1 mean they move together; near -1 means they move opposite; "
    "near 0 means no linear relationship."
)

daily_table = cross_metric_daily_table(df_f, wdf_f)
corr_matrix = correlation_matrix(daily_table)

if corr_matrix.empty or corr_matrix.shape[0] < 2:
    st.info(
        "Need at least 2 overlapping metric types with enough daily data to compute correlations. "
        "Import more data or expand the date range."
    )
else:
    import altair as alt

    # Melt to long form for Altair heatmap
    corr_long = corr_matrix.reset_index().melt(id_vars="index")
    corr_long.columns = ["metric_a", "metric_b", "correlation"]
    corr_long["correlation"] = corr_long["correlation"].round(2)

    # Nice labels
    METRIC_LABELS = {
        "steps": "Steps",
        "active_kcal": "Active kcal",
        "hrv": "HRV",
        "rhr": "Resting HR",
        "sleep_h": "Sleep (h)",
    }
    corr_long["metric_a"] = corr_long["metric_a"].map(lambda x: METRIC_LABELS.get(x, x))
    corr_long["metric_b"] = corr_long["metric_b"].map(lambda x: METRIC_LABELS.get(x, x))

    heat = (
        alt.Chart(corr_long)
        .mark_rect()
        .encode(
            x=alt.X("metric_a:N", axis=alt.Axis(title="", labelAngle=-30)),
            y=alt.Y("metric_b:N", axis=alt.Axis(title="")),
            color=alt.Color(
                "correlation:Q",
                scale=alt.Scale(scheme="redblue", domain=[-1, 1]),
                legend=alt.Legend(title="r"),
            ),
            tooltip=[
                alt.Tooltip("metric_a:N", title="Metric A"),
                alt.Tooltip("metric_b:N", title="Metric B"),
                alt.Tooltip("correlation:Q", title="r", format=".2f"),
            ],
        )
    )
    text = (
        alt.Chart(corr_long)
        .mark_text(fontSize=13)
        .encode(
            x=alt.X("metric_a:N"),
            y=alt.Y("metric_b:N"),
            text=alt.Text("correlation:Q", format=".2f"),
            color=alt.condition(
                (alt.datum.correlation > 0.5) | (alt.datum.correlation < -0.5),
                alt.value("white"),
                alt.value("black"),
            ),
        )
    )
    heatmap_chart = (heat + text).properties(
        title="Daily Metric Correlations (Pearson r)", height=350
    )
    st.altair_chart(heatmap_chart, use_container_width=True)

    # Highlight strongest off-diagonal correlations
    off_diag = corr_long[corr_long["metric_a"] != corr_long["metric_b"]].copy()
    off_diag["abs_corr"] = off_diag["correlation"].abs()
    top = off_diag.nlargest(3, "abs_corr")

    if not top.empty:
        st.markdown("**Strongest relationships in your data:**")
        for _, r in top.iterrows():
            direction = "positively" if r["correlation"] > 0 else "negatively"
            st.write(
                f"- **{r['metric_a']}** and **{r['metric_b']}** are {direction} correlated "
                f"(r = {r['correlation']:+.2f})"
            )

st.divider()

# ── Step Momentum ─────────────────────────────────────────────────────────────
st.markdown("## 🏃 Step Momentum")
st.caption(
    "Daily step count with a 7-day rolling average to reveal your activity trend. "
    "The dashed line marks the 8,000-step daily goal."
)

steps_data = steps_rolling(df_f)
if steps_data.empty or len(steps_data) < 7:
    st.info("Need at least 7 days of step data to show this analysis.")
else:
    steps_data["day"] = pd.to_datetime(steps_data["day"])

    # Summary metrics
    avg_steps = float(steps_data["steps"].mean())
    max_steps = float(steps_data["steps"].max())
    goal_days = int((steps_data["steps"] >= 8_000).sum())
    total_days = len(steps_data)

    col_sm, col_sa, col_sg = st.columns(3)
    col_sm.metric("Daily average", f"{avg_steps:,.0f} steps")
    col_sa.metric("Personal best", f"{max_steps:,.0f} steps")
    col_sg.metric("Days ≥ 8,000 steps", f"{goal_days}/{total_days}")

    bars = (
        alt.Chart(steps_data)
        .mark_bar(color="#CBD5E1", opacity=0.6)
        .encode(
            x=alt.X("day:T", axis=alt.Axis(labelAngle=-30, title="")),
            y=alt.Y("steps:Q", axis=alt.Axis(title="Steps")),
            tooltip=[
                alt.Tooltip("day:T", title="Date"),
                alt.Tooltip("steps:Q", title="Steps", format=","),
            ],
        )
    )
    rolling_line = (
        alt.Chart(steps_data)
        .mark_line(strokeWidth=2.5, color="#2E7D6E")
        .encode(
            x=alt.X("day:T"),
            y=alt.Y("steps_rolling:Q"),
            tooltip=[
                alt.Tooltip("day:T", title="Date"),
                alt.Tooltip("steps_rolling:Q", title="7-day avg", format=",.0f"),
            ],
        )
    )
    goal_line = (
        alt.Chart(pd.DataFrame({"y": [8_000]}))
        .mark_rule(strokeDash=[5, 3], color="#EF4444", strokeWidth=1.5)
        .encode(y=alt.Y("y:Q"))
    )
    st.altair_chart(
        (bars + rolling_line + goal_line)
        .properties(
            title="Daily Steps · Green line = 7-day rolling average · Red dashed = 8k goal",
            height=280,
        )
        .interactive(),
        use_container_width=True,
    )

st.divider()

# ── Active Energy Burn ────────────────────────────────────────────────────────
st.markdown("## 🔥 Active Energy Burn")
st.caption(
    "Daily active calories burned. The shaded area shows total burn; "
    "the line is a 7-day rolling average to smooth out single-day spikes."
)

kcal_data = active_energy_pairs(df_f)
if kcal_data.empty or len(kcal_data) < 7:
    st.info("Need at least 7 days of active energy data to show this analysis.")
else:
    kcal_data["day"] = pd.to_datetime(kcal_data["day"])
    kcal_data["kcal_rolling"] = kcal_data["active_kcal"].rolling(7, min_periods=1).mean()

    avg_kcal = float(kcal_data["active_kcal"].mean())
    max_kcal = float(kcal_data["active_kcal"].max())

    col_ka, col_km = st.columns(2)
    col_ka.metric("Daily average", f"{avg_kcal:,.0f} kcal")
    col_km.metric("Highest day", f"{max_kcal:,.0f} kcal")

    kcal_area = (
        alt.Chart(kcal_data)
        .mark_area(color="#F59E0B", opacity=0.25, line={"color": "#F59E0B", "strokeWidth": 1})
        .encode(
            x=alt.X("day:T", axis=alt.Axis(labelAngle=-30, title="")),
            y=alt.Y("active_kcal:Q", axis=alt.Axis(title="Active kcal")),
            tooltip=[
                alt.Tooltip("day:T", title="Date"),
                alt.Tooltip("active_kcal:Q", title="Active kcal", format=",.0f"),
            ],
        )
    )
    kcal_roll = (
        alt.Chart(kcal_data)
        .mark_line(strokeWidth=2.5, color="#D97706")
        .encode(
            x=alt.X("day:T"),
            y=alt.Y("kcal_rolling:Q"),
            tooltip=[
                alt.Tooltip("day:T", title="Date"),
                alt.Tooltip("kcal_rolling:Q", title="7-day avg", format=",.0f"),
            ],
        )
    )
    st.altair_chart(
        (kcal_area + kcal_roll)
        .properties(title="Active Energy Burn · Orange line = 7-day rolling average", height=260)
        .interactive(),
        use_container_width=True,
    )

st.divider()

# ── Sleep Stage Breakdown ─────────────────────────────────────────────────────
st.markdown("## 🌙 Sleep Stage Breakdown — Deep & REM")
st.caption(
    "Daily restorative (Deep + REM) sleep hours and what fraction of total sleep they represent. "
    "Aim for at least 20% of total sleep to be restorative."
)

stage_data = sleep_stages_daily(df_f)
if stage_data.empty or len(stage_data) < 7:
    st.info(
        "Need at least 7 nights of detailed sleep stage data (Deep + REM) to show this analysis. "
        "This requires an Apple Watch that records sleep stages."
    )
else:
    stage_data["day"] = pd.to_datetime(stage_data["day"])

    avg_pct = float(stage_data["restorative_pct"].mean())
    avg_rest_h = float(stage_data["restorative_h"].mean())
    best_pct = float(stage_data["restorative_pct"].max())

    col_rp, col_rh, col_rb = st.columns(3)
    col_rp.metric("Avg restorative %", f"{avg_pct:.0f}%")
    col_rh.metric("Avg restorative hours", f"{avg_rest_h:.1f}h")
    col_rb.metric("Best night", f"{best_pct:.0f}%")

    col_bars, col_pct = st.columns(2)

    with col_bars:
        stage_melted = stage_data[["day", "total_h", "restorative_h"]].melt(
            id_vars="day", value_vars=["total_h", "restorative_h"],
            var_name="type", value_name="hours",
        )
        stage_melted["type"] = stage_melted["type"].map(
            {"total_h": "Total sleep", "restorative_h": "Deep + REM"}
        )
        stacked = (
            alt.Chart(stage_melted)
            .mark_bar(opacity=0.85)
            .encode(
                x=alt.X("day:T", axis=alt.Axis(labelAngle=-30, title="")),
                y=alt.Y("hours:Q", axis=alt.Axis(title="Hours")),
                color=alt.Color(
                    "type:N",
                    scale=alt.Scale(
                        domain=["Total sleep", "Deep + REM"],
                        range=["#94A3B8", "#7C3AED"],
                    ),
                    legend=alt.Legend(title=""),
                ),
                tooltip=[
                    alt.Tooltip("day:T", title="Date"),
                    alt.Tooltip("type:N", title="Type"),
                    alt.Tooltip("hours:Q", title="Hours", format=".1f"),
                ],
            )
            .properties(title="Total vs Restorative Sleep", height=260)
        )
        st.altair_chart(stacked, use_container_width=True)

    with col_pct:
        ref20 = (
            alt.Chart(pd.DataFrame({"y": [20]}))
            .mark_rule(strokeDash=[4, 4], color="#10B981", strokeWidth=1.5)
            .encode(y=alt.Y("y:Q"))
        )
        pct_line = (
            alt.Chart(stage_data)
            .mark_line(strokeWidth=2, color="#7C3AED")
            .encode(
                x=alt.X("day:T", axis=alt.Axis(labelAngle=-30, title="")),
                y=alt.Y(
                    "restorative_pct:Q",
                    axis=alt.Axis(title="Restorative %"),
                    scale=alt.Scale(domain=[0, 100]),
                ),
                tooltip=[
                    alt.Tooltip("day:T", title="Date"),
                    alt.Tooltip("restorative_pct:Q", title="Deep+REM %", format=".1f"),
                ],
            )
        )
        st.altair_chart(
            (pct_line + ref20).properties(
                title="Restorative Sleep % · green dashed = 20% target",
                height=260,
            ),
            use_container_width=True,
        )
        st.caption("Green dashed line = 20% target")

st.divider()

# ── Workout Duration Trend ────────────────────────────────────────────────────
st.markdown("## ⏱️ Workout Duration Trend")
st.caption(
    "Each bar is one workout session. The line shows a 7-session rolling average "
    "so you can track whether your sessions are getting longer or shorter over time."
)

dur_data = workout_duration_trend(wdf_f)
if dur_data.empty or len(dur_data) < 5:
    st.info("Need at least 5 logged workouts to show this analysis.")
else:
    dur_data["day"] = pd.to_datetime(dur_data["day"])

    avg_dur = float(dur_data["duration_min"].mean())
    max_dur = float(dur_data["duration_min"].max())
    total_workouts = len(dur_data)

    col_da, col_dm, col_dt = st.columns(3)
    col_da.metric("Avg duration", f"{avg_dur:.0f} min")
    col_dm.metric("Longest session", f"{max_dur:.0f} min")
    col_dt.metric("Sessions analysed", f"{total_workouts:,}")

    dur_bars = (
        alt.Chart(dur_data)
        .mark_bar(color="#4CAF91", opacity=0.6)
        .encode(
            x=alt.X("day:T", axis=alt.Axis(labelAngle=-30, title="")),
            y=alt.Y("duration_min:Q", axis=alt.Axis(title="Minutes")),
            tooltip=[
                alt.Tooltip("day:T", title="Date"),
                alt.Tooltip("duration_min:Q", title="Duration (min)", format=".0f"),
            ],
        )
    )
    dur_roll = (
        alt.Chart(dur_data)
        .mark_line(strokeWidth=2.5, color="#2E7D6E")
        .encode(
            x=alt.X("day:T"),
            y=alt.Y("duration_rolling:Q"),
            tooltip=[
                alt.Tooltip("day:T", title="Date"),
                alt.Tooltip("duration_rolling:Q", title="7-session avg", format=".0f"),
            ],
        )
    )
    st.altair_chart(
        (dur_bars + dur_roll)
        .properties(title="Workout Duration · Green line = 7-session rolling average", height=280)
        .interactive(),
        use_container_width=True,
    )

st.divider()

# ── Workout Duration → Next-day HRV ──────────────────────────────────────────
st.markdown("## 🏋️ → ❤️ Workout Load & Next-Morning HRV")
st.caption(
    "Does working out harder (longer) hurt your recovery? "
    "Each dot is a day after a workout: total workout minutes vs next-morning HRV."
)

whrv = workout_duration_hrv_pairs(df_f, wdf_f)
if whrv.empty or len(whrv) < 7:
    st.info("Need at least 7 post-workout HRV readings to show this analysis.")
else:
    corr_wh = whrv["workout_duration_min"].corr(whrv["hrv"])
    col_wh, col_wi = st.columns([2, 1])

    with col_wh:
        whrv_chart = (
            alt.Chart(whrv)
            .mark_circle(size=60, opacity=0.7)
            .encode(
                x=alt.X(
                    "workout_duration_min:Q",
                    axis=alt.Axis(title="Total workout duration (min)"),
                ),
                y=alt.Y("hrv:Q", axis=alt.Axis(title="Next-morning HRV (ms)")),
                color=alt.Color(
                    "workout_type:N",
                    legend=alt.Legend(title="Workout type"),
                ),
                tooltip=[
                    alt.Tooltip("day:T", title="Date"),
                    alt.Tooltip("workout_type:N", title="Type"),
                    alt.Tooltip("workout_duration_min:Q", title="Duration (min)", format=".0f"),
                    alt.Tooltip("hrv:Q", title="Next-day HRV (ms)", format=".1f"),
                ],
            )
            .properties(title="Workout Duration → Next-day HRV", height=300)
        )
        st.altair_chart(whrv_chart, use_container_width=True)

    with col_wi:
        st.metric("Pearson correlation", f"{corr_wh:+.2f}")
        if corr_wh < -0.3:
            st.warning(
                f"⚠️ Longer workouts tend to reduce next-day HRV (r={corr_wh:.2f}). "
                "This is normal — harder training means more recovery needed. "
                "Build in rest days after long sessions."
            )
        elif corr_wh > 0.3:
            st.success(
                f"✅ Longer workouts are associated with higher next-day HRV (r={corr_wh:.2f}). "
                "Your body handles training volume well."
            )
        else:
            st.info(
                f"No strong link between workout duration and next-day HRV (r={corr_wh:.2f}). "
                "Workout intensity or type may matter more than duration alone."
            )
        st.metric("Pairs analysed", f"{len(whrv):,}")

st.divider()

# ── HRV Distribution ──────────────────────────────────────────────────────────
st.markdown("## 📊 HRV Distribution")
st.caption(
    "How your HRV values are distributed over the selected period. "
    "A wide, right-skewed distribution (peak at higher values) is a sign of "
    "good fitness and recovery."
)

hrv_dist_df = _hrv_trend(df_f)
if hrv_dist_df.empty or len(hrv_dist_df) < 14:
    st.info("Need at least 14 days of HRV data to show a meaningful distribution.")
else:
    avg_hrv = float(hrv_dist_df["hrv"].mean())
    median_hrv = float(hrv_dist_df["hrv"].median())
    p10 = float(hrv_dist_df["hrv"].quantile(0.10))
    p90 = float(hrv_dist_df["hrv"].quantile(0.90))

    col_ha, col_hm, col_hr = st.columns(3)
    col_ha.metric("Average HRV", f"{avg_hrv:.0f} ms")
    col_hm.metric("Median HRV", f"{median_hrv:.0f} ms")
    col_hr.metric("P10 – P90 range", f"{p10:.0f} – {p90:.0f} ms")

    hist = (
        alt.Chart(hrv_dist_df)
        .mark_bar(color="#7C3AED", opacity=0.75)
        .encode(
            x=alt.X(
                "hrv:Q",
                bin=alt.Bin(maxbins=25),
                axis=alt.Axis(title="HRV (ms)"),
            ),
            y=alt.Y("count():Q", axis=alt.Axis(title="Days")),
            tooltip=[
                alt.Tooltip("hrv:Q", bin=True, title="HRV range (ms)"),
                alt.Tooltip("count():Q", title="Days"),
            ],
        )
        .properties(title="HRV Distribution (daily values)", height=260)
    )
    avg_rule = (
        alt.Chart(pd.DataFrame({"x": [avg_hrv]}))
        .mark_rule(strokeDash=[4, 4], color="#EF4444", strokeWidth=2)
        .encode(x=alt.X("x:Q"))
    )
    st.altair_chart((hist + avg_rule).interactive(), use_container_width=True)
    st.caption("Red dashed line = your average HRV")

st.divider()

# ── Body Weight & BMI Trend ───────────────────────────────────────────────────
st.markdown("## ⚖️ Body Weight & BMI Trend")
st.caption(
    "Your weight measurements over time with BMI classification. "
    "Weight trends over weeks matter more than day-to-day fluctuations."
)

wb_data = weight_bmi_daily(df_f)
if wb_data.empty or "weight_kg" not in wb_data.columns or wb_data["weight_kg"].notna().sum() < 3:
    st.info("Need at least 3 weight measurements to show this analysis.")
else:
    wb_data["day"] = pd.to_datetime(wb_data["day"])
    latest_w = float(wb_data["weight_kg"].dropna().iloc[-1])
    first_w = float(wb_data["weight_kg"].dropna().iloc[0])
    delta_w = latest_w - first_w

    col_wl, col_wd, col_wb = st.columns(3)
    col_wl.metric("Latest weight", f"{latest_w:.1f} kg")
    col_wd.metric(
        "Change over period",
        f"{delta_w:+.1f} kg",
        delta_color="inverse",
    )
    if "bmi" in wb_data.columns and wb_data["bmi"].notna().any():
        from apple_health_dashboard.services.body import bmi_category

        latest_bmi = float(wb_data["bmi"].dropna().iloc[-1])
        col_wb.metric("Latest BMI", f"{latest_bmi:.1f} — {bmi_category(latest_bmi)}")

    w_area = (
        alt.Chart(wb_data[wb_data["weight_kg"].notna()])
        .mark_area(color="#3B82F6", opacity=0.2, line={"color": "#3B82F6", "strokeWidth": 2})
        .encode(
            x=alt.X("day:T", axis=alt.Axis(labelAngle=-30, title="")),
            y=alt.Y(
                "weight_kg:Q",
                axis=alt.Axis(title="Weight (kg)"),
                scale=alt.Scale(zero=False),
            ),
            tooltip=[
                alt.Tooltip("day:T", title="Date"),
                alt.Tooltip("weight_kg:Q", title="Weight (kg)", format=".1f"),
            ],
        )
    )
    layers = [w_area]

    if "bmi" in wb_data.columns and wb_data["bmi"].notna().any():
        bmi_line = (
            alt.Chart(wb_data[wb_data["bmi"].notna()])
            .mark_line(strokeWidth=2, color="#F59E0B", strokeDash=[4, 3])
            .encode(
                x=alt.X("day:T"),
                y=alt.Y(
                    "bmi:Q",
                    axis=alt.Axis(title="BMI"),
                    scale=alt.Scale(zero=False),
                ),
                tooltip=[
                    alt.Tooltip("day:T", title="Date"),
                    alt.Tooltip("bmi:Q", title="BMI", format=".1f"),
                ],
            )
        )
        layers.append(bmi_line)
        st.caption(
            "Blue area = weight (kg) · Orange dashed = BMI — "
            "Axes are independent (different scales). "
            "Use the correlation heatmap to cross-reference."
        )

    st.altair_chart(
        alt.layer(*layers).resolve_scale(y="independent")
        .properties(title="Body Weight & BMI over time", height=280)
        .interactive(),
        use_container_width=True,
    )

st.divider()

# ── Blood Oxygen (SpO₂) Trend ─────────────────────────────────────────────────
st.markdown("## 🫁 Blood Oxygen (SpO₂) Trend")
st.caption(
    "Daily average blood oxygen saturation. Normal range is 95–100%. "
    "Persistent dips may indicate sleep-disordered breathing."
)

spo2_data = spo2_daily(df_f)
if spo2_data.empty or len(spo2_data) < 3:
    st.info(
        "No SpO₂ (blood oxygen) data found. "
        "Requires an Apple Watch that measures blood oxygen."
    )
else:
    spo2_data["day"] = pd.to_datetime(spo2_data["day"])
    avg_spo2 = float(spo2_data["spo2"].mean())
    min_spo2 = float(spo2_data["spo2"].min())
    low_days = int((spo2_data["spo2"] < 95).sum())

    col_sa, col_sm, col_sl = st.columns(3)
    col_sa.metric("Average SpO₂", f"{avg_spo2:.1f}%")
    col_sm.metric("Lowest reading", f"{min_spo2:.1f}%")
    col_sl.metric("Days below 95%", str(low_days))

    spo2_line = (
        alt.Chart(spo2_data)
        .mark_line(strokeWidth=2, color="#06B6D4")
        .encode(
            x=alt.X("day:T", axis=alt.Axis(labelAngle=-30, title="")),
            y=alt.Y(
                "spo2:Q",
                axis=alt.Axis(title="SpO₂ (%)"),
                scale=alt.Scale(domain=[max(85, min_spo2 - 2), 101]),
            ),
            tooltip=[
                alt.Tooltip("day:T", title="Date"),
                alt.Tooltip("spo2:Q", title="SpO₂ (%)", format=".1f"),
            ],
        )
    )
    spo2_points = (
        alt.Chart(spo2_data)
        .mark_circle(size=40)
        .encode(
            x=alt.X("day:T"),
            y=alt.Y("spo2:Q"),
            color=alt.condition(
                alt.datum.spo2 < 95,
                alt.value("#EF4444"),
                alt.value("#06B6D4"),
            ),
            tooltip=[
                alt.Tooltip("day:T", title="Date"),
                alt.Tooltip("spo2:Q", title="SpO₂ (%)", format=".1f"),
            ],
        )
    )
    ref95 = (
        alt.Chart(pd.DataFrame({"y": [95]}))
        .mark_rule(strokeDash=[4, 3], color="#EF4444", strokeWidth=1.5)
        .encode(y=alt.Y("y:Q"))
    )
    st.altair_chart(
        (spo2_line + spo2_points + ref95)
        .properties(
            title="Daily SpO₂ · Red dots = below 95% · Red dashed = 95% threshold",
            height=260,
        )
        .interactive(),
        use_container_width=True,
    )

st.divider()

# ── Blood Pressure Trend ──────────────────────────────────────────────────────
st.markdown("## 🩺 Blood Pressure Trend")
st.caption(
    "Daily average systolic (upper) and diastolic (lower) blood pressure. "
    "Normal is <120/80 mmHg. Stage 1 hypertension: 130-139/80-89. "
    "Stage 2: ≥140/90."
)

bp_data = blood_pressure_daily(df_f)
if bp_data.empty or "systolic" not in bp_data.columns or bp_data["systolic"].notna().sum() < 3:
    st.info(
        "No blood pressure data found. "
        "Requires manual logging or a compatible blood pressure device."
    )
else:
    bp_data["day"] = pd.to_datetime(bp_data["day"])
    avg_sys = float(bp_data["systolic"].dropna().mean())
    max_sys = float(bp_data["systolic"].dropna().max())

    col_bs, col_bd, col_bm = st.columns(3)
    col_bs.metric("Avg systolic", f"{avg_sys:.0f} mmHg")

    if "diastolic" in bp_data.columns and bp_data["diastolic"].notna().any():
        avg_dia = float(bp_data["diastolic"].dropna().mean())
        col_bd.metric("Avg diastolic", f"{avg_dia:.0f} mmHg")
        col_bm.metric("Avg pulse pressure", f"{avg_sys - avg_dia:.0f} mmHg")
    else:
        avg_dia = None

    bp_melt = bp_data.melt(
        id_vars="day",
        value_vars=[c for c in ["systolic", "diastolic"] if c in bp_data.columns],
        var_name="metric",
        value_name="mmhg",
    ).dropna(subset=["mmhg"])
    bp_melt["metric"] = bp_melt["metric"].map(
        {"systolic": "Systolic", "diastolic": "Diastolic"}
    )

    bp_chart = (
        alt.Chart(bp_melt)
        .mark_line(strokeWidth=2)
        .encode(
            x=alt.X("day:T", axis=alt.Axis(labelAngle=-30, title="")),
            y=alt.Y("mmhg:Q", axis=alt.Axis(title="mmHg"), scale=alt.Scale(zero=False)),
            color=alt.Color(
                "metric:N",
                scale=alt.Scale(
                    domain=["Systolic", "Diastolic"],
                    range=["#EF4444", "#3B82F6"],
                ),
                legend=alt.Legend(title=""),
            ),
            tooltip=[
                alt.Tooltip("day:T", title="Date"),
                alt.Tooltip("metric:N", title="Metric"),
                alt.Tooltip("mmhg:Q", title="mmHg", format=".0f"),
            ],
        )
    )
    hyp_line = (
        alt.Chart(pd.DataFrame({"y": [120]}))
        .mark_rule(strokeDash=[4, 3], color="#94A3B8", strokeWidth=1.2)
        .encode(y=alt.Y("y:Q"))
    )
    st.altair_chart(
        (bp_chart + hyp_line)
        .properties(title="Blood Pressure · Grey dashed = 120 mmHg reference", height=260)
        .interactive(),
        use_container_width=True,
    )

st.divider()

# ── Heart Rate Zones ──────────────────────────────────────────────────────────
st.markdown("## 💓 Heart Rate Zone Distribution")
st.caption(
    "How your active time is split across HR zones (based on all heart rate records). "
    "Zone 2 (aerobic base) is the most efficient zone for long-term endurance fitness."
)

zone_data = hr_zone_distribution(df_f)
if zone_data.empty or zone_data["minutes"].sum() < 30:
    st.info(
        "Need at least 30 minutes of heart rate data to show zone distribution. "
        "This uses all heart rate records (workouts and daily activity)."
    )
else:
    total_zone_min = float(zone_data["minutes"].sum())
    col_z1, col_z2 = st.columns([2, 1])

    with col_z1:
        zone_bar = (
            alt.Chart(zone_data)
            .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
            .encode(
                x=alt.X(
                    "zone:N",
                    sort=list(zone_data["zone"]),
                    axis=alt.Axis(labelAngle=-20, title=""),
                ),
                y=alt.Y("pct:Q", axis=alt.Axis(title="% of time")),
                color=alt.Color(
                    "zone:N",
                    scale=alt.Scale(
                        domain=list(zone_data["zone"]),
                        range=["#94A3B8", "#22C55E", "#EAB308", "#F97316", "#EF4444"],
                    ),
                    legend=None,
                ),
                tooltip=[
                    alt.Tooltip("zone:N", title="Zone"),
                    alt.Tooltip("pct:Q", title="% of time", format=".1f"),
                    alt.Tooltip("minutes:Q", title="Minutes", format=".0f"),
                ],
            )
            .properties(title="HR Zone Distribution (% of total tracked time)", height=280)
        )
        st.altair_chart(zone_bar, use_container_width=True)

    with col_z2:
        st.markdown("**Zone guide**")
        for _, zrow in zone_data.iterrows():
            bar_pct = int(zrow["pct"])
            st.markdown(
                f"**{zrow['zone']}** — {zrow['pct']:.0f}% "
                f"({zrow['minutes']:.0f} min)"
            )
        st.markdown(
            f"**Total tracked time:** {total_zone_min / 60:.1f} hours"
        )

st.divider()

# ── Sleep Debt Tracker ────────────────────────────────────────────────────────
st.markdown("## 😴 Sleep Debt Tracker")
st.caption(
    "Cumulative sleep debt vs an 8-hour/night goal. "
    "A rising line means you're consistently under-sleeping; falling means surplus. "
    "The red zone shows accumulated debt."
)

debt_data = sleep_debt_daily(df_f)
if debt_data.empty or len(debt_data) < 5:
    st.info("Need at least 5 nights of sleep data to show this analysis.")
else:
    debt_data["day"] = pd.to_datetime(debt_data["day"])
    total_debt = float(debt_data["cumulative_debt_h"].iloc[-1])
    avg_sleep = float(debt_data["sleep_h"].mean())
    max_deficit = float(debt_data["cumulative_debt_h"].max())

    col_dd, col_da, col_dm = st.columns(3)
    col_dd.metric(
        "Net sleep debt / surplus",
        f"{abs(total_debt):.1f}h {'debt' if total_debt > 0 else 'surplus'}",
        delta_color="inverse",
    )
    col_da.metric("Avg nightly sleep", f"{avg_sleep:.1f}h")
    col_dm.metric("Peak debt", f"{max(0, max_deficit):.1f}h")

    debt_area = (
        alt.Chart(debt_data)
        .mark_area(
            color=alt.Gradient(
                gradient="linear",
                stops=[
                    alt.GradientStop(color="#EF444440", offset=0),
                    alt.GradientStop(color="#EF444410", offset=1),
                ],
                x1=0, x2=0, y1=0, y2=1,
            ),
            line={"color": "#EF4444", "strokeWidth": 2},
        )
        .transform_filter(alt.datum.cumulative_debt_h > 0)
        .encode(
            x=alt.X("day:T", axis=alt.Axis(labelAngle=-30, title="")),
            y=alt.Y("cumulative_debt_h:Q", axis=alt.Axis(title="Hours")),
        )
    )
    debt_line = (
        alt.Chart(debt_data)
        .mark_line(strokeWidth=2, color="#6366F1")
        .encode(
            x=alt.X("day:T"),
            y=alt.Y("cumulative_debt_h:Q"),
            tooltip=[
                alt.Tooltip("day:T", title="Date"),
                alt.Tooltip("sleep_h:Q", title="Sleep (h)", format=".1f"),
                alt.Tooltip("debt_h:Q", title="Nightly +/- (h)", format="+.1f"),
                alt.Tooltip(
                    "cumulative_debt_h:Q",
                    title="Cumulative debt (h)",
                    format="+.1f",
                ),
            ],
        )
    )
    zero_line = (
        alt.Chart(pd.DataFrame({"y": [0]}))
        .mark_rule(strokeDash=[4, 3], color="#64748B", strokeWidth=1.5)
        .encode(y=alt.Y("y:Q"))
    )
    st.altair_chart(
        (debt_area + debt_line + zero_line)
        .properties(
            title="Cumulative Sleep Debt · Above zero = debt · Below = surplus",
            height=260,
        )
        .interactive(),
        use_container_width=True,
    )

st.divider()

# ── Best Workout Type for Recovery ───────────────────────────────────────────
st.markdown("## 🏆 Best Workout Type for HRV Recovery")
st.caption(
    "Which workout type leaves you with the highest HRV the next morning? "
    "Higher next-day HRV = better recovery from that workout type."
)

best_type_data = best_workout_type_for_hrv(df_f, wdf_f)
if best_type_data.empty or len(best_type_data) < 2:
    st.info(
        "Need post-workout HRV data for at least 2 different workout types. "
        "Keep logging workouts and HRV measurements to unlock this analysis."
    )
else:
    col_bt, col_bi = st.columns([3, 1])

    with col_bt:
        best_bar = (
            alt.Chart(best_type_data)
            .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4, color="#4CAF91")
            .encode(
                x=alt.X(
                    "avg_hrv:Q",
                    axis=alt.Axis(title="Avg next-morning HRV (ms)"),
                    scale=alt.Scale(zero=False),
                ),
                y=alt.Y(
                    "workout_type:N",
                    sort="-x",
                    axis=alt.Axis(title=""),
                ),
                color=alt.Color(
                    "avg_hrv:Q",
                    scale=alt.Scale(scheme="greens"),
                    legend=None,
                ),
                tooltip=[
                    alt.Tooltip("workout_type:N", title="Workout type"),
                    alt.Tooltip("avg_hrv:Q", title="Avg HRV (ms)", format=".1f"),
                    alt.Tooltip("count:Q", title="Sessions", format="d"),
                ],
            )
            .properties(title="Average Next-Morning HRV by Workout Type", height=280)
        )
        st.altair_chart(best_bar, use_container_width=True)

    with col_bi:
        st.markdown("**Top 3 for recovery:**")
        for _, brow in best_type_data.head(3).iterrows():
            st.markdown(
                f"🟢 **{brow['workout_type']}** — "
                f"{brow['avg_hrv']:.0f} ms "
                f"({int(brow['count'])} sessions)"
            )
        if len(best_type_data) >= 2:
            worst = best_type_data.iloc[-1]
            st.markdown("**Hardest on recovery:**")
            st.markdown(
                f"🔴 **{worst['workout_type']}** — "
                f"{worst['avg_hrv']:.0f} ms "
                f"({int(worst['count'])} sessions)"
            )

st.divider()

# ── Walking HR Trend ──────────────────────────────────────────────────────────
st.markdown("## 🚶 Walking HR Trend — Aerobic Fitness Proxy")
st.caption(
    "Average walking heart rate over time. As cardiovascular fitness improves, "
    "your heart does the same walking work at a lower rate. "
    "A downward trend is a strong fitness signal."
)

whr_data = walking_hr_daily(df_f)
if whr_data.empty or len(whr_data) < 7:
    st.info("Need at least 7 days of walking heart rate data.")
else:
    whr_data["day"] = pd.to_datetime(whr_data["day"])
    whr_data["whr_rolling"] = whr_data["walking_hr"].rolling(7, min_periods=1).mean()

    avg_whr = float(whr_data["walking_hr"].mean())
    first_whr = float(whr_data["whr_rolling"].dropna().iloc[0])
    last_whr = float(whr_data["whr_rolling"].dropna().iloc[-1])
    delta_whr = last_whr - first_whr

    col_wa, col_wd = st.columns(2)
    col_wa.metric("Average walking HR", f"{avg_whr:.0f} bpm")
    col_wd.metric(
        "Change over period",
        f"{delta_whr:+.0f} bpm",
        delta_color="inverse",
    )

    whr_area = (
        alt.Chart(whr_data)
        .mark_area(color="#F97316", opacity=0.15, line={"color": "#F97316", "strokeWidth": 1})
        .encode(
            x=alt.X("day:T", axis=alt.Axis(labelAngle=-30, title="")),
            y=alt.Y(
                "walking_hr:Q",
                axis=alt.Axis(title="Walking HR (bpm)"),
                scale=alt.Scale(zero=False),
            ),
            tooltip=[
                alt.Tooltip("day:T", title="Date"),
                alt.Tooltip("walking_hr:Q", title="Walking HR (bpm)", format=".0f"),
            ],
        )
    )
    whr_roll = (
        alt.Chart(whr_data)
        .mark_line(strokeWidth=2.5, color="#EA580C")
        .encode(
            x=alt.X("day:T"),
            y=alt.Y("whr_rolling:Q"),
            tooltip=[
                alt.Tooltip("day:T", title="Date"),
                alt.Tooltip("whr_rolling:Q", title="7-day avg (bpm)", format=".0f"),
            ],
        )
    )
    st.altair_chart(
        (whr_area + whr_roll)
        .properties(title="Walking HR · Orange line = 7-day rolling average", height=260)
        .interactive(),
        use_container_width=True,
    )
    if delta_whr <= -3:
        st.success(
            f"📉 Your walking HR has dropped {abs(delta_whr):.0f} bpm over the period "
            "— a clear sign of improving aerobic fitness."
        )
    elif delta_whr >= 4:
        st.warning(
            f"📈 Your walking HR has increased {delta_whr:.0f} bpm. "
            "This could indicate fatigue, reduced activity, or seasonal changes."
        )

