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

    Note: kept for backward compatibility; prefer summarize_by_day_agg.
    """
    return summarize_by_day_agg(df, agg="sum")


def summarize_by_day_agg(df: pd.DataFrame, *, agg: str) -> pd.DataFrame:
    """Daily rollup for records.

    agg:
      - "sum": sum per day
      - "mean": mean per day
      - "last": last value per day (by start_at)

    Returns: columns [day, value, count]
    """
    if df.empty or "start_at" not in df.columns:
        return pd.DataFrame(columns=["day", "value", "count"])

    if "value" not in df.columns:
        return pd.DataFrame(columns=["day", "value", "count"])

    # Be defensive: make sure we pass a 1D array/Series into to_numeric.
    value_col = df["value"]
    if isinstance(value_col, pd.DataFrame):
        # Extremely defensive: pick first column if this ever happens.
        value_series = value_col.iloc[:, 0]
    else:
        value_series = value_col

    values = pd.to_numeric(value_series, errors="coerce")

    numeric = df.copy()
    numeric["value_num"] = values
    numeric = numeric[numeric["value_num"].notna() & numeric["start_at"].notna()].copy()

    if numeric.empty:
        return pd.DataFrame(columns=["day", "value", "count"])

    numeric["day"] = numeric["start_at"].dt.floor("D")

    if agg == "sum":
        out = (
            numeric.groupby("day", as_index=False)["value_num"]
            .agg(value="sum", count="count")
            .sort_values("day")
        )
        return out

    if agg == "mean":
        out = (
            numeric.groupby("day", as_index=False)["value_num"]
            .agg(value="mean", count="count")
            .sort_values("day")
        )
        return out

    if agg == "last":
        tmp = numeric.sort_values(["day", "start_at"]).copy()
        out = tmp.groupby("day", as_index=False).agg(
            value=("value_num", "last"),
            count=("value_num", "count"),
        )
        out = out.sort_values("day")
        return out

    raise ValueError(f"Unsupported agg: {agg}")
