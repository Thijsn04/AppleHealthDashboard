from __future__ import annotations

import pandas as pd

SLEEP_RECORD_TYPE = "HKCategoryTypeIdentifierSleepAnalysis"


def sleep_records(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "type" not in df.columns:
        return pd.DataFrame(columns=df.columns)
    return df[df["type"] == SLEEP_RECORD_TYPE].copy()


def sleep_value_counts(df: pd.DataFrame, *, limit: int = 20) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["value", "count"])

    s = df.get("value_str")
    if s is None:
        return pd.DataFrame(columns=["value", "count"])

    out = (
        s.astype("string")
        .fillna("(null)")
        .value_counts(dropna=False)
        .head(limit)
        .reset_index()
    )
    out.columns = ["value", "count"]
    return out


def sleep_duration_by_day(df: pd.DataFrame) -> pd.DataFrame:
    """Compute hours of sleep per day based on start/end intervals.

    Apple stores sleep as intervals with categorical values.
    We don't try to interpret phases here (asleep vs inbed), we simply sum duration.

    Returns columns: day, hours
    """
    if df.empty or "start_at" not in df.columns or "end_at" not in df.columns:
        return pd.DataFrame(columns=["day", "hours"])

    valid = df[df["start_at"].notna() & df["end_at"].notna()].copy()
    if valid.empty:
        return pd.DataFrame(columns=["day", "hours"])

    valid["duration_h"] = (valid["end_at"] - valid["start_at"]).dt.total_seconds() / 3600.0
    valid["day"] = valid["start_at"].dt.floor("D")

    out = (
        valid.groupby("day", as_index=False)["duration_h"]
        .sum()
        .rename(columns={"duration_h": "hours"})
    )
    return out.sort_values("day")
