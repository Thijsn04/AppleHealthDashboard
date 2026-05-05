from __future__ import annotations

import logging
import time
import zipfile
from pathlib import Path

import streamlit as st

from apple_health_dashboard.db import default_db_path
from apple_health_dashboard.ingest.importer import import_export_xml_to_sqlite_all
from apple_health_dashboard.local_data import delete_local_data
from apple_health_dashboard.logging_config import configure_logging
from apple_health_dashboard.storage.sqlite_store import (
    init_db,
    list_record_types,
    open_db,
)
from apple_health_dashboard.web.ui import apply_base_ui, info_card, Brand
from apple_health_dashboard.web.page_utils import sidebar_nav

logger = logging.getLogger(__name__)


def _save_uploaded_file_to_tmp(uploaded_file) -> Path:
    tmp_dir = Path(st.session_state.get("tmp_dir", Path.cwd() / ".tmp"))
    tmp_dir.mkdir(parents=True, exist_ok=True)
    dst = tmp_dir / uploaded_file.name
    dst.write_bytes(uploaded_file.getbuffer())
    return dst


def _extract_export_xml_from_zip(zip_path: Path) -> Path:
    tmp_dir = Path(st.session_state.get("tmp_dir", Path.cwd() / ".tmp"))
    tmp_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        candidates = [n for n in zf.namelist() if n.endswith("export.xml")]
        if not candidates:
            raise ValueError("No export.xml found in the zip.")
        export_name = sorted(candidates, key=len)[0]
        out_path = tmp_dir / "export.xml"
        out_path.write_bytes(zf.read(export_name))
        return out_path


def _db_stats(db_path: Path) -> dict[str, int]:
    """Return basic counts from the database."""
    try:
        con = open_db(db_path)
        init_db(con)
        try:
            n_records = con.execute("SELECT COUNT(*) FROM health_record").fetchone()[0]
            n_workouts = con.execute("SELECT COUNT(*) FROM workout").fetchone()[0]
            n_days = con.execute("SELECT COUNT(*) FROM activity_summary").fetchone()[0]
            n_types = len(list_record_types(con))
        finally:
            con.close()
        return {
            "records": n_records,
            "workouts": n_workouts,
            "ring_days": n_days,
            "record_types": n_types,
        }
    except Exception:
        return {}


def main() -> None:
    configure_logging()

    st.set_page_config(
        page_title="Apple Health Dashboard",
        page_icon="🍎",
        layout="wide",
    )

    st.markdown(
        """
<style>
.block-container { padding-top: 2rem; padding-bottom: 2rem; }
h1, h2, h3 { letter-spacing: -0.01em; }
.ahd-card {
  background: rgba(46, 125, 110, 0.06);
  border: 1px solid rgba(46, 125, 110, 0.18);
  padding: 16px 20px;
  border-radius: 14px;
  margin-bottom: 8px;
}
.ahd-muted { opacity: 0.85; font-size: 0.9rem; }
hr { margin: 1.2rem 0; opacity: 0.25; }
[data-testid="stDataFrame"] { border-radius: 12px; }
.stat-num { font-size: 2rem; font-weight: 700; color: #2E7D6E; }
.stat-label { font-size: 0.82rem; opacity: 0.7; text-transform: uppercase; letter-spacing: 0.06em; }
</style>
""",
        unsafe_allow_html=True,
    )

    # ── Header ───────────────────────────────────────────────────────────────
    col_title, col_badge = st.columns([3, 1])
    with col_title:
        st.title("🍎 Apple Health Dashboard")
        st.caption("100% local · privacy-first · all your health data in one place")

    db_path = default_db_path()
    stats = _db_stats(db_path)

    # ── Sidebar ──────────────────────────────────────────────────────────────
    with st.sidebar:
        st.header("📥 Import Data")
        st.write(
            "Upload your **export.xml** or **export.zip** from the Apple Health app."
        )
        st.caption("*How to export:* Apple Health → Profile → Export All Health Data")

        uploaded = st.file_uploader(
            "Choose file",
            type=["xml", "zip"],
            accept_multiple_files=False,
        )

        export_xml_path: Path | None = None
        if uploaded is not None:
            saved_path = _save_uploaded_file_to_tmp(uploaded)
            if saved_path.suffix.lower() == ".zip":
                try:
                    export_xml_path = _extract_export_xml_from_zip(saved_path)
                except ValueError as e:
                    st.error(str(e))
            else:
                export_xml_path = saved_path
            st.success(f"✓ File loaded: {saved_path.name}")

        st.divider()

        col_a, col_b = st.columns(2)
        with col_a:
            import_clicked = st.button(
                "Import →",
                type="primary",
                use_container_width=True,
                disabled=(export_xml_path is None),
            )
        with col_b:
            refresh_clicked = st.button("Refresh", use_container_width=True)

        st.caption(f"Database: `{db_path.name}`")

        st.divider()

        with st.expander("🗑️ Delete local data", expanded=False):
            st.write(
                "Permanently delete all locally stored data (database + temporary files)."
            )
            confirm = st.checkbox("Yes, delete everything")
            if st.button("Delete", type="secondary", disabled=not confirm):
                delete_local_data()
                st.success("Local data deleted.")
                st.rerun()

        st.divider()
        sidebar_nav(current="Home")

    # ── Import ────────────────────────────────────────────────────────────────
    if export_xml_path is not None and import_clicked:
        progress = st.progress(0, text="Starting import…")
        status = st.empty()

        def on_progress(stage: str, processed: int) -> None:
            label = "Records" if stage == "records" else "Workouts"
            pct = min((processed % 5000) / 5000.0, 0.99)
            progress.progress(pct, text=f"{label}: {processed:,} processed")
            status.write(f"⚙️ {label}: {processed:,} processed…")

        t0 = time.perf_counter()
        with st.spinner("Importing into SQLite (this may take 1–5 minutes for large exports)…"):
            try:
                counters = import_export_xml_to_sqlite_all(
                    export_xml_path,
                    db_path,
                    on_progress=on_progress,
                )
            except Exception as exc:
                st.error(f"Import failed: {exc}")
                logger.exception("Import failed")
                st.stop()

        dt = time.perf_counter() - t0
        progress.progress(1.0, text="Done ✓")
        status.empty()

        st.success(
            f"✅ Import complete in {dt:.1f}s · "
            f"Records: **{counters['records_inserted']:,}** · "
            f"Activity days: **{counters['activity_summaries_inserted']:,}** · "
            f"Workouts: **{counters['workouts_inserted']:,}**"
        )
        st.balloons()
        stats = _db_stats(db_path)

    if refresh_clicked:
        st.cache_data.clear()
        st.toast("Cache cleared — data reloaded")
        stats = _db_stats(db_path)

    # ── Info cards ───────────────────────────────────────────────────────────
    st.subheader("Your Data at a Glance")

    if stats:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Health Records", f"{stats.get('records', 0):,}")
        c2.metric("Workouts", f"{stats.get('workouts', 0):,}")
        c3.metric("Activity Ring Days", f"{stats.get('ring_days', 0):,}")
        c4.metric("Record Types", f"{stats.get('record_types', 0):,}")
    else:
        st.info(
            "No data imported yet. Upload your Apple Health export and click **Import →**"
        )

    st.divider()

    # ── Navigation cards ─────────────────────────────────────────────────────
    st.subheader("Explore your health data")
    st.caption("Use the sidebar to navigate between pages, or click a card below.")

    nav = [
        ("📊 Overview", "pages/1_📊_Overview.py", "Key metrics, trends & highlights at a glance."),
        ("❤️ Heart Health", "pages/2_❤️_Heart.py", "HR, HRV, VO₂ max, blood pressure & SpO₂."),
        ("🏃 Activity", "pages/3_🏃_Activity.py", "Steps, distance, calories & active minutes."),
        ("😴 Sleep", "pages/4_😴_Sleep.py", "Sleep stages, duration & consistency."),
        ("🏋️ Workouts", "pages/5_🏋️_Workouts.py", "All workout types, personal records & streaks."),
        ("🔥 Rings", "pages/6_🔥_Rings.py", "Activity ring completion, goals & streaks."),
        ("⚖️ Body", "pages/7_⚖️_Body.py", "Weight, BMI, body fat & composition trends."),
        ("🔬 Explorer", "pages/8_🔬_Explorer.py", "Browse & filter all raw health data."),
    ]

    for i in range(0, len(nav), 4):
        cols = st.columns(4)
        for j, (title, page, desc) in enumerate(nav[i : i + 4]):
            with cols[j]:
                st.markdown(
                    f"""
<div class="ahd-card">
  <div style="font-weight: 650; font-size: 1rem; margin-bottom: 6px;">{title}</div>
  <div class="ahd-muted">{desc}</div>
</div>
""",
                    unsafe_allow_html=True,
                )

    st.divider()

    # ── Privacy note ──────────────────────────────────────────────────────────
    c1, c2, c3 = st.columns(3)
    with c1:
        info_card(
            "🔒 Privacy-first",
            "Your export is never uploaded anywhere. Everything stays on your machine.",
        )
    with c2:
        info_card(
            "⚡ Fast reloads",
            "Data is stored in SQLite locally — reloading is instant after the first import.",
        )
    with c3:
        info_card(
            "📈 Deep insights",
            "From sleep stages to VO₂ max trends, explore every corner of your health data.",
        )


if __name__ == "__main__":
    main()
