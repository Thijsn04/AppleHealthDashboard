from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict

import pandas as pd

from apple_health_dashboard.ingest.apple_health_workouts import Workout

# Mapping from Apple workout type identifier suffix to human label
_WORKOUT_LABELS: dict[str, str] = {
    "HKWorkoutActivityTypeRunning": "Running",
    "HKWorkoutActivityTypeCycling": "Cycling",
    "HKWorkoutActivityTypeSwimming": "Swimming",
    "HKWorkoutActivityTypeWalking": "Walking",
    "HKWorkoutActivityTypeHiking": "Hiking",
    "HKWorkoutActivityTypeYoga": "Yoga",
    "HKWorkoutActivityTypePilates": "Pilates",
    "HKWorkoutActivityTypeStrengthTraining": "Strength Training",
    "HKWorkoutActivityTypeFunctionalStrengthTraining": "Functional Strength",
    "HKWorkoutActivityTypeCoreTraining": "Core Training",
    "HKWorkoutActivityTypeHighIntensityIntervalTraining": "HIIT",
    "HKWorkoutActivityTypeCrossTraining": "Cross Training",
    "HKWorkoutActivityTypeMixedCardio": "Mixed Cardio",
    "HKWorkoutActivityTypeElliptical": "Elliptical",
    "HKWorkoutActivityTypeStairClimbing": "Stair Climbing",
    "HKWorkoutActivityTypeRowing": "Rowing",
    "HKWorkoutActivityTypeSoccer": "Soccer",
    "HKWorkoutActivityTypeBasketball": "Basketball",
    "HKWorkoutActivityTypeTennis": "Tennis",
    "HKWorkoutActivityTypeGolf": "Golf",
    "HKWorkoutActivityTypeDance": "Dance",
    "HKWorkoutActivityTypeJumpRope": "Jump Rope",
    "HKWorkoutActivityTypeSkiing": "Skiing",
    "HKWorkoutActivityTypeSnowboarding": "Snowboarding",
    "HKWorkoutActivityTypeSkatingSports": "Skating",
    "HKWorkoutActivityTypeSurfingSports": "Surfing",
    "HKWorkoutActivityTypeBoxing": "Boxing",
    "HKWorkoutActivityTypeMartialArts": "Martial Arts",
    "HKWorkoutActivityTypeWaterSports": "Water Sports",
    "HKWorkoutActivityTypeOther": "Other",
    "HKWorkoutActivityTypeTraditionalStrengthTraining": "Weight Training",
    "HKWorkoutActivityTypeStairs": "Stairs",
    "HKWorkoutActivityTypeBadminton": "Badminton",
    "HKWorkoutActivityTypeRollerHockeySkating": "Roller Hockey",
    "HKWorkoutActivityTypeRacquetball": "Racquetball",
    "HKWorkoutActivityTypeSquash": "Squash",
    "HKWorkoutActivityTypeTableTennis": "Table Tennis",
    "HKWorkoutActivityTypeVolleyball": "Volleyball",
    "HKWorkoutActivityTypeWrestling": "Wrestling",
    "HKWorkoutActivityTypeCrossCountrySkiing": "Cross-Country Skiing",
    "HKWorkoutActivityTypeHandball": "Handball",
    "HKWorkoutActivityTypePickleball": "Pickleball",
}


def workout_label(activity_type: str) -> str:
    """Convert Apple workout type to a human-readable label."""
    label = _WORKOUT_LABELS.get(activity_type)
    if label:
        return label
    # Fallback: strip the prefix
    if "ActivityType" in activity_type:
        return activity_type.split("ActivityType", 1)[-1]
    return activity_type


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

    # Add human-readable type label
    df["activity_label"] = df["workout_activity_type"].map(workout_label)
    return df


def summarize_workouts_by_week(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["week", "count", "duration_hours", "energy_kcal"])

    tmp = df.copy()
    tmp["week"] = tmp["start_at"].dt.to_period("W").dt.start_time
    tmp["duration_hours"] = tmp["duration_s"].fillna(0.0) / 3600.0

    out = (
        tmp.groupby("week", as_index=False)
        .agg(
            count=("workout_activity_type", "count"),
            duration_hours=("duration_hours", "sum"),
            energy_kcal=("total_energy_kcal", "sum"),
        )
        .sort_values("week")
    )
    return out


def summarize_by_type(df: pd.DataFrame) -> pd.DataFrame:
    """Return per-type aggregates over the selected period.

    Columns: activity_label, count, total_duration_h, avg_duration_h,
             total_distance_km, total_energy_kcal
    """
    if df.empty:
        return pd.DataFrame(
            columns=[
                "activity_label",
                "count",
                "total_duration_h",
                "avg_duration_h",
                "total_distance_km",
                "total_energy_kcal",
            ]
        )

    tmp = df.copy()
    tmp["duration_h"] = tmp["duration_s"].fillna(0.0) / 3600.0
    tmp["distance_km"] = tmp["total_distance_m"].fillna(0.0) / 1000.0
    label_col = "activity_label" if "activity_label" in tmp.columns else "workout_activity_type"

    out = (
        tmp.groupby(label_col, as_index=False)
        .agg(
            count=(label_col, "count"),
            total_duration_h=("duration_h", "sum"),
            avg_duration_h=("duration_h", "mean"),
            total_distance_km=("distance_km", "sum"),
            total_energy_kcal=("total_energy_kcal", "sum"),
        )
        .sort_values("count", ascending=False)
    )

    for col in ["total_duration_h", "avg_duration_h", "total_energy_kcal", "total_distance_km"]:
        out[col] = out[col].round(1)

    return out.rename(columns={label_col: "activity_label"})


def personal_records_by_type(df: pd.DataFrame) -> pd.DataFrame:
    """Return personal records (best single session) per workout type.

    Columns: activity_label, longest_duration_h, longest_duration_date,
             farthest_distance_km, farthest_distance_date,
             most_energy_kcal, most_energy_date
    """
    if df.empty:
        return pd.DataFrame()

    tmp = df.copy()
    tmp["duration_h"] = tmp["duration_s"].fillna(0.0) / 3600.0
    tmp["distance_km"] = tmp["total_distance_m"].fillna(0.0) / 1000.0
    label_col = "activity_label" if "activity_label" in tmp.columns else "workout_activity_type"

    rows = []
    for label, group in tmp.groupby(label_col):
        row: dict[str, object] = {"activity_label": label, "count": len(group)}

        # Longest session
        if not group["duration_h"].isna().all():
            idx = group["duration_h"].idxmax()
            row["longest_h"] = round(float(group.loc[idx, "duration_h"]), 2)
            row["longest_date"] = group.loc[idx, "start_at"]

        # Farthest distance
        if not group["distance_km"].isna().all() and group["distance_km"].max() > 0:
            idx = group["distance_km"].idxmax()
            row["farthest_km"] = round(float(group.loc[idx, "distance_km"]), 2)
            row["farthest_date"] = group.loc[idx, "start_at"]

        # Most energy
        if "total_energy_kcal" in group.columns and not group["total_energy_kcal"].isna().all():
            idx = group["total_energy_kcal"].idxmax()
            row["most_energy_kcal"] = round(float(group.loc[idx, "total_energy_kcal"]), 0)
            row["most_energy_date"] = group.loc[idx, "start_at"]

        rows.append(row)

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows).sort_values("count", ascending=False)


def workout_calendar_heatmap_data(df: pd.DataFrame) -> pd.DataFrame:
    """Return daily workout count/duration for a calendar heatmap.

    Columns: day, count, duration_h
    """
    if df.empty or "start_at" not in df.columns:
        return pd.DataFrame(columns=["day", "count", "duration_h"])

    tmp = df.copy()
    tmp["day"] = tmp["start_at"].dt.floor("D")
    tmp["duration_h"] = tmp["duration_s"].fillna(0.0) / 3600.0

    out = (
        tmp.groupby("day", as_index=False)
        .agg(count=("workout_activity_type", "count"), duration_h=("duration_h", "sum"))
        .sort_values("day")
    )
    return out
