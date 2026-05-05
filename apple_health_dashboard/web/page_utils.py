from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from apple_health_dashboard.services.activity_summary import activity_summaries_to_dataframe
from apple_health_dashboard.services.filters import DateFilter, infer_date_filter
from apple_health_dashboard.services.stats import to_dataframe
from apple_health_dashboard.services.workouts import workouts_to_dataframe
from apple_health_dashboard.storage.sqlite_store import (
    init_db,
    iter_activity_summaries,
    iter_records,
    iter_workouts,
    open_db,
)


def page_config(title: str, icon: str = "🍎") -> None:
    """Apply consistent page config."""
    st.set_page_config(page_title=f"{title} · Apple Health Dashboard", page_icon=icon, layout="wide")


def sidebar_date_filter(df: pd.DataFrame) -> DateFilter | None:
    """Render the standard date filter sidebar and return the selected filter."""
    with st.sidebar:
        st.markdown("### 📅 Date Range")
        preset = st.selectbox("Preset", ["All", "7D", "30D", "90D", "180D", "1Y"], index=3)
        preset_filter = infer_date_filter(df, preset=preset)
        if preset_filter is None:
            return None

        use_custom = st.checkbox("Custom range", value=False)
        if use_custom:
            min_d = preset_filter.start.date()
            max_d = preset_filter.end.date()
            dates = st.date_input(
                "Date range",
                value=(min_d, max_d),
                min_value=min_d,
                max_value=max_d,
            )
            if isinstance(dates, (list, tuple)) and len(dates) == 2:
                start_d, end_d = dates
                return DateFilter(
                    start=pd.Timestamp(start_d, tz="UTC"),
                    end=pd.Timestamp(end_d, tz="UTC") + pd.Timedelta(days=1) - pd.Timedelta(seconds=1),
                )
        return preset_filter


@st.cache_data(ttl=300, show_spinner=False)
def load_all_records(db_path_str: str) -> pd.DataFrame:
    """Load all health records from SQLite (cached)."""
    db_path = Path(db_path_str)
    con = open_db(db_path)
    try:
        init_db(con)
        records = list(iter_records(con))
    finally:
        con.close()
    return to_dataframe(records)


@st.cache_data(ttl=300, show_spinner=False)
def load_all_workouts(db_path_str: str) -> pd.DataFrame:
    """Load all workout records from SQLite (cached)."""
    db_path = Path(db_path_str)
    con = open_db(db_path)
    try:
        init_db(con)
        rows = list(iter_workouts(con))
    finally:
        con.close()
    return workouts_to_dataframe(rows)


@st.cache_data(ttl=300, show_spinner=False)
def load_all_activity_summaries(db_path_str: str) -> pd.DataFrame:
    """Load all activity-ring summaries from SQLite (cached)."""
    db_path = Path(db_path_str)
    con = open_db(db_path)
    try:
        init_db(con)
        rows = list(iter_activity_summaries(con))
    finally:
        con.close()
    return activity_summaries_to_dataframe(rows)


_NAV_PAGES = [
    ("🏠", "Home", "app.py"),
    ("📊", "Overview", "pages/1_📊_Overview.py"),
    ("❤️", "Heart", "pages/2_❤️_Heart.py"),
    ("🏃", "Activity", "pages/3_🏃_Activity.py"),
    ("😴", "Sleep", "pages/4_😴_Sleep.py"),
    ("🏋️", "Workouts", "pages/5_🏋️_Workouts.py"),
    ("🔥", "Rings", "pages/6_🔥_Rings.py"),
    ("⚖️", "Body", "pages/7_⚖️_Body.py"),
    ("🔬", "Explorer", "pages/8_🔬_Explorer.py"),
    ("💡", "Insights", "pages/9_💡_Insights.py"),
]


def sidebar_nav(*, current: str = "") -> None:
    """Render page navigation links inside the sidebar."""
    st.markdown("### 🗺️ Navigation")
    for icon, label, page in _NAV_PAGES:
        is_current = label == current
        if is_current:
            st.markdown(
                f"<div style='padding:4px 8px;border-radius:8px;"
                f"background:rgba(46,125,110,0.15);font-weight:700;margin-bottom:2px;'>"
                f"{icon} {label}</div>",
                unsafe_allow_html=True,
            )
        else:
            st.page_link(page, label=f"{icon} {label}")


def require_data(db_path: Path) -> pd.DataFrame | None:
    """Load data and show an error if database is empty."""
    df = load_all_records(str(db_path))
    if df.empty:
        st.warning(
            "No data in the database yet. "
            "Please upload and import your Apple Health export on the **Home** page."
        )
        st.page_link("app.py", label="Go to Home →", icon="🏠")
        return None
    return df


def metric_delta(current: float, previous: float, unit: str = "", *, lower_is_better: bool = False) -> str:
    """Format a delta string with direction indicator."""
    diff = current - previous
    if diff == 0:
        return "—"
    sign = "+" if diff > 0 else ""
    better = (diff < 0) == lower_is_better
    arrow = "▲" if diff > 0 else "▼"
    return f"{arrow} {sign}{diff:.1f}{unit}"


def stat_metric(col, label: str, value: str, delta: str | None = None, help: str | None = None) -> None:
    """Render a styled metric."""
    with col:
        st.metric(label=label, value=value, delta=delta, help=help)
