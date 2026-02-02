from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pandas as pd
import streamlit as st

from apple_health_dashboard.storage.sqlite_store import (
    count_records,
    list_record_types,
    open_db,
    query_records_page,
)


@dataclass(frozen=True)
class ExploreParams:
    start_at: datetime | None
    end_at: datetime | None


def render_explore_records(db_path, params: ExploreParams) -> None:
    """Explore/browse raw records from SQLite without loading everything into memory."""

    con = open_db(db_path)
    try:
        all_types = list_record_types(con)
    finally:
        con.close()

    if not all_types:
        st.info("Geen records in database.")
        return

    with st.sidebar:
        st.subheader("Explore")
        record_type = st.selectbox(
            "Record type",
            options=all_types,
            index=0,
            key="explore_all_type",
        )
        order = st.selectbox(
            "Order",
            options=["Newest first", "Oldest first"],
            index=0,
            key="explore_all_order",
        )

    order_sql = "start_at_desc" if order == "Newest first" else "start_at_asc"

    con = open_db(db_path)
    try:
        total = count_records(
            con,
            record_type=record_type,
            start_at=params.start_at,
            end_at=params.end_at,
        )

        page_size = st.selectbox(
            "Rows per page",
            [100, 250, 500, 1000, 2000],
            index=2,
            key="explore_all_ps",
        )
        pages = max(1, (total + page_size - 1) // page_size)
        page = st.number_input(
            "Page",
            min_value=1,
            max_value=pages,
            value=1,
            step=1,
            key="explore_all_page",
        )
        offset = (page - 1) * page_size

        rows = query_records_page(
            con,
            record_type=record_type,
            start_at=params.start_at,
            end_at=params.end_at,
            order=order_sql,
            limit=page_size,
            offset=offset,
        )
    finally:
        con.close()

    st.caption(f"Total rows: {total:,} · Page {page}/{pages}")

    if not rows:
        st.info("Geen rijen gevonden voor deze filter.")
        return

    df = pd.DataFrame(rows)
    for col in ["start_at", "end_at", "creation_at"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], utc=True, errors="coerce")

    st.dataframe(df, use_container_width=True, height=520)
