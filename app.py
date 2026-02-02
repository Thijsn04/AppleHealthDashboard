from __future__ import annotations

import zipfile
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import streamlit as st

from apple_health_dashboard.ingest.apple_health import load_export_xml_from_path
from apple_health_dashboard.services.stats import (
    available_record_types,
    summarize_by_day,
    to_dataframe,
)
from apple_health_dashboard.web.ui import Brand, apply_base_ui, info_card


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


def _load_records(export_xml_path: Path):
    return load_export_xml_from_path(export_xml_path)


def _metric_picker(df: pd.DataFrame) -> str | None:
    types = available_record_types(df)
    if not types:
        return None
    return st.sidebar.selectbox("Metric", types, index=0)


def main() -> None:
    apply_base_ui(Brand())

    with st.sidebar:
        st.header("Import")
        st.write("Upload `export.xml` of `export.zip` vanuit Apple Gezondheid.")
        st.caption("Alles blijft lokaal op je computer.")

        uploaded = st.file_uploader(
            "Bestand",
            type=["xml", "zip"],
            accept_multiple_files=False,
        )

        st.divider()
        st.header("Tips")
        st.markdown(
            "- Begin met **Steps** of **Resting Heart Rate**\n"
            "- Gebruik de daily chart voor trends\n"
            "- Grote exports kunnen 1–5 min duren"
        )

    # Main content
    info_cols = st.columns([1.2, 1, 1])
    with info_cols[0]:
        info_card(
            "Privacy-first",
            "Je export wordt niet geüpload naar een cloud. We verwerken alles lokaal.",
        )
    with info_cols[1]:
        info_card("Schaalbaar", "De XML-parser werkt streaming (geschikt voor grote exports).")
    with info_cols[2]:
        info_card("Inzicht", "Kies een metric en bekijk trends per dag.")

    st.divider()

    export_xml_path: Path | None = None
    if uploaded is not None:
        saved_path = _save_uploaded_file_to_tmp(uploaded)
        if saved_path.suffix.lower() == ".zip":
            export_xml_path = _extract_export_xml_from_zip(saved_path)
        else:
            export_xml_path = saved_path

        st.success(f"Bestand geladen: {export_xml_path.name}")

    if export_xml_path is None:
        st.info("Upload een Apple Health export om te starten.")
        return

    with st.spinner("Bezig met importeren en analyseren..."):
        records = _load_records(export_xml_path)
        df = to_dataframe(records)

    if df.empty:
        st.warning("Geen records gevonden in export.xml.")
        return

    metric = _metric_picker(df)
    if metric is None:
        st.warning("Geen record types beschikbaar.")
        return

    filtered = df[df["type"] == metric].copy()

    st.subheader("Overzicht")
    c1, c2, c3, c4 = st.columns([1, 1, 1, 1])
    c1.metric("Records", f"{len(filtered):,}")
    c2.metric("Van", filtered["start_at"].min().date().isoformat())
    c3.metric("Tot", filtered["end_at"].max().date().isoformat())

    unit = filtered["unit"].dropna().unique().tolist()
    c4.metric("Unit", unit[0] if unit else "–")

    st.subheader("Trend per dag")
    daily = summarize_by_day(filtered)

    chart_col, table_col = st.columns([1.4, 1])
    with chart_col:
        if not daily.empty:
            st.line_chart(daily.set_index("day")["value_sum"], height=320)
        else:
            st.info("Niet genoeg numerieke data om per dag te summarizen.")

    with table_col:
        if not daily.empty:
            st.dataframe(daily, use_container_width=True, height=320)

    with st.expander("Ruwe data (sample)"):
        st.dataframe(filtered.head(250), use_container_width=True)


if __name__ == "__main__":
    main()
