from __future__ import annotations

import pandas as pd
import pytest

from apple_health_dashboard.services.sleep import (
    sleep_duration_by_day,
    sleep_consistency_stats,
    sleep_stages_by_day,
    SLEEP_STAGES_ACTUAL,
)
from apple_health_dashboard.services.heart import (
    hr_daily_stats,
    resting_hr_trend,
    hrv_trend,
    classify_vo2max,
    HEART_RATE_TYPE,
    RESTING_HR_TYPE,
    HRV_TYPE,
)
from apple_health_dashboard.services.body import (
    weight_trend,
    bmi_category,
    body_summary_stats,
)
from apple_health_dashboard.services.streaks import (
    daily_streak,
    longest_streak,
    personal_bests,
)
from apple_health_dashboard.services.workouts import (
    workout_label,
    summarize_by_type,
    personal_records_by_type,
)
from apple_health_dashboard.services.metrics import (
    metric_label,
    metric_aggregation,
    metrics_by_category,
    METRICS,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _sleep_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "type": ["HKCategoryTypeIdentifierSleepAnalysis"] * 3,
            "value_str": [
                "HKCategoryValueSleepAnalysisAsleepCore",
                "HKCategoryValueSleepAnalysisAsleepDeep",
                "HKCategoryValueSleepAnalysisAsleepREM",
            ],
            "start_at": pd.to_datetime(
                ["2024-01-01 23:00", "2024-01-02 01:00", "2024-01-02 03:00"], utc=True
            ),
            "end_at": pd.to_datetime(
                ["2024-01-02 01:00", "2024-01-02 03:00", "2024-01-02 07:00"], utc=True
            ),
        }
    )


def _hr_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "type": [HEART_RATE_TYPE] * 3,
            "value": [60.0, 75.0, 90.0],
            "start_at": pd.to_datetime(
                ["2024-01-01 08:00", "2024-01-01 12:00", "2024-01-02 08:00"], utc=True
            ),
            "end_at": pd.to_datetime(
                ["2024-01-01 08:05", "2024-01-01 12:05", "2024-01-02 08:05"], utc=True
            ),
        }
    )


def _rhr_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "type": [RESTING_HR_TYPE] * 2,
            "value": [58.0, 62.0],
            "start_at": pd.to_datetime(["2024-01-01", "2024-01-02"], utc=True),
            "end_at": pd.to_datetime(["2024-01-01", "2024-01-02"], utc=True),
        }
    )


def _weight_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "type": ["HKQuantityTypeIdentifierBodyMass"] * 3,
            "value": [80.0, 79.5, 79.0],
            "unit": ["kg", "kg", "kg"],
            "start_at": pd.to_datetime(["2024-01-01", "2024-01-05", "2024-01-10"], utc=True),
            "end_at": pd.to_datetime(["2024-01-01", "2024-01-05", "2024-01-10"], utc=True),
        }
    )


# ── Sleep tests ────────────────────────────────────────────────────────────────

class TestSleepDurationByDay:
    def test_actual_stages(self) -> None:
        df = _sleep_df()
        result = sleep_duration_by_day(df, stages="actual")
        assert not result.empty
        assert result["hours"].sum() == pytest.approx(8.0)

    def test_empty_df(self) -> None:
        result = sleep_duration_by_day(pd.DataFrame(), stages="actual")
        assert result.empty

    def test_stages_wide(self) -> None:
        df = _sleep_df()
        result = sleep_stages_by_day(df)
        assert not result.empty
        assert "day" in result.columns

    def test_consistency_stats_returns_dict(self) -> None:
        df = _sleep_df()
        stats = sleep_consistency_stats(df)
        assert isinstance(stats, dict)
        assert "avg_hours" in stats
        assert stats["avg_hours"] == pytest.approx(8.0)


# ── Heart tests ────────────────────────────────────────────────────────────────

class TestHeartServices:
    def test_hr_daily_stats(self) -> None:
        df = _hr_df()
        result = hr_daily_stats(df)
        assert "hr_mean" in result.columns
        assert len(result) == 2  # 2 distinct days

    def test_resting_hr_trend_dedicated(self) -> None:
        df = _rhr_df()
        result = resting_hr_trend(df)
        assert "rhr" in result.columns
        assert len(result) == 2

    def test_resting_hr_trend_falls_back_to_mean(self) -> None:
        # No resting HR records — should fall back to mean HR
        df = _hr_df()
        result = resting_hr_trend(df)
        assert "rhr" in result.columns

    def test_hrv_trend_empty(self) -> None:
        result = hrv_trend(pd.DataFrame())
        assert result.empty

    def test_classify_vo2max(self) -> None:
        assert classify_vo2max(25.0) == "Very Poor"
        assert classify_vo2max(45.0) == "Good"
        assert classify_vo2max(65.0) == "Superior"


# ── Body tests ────────────────────────────────────────────────────────────────

class TestBodyServices:
    def test_weight_trend(self) -> None:
        df = _weight_df()
        result = weight_trend(df)
        assert "weight_kg" in result.columns
        assert len(result) == 3

    def test_weight_trend_lbs_conversion(self) -> None:
        df = _weight_df().copy()
        df["value"] = df["value"] * 2.20462  # convert kg→lbs
        df["unit"] = "lb"
        result = weight_trend(df)
        assert result["weight_kg"].iloc[0] == pytest.approx(80.0, rel=0.01)

    def test_bmi_category(self) -> None:
        assert bmi_category(16.0) == "Underweight"
        assert bmi_category(22.0) == "Normal weight"
        assert bmi_category(27.0) == "Overweight"
        assert bmi_category(35.0) == "Obese"

    def test_body_summary_stats(self) -> None:
        df = _weight_df()
        stats = body_summary_stats(df)
        assert "latest_weight_kg" in stats
        assert stats["latest_weight_kg"] == pytest.approx(79.0)
        assert stats["weight_change_kg"] == pytest.approx(-1.0)


# ── Streaks tests ─────────────────────────────────────────────────────────────

class TestStreaks:
    def test_longest_streak(self) -> None:
        df = pd.DataFrame(
            {
                "day": pd.to_datetime(
                    ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-05"]
                ),
                "steps": [1000, 2000, 3000, 4000],
            }
        )
        assert longest_streak(df, threshold=0) == 3

    def test_personal_bests(self) -> None:
        df = pd.DataFrame(
            {
                "day": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
                "steps": [5000, 12000, 8000],
            }
        )
        pb = personal_bests(df)
        assert pb["max_value"] == 12000.0
        assert pb["avg_value"] == pytest.approx(25000 / 3)

    def test_daily_streak_empty(self) -> None:
        assert daily_streak(pd.DataFrame()) == 0


# ── Workouts tests ────────────────────────────────────────────────────────────

class TestWorkouts:
    def test_workout_label_known(self) -> None:
        assert workout_label("HKWorkoutActivityTypeRunning") == "Running"

    def test_workout_label_unknown_fallback(self) -> None:
        label = workout_label("HKWorkoutActivityTypeUnknownXYZ")
        assert "UnknownXYZ" in label

    def test_summarize_by_type(self) -> None:
        df = pd.DataFrame(
            {
                "workout_activity_type": ["HKWorkoutActivityTypeRunning"] * 2,
                "activity_label": ["Running", "Running"],
                "start_at": pd.to_datetime(["2024-01-01", "2024-01-02"], utc=True),
                "end_at": pd.to_datetime(["2024-01-01", "2024-01-02"], utc=True),
                "duration_s": [3600.0, 5400.0],
                "total_energy_kcal": [300.0, 450.0],
                "total_distance_m": [10000.0, 15000.0],
            }
        )
        result = summarize_by_type(df)
        assert len(result) == 1
        assert result.iloc[0]["count"] == 2
        assert result.iloc[0]["total_duration_h"] == pytest.approx(2.5)

    def test_personal_records_by_type(self) -> None:
        df = pd.DataFrame(
            {
                "workout_activity_type": ["HKWorkoutActivityTypeRunning"] * 2,
                "activity_label": ["Running", "Running"],
                "start_at": pd.to_datetime(["2024-01-01", "2024-01-02"], utc=True),
                "end_at": pd.to_datetime(["2024-01-01", "2024-01-02"], utc=True),
                "duration_s": [3600.0, 7200.0],
                "total_energy_kcal": [300.0, 600.0],
                "total_distance_m": [10000.0, 20000.0],
            }
        )
        result = personal_records_by_type(df)
        assert not result.empty
        run_row = result[result["activity_label"] == "Running"].iloc[0]
        assert run_row["longest_h"] == pytest.approx(2.0)
        assert run_row["farthest_km"] == pytest.approx(20.0)


# ── Metrics catalogue tests ───────────────────────────────────────────────────

class TestMetrics:
    def test_metric_label_known(self) -> None:
        assert metric_label("HKQuantityTypeIdentifierStepCount") == "Steps"

    def test_metric_label_unknown_fallback(self) -> None:
        label = metric_label("HKQuantityTypeIdentifierFooBar")
        assert "FooBar" in label

    def test_metric_aggregation_defaults_to_sum(self) -> None:
        assert metric_aggregation("HKQuantityTypeIdentifierStepCount") == "sum"
        assert metric_aggregation("HKQuantityTypeIdentifierUnknown") == "sum"

    def test_all_metrics_have_label(self) -> None:
        for m in METRICS:
            assert m.label, f"Metric {m.record_type} has no label"

    def test_metrics_by_category_not_empty(self) -> None:
        by_cat = metrics_by_category()
        assert len(by_cat) >= 5
        assert "Activity" in by_cat
        assert "Heart" in by_cat
