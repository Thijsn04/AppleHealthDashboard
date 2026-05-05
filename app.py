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
from apple_health_dashboard.web.page_utils import inject_global_css, sidebar_nav

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
    inject_global_css()

    db_path = default_db_path()
    stats = _db_stats(db_path)

    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        sidebar_nav(current="Home")
        st.divider()

        st.markdown("#### 📥 Import Data")
        st.caption(
            "Upload your **export.xml** or **export.zip** from the Apple Health app.  \n"
            "*How to export:* Health → Profile → Export All Health Data"
        )

        uploaded = st.file_uploader(
            "Choose file",
            type=["xml", "zip"],
            accept_multiple_files=False,
            label_visibility="collapsed",
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
            st.success(f"✓ {saved_path.name}")

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
            st.caption("Permanently delete all locally stored data (database + temporary files).")
            confirm = st.checkbox("Yes, delete everything")
            if st.button("Delete", type="secondary", disabled=not confirm):
                delete_local_data()
                st.success("Local data deleted.")
                st.rerun()

    # ── Hero header ───────────────────────────────────────────────────────────
    st.markdown(
        """<div style="padding:20px 0 18px 0;
                       border-bottom:1.5px solid rgba(46,125,110,0.14);
                       margin-bottom:1.6rem;">
  <div style="font-size:2rem;font-weight:800;letter-spacing:-0.028em;
              color:#0D2822;line-height:1.2;">
    🍎&nbsp;Apple Health Dashboard
  </div>
  <div style="margin-top:5px;font-size:0.92rem;color:#12312B;opacity:0.55;">
    100% local &nbsp;·&nbsp; privacy-first &nbsp;·&nbsp; all your health data in one place
  </div>
</div>""",
        unsafe_allow_html=True,
    )

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

    # ── Stats row ─────────────────────────────────────────────────────────────
    st.markdown(
        "<div style='font-size:1.05rem;font-weight:700;color:#0D2822;"
        "letter-spacing:-0.01em;margin-bottom:12px;'>Your Data at a Glance</div>",
        unsafe_allow_html=True,
    )

    if stats:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Health Records", f"{stats.get('records', 0):,}")
        c2.metric("Workouts", f"{stats.get('workouts', 0):,}")
        c3.metric("Activity Ring Days", f"{stats.get('ring_days', 0):,}")
        c4.metric("Record Types", f"{stats.get('record_types', 0):,}")
    else:
        st.info(
            "No data imported yet. Upload your Apple Health export and click **Import →** in the sidebar."
        )

    st.divider()

    # ── Navigation cards ─────────────────────────────────────────────────────
    st.markdown(
        "<div style='font-size:1.05rem;font-weight:700;color:#0D2822;"
        "letter-spacing:-0.01em;margin-bottom:4px;'>Explore your health data</div>",
        unsafe_allow_html=True,
    )
    st.caption("Select a section below to dive into your data.")

    nav = [
        ("📊", "Overview", "pages/1_📊_Overview.py",
         "Key metrics, trends & highlights at a glance."),
        ("❤️", "Heart Health", "pages/2_❤️_Heart.py",
         "HR, HRV, VO₂ max, blood pressure & SpO₂."),
        ("🏃", "Activity", "pages/3_🏃_Activity.py",
         "Steps, distance, calories & active minutes."),
        ("😴", "Sleep", "pages/4_😴_Sleep.py",
         "Sleep stages, duration & consistency."),
        ("🏋️", "Workouts", "pages/5_🏋️_Workouts.py",
         "All workout types, personal records & streaks."),
        ("🔥", "Rings", "pages/6_🔥_Rings.py",
         "Activity ring completion, goals & streaks."),
        ("⚖️", "Body", "pages/7_⚖️_Body.py",
         "Weight, BMI, body fat & composition trends."),
        ("🔬", "Explorer", "pages/8_🔬_Explorer.py",
         "Browse & filter all raw health data."),
        ("💡", "Insights", "pages/9_💡_Insights.py",
         "Cross-metric analysis that connects the dots."),
    ]

    for i in range(0, len(nav), 3):
        row_items = nav[i: i + 3]
        cols = st.columns(len(row_items))
        for col, (icon, name, page, desc) in zip(cols, row_items, strict=False):
            with col:
                st.markdown(
                    f"""<div class="ahd-nav-card">
  <div class="ahd-nav-card-title">{icon} {name}</div>
  <div class="ahd-nav-card-desc">{desc}</div>
</div>""",
                    unsafe_allow_html=True,
                )
                st.page_link(page, label=f"Open {name} →")

    st.divider()

    # ── Feature cards ─────────────────────────────────────────────────────────
    c1, c2, c3 = st.columns(3)
    _features = [
        ("🔒", "Privacy-first",
         "Your export is never uploaded anywhere. Everything stays on your machine."),
        ("⚡", "Fast reloads",
         "Data is stored in SQLite locally — reloading is instant after the first import."),
        ("📈", "Deep insights",
         "From sleep stages to VO₂ max trends, explore every corner of your health data."),
    ]
    for col, (icon, title, body) in zip([c1, c2, c3], _features, strict=False):
        with col:
            st.markdown(
                f"""<div class="ahd-card">
  <div style="font-weight:700;font-size:0.95rem;margin-bottom:6px;">{icon} {title}</div>
  <div class="ahd-muted">{body}</div>
</div>""",
                unsafe_allow_html=True,
            )


if __name__ == "__main__":
    main()

