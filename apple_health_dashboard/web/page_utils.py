from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from apple_health_dashboard.db import default_db_path
from apple_health_dashboard.services.filters import DateFilter, apply_date_filter, infer_date_filter
from apple_health_dashboard.storage.sqlite_store import init_db, iter_records, open_db
from apple_health_dashboard.services.stats import to_dataframe


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
