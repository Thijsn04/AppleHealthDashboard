from __future__ import annotations

import logging
import time
import zipfile
from pathlib import Path

import streamlit as st

from apple_health_dashboard.db import default_db_path
from apple_health_dashboard.ingest.importer import import_export_xml_to_duckdb_all
from apple_health_dashboard.local_data import delete_local_data
from apple_health_dashboard.storage.duckdb_store import (
    init_db,
    list_record_types,
    open_db,
)
from apple_health_dashboard.web.page_utils import page_header, sidebar_nav

logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Settings · Apple Health Dashboard",
    page_icon="⚙️",
    layout="wide",
)

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


with st.sidebar:
    sidebar_nav(current="Settings")
    st.divider()

page_header("⚙️", "Settings & Data Management", "Import, refresh, and manage your local DuckDB database.")

db_path = default_db_path()

# ── Stats row ─────────────────────────────────────────────────────────────
st.markdown("### 📊 Database Status")

stats = _db_stats(db_path)
if stats:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Health Records", f"{stats.get('records', 0):,}")
    c2.metric("Workouts", f"{stats.get('workouts', 0):,}")
    c3.metric("Activity Ring Days", f"{stats.get('ring_days', 0):,}")
    c4.metric("Record Types", f"{stats.get('record_types', 0):,}")
else:
    st.info("No data imported yet.")

st.divider()

col_l, col_r = st.columns([2, 1])

with col_l:
    st.markdown("### 📥 Import Data")
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

    import_clicked = st.button(
        "Import →",
        type="primary",
        disabled=(export_xml_path is None),
    )

    if export_xml_path is not None and import_clicked:
        progress = st.progress(0, text="Starting import…")
        status = st.empty()

        def on_progress(stage: str, processed: int) -> None:
            label = "Records" if stage == "records" else "Workouts"
            pct = min((processed % 5000) / 5000.0, 0.99)
            progress.progress(pct, text=f"{label}: {processed:,} processed")
            status.write(f"⚙️ {label}: {processed:,} processed…")

        t0 = time.perf_counter()
        with st.spinner("Importing into DuckDB (this may take 1–5 minutes for large exports)…"):
            try:
                counters = import_export_xml_to_duckdb_all(
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
        st.rerun()

with col_r:
    st.markdown("### 🛠️ Maintenance")
    if st.button("Refresh Cache", width="stretch"):
        st.cache_data.clear()
        st.toast("Cache cleared — data reloaded")
        st.rerun()
    
    st.markdown("#### Danger Zone")
    with st.expander("🗑️ Delete local data", expanded=False):
        st.caption("Permanently delete all locally stored data (database + temporary files).")
        confirm = st.checkbox("Yes, delete everything")
        if st.button("Delete", type="secondary", disabled=not confirm):
            delete_local_data()
            st.success("Local data deleted.")
            st.rerun()

    st.divider()
    st.markdown("### 🎨 UI & Theme")
    theme = st.selectbox("Dashboard Theme", ["Standard Glass", "High Contrast", "OLED Dark"], index=0)
    if st.button("Apply Theme"):
        st.session_state["theme"] = theme
        st.toast(f"Applied {theme} theme!")
        st.rerun()

