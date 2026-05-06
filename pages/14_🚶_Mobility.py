from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from apple_health_dashboard.db import default_db_path
from apple_health_dashboard.services.filters import apply_date_filter
from apple_health_dashboard.web.charts import line_chart
from apple_health_dashboard.web.page_utils import (
    load_all_records,
    page_header,
    sidebar_date_filter,
    sidebar_nav,
)

st.set_page_config(page_title="Mobility · Apple Health Dashboard", page_icon="🚶", layout="wide")
page_header("🚶", "Mobility", "Walking steadiness, asymmetry, and speed analytics.")

db_path = default_db_path()

with st.sidebar:
    sidebar_nav(current="Mobility")
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

def get_daily_avg(df, record_type):
    sub = df[df["type"] == record_type].copy()
    if sub.empty: return pd.DataFrame()
    sub["value"] = pd.to_numeric(sub["value"], errors="coerce")
    sub["day"] = sub["start_at"].dt.floor("D")
    return sub.groupby("day")["value"].mean().reset_index()

# ── Data Processing ───────────────────────────────────────────────────────────
steadiness = get_daily_avg(df_f, "HKQuantityTypeIdentifierWalkingSteadiness")
asymmetry = get_daily_avg(df_f, "HKQuantityTypeIdentifierWalkingAsymmetryPercentage")
double_support = get_daily_avg(df_f, "HKQuantityTypeIdentifierWalkingDoubleSupportPercentage")
walking_speed = get_daily_avg(df_f, "HKQuantityTypeIdentifierWalkingSpeed")

st.info("Mobility metrics like walking steadiness and asymmetry require an Apple Watch (Series 6 or later) or an iPhone (8 or later) carried in a waistband pocket or close to your center of gravity.")

c1, c2 = st.columns(2)

with c1:
    st.subheader("Walking Speed")
    if not walking_speed.empty:
        st.altair_chart(line_chart(walking_speed, "day", "value", "Speed (km/h)", color="#10B981"), use_container_width=True)
    else:
        st.info("No walking speed data found.")

with c2:
    st.subheader("Walking Steadiness")
    if not steadiness.empty:
        st.altair_chart(line_chart(steadiness, "day", "value", "Steadiness (%)", color="#3B82F6"), use_container_width=True)
    else:
        st.info("No walking steadiness data found.")

st.divider()
c3, c4 = st.columns(2)

with c3:
    st.subheader("Walking Asymmetry")
    if not asymmetry.empty:
        st.altair_chart(line_chart(asymmetry, "day", "value", "Asymmetry (%)", color="#EF4444"), use_container_width=True)
        st.caption("Lower is better. High asymmetry may indicate injury or mobility issues.")
    else:
        st.info("No walking asymmetry data found.")

with c4:
    st.subheader("Double Support %")
    if not double_support.empty:
        st.altair_chart(line_chart(double_support, "day", "value", "Double Support (%)", color="#F59E0B"), use_container_width=True)
    else:
        st.info("No double support data found.")
