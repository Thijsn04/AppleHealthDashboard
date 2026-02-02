from __future__ import annotations

import logging
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import streamlit as st

from apple_health_dashboard.db import default_db_path
from apple_health_dashboard.ingest.importer import import_export_xml_to_sqlite_all
from apple_health_dashboard.local_data import delete_local_data
from apple_health_dashboard.logging_config import configure_logging
from apple_health_dashboard.services.activity_summary import activity_summaries_to_dataframe
from apple_health_dashboard.services.filters import apply_date_filter, infer_date_filter
from apple_health_dashboard.services.metrics import METRICS, metric_aggregation, metric_label
from apple_health_dashboard.services.records_view import split_numeric_categorical, top_value_counts
from apple_health_dashboard.services.sleep import (
    SLEEP_RECORD_TYPE,
    sleep_duration_by_day,
    sleep_records,
    sleep_value_counts,
)
from apple_health_dashboard.services.stats import (
    available_record_types,
    summarize_by_day_agg,
    to_dataframe,
)
from apple_health_dashboard.services.units import normalize_units
from apple_health_dashboard.services.workouts import (
    summarize_workouts_by_week,
    workouts_to_dataframe,
)
from apple_health_dashboard.storage.sqlite_store import (
    get_record_metadata_for_hash,
    init_db,
    iter_activity_summaries,
    iter_records,
    iter_workouts,
    open_db,
)
from apple_health_dashboard.web.explore import ExploreParams, render_explore_records
from apple_health_dashboard.web.i18n import get_copy
from apple_health_dashboard.web.ui import Brand, apply_base_ui, info_card, stat_row

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class UploadResult:
    export_xml_path: Path


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


def _metric_picker(df: pd.DataFrame) -> str | None:
    """Select a metric.

    Shows curated metrics first, with an option to pick any raw record type.
    """
    st.sidebar.header("Filters")

    available = set(available_record_types(df))
    curated = [m for m in METRICS if m.record_type in available]

    options: list[tuple[str, str]] = []
    for m in curated:
        options.append((f"{m.category} · {m.label}", m.record_type))

    options.append(("Other · All types", "__all__"))

    labels = [o[0] for o in options]
    choice = st.sidebar.selectbox("Metric", labels, index=0)

    selected = dict(options).get(choice)
    if selected == "__all__":
        raw_types = sorted(available)
        if not raw_types:
            return None
        raw_label_map = {t: metric_label(t) for t in raw_types}
        picks = [f"{raw_label_map[t]}  ({t})" for t in raw_types]
        picked = st.sidebar.selectbox("Record type", picks, index=0)
        # Extract original type from the string
        return picked.rsplit("(", 1)[-1].rstrip(")")

    return selected


def _load_from_db(db_path: Path) -> pd.DataFrame:
    con = open_db(db_path)
    try:
        init_db(con)
        records = list(iter_records(con))
    finally:
        con.close()
    return to_dataframe(records)


def _load_workouts_from_db(db_path: Path) -> pd.DataFrame:
    con = open_db(db_path)
    try:
        init_db(con)
        workouts = list(iter_workouts(con))
    finally:
        con.close()
    return workouts_to_dataframe(workouts)


def _load_activity_from_db(db_path: Path) -> pd.DataFrame:
    con = open_db(db_path)
    try:
        init_db(con)
        rows = list(iter_activity_summaries(con))
    finally:
        con.close()
    return activity_summaries_to_dataframe(rows)


def _load_record_metadata(db_path: Path, record_hash: str) -> list[tuple[str, str]]:
    con = open_db(db_path)
    try:
        init_db(con)
        return get_record_metadata_for_hash(con, record_hash)
    finally:
        con.close()


def main() -> None:
    configure_logging()

    # Language selector (EN default)
    if "lang" not in st.session_state:
        st.session_state["lang"] = "en"

    with st.sidebar:
        st.selectbox(
            "Language",
            options=["en", "nl"],
            index=0 if st.session_state["lang"] == "en" else 1,
            key="lang",
        )

    t = get_copy(st.session_state.get("lang", "en"))

    apply_base_ui(Brand(tagline=t.app_tagline))

    db_path = default_db_path()

    # --- Sidebar: import + global controls ---
    with st.sidebar:
        st.header(t.sidebar_import_title)
        st.write(t.sidebar_upload_help)
        st.caption(t.sidebar_local_caption)

        uploaded = st.file_uploader(
            "File",
            type=["xml", "zip"],
            accept_multiple_files=False,
        )

        export_xml_path: Path | None = None
        if uploaded is not None:
            saved_path = _save_uploaded_file_to_tmp(uploaded)
            if saved_path.suffix.lower() == ".zip":
                export_xml_path = _extract_export_xml_from_zip(saved_path)
            else:
                export_xml_path = saved_path

            st.success(f"Bestand geladen: {export_xml_path.name}")

        st.divider()

        col_a, col_b = st.columns(2)
        with col_a:
            import_clicked = st.button(
                t.button_import,
                type="primary",
                use_container_width=True,
            )
        with col_b:
            refresh_clicked = st.button(t.button_refresh, use_container_width=True)

        st.caption(f"Database: `{db_path.name}`")

        with st.expander(t.sidebar_delete_local_title, expanded=False):
            st.write(t.sidebar_delete_local_body)
            confirm = st.checkbox(t.sidebar_delete_local_confirm)
            if st.button(t.sidebar_delete_local_button, type="secondary", disabled=not confirm):
                delete_local_data()
                st.success("Local data deleted.")
                st.rerun()

        st.divider()
        st.header(t.sidebar_tips_title)
        st.markdown(
            "- Import once per export\n"
            "- Reloads are fast after import\n"
            "- Large exports can take 1–5 minutes"
        )

    # --- Top info cards ---
    info_cols = st.columns([1.2, 1, 1])
    with info_cols[0]:
        info_card(t.card_privacy_title, t.card_privacy_body)
    with info_cols[1]:
        info_card(t.card_scale_title, t.card_scale_body)
    with info_cols[2]:
        info_card(t.card_insight_title, t.card_insight_body)

    st.divider()

    # We require an uploaded file path only for importing. Browsing works from DB.
    if export_xml_path is not None and import_clicked:
        # --- Import: XML → SQLite ---
        progress = st.progress(0, text="Import gestart...")
        status = st.empty()

        def on_progress(stage: str, processed: int) -> None:
            label = "Records" if stage == "records" else "Workouts"
            progress.progress((processed % 1000) / 1000.0, text=f"{label}: {processed:,} verwerkt")
            status.write(f"{label}: {processed:,} verwerkt")

        t0 = time.perf_counter()
        with st.spinner("Importeren naar SQLite (records + workouts)..."):
            counters = import_export_xml_to_sqlite_all(
                export_xml_path,
                db_path,
                on_progress=on_progress,
            )
        dt = time.perf_counter() - t0

        logger.info(
            "Import finished in %.2fs (records_inserted=%s record_metadata_inserted=%s "
            "activity_summaries_inserted=%s workouts_inserted=%s workout_metadata_inserted=%s)",
            dt,
            counters.get("records_inserted"),
            counters.get("record_metadata_inserted"),
            counters.get("activity_summaries_inserted"),
            counters.get("workouts_inserted"),
            counters.get("workout_metadata_inserted"),
        )

        progress.progress(1.0, text="Klaar")
        st.success(
            "Import klaar. "
            f"Records: {counters['records_inserted']:,} · "
            f"Metadata: {counters['record_metadata_inserted']:,} · "
            f"Rings: {counters['activity_summaries_inserted']:,} · "
            f"Workouts: {counters['workouts_inserted']:,}"
        )

    if refresh_clicked:
        st.toast("Verversing uitgevoerd")

    with st.spinner("Data laden vanuit database..."):
        df = _load_from_db(db_path)

    if df.empty:
        st.warning("Database is leeg. Klik links op 'Import naar database'.")
        st.stop()

    # Global date filter
    with st.sidebar:
        preset = st.selectbox(t.filter_date_range, ["All", "7D", "30D", "90D"], index=2)

    preset_filter = infer_date_filter(df, preset=preset)
    if preset_filter is None:
        st.warning("Kon geen datumrange bepalen uit de data.")
        st.stop()

    with st.sidebar:
        use_custom = st.checkbox(t.filter_custom_date, value=False)

        if use_custom:
            min_d = preset_filter.start.date()
            max_d = preset_filter.end.date()
            start_d, end_d = st.date_input(
                t.filter_select_dates,
                value=(min_d, max_d),
                min_value=min_d,
                max_value=max_d,
            )
            date_filter = type(preset_filter)(
                start=pd.Timestamp(start_d, tz="UTC"),
                end=pd.Timestamp(end_d, tz="UTC")
                + pd.Timedelta(days=1)
                - pd.Timedelta(seconds=1),
            )
        else:
            date_filter = preset_filter

    df_filtered = apply_date_filter(df, date_filter)

    metric = _metric_picker(df_filtered)
    if metric is None:
        st.warning("Geen record types beschikbaar.")
        st.stop()

    filtered = df_filtered[df_filtered["type"] == metric].copy()
    filtered = normalize_units(filtered, record_type=metric)

    # --- Tabs ---
    tabs = st.tabs(
        [
            t.tab_dashboard,
            t.tab_explore,
            t.tab_workouts,
            t.tab_rings,
            t.tab_sleep,
            t.tab_metadata,
        ]
    )

    period_str = f"{date_filter.start.date().isoformat()} → {date_filter.end.date().isoformat()}"
    status_items = [
        ("Period", period_str),
        ("Metric", metric_label(metric)),
        ("Records", f"{len(filtered):,}"),
    ]

    with tabs[0]:
        stat_row(status_items)
        st.divider()

        st.subheader(f"Overzicht · {metric_label(metric)}")

        c1, c2, c3, c4 = st.columns([1, 1, 1, 1])
        c1.metric("Records", f"{len(filtered):,}")
        c2.metric("Van", filtered["start_at"].min().date().isoformat())
        c3.metric("Tot", filtered["end_at"].max().date().isoformat())

        unit = filtered["unit"].dropna().unique().tolist()
        c4.metric("Unit", unit[0] if unit else "–")

        st.subheader("Trend / verdeling")
        agg = metric_aggregation(metric)

        num_df, cat_df = split_numeric_categorical(filtered)
        chart_col, table_col = st.columns([1.4, 1])

        with chart_col:
            if not num_df.empty:
                daily = summarize_by_day_agg(num_df.rename(columns={"value_num": "value"}), agg=agg)
                if not daily.empty:
                    st.line_chart(daily.set_index("day")["value"], height=320)
                else:
                    st.info("Geen dagelijkse rollup mogelijk voor deze metric in deze periode.")
            else:
                st.info("Deze metric lijkt niet-numeriek in de gekozen periode.")

        with table_col:
            if not cat_df.empty:
                counts = top_value_counts(cat_df, limit=30)
                st.caption("Top values")
                st.dataframe(counts, use_container_width=True, height=320)
            elif not num_df.empty:
                daily = summarize_by_day_agg(num_df.rename(columns={"value_num": "value"}), agg=agg)
                st.dataframe(daily, use_container_width=True, height=320)

        with st.expander("Ruwe data (filter + paginering)"):
            q = st.text_input("Zoek (source/unit/value)", value="", key="dash_q")
            view = filtered.copy()
            if q:
                q_lower = q.lower()
                cols = [
                    c
                    for c in ["source_name", "unit", "value", "value_str"]
                    if c in view.columns
                ]
                mask = pd.Series(False, index=view.index)
                for c in cols:
                    s = view[c].astype("string").fillna("").str.lower()
                    mask = mask | s.str.contains(q_lower)
                view = view[mask].copy()

            page_size = st.selectbox(
                "Rows per page",
                [100, 250, 500, 1000],
                index=1,
                key="dash_ps",
            )
            total = len(view)
            pages = max(1, (total + page_size - 1) // page_size)
            page = st.number_input(
                "Page",
                min_value=1,
                max_value=pages,
                value=1,
                step=1,
                key="dash_page",
            )
            start = (page - 1) * page_size
            end = start + page_size
            st.caption(f"Rows {start + 1}–{min(end, total)} van {total}")
            st.dataframe(view.iloc[start:end], use_container_width=True)

    with tabs[1]:
        stat_row(status_items)
        st.write(
            "Explore (DB-first): browse records direct uit SQLite. "
            "Dit is sneller en werkt ook bij hele grote exports."
        )

        explore_params = ExploreParams(
            start_at=date_filter.start.to_pydatetime(),
            end_at=date_filter.end.to_pydatetime(),
        )
        render_explore_records(db_path, explore_params)

    with tabs[2]:
        st.header("Workouts")
        with st.spinner("Workouts laden..."):
            wdf = _load_workouts_from_db(db_path)

        if not wdf.empty and "start_at" in wdf.columns:
            wdf = wdf[
                (wdf["start_at"] >= date_filter.start)
                & (wdf["start_at"] <= date_filter.end)
            ].copy()

        if wdf.empty:
            st.info("Geen workouts gevonden in deze periode.")
        else:
            stat_row(
                [
                    ("Workouts", f"{len(wdf):,}"),
                    ("First", wdf["start_at"].min().date().isoformat()),
                    ("Last", wdf["end_at"].max().date().isoformat()),
                ]
            )
            st.divider()
            weekly = summarize_workouts_by_week(wdf)
            if not weekly.empty:
                st.subheader("Per week")
                st.bar_chart(weekly.set_index("week")["count"], height=240)
                st.dataframe(weekly, use_container_width=True)

            with st.expander("Workouts (raw)"):
                st.dataframe(
                    wdf.sort_values("start_at", ascending=False).head(2000),
                    use_container_width=True,
                )

    with tabs[3]:
        st.header("Activity (Rings)")
        with st.spinner("Rings laden..."):
            adf = _load_activity_from_db(db_path)

        if not adf.empty and "day" in adf.columns:
            mask = (adf["day"] >= pd.Timestamp(date_filter.start.date())) & (
                adf["day"] <= pd.Timestamp(date_filter.end.date())
            )
            adf = adf.loc[mask].copy()

        if adf.empty:
            st.info("Geen ActivitySummary gevonden in deze periode.")
        else:
            stat_row(
                [
                    ("Days", f"{len(adf):,}"),
                    ("From", adf["day"].min().date().isoformat()),
                    ("To", adf["day"].max().date().isoformat()),
                ]
            )
            st.divider()

            st.subheader("Move")
            st.line_chart(adf.set_index("day")["active_energy_burned_kcal"], height=220)
            st.subheader("Exercise")
            st.line_chart(adf.set_index("day")["apple_exercise_time_min"], height=220)
            st.subheader("Stand")
            st.line_chart(adf.set_index("day")["apple_stand_hours"], height=220)

            with st.expander("Rings (raw)"):
                st.dataframe(adf, use_container_width=True)

    with tabs[4]:
        st.header("Sleep")
        srec = sleep_records(df_filtered)
        if srec.empty:
            st.info(
                "Geen sleep data gevonden. Tip: in Apple Health staat dit meestal als "
                f"record type `{SLEEP_RECORD_TYPE}`."
            )
        else:
            stat_row(
                [
                    ("Sleep records", f"{len(srec):,}"),
                    ("From", srec["start_at"].min().date().isoformat()),
                    ("To", srec["end_at"].max().date().isoformat()),
                ]
            )
            st.divider()

            st.subheader("Sleep duration per day (hours)")
            dur = sleep_duration_by_day(srec)
            if not dur.empty:
                st.line_chart(dur.set_index("day")["hours"], height=260)
                st.dataframe(dur, use_container_width=True)

            st.subheader("Sleep states (top values)")
            counts = sleep_value_counts(srec)
            st.dataframe(counts, use_container_width=True)

            with st.expander("Sleep raw (paged)"):
                page_size = st.selectbox("Rows", [200, 500, 1000, 2000], index=1, key="sleep_ps")
                total = len(srec)
                pages = max(1, (total + page_size - 1) // page_size)
                page = st.number_input(
                    "Page",
                    min_value=1,
                    max_value=pages,
                    value=1,
                    step=1,
                    key="sleep_page",
                )
                start = (page - 1) * page_size
                end = start + page_size
                st.dataframe(srec.iloc[start:end], use_container_width=True)

    with tabs[5]:
        st.header("Metadata")
        st.write("Bekijk record-metadata voor een sample uit de gekozen metric en periode.")
        sample = filtered.head(200).copy()
        if sample.empty:
            st.info("Geen records in deze periode voor deze metric.")
        else:
            sample["record_hash"] = sample.apply(
                lambda r: __import__(
                    "apple_health_dashboard.storage.sqlite_store",
                    fromlist=["stable_record_hash"],
                ).stable_record_hash(
                    __import__(
                        "apple_health_dashboard.ingest.apple_health",
                        fromlist=["HealthRecord"],
                    ).HealthRecord(
                        type=r["type"],
                        start_at=r["start_at"].to_pydatetime(),
                        end_at=r["end_at"].to_pydatetime(),
                        creation_at=(
                            r["creation_at"].to_pydatetime() if pd.notna(r["creation_at"]) else None
                        ),
                        source_name=r["source_name"],
                        unit=r["unit"],
                        value=r["value"],
                        value_str=r["value_str"],
                    )
                ),
                axis=1,
            )
            chosen_hash = st.selectbox("Record (hash)", sample["record_hash"].tolist())
            meta = _load_record_metadata(db_path, chosen_hash)
            if not meta:
                st.info("Geen metadata gevonden voor dit record.")
            else:
                st.dataframe(pd.DataFrame(meta, columns=["key", "value"]), use_container_width=True)

    # Keep the existing dashboard content rendering in tab 0 below

    if export_xml_path is None:
        st.info("Upload een Apple Health export om te starten.")
        st.stop()


if __name__ == "__main__":
    main()
