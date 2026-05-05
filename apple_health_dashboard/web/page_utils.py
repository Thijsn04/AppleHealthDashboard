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

# ── Global stylesheet ─────────────────────────────────────────────────────────
_GLOBAL_CSS = """<style>
/* ── Streamlit chrome ───────────────────────────── */
footer { visibility: hidden !important; }
#MainMenu { visibility: hidden !important; }
.stDeployButton { display: none !important; }
header[data-testid="stHeader"] { background: transparent !important; }

/* ── Layout ─────────────────────────────────────── */
.block-container { padding-top: 0.6rem !important; padding-bottom: 2rem !important; }

/* ── Typography ─────────────────────────────────── */
h1 { letter-spacing: -0.025em !important; font-weight: 800 !important; }
h2 { letter-spacing: -0.018em !important; font-weight: 700 !important; }
h3 { letter-spacing: -0.012em !important; }

/* ── Sidebar ─────────────────────────────────────── */
[data-testid="stSidebar"] {
  border-right: 1px solid rgba(46,125,110,0.14) !important;
}

/* ── Sidebar page-link nav items ─────────────────── */
[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"] {
  border-radius: 8px !important;
  padding: 4px 12px !important;
  margin-bottom: 2px !important;
  font-weight: 500 !important;
  font-size: 0.88rem !important;
  transition: background 0.15s ease !important;
}
[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"]:hover {
  background: rgba(46,125,110,0.10) !important;
}

/* ── Metric boxes ────────────────────────────────── */
[data-testid="metric-container"],
[data-testid="stMetric"] {
  background: rgba(46,125,110,0.04) !important;
  border: 1px solid rgba(46,125,110,0.11) !important;
  border-radius: 12px !important;
  padding: 0.85rem 1rem !important;
}

/* ── Shared card component ───────────────────────── */
.ahd-card {
  background: rgba(46,125,110,0.04);
  border: 1px solid rgba(46,125,110,0.14);
  padding: 16px 20px;
  border-radius: 12px;
  margin-bottom: 8px;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}
.ahd-card:hover {
  border-color: rgba(46,125,110,0.28);
  box-shadow: 0 3px 12px rgba(46,125,110,0.09);
}
.ahd-muted { font-size: 0.87rem; opacity: 0.70; line-height: 1.45; }

/* ── Active sidebar nav highlight ────────────────── */
.ahd-nav-active {
  padding: 5px 12px;
  border-radius: 8px;
  background: rgba(46,125,110,0.14);
  font-weight: 700;
  font-size: 0.88rem;
  color: #1A5048;
  margin-bottom: 2px;
  display: block;
  line-height: 1.6;
}

/* ── Tabs ────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
  gap: 2px;
  border-bottom: 2px solid rgba(46,125,110,0.10) !important;
}
.stTabs [data-baseweb="tab"] {
  border-radius: 8px 8px 0 0 !important;
  padding: 8px 18px !important;
  font-weight: 500 !important;
}
.stTabs [aria-selected="true"] {
  background: rgba(46,125,110,0.08) !important;
  color: #2E7D6E !important;
  font-weight: 700 !important;
}

/* ── Dataframes ──────────────────────────────────── */
[data-testid="stDataFrame"] {
  border-radius: 10px !important;
  overflow: hidden !important;
}

/* ── Dividers ────────────────────────────────────── */
hr {
  border: none !important;
  border-top: 1px solid rgba(46,125,110,0.12) !important;
  margin: 1.4rem 0 !important;
}

/* ── Buttons ─────────────────────────────────────── */
.stButton > button { border-radius: 8px !important; font-weight: 600 !important; }

/* ── Expanders ───────────────────────────────────── */
[data-testid="stExpander"] {
  border: 1px solid rgba(46,125,110,0.13) !important;
  border-radius: 10px !important;
}

/* ── Alert / info boxes ─────────────────────────── */
[data-testid="stAlert"] { border-radius: 10px !important; }

/* ── Home page nav cards ─────────────────────────── */
.ahd-nav-card {
  background: rgba(46,125,110,0.04);
  border: 1px solid rgba(46,125,110,0.14);
  border-radius: 12px;
  padding: 16px 18px 10px;
  margin-bottom: 4px;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
  min-height: 100px;
}
.ahd-nav-card:hover {
  border-color: rgba(46,125,110,0.30);
  box-shadow: 0 3px 14px rgba(46,125,110,0.10);
}
.ahd-nav-card-title { font-size: 0.95rem; font-weight: 700; color: #12312B; margin-bottom: 5px; }
.ahd-nav-card-desc  { font-size: 0.82rem; opacity: 0.62; line-height: 1.4; margin-bottom: 2px; }

/* ── Page-link buttons inside nav cards ─────────── */
.block-container a[data-testid="stPageLink-NavLink"] {
  font-weight: 600 !important;
  font-size: 0.82rem !important;
  color: #2E7D6E !important;
}
.block-container a[data-testid="stPageLink-NavLink"]:hover {
  text-decoration: underline !important;
}

/* ── Insight cards ───────────────────────────────── */
.insight-card {
  padding: 14px 18px; border-radius: 12px; margin-bottom: 10px;
  border-left: 4px solid;
}
.insight-positive { background: rgba(16,185,129,0.07); border-color: #10B981; }
.insight-negative { background: rgba(239,68,68,0.07);  border-color: #EF4444; }
.insight-neutral  { background: rgba(245,158,11,0.07); border-color: #F59E0B; }
.insight-info     { background: rgba(59,130,246,0.07); border-color: #3B82F6; }
.insight-title { font-weight: 700; font-size: 1.05rem; margin-bottom: 4px; }
.insight-body  { font-size: 0.92rem; opacity: 0.85; }
</style>"""


def inject_global_css() -> None:
    """Inject the global stylesheet. Call once per page after st.set_page_config()."""
    st.markdown(_GLOBAL_CSS, unsafe_allow_html=True)


def page_header(icon: str, title: str, subtitle: str = "") -> None:
    """Inject global CSS and render a polished page header.

    Replaces the plain ``st.title()`` + ``st.caption()`` pattern with a
    visually distinct header that has consistent typography and spacing.
    """
    inject_global_css()
    sub_html = (
        f'<div style="margin-top:4px;font-size:0.9rem;color:#12312B;opacity:0.58;">{subtitle}</div>'
        if subtitle
        else ""
    )
    st.markdown(
        f"""<div style="padding:0 0 14px 0;
                        border-bottom:1.5px solid rgba(46,125,110,0.14);
                        margin-bottom:1.4rem;">
  <div style="font-size:1.85rem;font-weight:800;letter-spacing:-0.026em;
              color:#0D2822;line-height:1.2;">
    {icon}&nbsp;{title}
  </div>
  {sub_html}
</div>""",
        unsafe_allow_html=True,
    )


def page_config(title: str, icon: str = "🍎") -> None:
    """Apply consistent page config."""
    st.set_page_config(page_title=f"{title} · Apple Health Dashboard", page_icon=icon, layout="wide")


def sidebar_date_filter(df: pd.DataFrame, *, current: str = "") -> DateFilter | None:
    """Render the standard date filter sidebar and return the selected filter.

    If *current* is provided the branded navigation is rendered above the date
    filter so it appears at the top of the sidebar on every content page.
    """
    with st.sidebar:
        if current:
            sidebar_nav(current=current)
            st.divider()
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
    """Render branded page navigation inside the sidebar."""
    st.markdown(
        """<div style="display:flex;align-items:center;gap:9px;
                       padding:4px 0 12px 0;
                       border-bottom:1px solid rgba(46,125,110,0.14);
                       margin-bottom:6px;">
          <span style="font-size:1.35rem;line-height:1;">🍎</span>
          <span style="font-size:0.95rem;font-weight:800;color:#0D2822;
                       letter-spacing:-0.022em;line-height:1.2;">Apple Health</span>
        </div>""",
        unsafe_allow_html=True,
    )
    for icon, label, page in _NAV_PAGES:
        is_current = label == current
        if is_current:
            st.markdown(
                f'<div class="ahd-nav-active">{icon}&nbsp;&nbsp;{label}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.page_link(page, label=f"{icon}  {label}")


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
