from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict

import pandas as pd

from apple_health_dashboard.ingest.apple_health import HealthRecord


def to_dataframe(records: Iterable[HealthRecord]) -> pd.DataFrame:
    """Convert records to a pandas DataFrame."""
    rows = [asdict(r) for r in records]
    if not rows:
        return pd.DataFrame(
            columns=[
                "type",
                "start_at",
                "end_at",
                "creation_at",
                "source_name",
                "unit",
                "value",
                "value_str",
            ]
        )

    df = pd.DataFrame(rows)
    for col in ["start_at", "end_at", "creation_at"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], utc=True, errors="coerce")
    return df


def available_record_types(df: pd.DataFrame) -> list[str]:
    if df.empty or "type" not in df.columns:
        return []
    return sorted([t for t in df["type"].dropna().unique().tolist()])


def summarize_by_day(df: pd.DataFrame) -> pd.DataFrame:
    """Daily rollup for numeric records.

    Returns columns: day, value_sum, value_mean, count
    """
    if df.empty:
        return pd.DataFrame(columns=["day", "value_sum", "value_mean", "count"])

    if "start_at" not in df.columns or "value" not in df.columns:
        return pd.DataFrame(columns=["day", "value_sum", "value_mean", "count"])

    numeric = df[df["value"].notna()].copy()
    if numeric.empty:
        return pd.DataFrame(columns=["day", "value_sum", "value_mean", "count"])

    numeric["day"] = numeric["start_at"].dt.floor("D")
    out = (
        numeric.groupby("day", as_index=False)["value"]
        .agg(value_sum="sum", value_mean="mean", count="count")
        .sort_values("day")
    )
    return out
