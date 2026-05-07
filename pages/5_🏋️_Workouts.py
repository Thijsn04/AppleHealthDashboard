from __future__ import annotations

import pandas as pd
import streamlit as st

from apple_health_dashboard.db import default_db_path
from apple_health_dashboard.services.filters import apply_date_filter
from apple_health_dashboard.services.workouts import (
    personal_records_by_type,
    summarize_by_type,
    summarize_workouts_by_week,
    workout_calendar_heatmap_data,
)
from apple_health_dashboard.web.charts import area_chart, bar_chart, line_chart
from apple_health_dashboard.web.page_utils import (
    load_all_workouts,
    page_header,
    sidebar_nav,
)

st.set_page_config(
    page_title="Workouts · Apple Health Dashboard",
    page_icon="🏋️",
    layout="wide",
)

page_header("🏋️", "Workouts", "All workout types, personal records, weekly trends and calendar view.")

db_path = default_db_path()

with st.spinner("Loading workouts..."):
    wdf = load_all_workouts(str(db_path))

if wdf.empty:
    st.warning("No workouts found. Please import your Apple Health export on the Home page.")
    st.page_link("app.py", label="Go to Home →", icon="🏠")
    st.stop()

# ── Date filter needs a start_at reference ────────────────────────────────────
# Build a minimal "df" just for the date filter
_date_df = wdf[["start_at"]].rename(columns={"start_at": "start_at"})
_date_df["type"] = "workout"

from apple_health_dashboard.services.filters import infer_date_filter, DateFilter

with st.sidebar:
    sidebar_nav(current="Workouts")
    st.divider()
    st.markdown("### 📅 Date Range")
    preset = st.selectbox("Preset", ["All", "7D", "30D", "90D", "180D", "1Y"], index=3)
    preset_filter = infer_date_filter(_date_df, preset=preset)
    if preset_filter is None:
        st.warning("No dates found.")
        st.stop()

    use_custom = st.checkbox("Custom range", value=False)
    if use_custom:
        min_d = preset_filter.start.date()
        max_d = preset_filter.end.date()
        dates = st.date_input("Date range", value=(min_d, max_d), min_value=min_d, max_value=max_d)
        if isinstance(dates, (list, tuple)) and len(dates) == 2:
            start_d, end_d = dates
            date_filter = DateFilter(
                start=pd.Timestamp(start_d, tz="UTC"),
                end=pd.Timestamp(end_d, tz="UTC") + pd.Timedelta(days=1) - pd.Timedelta(seconds=1),
            )
        else:
            date_filter = preset_filter
    else:
        date_filter = preset_filter

# Filter workouts
wdf_f = wdf[(wdf["start_at"] >= date_filter.start) & (wdf["start_at"] <= date_filter.end)].copy()

with st.sidebar:
    st.caption(f"{date_filter.start.date()} → {date_filter.end.date()}")

    # Workout type filter
    label_col = "activity_label" if "activity_label" in wdf_f.columns else "workout_activity_type"
    all_types = sorted(wdf_f[label_col].unique().tolist())
    selected_types = st.multiselect("Filter by type", all_types, default=all_types, key="wtype_filter")
    if selected_types:
        wdf_f = wdf_f[wdf_f[label_col].isin(selected_types)]

if wdf_f.empty:
    st.info("No workouts in the selected period.")
    st.stop()

# ── KPIs ──────────────────────────────────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)
total_workouts = len(wdf_f)
total_hours = wdf_f["duration_s"].fillna(0).sum() / 3600
total_kcal = wdf_f["total_energy_kcal"].fillna(0).sum()
total_km = wdf_f["total_distance_m"].fillna(0).sum() / 1000
unique_types = wdf_f[label_col].nunique()

c1.metric("Total Workouts", f"{total_workouts:,}")
c2.metric("Total Hours", f"{total_hours:.1f}h")
c3.metric("Total Calories", f"{total_kcal:,.0f} kcal")
c4.metric("Total Distance", f"{total_km:.1f} km")
c5.metric("Activity Types", f"{unique_types}")

st.divider()

tabs = st.tabs(["Overview", "By Type", "Personal Records", "Calendar", "Training Load", "Muscle Tracking", "Raw Data"])

# ── Overview tab ───────────────────────────────────────────────────────────────
with tabs[0]:
    col_l, col_r = st.columns(2)

    with col_l:
        st.markdown("**Workouts per Week**")
        weekly = summarize_workouts_by_week(wdf_f)
        if not weekly.empty:
            st.altair_chart(
                bar_chart(weekly, x="week", y="count", y_title="Workouts", height=220),
                width="stretch",
            )

    with col_r:
        st.markdown("**Weekly Duration (hours)**")
        if not weekly.empty:
            st.altair_chart(
                area_chart(weekly, x="week", y="duration_hours", y_title="Hours", height=220),
                width="stretch",
            )

    st.markdown("**Cumulative Workouts**")
    cum_df = wdf_f.copy()
    cum_df["day"] = cum_df["start_at"].dt.floor("D")
    cum_df = cum_df.groupby("day").size().reset_index(name="count")
    cum_df["cumulative"] = cum_df["count"].cumsum()
    st.altair_chart(
        area_chart(cum_df, x="day", y="cumulative", y_title="Total workouts", color="#7C3AED", height=200),
        width="stretch",
    )

    # Type distribution donut
    st.markdown("**Workout Types Distribution**")
    type_counts = wdf_f[label_col].value_counts().reset_index()
    type_counts.columns = ["type", "count"]

    import altair as alt
    col_donut, col_table = st.columns([1, 1])
    with col_donut:
        donut = (
            alt.Chart(type_counts.head(15))
            .mark_arc(innerRadius=60)
            .encode(
                theta=alt.Theta("count:Q"),
                color=alt.Color("type:N", scale=alt.Scale(scheme="tableau20")),
                tooltip=[alt.Tooltip("type:N"), alt.Tooltip("count:Q")],
            )
            .properties(title="Workout Types", height=300)
        )
        st.altair_chart(donut, width="stretch")
    with col_table:
        st.dataframe(type_counts, width="stretch", hide_index=True)

# ── By Type tab ────────────────────────────────────────────────────────────────
with tabs[1]:
    st.subheader("Aggregates by Workout Type")
    by_type = summarize_by_type(wdf_f)
    if not by_type.empty:
        st.dataframe(
            by_type,
            width="stretch",
            hide_index=True,
            column_config={
                "activity_label": st.column_config.TextColumn("Type"),
                "count": st.column_config.NumberColumn("Count", format="%d"),
                "total_duration_h": st.column_config.NumberColumn("Total Hours", format="%.1f"),
                "avg_duration_h": st.column_config.NumberColumn("Avg Duration (h)", format="%.2f"),
                "total_distance_km": st.column_config.NumberColumn("Total Distance (km)", format="%.1f"),
                "total_energy_kcal": st.column_config.NumberColumn("Total kcal", format="%.0f"),
            },
        )

    # Deep-dive: select a type and see its trend
    st.markdown("**Trend for a Specific Type**")
    if all_types:
        selected_type = st.selectbox("Select workout type", all_types, key="type_trend_select")
        type_df = wdf_f[wdf_f[label_col] == selected_type].copy()
        if not type_df.empty:
            type_df["day"] = type_df["start_at"].dt.floor("D")
            type_df["duration_h"] = type_df["duration_s"].fillna(0) / 3600

            c_dur, c_kcal = st.columns(2)
            with c_dur:
                daily_dur = type_df.groupby("day")["duration_h"].sum().reset_index()
                st.altair_chart(
                    bar_chart(daily_dur, x="day", y="duration_h", y_title="Hours", height=200),
                    width="stretch",
                )
            with c_kcal:
                if type_df["total_energy_kcal"].notna().any():
                    daily_kcal = type_df.groupby("day")["total_energy_kcal"].sum().reset_index()
                    st.altair_chart(
                        bar_chart(
                            daily_kcal, x="day", y="total_energy_kcal",
                            y_title="kcal", color="#FF6B6B", height=200,
                        ),
                        width="stretch",
                    )

# ── Personal Records tab ───────────────────────────────────────────────────────
with tabs[2]:
    st.subheader("Personal Records")
    st.caption("Best single-session performance per workout type.")

    prs = personal_records_by_type(wdf_f)
    if prs.empty:
        st.info("No personal record data available.")
    else:
        display_prs = prs.copy()
        for date_col in ["longest_date", "farthest_date", "most_energy_date"]:
            if date_col in display_prs.columns:
                display_prs[date_col] = pd.to_datetime(display_prs[date_col]).dt.date

        st.dataframe(
            display_prs,
            width="stretch",
            hide_index=True,
            column_config={
                "activity_label": st.column_config.TextColumn("Type"),
                "count": st.column_config.NumberColumn("Sessions", format="%d"),
                "longest_h": st.column_config.NumberColumn("Longest (h)", format="%.2f"),
                "longest_date": st.column_config.DateColumn("Date"),
                "farthest_km": st.column_config.NumberColumn("Farthest (km)", format="%.2f"),
                "farthest_date": st.column_config.DateColumn("Date"),
                "most_energy_kcal": st.column_config.NumberColumn("Most kcal", format="%.0f"),
                "most_energy_date": st.column_config.DateColumn("Date"),
            },
        )

# ── Calendar tab ───────────────────────────────────────────────────────────────
with tabs[3]:
    st.subheader("Workout Calendar Heatmap")
    cal_df = workout_calendar_heatmap_data(wdf_f)

    if not cal_df.empty:
        cal_df["day_dt"] = pd.to_datetime(cal_df["day"])
        cal_df["month"] = cal_df["day_dt"].dt.strftime("%b %Y")
        cal_df["week_of_year"] = cal_df["day_dt"].dt.isocalendar().week.astype(str)
        cal_df["weekday"] = cal_df["day_dt"].dt.day_name()
        WEEKDAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        cal_df["weekday"] = pd.Categorical(cal_df["weekday"], categories=WEEKDAY_ORDER, ordered=True)

        import altair as alt
        heat = (
            alt.Chart(cal_df)
            .mark_rect(cornerRadius=2)
            .encode(
                x=alt.X("week_of_year:O", axis=alt.Axis(title="Week")),
                y=alt.Y("weekday:O", sort=WEEKDAY_ORDER, axis=alt.Axis(title="")),
                color=alt.Color(
                    "count:Q",
                    scale=alt.Scale(scheme="greens", domain=[0, cal_df["count"].max()]),
                    legend=alt.Legend(title="Workouts"),
                ),
                tooltip=[
                    alt.Tooltip("day_dt:T", title="Date"),
                    alt.Tooltip("count:Q", title="Workouts"),
                    alt.Tooltip("duration_h:Q", title="Hours", format=".1f"),
                ],
            )
            .properties(
                title="Workout Calendar (green = more workouts)",
                height=220,
            )
        )
        st.altair_chart(heat, width="stretch")

        # Monthly summary
        st.markdown("**Monthly Summary**")
        cal_df["month_period"] = cal_df["day_dt"].dt.to_period("M").dt.start_time
        monthly = cal_df.groupby("month_period").agg(
            total_workouts=("count", "sum"),
            total_hours=("duration_h", "sum"),
        ).reset_index()
        monthly.columns = ["Month", "Workouts", "Total Hours"]
        monthly["Total Hours"] = monthly["Total Hours"].round(1)
        st.dataframe(monthly, width="stretch", hide_index=True)

# ── Training Load tab ──────────────────────────────────────────────────────────
with tabs[4]:
    st.subheader("Training Load & Running Pace")
    st.caption("Weekly training load estimate (TRIMP proxy) and running pace trend.")

    import altair as alt

    # Weekly TRIMP proxy: duration × an intensity factor (1 for low, 1.5 medium, 2 hard)
    INTENSITY_MAP = {
        "Running": 1.8, "Cycling": 1.5, "Swimming": 1.7, "HIIT": 2.0,
        "CrossTraining": 1.6, "Walking": 0.8, "Yoga": 0.6, "Strength Training": 1.4,
    }
    tl_df = wdf_f.copy()
    tl_df["duration_h"] = tl_df["duration_s"].fillna(0) / 3600
    tl_df["intensity"] = tl_df[label_col].map(lambda x: next(
        (v for k, v in INTENSITY_MAP.items() if k.lower() in str(x).lower()), 1.0
    ))
    tl_df["trimp"] = tl_df["duration_h"] * 60 * tl_df["intensity"]  # in arbitrary units
    tl_df["week"] = tl_df["start_at"].dt.to_period("W").dt.start_time
    weekly_load = tl_df.groupby("week")["trimp"].sum().reset_index()
    weekly_load.columns = ["week", "load"]

    if not weekly_load.empty:
        col_tl1, col_tl2 = st.columns([3, 1])
        with col_tl1:
            load_chart = (
                alt.Chart(weekly_load)
                .mark_bar(color="#7C3AED", opacity=0.8)
                .encode(
                    x=alt.X("week:T", axis=alt.Axis(labelAngle=-30, title="")),
                    y=alt.Y("load:Q", axis=alt.Axis(title="Weekly Load (AU)")),
                    tooltip=[alt.Tooltip("week:T", title="Week"), alt.Tooltip("load:Q", title="Load (AU)", format=".0f")],
                )
                .properties(title="Weekly Training Load (TRIMP proxy)", height=260)
                .interactive()
            )
            st.altair_chart(load_chart, width="stretch")
            st.caption("AU = Arbitrary Units. Duration × intensity factor. Higher = harder week.")
        with col_tl2:
            st.metric("Peak week load", f"{weekly_load['load'].max():.0f} AU")
            st.metric("Avg week load", f"{weekly_load['load'].mean():.0f} AU")
            st.metric("Recent vs avg",
                      f"{weekly_load['load'].iloc[-1]:.0f} AU" if len(weekly_load) >= 1 else "—",
                      delta=f"{weekly_load['load'].iloc[-1] - weekly_load['load'].mean():+.0f}" if len(weekly_load) >= 1 else None)

    # Running pace trend
    st.divider()
    st.markdown("**🏃 Running Pace Trend**")
    run_df = wdf_f[wdf_f[label_col].str.contains("Run", case=False, na=False)].copy()
    if not run_df.empty and run_df["total_distance_m"].notna().any() and run_df["duration_s"].notna().any():
        run_df = run_df[(run_df["total_distance_m"] > 100) & (run_df["duration_s"] > 60)].copy()
        run_df["pace_min_km"] = (run_df["duration_s"] / 60) / (run_df["total_distance_m"] / 1000)
        run_df["day"] = run_df["start_at"].dt.floor("D")
        run_df = run_df.sort_values("day")
        run_pace = run_df.groupby("day")["pace_min_km"].mean().reset_index()
        if not run_pace.empty:
            pace_chart = (
                alt.Chart(run_pace)
                .mark_line(strokeWidth=2, color="#F97316")
                .encode(
                    x=alt.X("day:T", axis=alt.Axis(labelAngle=-30, title="")),
                    y=alt.Y("pace_min_km:Q", axis=alt.Axis(title="Pace (min/km)"),
                            scale=alt.Scale(zero=False)),
                    tooltip=[alt.Tooltip("day:T", title="Date"),
                             alt.Tooltip("pace_min_km:Q", title="Pace (min/km)", format=".2f")],
                )
                .properties(title="Running Pace Trend (lower = faster)", height=220)
                .interactive()
            )
            st.altair_chart(pace_chart, width="stretch")
            best_pace = run_pace["pace_min_km"].min()
            avg_pace = run_pace["pace_min_km"].mean()
            col_p1, col_p2 = st.columns(2)
            col_p1.metric("Best pace", f"{best_pace:.2f} min/km")
            col_p2.metric("Avg pace", f"{avg_pace:.2f} min/km")
    else:
        st.info("No running workouts with distance data found.")

# ── Muscle Tracking tab ────────────────────────────────────────────────────────
with tabs[5]:
    st.subheader("Muscle Group Engagement")
    st.caption("Based on your recent workout types, here is a heatmap of your muscle engagement.")
    
    from apple_health_dashboard.web.body_map import render_body_map
    
    # Simple heuristic for muscle engagement
    engaged = []
    types_str = " ".join(wdf_f[label_col].astype(str).tolist()).lower()
    if any(x in types_str for x in ["run", "walk", "cycle", "leg"]): engaged.extend(["Left Leg", "Right Leg"])
    if any(x in types_str for x in ["strength", "pushup", "bench", "chest", "arm"]): engaged.extend(["Left Arm", "Right Arm", "Torso"])
    if any(x in types_str for x in ["back", "row", "pull"]): engaged.append("Torso")
    
    render_body_map(selected_regions=list(set(engaged)))
    
    st.info("Interactive muscle tracking is based on workout type inference. You can manually highlight areas for pain/symptom tracking on the **Body** page.")

# ── Raw Data tab ────────────────────────────────────────────────────────────
with tabs[6]:
    st.subheader("All Workouts")
    display_cols = [label_col, "start_at", "end_at", "duration_s", "total_energy_kcal",
                    "total_distance_m", "source_name"]
    display_cols = [c for c in display_cols if c in wdf_f.columns]
    raw = wdf_f[display_cols].copy()
    raw["duration_min"] = (raw["duration_s"].fillna(0) / 60).round(1)
    raw["distance_km"] = (raw["total_distance_m"].fillna(0) / 1000).round(2)
    raw = raw.sort_values("start_at", ascending=False)

    # CSV export
    csv_data = raw.drop(columns=["duration_s", "total_distance_m"], errors="ignore").to_csv(index=False)
    st.download_button("⬇️ Download as CSV", data=csv_data, file_name="workouts.csv",
                       mime="text/csv", help="Download all filtered workouts as CSV")

    st.dataframe(
        raw.drop(columns=["duration_s", "total_distance_m"], errors="ignore"),
        width="stretch",
        column_config={
            label_col: st.column_config.TextColumn("Type"),
            "start_at": st.column_config.DatetimeColumn("Start"),
            "end_at": st.column_config.DatetimeColumn("End"),
            "duration_min": st.column_config.NumberColumn("Duration (min)", format="%.1f"),
            "total_energy_kcal": st.column_config.NumberColumn("kcal", format="%.0f"),
            "distance_km": st.column_config.NumberColumn("Distance (km)", format="%.2f"),
        },
        hide_index=True,
    )
