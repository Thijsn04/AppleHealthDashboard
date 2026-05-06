from __future__ import annotations

import pandas as pd
import streamlit as st
import altair as alt

from apple_health_dashboard.db import default_db_path
from apple_health_dashboard.services.filters import apply_date_filter
from apple_health_dashboard.web.page_utils import (
    load_all_records,
    page_header,
    sidebar_date_filter,
    sidebar_nav,
)

st.set_page_config(page_title="Symptoms · Apple Health Dashboard", page_icon="🤒", layout="wide")
page_header("🤒", "Symptoms", "Tracking headaches, fever, and other logged symptoms.")

db_path = default_db_path()

with st.sidebar:
    sidebar_nav(current="Symptoms")
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

# ── Data Processing ───────────────────────────────────────────────────────────
symptom_types = [
    "HKCategoryTypeIdentifierHeadache",
    "HKCategoryTypeIdentifierSoreThroat",
    "HKCategoryTypeIdentifierCoughing",
    "HKCategoryTypeIdentifierFever",
    "HKCategoryTypeIdentifierNausea",
    "HKCategoryTypeIdentifierFatigue",
]

symptoms = df_f[df_f["type"].isin(symptom_types)].copy()

if symptoms.empty:
    st.info("No symptoms logged in the selected period. You can log symptoms in the Apple Health app under Browse > Symptoms.")
else:
    # Summarize frequency
    symptoms["label"] = symptoms["type"].apply(lambda x: x.split("Identifier")[-1])
    freq = symptoms.groupby("label").size().reset_index(name="Count")
    
    c1, c2 = st.columns([1, 2])
    
    with c1:
        st.subheader("Symptom Frequency")
        st.dataframe(freq, hide_index=True, use_container_width=True)
        
    with c2:
        chart = alt.Chart(freq).mark_bar().encode(
            x=alt.X("Count:Q", title="Frequency (Logged instances)"),
            y=alt.Y("label:N", sort="-x", title="Symptom"),
            color=alt.Color("label:N", legend=None)
        ).properties(height=300)
        st.altair_chart(chart, use_container_width=True)

    st.divider()
    st.subheader("Symptom Timeline")
    symptoms["day"] = symptoms["start_at"].dt.floor("D")
    
    timeline = alt.Chart(symptoms).mark_circle(size=100).encode(
        x="day:T",
        y="label:N",
        color="label:N",
        tooltip=["day:T", "label:N", "value:N"]
    ).properties(height=300).interactive()
    st.altair_chart(timeline, use_container_width=True)
