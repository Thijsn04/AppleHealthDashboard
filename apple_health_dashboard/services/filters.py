from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class DateFilter:
    start: pd.Timestamp
    end: pd.Timestamp


def apply_date_filter(df: pd.DataFrame, date_filter: DateFilter) -> pd.DataFrame:
    if df.empty or "start_at" not in df.columns:
        return df

    start_at = df["start_at"]
    mask = (start_at >= date_filter.start) & (start_at <= date_filter.end)
    return df.loc[mask].copy()


def infer_date_filter(df: pd.DataFrame, *, preset: str) -> DateFilter | None:
    """Infer a date filter from data and a preset.

    preset: "All" | "7D" | "30D" | "90D"
    """
    if df.empty or "start_at" not in df.columns:
        return None

    start_at = df["start_at"].dropna()
    if start_at.empty:
        return None

    end = start_at.max()

    if preset == "All":
        return DateFilter(start=start_at.min(), end=end)

    days = {"7D": 7, "30D": 30, "90D": 90}.get(preset)
    if days is None:
        return None

    start = end - pd.Timedelta(days=days)
    return DateFilter(start=start, end=end)
