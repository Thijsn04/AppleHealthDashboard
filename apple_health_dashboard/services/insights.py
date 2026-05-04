"""Cross-metric insight engine.

Provides functions that connect the dots between different health domains
(sleep, heart, activity, workouts) to surface insights Apple Health doesn't
natively offer.
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from apple_health_dashboard.services.heart import (
    HRV_TYPE,
    RESTING_HR_TYPE,
    hrv_trend,
    resting_hr_trend,
)
from apple_health_dashboard.services.sleep import (
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


# ── Cross-metric correlation matrix ──────────────────────────────────────────

def cross_metric_daily_table(df: pd.DataFrame, wdf: pd.DataFrame) -> pd.DataFrame:
    """Build a daily table of key metrics suitable for a correlation matrix.

    Returns columns: day, steps, sleep_h, rhr, hrv, active_kcal (if available).
    """
    from apple_health_dashboard.services.stats import summarize_by_day_agg
    from apple_health_dashboard.services.activity_summary import activity_summaries_to_dataframe

    result: dict[str, pd.Series] = {}

    STEP_TYPE = "HKQuantityTypeIdentifierStepCount"
    KCAL_TYPE = "HKQuantityTypeIdentifierActiveEnergyBurned"

    if not df.empty and "type" in df.columns:
        for rt, col, agg in [
            (STEP_TYPE, "steps", "sum"),
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
