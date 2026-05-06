from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from apple_health_dashboard.db import default_db_path
from apple_health_dashboard.services.filters import apply_date_filter
from apple_health_dashboard.web.charts import area_chart, bar_chart
from apple_health_dashboard.web.heatmaps import calendar_heatmap
from apple_health_dashboard.web.page_utils import (
    load_all_records,
    page_header,
    sidebar_date_filter,
    sidebar_nav,
)

st.set_page_config(page_title="Nutrition · Apple Health Dashboard", page_icon="🥗", layout="wide")
page_header("🥗", "Nutrition", "Dietary energy, macronutrients, and hydration tracking.")

db_path = default_db_path()

with st.sidebar:
    sidebar_nav(current="Nutrition")
    st.divider()

with st.spinner("Loading data…"):
    df = load_all_records(str(db_path))

if df.empty:
    st.warning("No data found. Please import your Apple Health export.")
    st.page_link("app.py", label="Go to Home →", icon="🏠")
    st.stop()

date_filter = sidebar_date_filter(df)
if date_filter is None:
    st.stop()

df_f = apply_date_filter(df, date_filter)

def get_daily_sum(df, record_type):
    sub = df[df["type"] == record_type].copy()
    if sub.empty: return pd.DataFrame()
    sub["value"] = pd.to_numeric(sub["value"], errors="coerce")
    sub["day"] = sub["start_at"].dt.floor("D")
    return sub.groupby("day")["value"].sum().reset_index()

# ── Data Processing ───────────────────────────────────────────────────────────
calories = get_daily_sum(df_f, "HKQuantityTypeIdentifierDietaryEnergyConsumed")
protein = get_daily_sum(df_f, "HKQuantityTypeIdentifierDietaryProtein")
carbs = get_daily_sum(df_f, "HKQuantityTypeIdentifierDietaryCarbohydrates")
fat = get_daily_sum(df_f, "HKQuantityTypeIdentifierDietaryFatTotal")
water = get_daily_sum(df_f, "HKQuantityTypeIdentifierDietaryWater")

tabs = st.tabs(["Overview", "Macronutrients", "Hydration"])

with tabs[0]:
    st.subheader("Daily Calorie Intake")
    if not calories.empty:
        st.altair_chart(area_chart(calories, "day", "value", "Calories (kcal)", color="#10B981"), use_container_width=True)
        
        st.divider()
        st.subheader("🗓️ Calorie Consistency")
        h_chart = calendar_heatmap(calories, "day", "value", color_scheme="greens")
        if h_chart:
            st.altair_chart(h_chart, use_container_width=True)
    else:
        st.info("No dietary energy data found.")

with tabs[1]:
    st.subheader("Macronutrient Breakdown")
    if not protein.empty or not carbs.empty or not fat.empty:
        # Combine for a stacked area chart
        protein["macro"] = "Protein (g)"
        carbs["macro"] = "Carbs (g)"
        fat["macro"] = "Fat (g)"
        combined = pd.concat([protein, carbs, fat])
        
        chart = alt.Chart(combined).mark_area().encode(
            x="day:T",
            y="value:Q",
            color=alt.Color("macro:N", scale=alt.Scale(scheme="category10")),
            tooltip=["day:T", "macro:N", "value:Q"]
        ).properties(height=350).interactive()
        st.altair_chart(chart, use_container_width=True)
    else:
        st.info("No macronutrient data found.")

with tabs[2]:
    st.subheader("Hydration")
    if not water.empty:
        st.altair_chart(bar_chart(water, "day", "value", "Water (mL)", color="#3B82F6"), use_container_width=True)
    else:
        st.info("No hydration (water) data found.")
