"""Cross-metric insight engine.

Provides functions that connect the dots between different health domains
(sleep, heart, activity, workouts) to surface insights Apple Health doesn't
natively offer.
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING

import pandas as pd

from apple_health_dashboard.services.heart import (
    DIASTOLIC_TYPE,
    SYSTOLIC_TYPE,
    WALKING_HR_TYPE,
    hr_zone_distribution,
    hrv_trend,
    resting_hr_trend,
    spo2_trend,
    vo2max_trend,
)
from apple_health_dashboard.services.sleep import (
    SLEEP_STAGES_RESTORATIVE,
    sleep_duration_by_day,
    sleep_records,
)

if TYPE_CHECKING:
    pass

# ── Readiness score ───────────────────────────────────────────────────────────

_READINESS_WEIGHTS = {"hrv": 0.40, "rhr": 0.35, "sleep": 0.25}


def daily_readiness_score(
    df: pd.DataFrame,
    *,
    sleep_goal_h: float = 8.0,
) -> pd.DataFrame:
    """Compute a 0-100 daily readiness score.

    The score combines:
    - HRV (40 %): today's HRV vs personal 30-day baseline
    - Resting HR (35 %): today's RHR vs personal 30-day baseline (lower = better)
    - Sleep duration from the previous night (25 %): vs goal

    Returns columns: day, score, hrv_score, rhr_score, sleep_score,
                     hrv, rhr, sleep_h
    """
    srec = sleep_records(df)
    sleep_df = sleep_duration_by_day(srec, stages="actual")
    if sleep_df.empty:
        sleep_df = sleep_duration_by_day(srec, stages="all")

    hrv_df = hrv_trend(df)
    rhr_df = resting_hr_trend(df)

    # Build a date-indexed frame
    frames = {}
    if not hrv_df.empty:
        frames["hrv"] = hrv_df.set_index("day")["hrv"]
    if not rhr_df.empty:
        frames["rhr"] = rhr_df.set_index("day")["rhr"]
    if not sleep_df.empty:
        # Sleep is attributed to the morning it ended; use as "previous night"
        sleep_indexed = sleep_df.set_index("day")["hours"]
        # Shift forward one day so today's readiness reflects last night's sleep
        sleep_indexed.index = pd.to_datetime(sleep_indexed.index) + pd.Timedelta(days=1)
        frames["sleep"] = sleep_indexed

    if not frames:
        return pd.DataFrame(columns=["day", "score", "hrv_score", "rhr_score", "sleep_score"])

    combined = pd.DataFrame(frames)
    combined.index = pd.to_datetime(combined.index)
    combined = combined.sort_index()

    # Compute rolling 30-day baselines for HRV and RHR
    if "hrv" in combined.columns:
        combined["hrv_baseline"] = combined["hrv"].rolling(30, min_periods=7).mean()
        combined["hrv_std"] = combined["hrv"].rolling(30, min_periods=7).std()
    if "rhr" in combined.columns:
        combined["rhr_baseline"] = combined["rhr"].rolling(30, min_periods=7).mean()
        combined["rhr_std"] = combined["rhr"].rolling(30, min_periods=7).std()

    scores = []
    for ts, row in combined.iterrows():
        row_scores: dict[str, float | None] = {}

        # HRV score: 50 + z-score * 10, clamped to [0, 100]
        if "hrv" in combined.columns and pd.notna(row.get("hrv")) and pd.notna(row.get("hrv_baseline")):
            std = row.get("hrv_std") or 1.0
            std = max(std, 0.1)
            z = (row["hrv"] - row["hrv_baseline"]) / std
            row_scores["hrv_score"] = float(min(max(50 + z * 10, 0), 100))
            row_scores["hrv"] = float(row["hrv"])
        else:
            row_scores["hrv_score"] = None
            row_scores["hrv"] = None

        # RHR score: 50 - z-score * 10 (lower RHR is better)
        if "rhr" in combined.columns and pd.notna(row.get("rhr")) and pd.notna(row.get("rhr_baseline")):
            std = row.get("rhr_std") or 1.0
            std = max(std, 0.1)
            z = (row["rhr"] - row["rhr_baseline"]) / std
            row_scores["rhr_score"] = float(min(max(50 - z * 10, 0), 100))
            row_scores["rhr"] = float(row["rhr"])
        else:
            row_scores["rhr_score"] = None
            row_scores["rhr"] = None

        # Sleep score: linear, 0 h → 0, goal → 100 (cap at 100)
        if "sleep" in combined.columns and pd.notna(row.get("sleep")):
            row_scores["sleep_score"] = float(min(row["sleep"] / sleep_goal_h * 100, 100))
            row_scores["sleep_h"] = float(row["sleep"])
        else:
            row_scores["sleep_score"] = None
            row_scores["sleep_h"] = None

        # Weighted average over available components
        available = {k: v for k, v in [
            ("hrv", row_scores["hrv_score"]),
            ("rhr", row_scores["rhr_score"]),
            ("sleep", row_scores["sleep_score"]),
        ] if v is not None}

        if available:
            total_w = sum(_READINESS_WEIGHTS[k] for k in available)
            score = sum(_READINESS_WEIGHTS[k] * v for k, v in available.items()) / total_w
            row_scores["score"] = round(score, 1)
        else:
            row_scores["score"] = None

        row_scores["day"] = ts
        scores.append(row_scores)

    out = pd.DataFrame(scores)
    out = out[out["score"].notna()].copy()
    if out.empty:
        return pd.DataFrame(columns=["day", "score", "hrv_score", "rhr_score", "sleep_score"])
    out["day"] = pd.to_datetime(out["day"])
    return out.sort_values("day").reset_index(drop=True)


# ── Sleep → next-day HRV ─────────────────────────────────────────────────────

def sleep_hrv_pairs(df: pd.DataFrame) -> pd.DataFrame:
    """Pair each night's sleep duration with the HRV measured the following morning.

    Returns columns: day (date of HRV measurement), sleep_h, hrv, next_day
    """
    srec = sleep_records(df)
    sleep_df = sleep_duration_by_day(srec, stages="actual")
    if sleep_df.empty:
        sleep_df = sleep_duration_by_day(srec, stages="all")

    hrv_df = hrv_trend(df)

    if sleep_df.empty or hrv_df.empty:
        return pd.DataFrame(columns=["day", "sleep_h", "hrv"])

    sleep_df = sleep_df.copy()
    sleep_df["day"] = pd.to_datetime(sleep_df["day"])
    hrv_df = hrv_df.copy()
    hrv_df["day"] = pd.to_datetime(hrv_df["day"])

    # Shift sleep forward one day so we can join on the HRV day
    sleep_shifted = sleep_df.copy()
    sleep_shifted["day"] = sleep_shifted["day"] + pd.Timedelta(days=1)
    sleep_shifted = sleep_shifted.rename(columns={"hours": "sleep_h"})

    merged = hrv_df.merge(sleep_shifted, on="day", how="inner")
    return merged.sort_values("day").reset_index(drop=True)


# ── Activity → sleep ─────────────────────────────────────────────────────────

def steps_sleep_pairs(df: pd.DataFrame) -> pd.DataFrame:
    """Pair daily step count with that night's sleep duration.

    Returns columns: day, steps, sleep_h
    """
    from apple_health_dashboard.services.stats import summarize_by_day_agg

    STEP_TYPE = "HKQuantityTypeIdentifierStepCount"
    if df.empty or "type" not in df.columns:
        return pd.DataFrame(columns=["day", "steps", "sleep_h"])

    steps_raw = df[df["type"] == STEP_TYPE].copy()
    steps_daily = summarize_by_day_agg(steps_raw, agg="sum")

    srec = sleep_records(df)
    sleep_df = sleep_duration_by_day(srec, stages="actual")
    if sleep_df.empty:
        sleep_df = sleep_duration_by_day(srec, stages="all")

    if steps_daily.empty or sleep_df.empty:
        return pd.DataFrame(columns=["day", "steps", "sleep_h"])

    steps_daily = steps_daily.copy()
    steps_daily["day"] = pd.to_datetime(steps_daily["day"])
    steps_daily = steps_daily.rename(columns={"value": "steps"})

    sleep_df = sleep_df.copy()
    sleep_df["day"] = pd.to_datetime(sleep_df["day"])
    sleep_df = sleep_df.rename(columns={"hours": "sleep_h"})

    merged = steps_daily.merge(sleep_df, on="day", how="inner")
    return merged.sort_values("day").reset_index(drop=True)


# ── Workout → recovery (RHR next day) ────────────────────────────────────────

def workout_recovery_pairs(
    df: pd.DataFrame,
    wdf: pd.DataFrame,
) -> pd.DataFrame:
    """Compare resting HR on day-after-workout days vs rest days.

    Returns columns: day, rhr, is_post_workout
    """
    rhr_df = resting_hr_trend(df)
    if rhr_df.empty or wdf.empty or "start_at" not in wdf.columns:
        return pd.DataFrame(columns=["day", "rhr", "is_post_workout"])

    rhr_df = rhr_df.copy()
    rhr_df["day"] = pd.to_datetime(rhr_df["day"])

    workout_days = pd.to_datetime(wdf["start_at"].dt.floor("D").unique())
    # "Post-workout" days are the day after a workout
    post_workout_days = set((workout_days + pd.Timedelta(days=1)).normalize())

    rhr_df["is_post_workout"] = rhr_df["day"].isin(post_workout_days)
    return rhr_df.sort_values("day").reset_index(drop=True)


# ── Circadian profile ─────────────────────────────────────────────────────────

def circadian_profile(df: pd.DataFrame) -> pd.DataFrame:
    """Compute average bedtime and wake time by day of week.

    Returns columns: weekday (0=Mon…6=Sun), avg_bedtime_h (hour since midnight),
                     avg_waketime_h, n_nights
    """
    srec = sleep_records(df)
    if srec.empty or "start_at" not in srec.columns or "end_at" not in srec.columns:
        return pd.DataFrame(columns=["weekday", "avg_bedtime_h", "avg_waketime_h", "n_nights"])

    valid = srec[srec["start_at"].notna() & srec["end_at"].notna()].copy()
    # Keep only "asleep" records, not "in bed" noise
    if "value_str" in valid.columns:
        from apple_health_dashboard.services.sleep import SLEEP_STAGES_ACTUAL
        valid = valid[valid["value_str"].isin(SLEEP_STAGES_ACTUAL)]
    if valid.empty:
        return pd.DataFrame(columns=["weekday", "avg_bedtime_h", "avg_waketime_h", "n_nights"])

    # Group by the night date (date of sleep start, normalised)
    valid["night"] = valid["start_at"].dt.normalize()
    agg = valid.groupby("night").agg(
        bed_at=("start_at", "min"),
        wake_at=("end_at", "max"),
    ).reset_index()

    agg["weekday"] = agg["night"].dt.dayofweek  # 0=Mon

    def _to_decimal_hour(ts: pd.Timestamp) -> float:
        """Convert timestamp to hours since midnight, wrapping late nights past 24."""
        h = ts.hour + ts.minute / 60 + ts.second / 3600
        # Bedtimes after 18:00 are normal; times < 12:00 are next-day (add 24)
        return h if h >= 12 else h + 24

    agg["bed_h"] = agg["bed_at"].apply(_to_decimal_hour)
    agg["wake_h"] = agg["wake_at"].apply(lambda ts: ts.hour + ts.minute / 60 + ts.second / 3600)

    out = (
        agg.groupby("weekday")
        .agg(
            avg_bedtime_h=("bed_h", "mean"),
            avg_waketime_h=("wake_h", "mean"),
            n_nights=("night", "count"),
        )
        .reset_index()
    )
    return out.sort_values("weekday").reset_index(drop=True)


# ── Active energy pairs ───────────────────────────────────────────────────────

KCAL_TYPE = "HKQuantityTypeIdentifierActiveEnergyBurned"
STEP_TYPE_ID = "HKQuantityTypeIdentifierStepCount"


def active_energy_pairs(df: pd.DataFrame) -> pd.DataFrame:
    """Return daily active energy burned.

    Returns columns: day, active_kcal
    """
    from apple_health_dashboard.services.stats import summarize_by_day_agg

    if df.empty or "type" not in df.columns:
        return pd.DataFrame(columns=["day", "active_kcal"])

    sub = df[df["type"] == KCAL_TYPE].copy()
    daily = summarize_by_day_agg(sub, agg="sum")
    if daily.empty:
        return pd.DataFrame(columns=["day", "active_kcal"])

    daily["day"] = pd.to_datetime(daily["day"])
    return daily[["day", "value"]].rename(columns={"value": "active_kcal"}).sort_values("day")


def steps_rolling(df: pd.DataFrame, window: int = 7) -> pd.DataFrame:
    """Return daily step count with a rolling average.

    Returns columns: day, steps, steps_rolling
    """
    from apple_health_dashboard.services.stats import summarize_by_day_agg

    if df.empty or "type" not in df.columns:
        return pd.DataFrame(columns=["day", "steps", "steps_rolling"])

    sub = df[df["type"] == STEP_TYPE_ID].copy()
    daily = summarize_by_day_agg(sub, agg="sum")
    if daily.empty:
        return pd.DataFrame(columns=["day", "steps", "steps_rolling"])

    daily["day"] = pd.to_datetime(daily["day"])
    daily = daily.rename(columns={"value": "steps"}).sort_values("day").reset_index(drop=True)
    daily["steps_rolling"] = daily["steps"].rolling(window, min_periods=1).mean()
    return daily[["day", "steps", "steps_rolling"]]


def sleep_stages_daily(df: pd.DataFrame) -> pd.DataFrame:
    """Return daily restorative (deep + REM) sleep hours and fraction of total sleep.

    Returns columns: day, total_h, restorative_h, restorative_pct
    """
    srec = sleep_records(df)
    if srec.empty or "start_at" not in srec.columns or "end_at" not in srec.columns:
        return pd.DataFrame(columns=["day", "total_h", "restorative_h", "restorative_pct"])

    total_df = sleep_duration_by_day(srec, stages="actual")
    if total_df.empty:
        total_df = sleep_duration_by_day(srec, stages="all")

    valid = srec[srec["start_at"].notna() & srec["end_at"].notna()].copy()
    if "value_str" in valid.columns:
        valid = valid[valid["value_str"].isin(SLEEP_STAGES_RESTORATIVE)]
    else:
        return pd.DataFrame(columns=["day", "total_h", "restorative_h", "restorative_pct"])

    if valid.empty:
        return pd.DataFrame(columns=["day", "total_h", "restorative_h", "restorative_pct"])

    valid["duration_h"] = (valid["end_at"] - valid["start_at"]).dt.total_seconds() / 3600.0
    valid["day"] = valid["end_at"].dt.floor("D")
    rest_df = valid.groupby("day", as_index=False)["duration_h"].sum().rename(
        columns={"duration_h": "restorative_h"}
    )
    rest_df["day"] = pd.to_datetime(rest_df["day"])
    total_df["day"] = pd.to_datetime(total_df["day"])

    merged = total_df.merge(rest_df, on="day", how="inner").rename(columns={"hours": "total_h"})
    merged = merged[merged["total_h"] > 0].copy()
    merged["restorative_pct"] = (merged["restorative_h"] / merged["total_h"] * 100).round(1)
    return merged.sort_values("day").reset_index(drop=True)


def workout_duration_hrv_pairs(df: pd.DataFrame, wdf: pd.DataFrame) -> pd.DataFrame:
    """Pair each workout's duration with next-morning HRV.

    Returns columns: day (HRV measurement day), workout_duration_min, hrv, workout_type
    """
    from apple_health_dashboard.services.workouts import workout_label

    hrv_df = hrv_trend(df)
    if hrv_df.empty or wdf.empty or "start_at" not in wdf.columns:
        return pd.DataFrame(columns=["day", "workout_duration_min", "hrv", "workout_type"])

    hrv_df = hrv_df.copy()
    hrv_df["day"] = pd.to_datetime(hrv_df["day"])

    wdf2 = wdf.copy()
    wdf2["workout_day"] = pd.to_datetime(wdf2["start_at"]).dt.normalize()

    if "duration_min" not in wdf2.columns:
        if "end_at" in wdf2.columns and "start_at" in wdf2.columns:
            wdf2["duration_min"] = (
                (pd.to_datetime(wdf2["end_at"]) - pd.to_datetime(wdf2["start_at"]))
                .dt.total_seconds() / 60
            )
        else:
            return pd.DataFrame(columns=["day", "workout_duration_min", "hrv", "workout_type"])

    wdf2["hrv_day"] = wdf2["workout_day"] + pd.Timedelta(days=1)
    wdf2_agg = (
        wdf2.groupby("hrv_day")
        .agg(
            workout_duration_min=("duration_min", "sum"),
            workout_type=("workout_activity_type", "first"),
        )
        .reset_index()
        .rename(columns={"hrv_day": "day"})
    )
    wdf2_agg["workout_type"] = wdf2_agg["workout_type"].apply(
        lambda x: workout_label(x) if pd.notna(x) else "Unknown"
    )

    merged = hrv_df.merge(wdf2_agg, on="day", how="inner")
    return merged.sort_values("day").reset_index(drop=True)


def workout_duration_trend(wdf: pd.DataFrame, window: int = 7) -> pd.DataFrame:
    """Return per-workout durations with a rolling mean.

    Returns columns: day, duration_min, duration_rolling
    """
    if wdf.empty or "start_at" not in wdf.columns:
        return pd.DataFrame(columns=["day", "duration_min", "duration_rolling"])

    wdf2 = wdf.copy()
    wdf2["day"] = pd.to_datetime(wdf2["start_at"]).dt.normalize()

    if "duration_min" not in wdf2.columns:
        if "end_at" in wdf2.columns:
            wdf2["duration_min"] = (
                (pd.to_datetime(wdf2["end_at"]) - pd.to_datetime(wdf2["start_at"]))
                .dt.total_seconds() / 60
            )
        else:
            return pd.DataFrame(columns=["day", "duration_min", "duration_rolling"])

    wdf2 = wdf2[wdf2["duration_min"].notna() & (wdf2["duration_min"] > 0)].copy()
    if wdf2.empty:
        return pd.DataFrame(columns=["day", "duration_min", "duration_rolling"])

    wdf2 = wdf2.sort_values("day").reset_index(drop=True)
    wdf2["duration_rolling"] = wdf2["duration_min"].rolling(window, min_periods=1).mean()
    return wdf2[["day", "duration_min", "duration_rolling"]]


def sleep_debt_daily(
    df: pd.DataFrame,
    *,
    goal_h: float = 8.0,
) -> pd.DataFrame:
    """Return cumulative sleep debt relative to a nightly goal.

    Returns columns: day, sleep_h, debt_h, cumulative_debt_h
    A positive debt means you slept less than the goal; negative means surplus.
    """
    srec = sleep_records(df)
    sleep_df = sleep_duration_by_day(srec, stages="actual")
    if sleep_df.empty:
        sleep_df = sleep_duration_by_day(srec, stages="all")

    if sleep_df.empty:
        return pd.DataFrame(columns=["day", "sleep_h", "debt_h", "cumulative_debt_h"])

    out = sleep_df.rename(columns={"hours": "sleep_h"}).copy()
    out["day"] = pd.to_datetime(out["day"])
    out["debt_h"] = goal_h - out["sleep_h"]
    out["cumulative_debt_h"] = out["debt_h"].cumsum()
    return out.sort_values("day").reset_index(drop=True)


def best_workout_type_for_hrv(
    df: pd.DataFrame,
    wdf: pd.DataFrame,
) -> pd.DataFrame:
    """Return average next-morning HRV grouped by workout type.

    Returns columns: workout_type, avg_hrv, count
    Sorted by avg_hrv descending.
    """
    pairs = workout_duration_hrv_pairs(df, wdf)
    if pairs.empty or "workout_type" not in pairs.columns:
        return pd.DataFrame(columns=["workout_type", "avg_hrv", "count"])

    out = (
        pairs.groupby("workout_type")["hrv"]
        .agg(avg_hrv="mean", count="count")
        .reset_index()
        .sort_values("avg_hrv", ascending=False)
    )
    out["avg_hrv"] = out["avg_hrv"].round(1)
    return out


def weight_bmi_daily(df: pd.DataFrame) -> pd.DataFrame:
    """Return daily weight (kg) and BMI, merged on day.

    Returns columns: day, weight_kg, bmi (both are optional — only present rows are returned).
    """
    from apple_health_dashboard.services.body import bmi_trend, weight_trend

    w = weight_trend(df)
    b = bmi_trend(df)

    if w.empty and b.empty:
        return pd.DataFrame(columns=["day", "weight_kg", "bmi"])

    w["day"] = pd.to_datetime(w["day"])
    b["day"] = pd.to_datetime(b["day"])

    if w.empty:
        return b.rename(columns={"value": "bmi"})
    if b.empty:
        return w

    merged = w.merge(b, on="day", how="outer").sort_values("day").reset_index(drop=True)
    return merged


def spo2_daily(df: pd.DataFrame) -> pd.DataFrame:
    """Return daily SpO₂ (blood oxygen %).

    Returns columns: day, spo2
    """
    return spo2_trend(df)


def blood_pressure_daily(df: pd.DataFrame) -> pd.DataFrame:
    """Return daily systolic and diastolic blood pressure.

    Returns columns: day, systolic, diastolic
    """
    if df.empty or "type" not in df.columns:
        return pd.DataFrame(columns=["day", "systolic", "diastolic"])

    def _daily_mean(record_type: str, col: str) -> pd.DataFrame:
        sub = df[df["type"] == record_type].copy()
        if sub.empty or "value" not in sub.columns:
            return pd.DataFrame(columns=["day", col])
        sub = sub[sub["value"].notna() & sub["start_at"].notna()].copy()
        if sub.empty:
            return pd.DataFrame(columns=["day", col])
        sub["day"] = sub["start_at"].dt.floor("D")
        return sub.groupby("day")["value"].mean().reset_index().rename(columns={"value": col})

    sys_df = _daily_mean(SYSTOLIC_TYPE, "systolic")
    dia_df = _daily_mean(DIASTOLIC_TYPE, "diastolic")

    if sys_df.empty and dia_df.empty:
        return pd.DataFrame(columns=["day", "systolic", "diastolic"])

    sys_df["day"] = pd.to_datetime(sys_df["day"])
    dia_df["day"] = pd.to_datetime(dia_df["day"])

    if sys_df.empty:
        return dia_df
    if dia_df.empty:
        return sys_df

    merged = sys_df.merge(dia_df, on="day", how="outer").sort_values("day").reset_index(drop=True)
    return merged


def walking_hr_daily(df: pd.DataFrame) -> pd.DataFrame:
    """Return daily walking heart rate average.

    Returns columns: day, walking_hr
    """
    if df.empty or "type" not in df.columns:
        return pd.DataFrame(columns=["day", "walking_hr"])

    sub = df[df["type"] == WALKING_HR_TYPE].copy()
    if sub.empty or "value" not in sub.columns:
        return pd.DataFrame(columns=["day", "walking_hr"])

    sub = sub[sub["value"].notna() & sub["start_at"].notna()].copy()
    if sub.empty:
        return pd.DataFrame(columns=["day", "walking_hr"])

    sub["day"] = sub["start_at"].dt.floor("D")
    out = sub.groupby("day")["value"].mean().reset_index().rename(columns={"value": "walking_hr"})
    return out.sort_values("day").reset_index(drop=True)


def cross_metric_daily_table(df: pd.DataFrame, wdf: pd.DataFrame) -> pd.DataFrame:
    """Build a daily table of key metrics suitable for a correlation matrix.

    Returns columns: day, steps, sleep_h, rhr, hrv, active_kcal, restorative_h (if available).
    """
    from apple_health_dashboard.services.stats import summarize_by_day_agg

    result: dict[str, pd.Series] = {}

    if not df.empty and "type" in df.columns:
        for rt, col, agg in [
            (STEP_TYPE_ID, "steps", "sum"),
            (KCAL_TYPE, "active_kcal", "sum"),
        ]:
            sub = df[df["type"] == rt].copy()
            daily = summarize_by_day_agg(sub, agg=agg)
            if not daily.empty:
                result[col] = daily.set_index(pd.to_datetime(daily["day"]))["value"]

    hrv_df = hrv_trend(df)
    if not hrv_df.empty:
        result["hrv"] = hrv_df.set_index(pd.to_datetime(hrv_df["day"]))["hrv"]

    rhr_df = resting_hr_trend(df)
    if not rhr_df.empty:
        result["rhr"] = rhr_df.set_index(pd.to_datetime(rhr_df["day"]))["rhr"]

    srec = sleep_records(df)
    sleep_df = sleep_duration_by_day(srec, stages="actual")
    if sleep_df.empty:
        sleep_df = sleep_duration_by_day(srec, stages="all")
    if not sleep_df.empty:
        result["sleep_h"] = sleep_df.set_index(pd.to_datetime(sleep_df["day"]))["hours"]

    # Add restorative sleep hours to the correlation table
    rest_df = sleep_stages_daily(df)
    if not rest_df.empty:
        result["restorative_h"] = rest_df.set_index(pd.to_datetime(rest_df["day"]))["restorative_h"]

    if not result:
        return pd.DataFrame()

    combined = pd.DataFrame(result)
    combined.index.name = "day"
    return combined.reset_index().sort_values("day")


def correlation_matrix(daily_table: pd.DataFrame) -> pd.DataFrame:
    """Compute a Pearson correlation matrix from the daily table.

    Returns a square DataFrame indexed and columned by metric names.
    """
    if daily_table.empty:
        return pd.DataFrame()
    numeric = daily_table.drop(columns=["day"], errors="ignore").select_dtypes(include="number")
    if numeric.shape[1] < 2:
        return pd.DataFrame()
    return numeric.corr(method="pearson")


# ── Auto-generated insight cards ─────────────────────────────────────────────

def generate_insights(
    df: pd.DataFrame,
    wdf: pd.DataFrame,
    *,
    min_days: int = 14,
) -> list[dict[str, str]]:
    """Return a list of insight dicts with keys: title, body, icon, kind.

    kind is one of: "positive", "negative", "neutral", "info"
    Insights are only generated when there is enough data (min_days).
    """
    insights: list[dict[str, str]] = []

    srec = sleep_records(df)
    sleep_df = sleep_duration_by_day(srec, stages="actual")
    if sleep_df.empty:
        sleep_df = sleep_duration_by_day(srec, stages="all")

    hrv_df = hrv_trend(df)
    rhr_df = resting_hr_trend(df)

    # ── Sleep quality trend ────────────────────────────────────────────────────
    if not sleep_df.empty and len(sleep_df) >= min_days:
        hours = sleep_df["hours"]
        avg = hours.mean()
        recent_avg = hours.iloc[-7:].mean() if len(hours) >= 7 else avg
        older_avg = hours.iloc[-30:-7].mean() if len(hours) >= 30 else avg

        if len(hours) >= 30:
            delta = recent_avg - older_avg
            if delta >= 0.3:
                insights.append({
                    "title": "Sleep improving 📈",
                    "body": (
                        f"Your average sleep over the past 7 nights ({recent_avg:.1f}h) "
                        f"is {delta:.1f}h more than your recent 30-day average ({older_avg:.1f}h). "
                        "Better sleep supports better recovery, mood and performance."
                    ),
                    "icon": "😴",
                    "kind": "positive",
                })
            elif delta <= -0.3:
                insights.append({
                    "title": "Sleep declining ⚠️",
                    "body": (
                        f"Your average sleep this week ({recent_avg:.1f}h) is "
                        f"{abs(delta):.1f}h below your 30-day average ({older_avg:.1f}h). "
                        "Chronic sleep restriction affects HRV, weight and cognitive function."
                    ),
                    "icon": "😴",
                    "kind": "negative",
                })

        if avg < 7:
            insights.append({
                "title": "Below recommended sleep",
                "body": (
                    f"Your average sleep is {avg:.1f}h — below the 7h minimum recommended "
                    "for adults. Even 30 more minutes per night can meaningfully improve "
                    "HRV, focus and cardiovascular health."
                ),
                "icon": "⚠️",
                "kind": "negative",
            })

    # ── HRV trend ──────────────────────────────────────────────────────────────
    if not hrv_df.empty and len(hrv_df) >= min_days:
        hrv = hrv_df["hrv"]
        recent_hrv = hrv.iloc[-7:].mean()
        older_hrv = hrv.iloc[-30:-7].mean() if len(hrv) >= 30 else hrv.mean()

        if len(hrv) >= 30:
            pct_change = (recent_hrv - older_hrv) / max(older_hrv, 0.1) * 100
            if pct_change >= 10:
                insights.append({
                    "title": "HRV rising — great recovery 🟢",
                    "body": (
                        f"Your 7-day average HRV ({recent_hrv:.0f} ms) is "
                        f"{pct_change:.0f}% higher than your 30-day average ({older_hrv:.0f} ms). "
                        "Rising HRV signals your body is adapting well to training and stress."
                    ),
                    "icon": "❤️",
                    "kind": "positive",
                })
            elif pct_change <= -10:
                insights.append({
                    "title": "HRV dropping — consider recovery",
                    "body": (
                        f"Your 7-day average HRV ({recent_hrv:.0f} ms) is "
                        f"{abs(pct_change):.0f}% below your 30-day average ({older_hrv:.0f} ms). "
                        "Low HRV can indicate accumulated fatigue, stress or illness. "
                        "Prioritize sleep and reduce training intensity."
                    ),
                    "icon": "❤️",
                    "kind": "negative",
                })

    # ── Sleep ↔ HRV correlation ────────────────────────────────────────────────
    pairs = sleep_hrv_pairs(df)
    if not pairs.empty and len(pairs) >= min_days:
        corr = pairs["sleep_h"].corr(pairs["hrv"])
        if not math.isnan(corr) and abs(corr) >= 0.3:
            direction = "longer" if corr > 0 else "shorter"
            strength = "strongly" if abs(corr) >= 0.5 else "moderately"
            insights.append({
                "title": f"Sleep {direction} → better HRV next morning",
                "body": (
                    f"There is a {strength} {'positive' if corr > 0 else 'negative'} "
                    f"correlation ({corr:+.2f}) between how long you sleep and your "
                    "HRV the following morning. "
                    f"{'More sleep tends to mean better recovery.' if corr > 0 else 'Something is affecting both sleep and recovery — worth investigating.'}"
                ),
                "icon": "🔗",
                "kind": "positive" if corr > 0 else "neutral",
            })

    # ── Resting HR trend ──────────────────────────────────────────────────────
    if not rhr_df.empty and len(rhr_df) >= min_days:
        rhr = rhr_df["rhr"]
        recent_rhr = rhr.iloc[-7:].mean()
        older_rhr = rhr.iloc[-30:-7].mean() if len(rhr) >= 30 else rhr.mean()

        if len(rhr) >= 30:
            delta = recent_rhr - older_rhr
            if delta <= -2:
                insights.append({
                    "title": "Resting HR trending down 💪",
                    "body": (
                        f"Your resting HR this week ({recent_rhr:.0f} bpm) is "
                        f"{abs(delta):.0f} bpm lower than your 30-day average ({older_rhr:.0f} bpm). "
                        "A decreasing resting HR is one of the most reliable signs of improving cardiovascular fitness."
                    ),
                    "icon": "❤️",
                    "kind": "positive",
                })
            elif delta >= 3:
                insights.append({
                    "title": "Resting HR elevated",
                    "body": (
                        f"Your resting HR this week ({recent_rhr:.0f} bpm) is "
                        f"{delta:.0f} bpm above your 30-day average ({older_rhr:.0f} bpm). "
                        "An elevated resting HR can signal fatigue, illness or overtraining."
                    ),
                    "icon": "⚠️",
                    "kind": "negative",
                })

    # ── Workout frequency ─────────────────────────────────────────────────────
    if not wdf.empty and "start_at" in wdf.columns and len(wdf) >= 7:
        wdf_copy = wdf.copy()
        wdf_copy["day"] = pd.to_datetime(wdf_copy["start_at"]).dt.normalize()
        recent_7 = len(wdf_copy[wdf_copy["day"] >= wdf_copy["day"].max() - pd.Timedelta(days=6)])
        prev_7 = len(
            wdf_copy[
                (wdf_copy["day"] < wdf_copy["day"].max() - pd.Timedelta(days=6))
                & (wdf_copy["day"] >= wdf_copy["day"].max() - pd.Timedelta(days=13))
            ]
        )
        if recent_7 > prev_7 + 1:
            insights.append({
                "title": "Workout frequency up this week 🏋️",
                "body": (
                    f"You logged {recent_7} workout{'s' if recent_7 != 1 else ''} this week, "
                    f"up from {prev_7} the week before. "
                    "Consistent training is the strongest predictor of long-term fitness gains."
                ),
                "icon": "🏋️",
                "kind": "positive",
            })
        elif recent_7 < prev_7 - 1 and prev_7 > 0:
            insights.append({
                "title": "Workout frequency down this week",
                "body": (
                    f"You logged {recent_7} workout{'s' if recent_7 != 1 else ''} this week, "
                    f"down from {prev_7} the previous week. "
                    "If this is intentional recovery, great — otherwise consider what's getting in the way."
                ),
                "icon": "🏋️",
                "kind": "neutral",
            })

    # ── Post-workout recovery insight ─────────────────────────────────────────
    recovery = workout_recovery_pairs(df, wdf)
    if not recovery.empty and recovery["is_post_workout"].any() and (~recovery["is_post_workout"]).any():
        post = recovery[recovery["is_post_workout"]]["rhr"].mean()
        rest = recovery[~recovery["is_post_workout"]]["rhr"].mean()
        delta = post - rest
        if abs(delta) >= 1.5:
            if delta > 0:
                insights.append({
                    "title": "Your HR elevates after workouts",
                    "body": (
                        f"Your resting HR on days after a workout ({post:.0f} bpm) is "
                        f"{delta:.0f} bpm higher than on rest days ({rest:.0f} bpm). "
                        "This is normal — your heart is working harder to repair and adapt. "
                        "Watch that the elevation returns to baseline within 24-48 hours."
                    ),
                    "icon": "🔥",
                    "kind": "neutral",
                })
            else:
                insights.append({
                    "title": "Post-workout RHR actually lower 🌟",
                    "body": (
                        f"Your resting HR on days after a workout ({post:.0f} bpm) is "
                        f"{abs(delta):.0f} bpm *lower* than on rest days ({rest:.0f} bpm). "
                        "This indicates excellent aerobic adaptation — your cardiovascular system "
                        "recovers efficiently from training stress."
                    ),
                    "icon": "🌟",
                    "kind": "positive",
                })

    # ── Weekend warrior pattern ────────────────────────────────────────────────
    if not sleep_df.empty and len(sleep_df) >= 14:
        sleep_df2 = sleep_df.copy()
        sleep_df2["dow"] = pd.to_datetime(sleep_df2["day"]).dt.dayofweek
        weekday_sleep = sleep_df2[sleep_df2["dow"] < 5]["hours"].mean()
        weekend_sleep = sleep_df2[sleep_df2["dow"] >= 5]["hours"].mean()
        diff = weekend_sleep - weekday_sleep
        if diff >= 1.0:
            insights.append({
                "title": "Social jet lag detected 🕰️",
                "body": (
                    f"You sleep {diff:.1f}h more on weekends ({weekend_sleep:.1f}h) "
                    f"than weekdays ({weekday_sleep:.1f}h). "
                    "This 'social jet lag' can disrupt your circadian rhythm, making Monday mornings "
                    "feel harder and reducing weekday performance."
                ),
                "icon": "🕰️",
                "kind": "neutral",
            })

    # ── Steps goal compliance ─────────────────────────────────────────────────
    _STEP_GOAL = 8_000
    steps_df = steps_rolling(df)
    if not steps_df.empty and len(steps_df) >= min_days:
        goal_pct = float((steps_df["steps"] >= _STEP_GOAL).sum() / len(steps_df) * 100)
        avg_steps = float(steps_df["steps"].mean())
        if goal_pct >= 80:
            insights.append({
                "title": f"Steps goal crushed {goal_pct:.0f}% of days 🎯",
                "body": (
                    f"You hit {_STEP_GOAL:,} steps on {goal_pct:.0f}% of days "
                    f"(average {avg_steps:,.0f} steps/day). "
                    "Consistent daily movement is linked to lower cardiovascular risk "
                    "and better mood."
                ),
                "icon": "🏃",
                "kind": "positive",
            })
        elif goal_pct < 40:
            insights.append({
                "title": "Steps goal missed most days",
                "body": (
                    f"You reached {_STEP_GOAL:,} steps on only {goal_pct:.0f}% of days "
                    f"(average {avg_steps:,.0f} steps/day). "
                    "Even adding a 10-minute walk can make a measurable "
                    "difference to your health over time."
                ),
                "icon": "🚶",
                "kind": "negative",
            })

    # ── Active calorie burn trend ─────────────────────────────────────────────
    kcal_df = active_energy_pairs(df)
    if not kcal_df.empty and len(kcal_df) >= min_days:
        kcal = kcal_df["active_kcal"]
        recent_kcal = kcal.iloc[-7:].mean()
        older_kcal = kcal.iloc[-30:-7].mean() if len(kcal) >= 30 else kcal.mean()
        if len(kcal) >= 30:
            pct = (recent_kcal - older_kcal) / max(older_kcal, 1) * 100
            if pct >= 15:
                insights.append({
                    "title": "Active burn ramping up 🔥",
                    "body": (
                        f"Your active calorie burn this week ({recent_kcal:.0f} kcal/day) is "
                        f"{pct:.0f}% above your 30-day average ({older_kcal:.0f} kcal/day). "
                        "More active days mean more energy expenditure — keep it up!"
                    ),
                    "icon": "🔥",
                    "kind": "positive",
                })
            elif pct <= -15:
                insights.append({
                    "title": "Activity drop detected",
                    "body": (
                        f"Your active calorie burn this week ({recent_kcal:.0f} kcal/day) is "
                        f"{abs(pct):.0f}% below your 30-day average ({older_kcal:.0f} kcal/day). "
                        "A dip in active energy is normal after hard training blocks, "
                        "but worth noting if it persists."
                    ),
                    "icon": "📉",
                    "kind": "neutral",
                })

    # ── Restorative sleep (deep + REM) ────────────────────────────────────────
    rest_stages = sleep_stages_daily(df)
    if not rest_stages.empty and len(rest_stages) >= min_days:
        avg_rest_pct = float(rest_stages["restorative_pct"].mean())
        avg_rest_h = float(rest_stages["restorative_h"].mean())
        if avg_rest_pct >= 25:
            insights.append({
                "title": "Excellent restorative sleep 🌙",
                "body": (
                    f"On average {avg_rest_pct:.0f}% of your sleep ({avg_rest_h:.1f}h) "
                    "is Deep or REM sleep — above the typical 20-25% range. "
                    "Restorative sleep is when your brain consolidates memories "
                    "and your body repairs tissue."
                ),
                "icon": "🌙",
                "kind": "positive",
            })
        elif avg_rest_pct < 15:
            insights.append({
                "title": "Low restorative sleep ⚠️",
                "body": (
                    f"Only {avg_rest_pct:.0f}% of your sleep ({avg_rest_h:.1f}h) "
                    "is Deep or REM — below the recommended 20%. "
                    "Reducing alcohol, maintaining a consistent bedtime and avoiding screens "
                    "can increase restorative sleep stages."
                ),
                "icon": "⚠️",
                "kind": "negative",
            })

    # ── Sleep consistency (std dev) ───────────────────────────────────────────
    if not sleep_df.empty and len(sleep_df) >= min_days:
        sleep_std = float(sleep_df["hours"].std())
        sleep_avg = float(sleep_df["hours"].mean())
        if sleep_std <= 0.75 and sleep_avg >= 6.5:
            insights.append({
                "title": "Very consistent sleep schedule ✅",
                "body": (
                    f"Your nightly sleep duration varies by only ±{sleep_std:.1f}h on average. "
                    "High sleep consistency reinforces your circadian rhythm, "
                    "improves energy levels "
                    "and is associated with better cognitive performance."
                ),
                "icon": "✅",
                "kind": "positive",
            })
        elif sleep_std >= 1.5:
            insights.append({
                "title": "Irregular sleep pattern",
                "body": (
                    f"Your sleep duration varies by ±{sleep_std:.1f}h night to night. "
                    "Irregular sleep schedules are linked to metabolic issues "
                    "and poorer next-day mood. "
                    "Try to keep bedtime and wake time within a 30-minute "
                    "window each day."
                ),
                "icon": "🕐",
                "kind": "negative",
            })

    # ── VO₂ max trend ─────────────────────────────────────────────────────────
    vo2_df = vo2max_trend(df)
    if not vo2_df.empty and len(vo2_df) >= 7:
        from apple_health_dashboard.services.heart import classify_vo2max

        latest_vo2 = float(vo2_df["vo2max"].iloc[-1])
        classification = classify_vo2max(latest_vo2)
        if len(vo2_df) >= 14:
            older_vo2 = float(vo2_df["vo2max"].iloc[:-7].mean())
            recent_vo2 = float(vo2_df["vo2max"].iloc[-7:].mean())
            delta_vo2 = recent_vo2 - older_vo2
            if delta_vo2 >= 1.0:
                insights.append({
                    "title": "VO₂ max improving 📈",
                    "body": (
                        f"Your estimated VO₂ max has risen by {delta_vo2:.1f} mL/kg/min "
                        f"recently (latest: {latest_vo2:.1f} — {classification}). "
                        "This is the single best predictor of long-term cardiovascular health."
                    ),
                    "icon": "🫁",
                    "kind": "positive",
                })
            elif delta_vo2 <= -1.0:
                insights.append({
                    "title": "VO₂ max declining",
                    "body": (
                        f"Your estimated VO₂ max has dropped by {abs(delta_vo2):.1f} mL/kg/min "
                        f"recently (latest: {latest_vo2:.1f} — {classification}). "
                        "Aerobic training such as running, cycling or swimming "
                        "can reverse this trend."
                    ),
                    "icon": "🫁",
                    "kind": "negative",
                })
        else:
            insights.append({
                "title": f"VO₂ max: {classification}",
                "body": (
                    f"Your current estimated VO₂ max is {latest_vo2:.1f} mL/kg/min "
                    f"({classification}). "
                    "Regular cardio training — especially zone-2 sessions — "
                    "is the most effective way to raise this number over time."
                ),
                "icon": "🫁",
                "kind": "info",
            })

    # ── HRV absolute level ────────────────────────────────────────────────────
    if not hrv_df.empty and len(hrv_df) >= 7:
        _hrv_window = hrv_df["hrv"].iloc[-14:] if len(hrv_df) >= 14 else hrv_df["hrv"]
        avg_hrv = float(_hrv_window.mean())
        if avg_hrv >= 60:
            insights.append({
                "title": "Strong HRV baseline 💚",
                "body": (
                    f"Your recent average HRV is {avg_hrv:.0f} ms — above 60 ms, "
                    "which is associated with robust autonomic nervous system balance "
                    "and good aerobic fitness."
                ),
                "icon": "💚",
                "kind": "positive",
            })
        elif avg_hrv < 30:
            insights.append({
                "title": "HRV below typical range",
                "body": (
                    f"Your recent average HRV is {avg_hrv:.0f} ms — below 30 ms. "
                    "Low HRV can reflect chronic stress, insufficient sleep "
                    "or low aerobic fitness. "
                    "Sleep, stress management and consistent aerobic exercise are "
                    "the top levers to improve it."
                ),
                "icon": "💔",
                "kind": "negative",
            })

    # ── Workout type diversity ────────────────────────────────────────────────
    if not wdf.empty and "activity_type" in wdf.columns and len(wdf) >= 10:
        from apple_health_dashboard.services.workouts import workout_label

        n_types = wdf["activity_type"].nunique()
        top_type = wdf["activity_type"].value_counts().idxmax()
        top_label = workout_label(top_type)
        top_pct = float(wdf["activity_type"].value_counts().iloc[0] / len(wdf) * 100)
        if n_types >= 4:
            insights.append({
                "title": f"Varied training — {n_types} different workout types 🎯",
                "body": (
                    f"You've done {n_types} distinct workout types. "
                    f"Your most frequent is {top_label} ({top_pct:.0f}% of sessions). "
                    "Training variety reduces injury risk and builds well-rounded fitness."
                ),
                "icon": "🎯",
                "kind": "positive",
            })
        elif n_types == 1:
            insights.append({
                "title": f"All-in on {top_label}",
                "body": (
                    f"100% of your workouts are {top_label}. "
                    "Adding cross-training (e.g. strength work, yoga or swimming) "
                    "can reduce injury risk and improve overall performance "
                    "in your primary sport."
                ),
                "icon": "🔄",
                "kind": "neutral",
            })

    # ── Workout duration trend ────────────────────────────────────────────────
    dur_df = workout_duration_trend(wdf)
    if not dur_df.empty and len(dur_df) >= 14:
        recent_dur = float(dur_df["duration_min"].iloc[-7:].mean())
        if len(dur_df) >= 30:
            older_dur = float(dur_df["duration_min"].iloc[-30:-7].mean())
        else:
            older_dur = float(dur_df["duration_min"].mean())
        delta_dur = recent_dur - older_dur
        if len(dur_df) >= 30 and delta_dur >= 10:
            insights.append({
                "title": "Workouts getting longer ⏱️",
                "body": (
                    f"Your recent workout sessions average {recent_dur:.0f} min, "
                    f"up {delta_dur:.0f} min from your 30-day average ({older_dur:.0f} min). "
                    "Longer sessions can build endurance — just be mindful of recovery."
                ),
                "icon": "⏱️",
                "kind": "positive",
            })
        elif len(dur_df) >= 30 and delta_dur <= -10:
            insights.append({
                "title": "Shorter sessions recently",
                "body": (
                    f"Recent workouts average {recent_dur:.0f} min vs {older_dur:.0f} min before. "
                    "If intentional (deload, taper), this is smart. "
                    "Otherwise, shorter sessions can still be effective — quality beats quantity."
                ),
                "icon": "⏱️",
                "kind": "neutral",
            })

    # ── Steps weekday vs weekend ──────────────────────────────────────────────
    if not steps_df.empty and len(steps_df) >= 14:
        steps_df2 = steps_df.copy()
        steps_df2["dow"] = pd.to_datetime(steps_df2["day"]).dt.dayofweek
        weekday_steps = steps_df2[steps_df2["dow"] < 5]["steps"].mean()
        weekend_steps = steps_df2[steps_df2["dow"] >= 5]["steps"].mean()
        if not (pd.isna(weekday_steps) or pd.isna(weekend_steps)):
            diff_steps = weekday_steps - weekend_steps
            if diff_steps >= 2000:
                insights.append({
                    "title": "More active on weekdays 💼",
                    "body": (
                        f"You average {weekday_steps:,.0f} steps on weekdays vs "
                        f"{weekend_steps:,.0f} on weekends "
                        f"— a difference of {diff_steps:,.0f}. "
                        "Try adding a weekend walk or outdoor activity "
                        "to balance your weekly movement."
                    ),
                    "icon": "💼",
                    "kind": "neutral",
                })
            elif diff_steps <= -2000:
                insights.append({
                    "title": "Weekend warrior walker 🏖️",
                    "body": (
                        f"You move more on weekends ({weekend_steps:,.0f} steps) "
                        f"than weekdays ({weekday_steps:,.0f} steps). "
                        "Adding short walking breaks during the work week can significantly "
                        "reduce sedentary time and improve metabolic health."
                    ),
                    "icon": "🏖️",
                    "kind": "neutral",
                })

    # ── Steps ↔ active calories correlation ──────────────────────────────────
    if not steps_df.empty and not kcal_df.empty:
        sc = steps_df.merge(kcal_df, on="day", how="inner")
        if len(sc) >= min_days:
            corr_sc = sc["steps"].corr(sc["active_kcal"])
            if not math.isnan(corr_sc) and corr_sc >= 0.7:
                insights.append({
                    "title": "Steps drive your calorie burn 🔗",
                    "body": (
                        f"Steps and active calorie burn are strongly correlated "
                        f"(r={corr_sc:.2f}). "
                        "Daily walking is your most reliable lever for increasing "
                        "total energy expenditure."
                    ),
                    "icon": "🔗",
                    "kind": "info",
                })

    # ── Body weight trend ─────────────────────────────────────────────────────
    wb_df = weight_bmi_daily(df)
    if not wb_df.empty and "weight_kg" in wb_df.columns and len(wb_df) >= min_days:
        wt = wb_df["weight_kg"].dropna()
        if len(wt) >= 7:
            first_w = float(wt.iloc[0])
            last_w = float(wt.iloc[-1])
            delta_w = last_w - first_w
            if abs(delta_w) >= 1.0:
                direction = "lost" if delta_w < 0 else "gained"
                kind = "positive" if delta_w < 0 else "neutral"
                insights.append({
                    "title": f"Weight {direction} {abs(delta_w):.1f} kg over the period",
                    "body": (
                        f"You have {direction} {abs(delta_w):.1f} kg "
                        f"(from {first_w:.1f} kg to {last_w:.1f} kg). "
                        "Weight trends over weeks are more meaningful than day-to-day fluctuations."
                    ),
                    "icon": "⚖️",
                    "kind": kind,
                })

    # ── SpO₂ alert ────────────────────────────────────────────────────────────
    spo2_df = spo2_daily(df)
    if not spo2_df.empty and len(spo2_df) >= 7:
        recent_spo2 = float(spo2_df["spo2"].iloc[-7:].mean())
        low_nights = int((spo2_df["spo2"] < 95).sum())
        if recent_spo2 < 95:
            insights.append({
                "title": "Blood oxygen below normal ⚠️",
                "body": (
                    f"Your average SpO₂ over the last 7 readings is {recent_spo2:.1f}% "
                    "— below the normal range (≥95%). "
                    "Persistently low blood oxygen can indicate sleep apnea or other "
                    "conditions worth discussing with a doctor."
                ),
                "icon": "🫁",
                "kind": "negative",
            })
        elif low_nights >= 5:
            insights.append({
                "title": f"SpO₂ dipped below 95% on {low_nights} nights",
                "body": (
                    f"You had {low_nights} readings below 95% SpO₂. "
                    "Occasional brief dips are normal, but frequent low readings "
                    "during sleep may indicate sleep-disordered breathing."
                ),
                "icon": "💨",
                "kind": "neutral",
            })
        else:
            avg_spo2 = float(spo2_df["spo2"].mean())
            if avg_spo2 >= 98:
                insights.append({
                    "title": "Excellent blood oxygen ✅",
                    "body": (
                        f"Your average SpO₂ is {avg_spo2:.1f}% — in the excellent range. "
                        "Good blood oxygen reflects healthy lung and cardiovascular function."
                    ),
                    "icon": "✅",
                    "kind": "positive",
                })

    # ── Blood pressure ────────────────────────────────────────────────────────
    bp_df = blood_pressure_daily(df)
    if not bp_df.empty and "systolic" in bp_df.columns and len(bp_df) >= 5:
        avg_sys = float(bp_df["systolic"].dropna().mean())
        _has_dia = "diastolic" in bp_df.columns and bp_df["diastolic"].notna().any()
        avg_dia = float(bp_df["diastolic"].dropna().mean()) if _has_dia else None
        if avg_sys >= 140:
            insights.append({
                "title": "Blood pressure: Stage 2 hypertension range ⚠️",
                "body": (
                    f"Your average systolic BP is {avg_sys:.0f} mmHg "
                    + (f"/ {avg_dia:.0f} mmHg diastolic" if avg_dia else "")
                    + ". Readings ≥140/90 mmHg consistently indicate hypertension. "
                    "Consult a healthcare professional."
                ),
                "icon": "🩺",
                "kind": "negative",
            })
        elif avg_sys >= 130:
            insights.append({
                "title": "Blood pressure: elevated",
                "body": (
                    f"Your average systolic BP is {avg_sys:.0f} mmHg — in the Stage 1 "
                    "hypertension range (130-139). "
                    "Lifestyle changes (less sodium, more exercise, stress reduction) "
                    "can bring this down."
                ),
                "icon": "🩺",
                "kind": "neutral",
            })
        elif avg_sys < 120:
            insights.append({
                "title": "Blood pressure: healthy range 🟢",
                "body": (
                    f"Your average systolic BP is {avg_sys:.0f} mmHg "
                    "— in the healthy normal range (<120 mmHg). "
                    "Regular physical activity, a healthy diet and good sleep all "
                    "contribute to healthy blood pressure."
                ),
                "icon": "🟢",
                "kind": "positive",
            })

    # ── Walking HR as fitness proxy ───────────────────────────────────────────
    whr_df = walking_hr_daily(df)
    if not whr_df.empty and len(whr_df) >= min_days:
        whr = whr_df["walking_hr"]
        recent_whr = float(whr.iloc[-7:].mean())
        older_whr = float(whr.iloc[-30:-7].mean()) if len(whr) >= 30 else float(whr.mean())
        if len(whr) >= 30:
            delta_whr = recent_whr - older_whr
            if delta_whr <= -3:
                insights.append({
                    "title": "Walking HR improving — aerobic fitness up 📉",
                    "body": (
                        f"Your walking heart rate has dropped by {abs(delta_whr):.0f} bpm "
                        f"recently ({recent_whr:.0f} bpm vs {older_whr:.0f} bpm). "
                        "A lower walking HR at the same effort is a sign that your "
                        "cardiovascular fitness is improving."
                    ),
                    "icon": "🚶",
                    "kind": "positive",
                })
            elif delta_whr >= 4:
                insights.append({
                    "title": "Walking HR elevated this week",
                    "body": (
                        f"Your walking heart rate is {delta_whr:.0f} bpm higher this week "
                        f"({recent_whr:.0f} bpm) than your recent average. "
                        "This could reflect fatigue, illness or reduced activity. "
                        "Worth monitoring over the next few days."
                    ),
                    "icon": "🚶",
                    "kind": "neutral",
                })

    # ── Sleep debt ────────────────────────────────────────────────────────────
    debt_df = sleep_debt_daily(df)
    if not debt_df.empty and len(debt_df) >= 7:
        recent_debt = float(debt_df["cumulative_debt_h"].iloc[-1])
        nightly_avg = float(debt_df["sleep_h"].mean())
        if recent_debt >= 7:
            insights.append({
                "title": f"You've built up ~{recent_debt:.0f}h of sleep debt 😴",
                "body": (
                    f"Based on an 8-hour goal, you have accumulated ~{recent_debt:.0f}h "
                    f"of sleep debt (averaging {nightly_avg:.1f}h/night). "
                    "Research shows sleep debt impairs cognition, mood and immune function. "
                    "Catching up gradually with 30-60 min extra per night is most effective."
                ),
                "icon": "😴",
                "kind": "negative",
            })
        elif recent_debt <= -5:
            insights.append({
                "title": "Sleep surplus 🌟",
                "body": (
                    f"You're averaging {nightly_avg:.1f}h/night — "
                    f"{abs(recent_debt):.0f}h above an 8-hour goal. "
                    "Consistent quality sleep this long is excellent for recovery, "
                    "cognitive function and long-term health."
                ),
                "icon": "🌟",
                "kind": "positive",
            })

    # ── Best workout type for HRV ─────────────────────────────────────────────
    best_type_df = best_workout_type_for_hrv(df, wdf)
    if not best_type_df.empty and len(best_type_df) >= 2:
        best = best_type_df.iloc[0]
        worst = best_type_df.iloc[-1]
        if best["count"] >= 3 and worst["count"] >= 3:
            diff = float(best["avg_hrv"]) - float(worst["avg_hrv"])
            if diff >= 5:
                insights.append({
                    "title": (
                        f"{best['workout_type']} leaves you most recovered 🏆"
                    ),
                    "body": (
                        f"After {best['workout_type']} sessions your next-morning HRV "
                        f"averages {best['avg_hrv']:.0f} ms — {diff:.0f} ms higher than "
                        f"after {worst['workout_type']} ({worst['avg_hrv']:.0f} ms). "
                        "Scheduling more of your best-recovery workouts may help you "
                        "maintain higher readiness across the week."
                    ),
                    "icon": "🏆",
                    "kind": "positive",
                })

    # ── HR zone balance ───────────────────────────────────────────────────────
    zone_df = hr_zone_distribution(df)
    if not zone_df.empty:
        total_min = zone_df["minutes"].sum()
        if total_min > 60:
            _z2_rows = zone_df.loc[zone_df["zone"].str.contains("Zone 2", na=False), "pct"]
            z2_pct = float(_z2_rows.values[0]) if not _z2_rows.empty else 0.0
            _z5_rows = zone_df.loc[zone_df["zone"].str.contains("Zone 5", na=False), "pct"]
            z5_pct = float(_z5_rows.values[0]) if not _z5_rows.empty else 0.0
            if z2_pct >= 40:
                insights.append({
                    "title": "Great aerobic base training 🟢",
                    "body": (
                        f"You spend {z2_pct:.0f}% of your active HR time in Zone 2 "
                        "(aerobic base). "
                        "Zone 2 training is the foundation of endurance — it builds "
                        "mitochondrial density and fat-burning efficiency."
                    ),
                    "icon": "🟢",
                    "kind": "positive",
                })
            elif z5_pct >= 30:
                insights.append({
                    "title": "Heavy Zone 5 — add more easy training 🔴",
                    "body": (
                        f"You spend {z5_pct:.0f}% of your HR time in Zone 5 (VO₂ max). "
                        "While intense training builds speed, excessive Zone 5 without "
                        "adequate Zone 2 base work can increase injury risk and hinder "
                        "recovery."
                    ),
                    "icon": "⚠️",
                    "kind": "neutral",
                })

    # ── Resting HR vs VO₂ max synergy ─────────────────────────────────────────
    vo2_df_i = vo2max_trend(df)
    rhr_df_i = resting_hr_trend(df)
    if not vo2_df_i.empty and not rhr_df_i.empty and len(vo2_df_i) >= 7:
        latest_vo2 = float(vo2_df_i["vo2max"].iloc[-1])
        latest_rhr = float(rhr_df_i["rhr"].iloc[-1])
        if latest_vo2 >= 45 and latest_rhr <= 55:
            insights.append({
                "title": "Excellent cardio fitness profile 🏆",
                "body": (
                    f"Your latest VO₂ max ({latest_vo2:.1f} mL/kg/min) "
                    f"and resting HR ({latest_rhr:.0f} bpm) are both in excellent ranges. "
                    "This combination is one of the strongest predictors of long-term "
                    "cardiovascular health and longevity."
                ),
                "icon": "🏆",
                "kind": "positive",
            })

    # ── No-insight fallback ───────────────────────────────────────────────────
    if not insights:
        insights.append({
            "title": "Keep collecting data",
            "body": (
                "Import more Apple Health data to unlock personalised cross-metric insights. "
                "At least 2 weeks of combined heart, sleep and activity data is needed."
            ),
            "icon": "ℹ️",
            "kind": "info",
        })

    return insights
