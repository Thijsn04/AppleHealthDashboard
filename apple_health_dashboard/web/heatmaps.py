from __future__ import annotations

import altair as alt
import pandas as pd

def calendar_heatmap(df: pd.DataFrame, date_col: str, value_col: str, title: str = "", color_scheme: str = "greens"):
    """
    Creates a GitHub-style calendar heatmap.
    """
    if df.empty:
        return None

    df_h = df.copy()
    df_h[date_col] = pd.to_datetime(df_h[date_col])
    
    # Extract time features
    df_h["month"] = df_h[date_col].dt.month
    df_h["year"] = df_h[date_col].dt.year
    df_h["week"] = df_h[date_col].dt.isocalendar().week
    df_h["day_of_week"] = df_h[date_col].dt.dayofweek  # 0=Mon, 6=Sun
    df_h["day"] = df_h[date_col].dt.date  # overwrite last — keep datetime for .dt above
    
    # Map day names
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    df_h["day_name"] = df_h["day_of_week"].apply(lambda x: days[x])

    chart = alt.Chart(df_h).mark_rect(
        stroke="white",
        strokeWidth=1,
        cornerRadius=2
    ).encode(
        x=alt.X("week:O", title="Week of Year", axis=alt.Axis(labels=False, ticks=False, domain=False)),
        y=alt.Y("day_name:O", title="", sort=days),
        color=alt.Color(f"{value_col}:Q", scale=alt.Scale(scheme=color_scheme), legend=None),
        tooltip=[
            alt.Tooltip(f"{date_col}:T", title="Date"),
            alt.Tooltip(f"{value_col}:Q", title="Value", format=".1f")
        ]
    ).properties(
        width="container",
        height=180,
        title=title
    ).configure_view(
        strokeWidth=0
    ).configure_axis(
        labelFontSize=10,
        titleFontSize=12
    )

    return chart

def hourly_heatmap(df: pd.DataFrame, time_col: str, value_col: str, title: str = ""):
    """
    Creates an hourly heatmap (Days vs Hours).
    """
    if df.empty:
        return None

    df_h = df.copy()
    df_h[time_col] = pd.to_datetime(df_h[time_col])
    df_h["hour"] = df_h[time_col].dt.hour
    df_h["day_name"] = df_h[time_col].dt.strftime("%a")
    days_order = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    chart = alt.Chart(df_h).mark_rect().encode(
        x=alt.X("hour:O", title="Hour of Day"),
        y=alt.Y("day_name:O", title="", sort=days_order),
        color=alt.Color(f"{value_col}:Q", scale=alt.Scale(scheme="viridis")),
        tooltip=[
            alt.Tooltip("day_name:O", title="Day"),
            alt.Tooltip("hour:O", title="Hour"),
            alt.Tooltip(f"{value_col}:Q", title="Avg Value", format=".1f")
        ]
    ).properties(
        width="container",
        height=250,
        title=title
    )

    return chart
