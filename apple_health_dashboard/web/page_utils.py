from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from apple_health_dashboard.services.activity_summary import activity_summaries_to_dataframe
from apple_health_dashboard.services.filters import DateFilter, infer_date_filter
from apple_health_dashboard.services.stats import to_dataframe
from apple_health_dashboard.services.workouts import workouts_to_dataframe
from apple_health_dashboard.storage.duckdb_store import (
    init_db,
    iter_activity_summaries,
    iter_records,
    iter_workouts,
    open_db,
)

# ── Global stylesheet ─────────────────────────────────────────────────────────
_GLOBAL_CSS = """<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700;800&family=Inter:wght@400;500;600;700;800&display=swap');

:root {
  --primary: #10B981;
  --secondary: #2E7D6E;
  --bg-dark: #0F172A;
  --glass-white: rgba(255, 255, 255, 0.08);
  --glass-border: rgba(255, 255, 255, 0.12);
}

html, body, [class*="css"] {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
}

h1, h2, .ahd-hero-title {
  font-family: 'Outfit', sans-serif !important;
}

footer { visibility: hidden !important; }
#MainMenu { visibility: hidden !important; }
.stDeployButton { display: none !important; }
header[data-testid="stHeader"] { background: transparent !important; }

@keyframes ahd-fadein {
  from { opacity: 0; transform: translateY(8px); }
  to   { opacity: 1; transform: translateY(0); }
}
.block-container {
  padding-top: 0.6rem !important;
  padding-bottom: 2rem !important;
  animation: ahd-fadein 0.4s cubic-bezier(0.16, 1, 0.3, 1) both;
}

@keyframes ahd-gradient {
  0%   { background-position: 0% 50%; }
  50%  { background-position: 100% 50%; }
  100% { background-position: 0% 50%; }
}
.ahd-hero {
  background: linear-gradient(-45deg, #0D2822, #1a5048, #2E7D6E, #10B981);
  background-size: 400% 400%;
  animation: ahd-gradient 12s ease infinite;
  border-radius: 20px;
  padding: 32px 36px 28px;
  margin-bottom: 2rem;
  color: white;
  box-shadow: 0 10px 30px -10px rgba(16, 185, 129, 0.3);
}
.ahd-hero-title {
  font-size: 2.2rem; font-weight: 800;
  letter-spacing: -0.04em; line-height: 1.1;
  color: white; margin-bottom: 8px;
}
.ahd-hero-sub {
  font-size: 1rem; opacity: 0.85; color: white;
  font-weight: 400;
}

[data-testid="stSidebar"] {
  border-right: 1px solid rgba(16, 185, 129, 0.1) !important;
  background: rgba(255, 255, 255, 0.02) !important;
}

[data-testid="stMetric"] {
  background: rgba(255, 255, 255, 0.03) !important;
  border: 1px solid rgba(255, 255, 255, 0.08) !important;
  border-radius: 12px !important;
  padding: 16px !important;
  transition: all 0.2s ease !important;
}
[data-testid="stMetric"]:hover {
  background: rgba(255, 255, 255, 0.06) !important;
  transform: translateY(-2px) !important;
  box-shadow: 0 4px 12px rgba(0,0,0,0.1) !important;
}

.stTabs [data-baseweb="tab-list"] {
  gap: 8px;
  background-color: transparent !important;
}
.stTabs [data-baseweb="tab"] {
  height: 40px;
  white-space: pre-wrap;
  background-color: rgba(255, 255, 255, 0.05) !important;
  border-radius: 8px !important;
  border: 1px solid transparent !important;
  padding: 8px 16px !important;
  font-weight: 500 !important;
}
.stTabs [aria-selected="true"] {
  background-color: rgba(16, 185, 129, 0.15) !important;
  border: 1px solid rgba(16, 185, 129, 0.3) !important;
  color: #10B981 !important;
}
</style>"""
  border-color: rgba(46,125,110,0.2) !important;
}


.ahd-card {
  background: rgba(255, 255, 255, 0.65);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid rgba(46,125,110,0.08);
  padding: 18px 22px; border-radius: 16px;
  margin-bottom: 12px;
  transition: transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1), border-color 0.3s ease, box-shadow 0.3s ease;
}
.ahd-card:hover {
  transform: translateY(-2px);
  border-color: rgba(46,125,110,0.25);
  box-shadow: 0 8px 24px rgba(46,125,110,0.06);
}
.ahd-muted { font-size: 0.87rem; opacity: 0.68; line-height: 1.45; }


.ahd-score-badge {
  display: inline-flex; align-items: center; justify-content: center;
  width: 80px; height: 80px; border-radius: 50%;
  font-size: 1.8rem; font-weight: 800;
  border: 3px solid;
  margin-bottom: 8px;
}
.ahd-score-green  { color: #10B981; border-color: #10B981; background: rgba(16,185,129,0.08); }
.ahd-score-yellow { color: #F59E0B; border-color: #F59E0B; background: rgba(245,158,11,0.08); }
.ahd-score-red    { color: #EF4444; border-color: #EF4444; background: rgba(239,68,68,0.08); }


.ahd-ring-wrap { display: flex; flex-direction: column; align-items: center; gap: 4px; }
.ahd-ring-label { font-size: 0.75rem; font-weight: 600; opacity: 0.65; letter-spacing: 0.04em; text-transform: uppercase; }
.ahd-ring-val   { font-size: 0.88rem; font-weight: 700; }


.ahd-nav-active {
  padding: 0.375rem 0.75rem; border-radius: 8px;
  background: rgba(46,125,110,0.16);
  font-weight: 600; font-size: 1rem;
  color: #1A5048; margin-bottom: 2px;
  display: flex; align-items: center; gap: 0.75rem;
  line-height: 1.5;
  border-left: 3px solid #2E7D6E;
}


.stTabs [data-baseweb="tab-list"] {
  gap: 2px;
  border-bottom: 2px solid rgba(46,125,110,0.12) !important;
}
.stTabs [data-baseweb="tab"] {
  border-radius: 8px 8px 0 0 !important;
  padding: 8px 20px !important;
  font-weight: 500 !important;
  transition: background 0.15s ease !important;
}
.stTabs [aria-selected="true"] {
  background: rgba(46,125,110,0.10) !important;
  color: #2E7D6E !important;
  font-weight: 700 !important;
}


[data-testid="stDataFrame"] {
  border-radius: 12px !important;
  overflow: hidden !important;
  border: 1px solid rgba(46,125,110,0.10) !important;
}


hr {
  border: none !important;
  border-top: 1px solid rgba(46,125,110,0.12) !important;
  margin: 1.5rem 0 !important;
}


.stButton > button {
  border-radius: 8px !important;
  font-weight: 600 !important;
  transition: transform 0.12s ease, box-shadow 0.12s ease !important;
}
.stButton > button:hover {
  transform: translateY(-1px) !important;
  box-shadow: 0 4px 12px rgba(46,125,110,0.18) !important;
}


[data-testid="stExpander"] {
  border: 1px solid rgba(46,125,110,0.14) !important;
  border-radius: 12px !important;
  transition: border-color 0.2s ease !important;
}
[data-testid="stExpander"]:hover {
  border-color: rgba(46,125,110,0.26) !important;
}


[data-testid="stAlert"] { border-radius: 10px !important; }


.ahd-nav-card {
  background: rgba(46,125,110,0.04);
  border: 1px solid rgba(46,125,110,0.14);
  border-radius: 14px;
  padding: 18px 20px 12px;
  margin-bottom: 6px;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
  min-height: 100px;
}
.ahd-nav-card:hover {
  border-color: rgba(46,125,110,0.32);
  box-shadow: 0 6px 20px rgba(46,125,110,0.12);
  transform: translateY(-2px);
}
.ahd-nav-card-title { font-size: 0.96rem; font-weight: 700; color: #0D2822; margin-bottom: 6px; }
.ahd-nav-card-desc  { font-size: 0.82rem; opacity: 0.62; line-height: 1.4; margin-bottom: 4px; }
.ahd-nav-card-count { font-size: 0.75rem; opacity: 0.45; font-weight: 500; }


.block-container a[data-testid="stPageLink-NavLink"] {
  font-weight: 600 !important;
  font-size: 0.82rem !important;
  color: #2E7D6E !important;
}
.block-container a[data-testid="stPageLink-NavLink"]:hover {
  text-decoration: underline !important;
}


.insight-card {
  padding: 14px 18px; border-radius: 12px; margin-bottom: 10px;
  border-left: 4px solid;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}
.insight-card:hover { transform: translateX(2px); }
.insight-positive { background: rgba(16,185,129,0.07); border-color: #10B981; }
.insight-negative { background: rgba(239,68,68,0.07);  border-color: #EF4444; }
.insight-neutral  { background: rgba(245,158,11,0.07); border-color: #F59E0B; }
.insight-info     { background: rgba(59,130,246,0.07); border-color: #3B82F6; }
.insight-title { font-weight: 700; font-size: 1.0rem; margin-bottom: 5px; }
.insight-body  { font-size: 0.88rem; opacity: 0.84; line-height: 1.5; }


.ahd-ring-dots { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; margin: 4px 0; }
.ahd-dot { width: 24px; height: 24px; border-radius: 50%; display: inline-flex;
           align-items: center; justify-content: center; font-size: 0.65rem; font-weight: 700;
           color: white; flex-shrink: 0; }
.ahd-dot-green  { background: #10B981; }
.ahd-dot-red    { background: #EF4444; }
.ahd-dot-yellow { background: #F59E0B; }
.ahd-dot-gray   { background: #CBD5E1; }


.ahd-pill {
  display: inline-flex; align-items: center; gap: 3px;
  padding: 2px 8px; border-radius: 20px;
  font-size: 0.75rem; font-weight: 700;
}
.ahd-pill-up   { background: rgba(16,185,129,0.12); color: #059669; }
.ahd-pill-down { background: rgba(239,68,68,0.12); color: #DC2626; }
.ahd-pill-flat { background: rgba(148,163,184,0.15); color: #64748B; }


.ahd-footer {
  margin-top: 3rem; padding: 12px 0 6px;
  border-top: 1px solid rgba(46,125,110,0.12);
  font-size: 0.78rem; opacity: 0.45;
  display: flex; gap: 16px; flex-wrap: wrap;
}


.ahd-report-card {
  background: linear-gradient(135deg, rgba(46,125,110,0.06), rgba(16,185,129,0.04));
  border: 1px solid rgba(46,125,110,0.18);
  border-radius: 16px; padding: 20px 24px; margin-bottom: 12px;
}
.ahd-report-title { font-size: 1.1rem; font-weight: 800; color: #0D2822; margin-bottom: 8px; }
.ahd-report-row   { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 6px; }
.ahd-report-badge {
  display: inline-flex; align-items: center; gap: 4px;
  background: rgba(255,255,255,0.7); border: 1px solid rgba(46,125,110,0.16);
  border-radius: 20px; padding: 4px 10px;
  font-size: 0.8rem; font-weight: 600; color: #1A5048;
}


@media (max-width: 768px) {
  .ahd-hero { padding: 18px 18px 14px; }
  .ahd-hero-title { font-size: 1.5rem; }
  .block-container { padding-left: 0.5rem !important; padding-right: 0.5rem !important; }
}


.ahd-sticky-bar {
  position: sticky; top: 0; z-index: 100;
  background: rgba(255,255,255,0.92);
  backdrop-filter: blur(10px);
  border-bottom: 1px solid rgba(46,125,110,0.12);
  padding: 8px 0; margin-bottom: 12px;
  display: flex; gap: 20px; flex-wrap: wrap; align-items: center;
}
.ahd-sticky-item { font-size: 0.82rem; font-weight: 600; color: #1A5048; }
.ahd-sticky-val  { font-size: 0.95rem; font-weight: 800; color: #0D2822; }

[data-testid="stSidebarNav"] { display: none !important; }
</style>
"""


def inject_global_css() -> None:
    """Inject the global stylesheet. Call once per page after st.set_page_config()."""
    theme = st.session_state.get("theme", "Standard Glass")
    css = _GLOBAL_CSS
    
    if theme == "High Contrast":
        css += """
        <style>
        :root { --ahd-glass: rgba(255,255,255,1) !important; --ahd-border: #000 !important; }
        .ahd-nav-active { background: #000 !important; color: #fff !important; }
        </style>
        """
    elif theme == "OLED Dark":
        css += """
        <style>
        :root { --ahd-glass: rgba(20,20,20,0.8) !important; --ahd-bg: #000 !important; }
        body, .main { background-color: #000 !important; color: #fff !important; }
        </style>
        """
    st.markdown(css, unsafe_allow_html=True)


def page_header(icon: str, title: str, subtitle: str = "") -> None:
    """Inject global CSS and render a polished page header."""
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


def page_footer(db_path: Path | None = None) -> None:
    """Render a subtle footer with database info."""
    parts = ["🍎 Apple Health Dashboard"]
    if db_path and db_path.exists():
        size_mb = db_path.stat().st_size / 1_048_576
        parts.append(f"DB: {db_path.name} ({size_mb:.1f} MB)")
    st.markdown(
        f'<div class="ahd-footer">' + " &middot; ".join(parts) + "</div>",
        unsafe_allow_html=True,
    )


def score_badge(score: float) -> str:
    """Return HTML for a circular score badge."""
    cls = "ahd-score-green" if score >= 60 else ("ahd-score-yellow" if score >= 40 else "ahd-score-red")
    return f'<div class="ahd-score-badge {cls}">{score:.0f}</div>'


def ring_dots_html(days: list[bool | None]) -> str:
    """Return HTML for a row of colored dots (True=green, False=red, None=gray)."""
    dots = []
    for d in days:
        if d is True:
            dots.append('<span class="ahd-dot ahd-dot-green">✓</span>')
        elif d is False:
            dots.append('<span class="ahd-dot ahd-dot-red">✗</span>')
        else:
            dots.append('<span class="ahd-dot ahd-dot-gray">·</span>')
    return f'<div class="ahd-ring-dots">{"".join(dots)}</div>'


def trend_pill(delta: float, unit: str = "", *, lower_is_better: bool = False) -> str:
    """Return a colored trend pill HTML snippet."""
    if abs(delta) < 0.01:
        return '<span class="ahd-pill ahd-pill-flat">→ Stable</span>'
    going_up = delta > 0
    good = going_up != lower_is_better
    arrow = "↑" if going_up else "↓"
    css = "ahd-pill-up" if good else "ahd-pill-down"
    sign = "+" if going_up else ""
    return f'<span class="ahd-pill {css}">{arrow} {sign}{delta:.1f}{unit}</span>'


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
    """Load all health records from DuckDB (cached)."""
    db_path = Path(db_path_str)
    con = open_db(db_path)
    try:
        init_db(con)
        try:
            df = con.execute("SELECT * FROM health_record").df()
            for col in ["start_at", "end_at", "creation_at"]:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], utc=True, errors="coerce")
            return df
        except Exception:
            return pd.DataFrame()
    finally:
        con.close()


@st.cache_data(ttl=300, show_spinner=False)
def load_all_workouts(db_path_str: str) -> pd.DataFrame:
    """Load all workout records from DuckDB (cached)."""
    db_path = Path(db_path_str)
    con = open_db(db_path)
    try:
        init_db(con)
        try:
            df = con.execute("SELECT * FROM workout").df()
            for col in ["start_at", "end_at", "creation_at"]:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], utc=True, errors="coerce")
            return df
        except Exception:
            return pd.DataFrame()
    finally:
        con.close()


@st.cache_data(ttl=300, show_spinner=False)
def load_all_activity_summaries(db_path_str: str) -> pd.DataFrame:
    """Load all activity-ring summaries from DuckDB (cached)."""
    db_path = Path(db_path_str)
    con = open_db(db_path)
    try:
        init_db(con)
        try:
            df = con.execute("SELECT * FROM activity_summary").df()
            if "day" in df.columns:
                df["day"] = pd.to_datetime(df["day"], utc=True, errors="coerce")
            return df
        except Exception:
            return pd.DataFrame()
    finally:
        con.close()


_NAV_SECTIONS = {
    "Dashboards": [
        ("🏠", "Home", "app.py"),
        ("📊", "Overview", "pages/1_📊_Overview.py"),
        ("💡", "Insights", "pages/9_💡_Insights.py"),
        ("📈", "Trends", "pages/11_📈_Trends.py"),
        ("🤖", "Health Chat", "pages/12_🤖_Health_Chat.py"),
    ],
    "Health Metrics": [
        ("❤️", "Heart", "pages/2_❤️_Heart.py"),
        ("🏃", "Activity", "pages/3_🏃_Activity.py"),
        ("😴", "Sleep", "pages/4_😴_Sleep.py"),
        ("🏋️", "Workouts", "pages/5_🏋️_Workouts.py"),
        ("🔥", "Rings", "pages/6_🔥_Rings.py"),
        ("⚖️", "Body", "pages/7_⚖️_Body.py"),
        ("🥗", "Nutrition", "pages/13_🥗_Nutrition.py"),
        ("🚶", "Mobility", "pages/14_🚶_Mobility.py"),
        ("🤒", "Symptoms", "pages/15_🤒_Symptoms.py"),
    ],
    "Tools": [
        ("🔬", "Explorer", "pages/8_🔬_Explorer.py"),
        ("⚙️", "Settings", "pages/10_⚙️_Settings.py"),
    ]
}

def sidebar_nav(*, current: str = "") -> None:
    """Render branded page navigation inside the sidebar."""
    st.markdown(
        """<div style="display:flex;align-items:center;gap:9px;
                       padding:4px 0 12px 0;
                       border-bottom:1px solid rgba(46,125,110,0.14);
                       margin-bottom:16px;">
          <span style="font-size:1.35rem;line-height:1;">🍎</span>
          <span style="font-size:0.95rem;font-weight:800;color:#0D2822;
                       letter-spacing:-0.022em;line-height:1.2;">Apple Health</span>
        </div>""",
        unsafe_allow_html=True,
    )
    for section_name, pages in _NAV_SECTIONS.items():
        st.markdown(f'<div style="font-size:0.75rem;font-weight:700;color:#2E7D6E;opacity:0.8;text-transform:uppercase;letter-spacing:0.05em;margin:12px 0 4px 6px;">{section_name}</div>', unsafe_allow_html=True)
        for icon, label, page in pages:
            is_current = label == current
            if is_current:
                st.markdown(
                    f'<div class="ahd-nav-active" style="margin-bottom:2px;"><span>{icon}</span><span>{label}</span></div>',
                    unsafe_allow_html=True,
                )
            else:
                st.page_link(page, label=label, icon=icon)
        st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)


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
    arrow = "▲" if diff > 0 else "▼"
    return f"{arrow} {sign}{diff:.1f}{unit}"


def stat_metric(col, label: str, value: str, delta: str | None = None, help: str | None = None) -> None:
    """Render a styled metric."""
    with col:
        st.metric(label=label, value=value, delta=delta, help=help)
