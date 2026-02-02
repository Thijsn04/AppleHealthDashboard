from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict

import pandas as pd

from apple_health_dashboard.ingest.apple_health_workouts import Workout


def workouts_to_dataframe(workouts: Iterable[Workout]) -> pd.DataFrame:
    rows = [asdict(w) for w in workouts]
    if not rows:
        return pd.DataFrame(
            columns=[
                "workout_activity_type",
                "start_at",
                "end_at",
                "creation_at",
                "source_name",
                "device",
                "duration_s",
                "total_energy_kcal",
                "total_distance_m",
            ]
        )

    df = pd.DataFrame(rows)
    for col in ["start_at", "end_at", "creation_at"]:
        df[col] = pd.to_datetime(df[col], utc=True, errors="coerce")
    return df


def summarize_workouts_by_week(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["week", "count", "duration_hours"])

    tmp = df.copy()
    tmp["week"] = tmp["start_at"].dt.to_period("W").dt.start_time
    tmp["duration_hours"] = (tmp["duration_s"].fillna(0.0) / 3600.0)

    out = (
        tmp.groupby("week", as_index=False)
        .agg(count=("workout_activity_type", "count"), duration_hours=("duration_hours", "sum"))
        .sort_values("week")
    )
    return out
