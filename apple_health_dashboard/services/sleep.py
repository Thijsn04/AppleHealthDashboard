from __future__ import annotations

import pandas as pd

SLEEP_RECORD_TYPE = "HKCategoryTypeIdentifierSleepAnalysis"

# Apple Health sleep stage value strings
SLEEP_STAGES: dict[str, str] = {
    "HKCategoryValueSleepAnalysisInBed": "In Bed",
    "HKCategoryValueSleepAnalysisAsleepUnspecified": "Asleep (Unspecified)",
    "HKCategoryValueSleepAnalysisAsleep": "Asleep",
    "HKCategoryValueSleepAnalysisAwake": "Awake",
    "HKCategoryValueSleepAnalysisAsleepCore": "Core Sleep",
    "HKCategoryValueSleepAnalysisAsleepDeep": "Deep Sleep",
    "HKCategoryValueSleepAnalysisAsleepREM": "REM Sleep",
}

# Stages that count as actual sleep (not just "in bed")
SLEEP_STAGES_ACTUAL = {
    "HKCategoryValueSleepAnalysisAsleepUnspecified",
    "HKCategoryValueSleepAnalysisAsleep",
    "HKCategoryValueSleepAnalysisAsleepCore",
    "HKCategoryValueSleepAnalysisAsleepDeep",
    "HKCategoryValueSleepAnalysisAsleepREM",
}

# Deep/restorative stages
SLEEP_STAGES_RESTORATIVE = {
    "HKCategoryValueSleepAnalysisAsleepDeep",
    "HKCategoryValueSleepAnalysisAsleepREM",
}


def sleep_records(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "type" not in df.columns:
        return pd.DataFrame(columns=df.columns)
    return df[df["type"] == SLEEP_RECORD_TYPE].copy()


def _normalize_sleep_stage(value_str: str | None) -> str:
    """Map raw Apple Health stage string to a human-readable label."""
    if value_str is None:
        return "Unknown"
    return SLEEP_STAGES.get(value_str, value_str)


def sleep_value_counts(df: pd.DataFrame, *, limit: int = 20) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["stage", "count"])

    s = df.get("value_str")
    if s is None:
        return pd.DataFrame(columns=["stage", "count"])

    out = (
        s.astype("string")
        .fillna("(null)")
        .map(lambda v: SLEEP_STAGES.get(v, v))
        .value_counts(dropna=False)
        .head(limit)
        .reset_index()
    )
    out.columns = ["stage", "count"]
    return out


def sleep_duration_by_day(df: pd.DataFrame, *, stages: str = "all") -> pd.DataFrame:
    """Compute hours of sleep per day.

    stages:
      - "all": include all intervals (in bed + asleep)
      - "actual": only actual sleep stages (excludes InBed-only)
      - "restorative": only deep + REM

    Returns columns: day, hours
    """
    if df.empty or "start_at" not in df.columns or "end_at" not in df.columns:
        return pd.DataFrame(columns=["day", "hours"])

    valid = df[df["start_at"].notna() & df["end_at"].notna()].copy()
    if valid.empty:
        return pd.DataFrame(columns=["day", "hours"])

    if stages == "actual" and "value_str" in valid.columns:
        mask = valid["value_str"].isin(SLEEP_STAGES_ACTUAL)
        valid = valid[mask]
    elif stages == "restorative" and "value_str" in valid.columns:
        mask = valid["value_str"].isin(SLEEP_STAGES_RESTORATIVE)
        valid = valid[mask]

    if valid.empty:
        return pd.DataFrame(columns=["day", "hours"])

    valid["duration_h"] = (valid["end_at"] - valid["start_at"]).dt.total_seconds() / 3600.0
    # Attribute sleep to the calendar day of the *end* time, not the start time.
    # This means overnight sleep (e.g. 23:00 Jan 1 → 07:00 Jan 2) is counted as a Jan 2 night,
    # which aligns with how people intuitively think about "last night's sleep".
    valid["day"] = valid["end_at"].dt.floor("D")

    out = (
        valid.groupby("day", as_index=False)["duration_h"]
        .sum()
        .rename(columns={"duration_h": "hours"})
    )
    return out.sort_values("day")


def sleep_stages_by_day(df: pd.DataFrame) -> pd.DataFrame:
    """Return a wide table with hours per sleep stage per day.

    Columns: day, In Bed, Asleep, Core Sleep, Deep Sleep, REM Sleep, Awake
    """
    if df.empty or "start_at" not in df.columns or "value_str" not in df.columns:
        return pd.DataFrame()

    valid = df[df["start_at"].notna() & df["end_at"].notna()].copy()
    if valid.empty:
        return pd.DataFrame()

    valid["duration_h"] = (valid["end_at"] - valid["start_at"]).dt.total_seconds() / 3600.0
    valid["day"] = valid["end_at"].dt.floor("D")
    valid["stage"] = valid["value_str"].map(lambda v: _normalize_sleep_stage(v))

    pivoted = (
        valid.groupby(["day", "stage"])["duration_h"]
        .sum()
        .unstack(fill_value=0.0)
        .reset_index()
    )
    return pivoted.sort_values("day")


def sleep_consistency_stats(df: pd.DataFrame) -> dict[str, float]:
    """Compute sleep consistency statistics.

    Returns:
      avg_hours: average sleep hours per night
      std_hours: standard deviation
      nights_gte_7h: fraction of nights with ≥7h sleep
      nights_gte_8h: fraction of nights with ≥8h sleep
    """
    daily = sleep_duration_by_day(df, stages="actual")
    if daily.empty:
        # Fallback to all stages
        daily = sleep_duration_by_day(df, stages="all")

    if daily.empty:
        return {}

    hours = daily["hours"]
    total = len(hours)
    return {
        "avg_hours": float(hours.mean()),
        "std_hours": float(hours.std()),
        "median_hours": float(hours.median()),
        "nights_gte_7h": float((hours >= 7).sum() / total),
        "nights_gte_8h": float((hours >= 8).sum() / total),
        "total_nights": total,
    }

def sleep_timing_consistency(df: pd.DataFrame) -> dict[str, float]:
    """Calculate the consistency of bedtimes and wake times.
    
    Returns:
      avg_bedtime: average bedtime in hours (e.g. 23.5 for 11:30 PM)
      avg_waketime: average wake time in hours (e.g. 7.5 for 7:30 AM)
      bedtime_variance_h: standard deviation of bedtimes
      waketime_variance_h: standard deviation of wake times
      consistency_score: 0-100 score based on variance
    """
    valid = df[df["start_at"].notna() & df["end_at"].notna()].copy()
    if valid.empty:
        return {}
        
    mask = valid["value_str"].isin(SLEEP_STAGES_ACTUAL)
    valid = valid[mask]
    if valid.empty:
        return {}
        
    valid["day"] = valid["end_at"].dt.floor("D")
    daily = valid.groupby("day").agg(
        bedtime=("start_at", "min"),
        waketime=("end_at", "max")
    ).reset_index()
    
    # Convert to fractional hours. Bedtimes after midnight get +24 for easier math.
    daily["bedtime_hour"] = daily["bedtime"].dt.hour + daily["bedtime"].dt.minute / 60.0
    daily["bedtime_hour"] = daily["bedtime_hour"].apply(lambda x: x + 24 if x < 12 else x)
    daily["waketime_hour"] = daily["waketime"].dt.hour + daily["waketime"].dt.minute / 60.0
    
    bed_std = float(daily["bedtime_hour"].std())
    wake_std = float(daily["waketime_hour"].std())
    
    # Simple 0-100 score: 0 std = 100, 2h std = 50, 4h+ std = 0
    avg_std = (bed_std + wake_std) / 2
    score = max(0, 100 - (avg_std * 25)) if pd.notna(avg_std) else 0.0
    
    return {
        "bedtime_variance_h": bed_std,
        "waketime_variance_h": wake_std,
        "consistency_score": float(score),
        "avg_bedtime": float(daily["bedtime_hour"].mean()),
        "avg_waketime": float(daily["waketime_hour"].mean())
    }
