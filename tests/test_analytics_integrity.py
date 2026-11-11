from datetime import date
from pathlib import Path

import duckdb
import pytest

from apple_health_dashboard.api.analytics import (
    metric_series,
    paged_records,
    sleep_summary,
    workout_summary,
)
from apple_health_dashboard.ingest.importer import import_export_xml_to_duckdb_all
from apple_health_dashboard.ingest.safe_import import ImportValidationError, preview_export
from apple_health_dashboard.storage.duckdb_store import init_db

DISTANCE = "HKQuantityTypeIdentifierDistanceWalkingRunning"
SLEEP = "HKCategoryTypeIdentifierSleepAnalysis"


def record(kind, start, end, value, *, unit="", source="Watch", extra=""):
    unit_attribute = f'unit="{unit}"' if unit else ""
    return (
        f'<Record type="{kind}" startDate="{start}" endDate="{end}" value="{value}" '
        f'sourceName="{source}" {unit_attribute} {extra}/>'
    )


def load(tmp_path: Path, *elements: str) -> Path:
    xml = tmp_path / "sample.xml"
    xml.write_text("<HealthData>" + "".join(elements) + "</HealthData>", encoding="utf-8")
    db = tmp_path / "sample.duckdb"
    import_export_xml_to_duckdb_all(xml, db)
    return db


def test_source_calendar_units_overlaps_and_missing_buckets(tmp_path: Path):
    early = "2024-01-01 00:10:00 +0200"
    end = "2024-01-01 00:20:00 +0200"
    later = "2024-01-01 00:30:00 +0200"
    db = load(
        tmp_path,
        record(DISTANCE, early, end, 500, unit="m", extra='device="Watch A"'),
        record(DISTANCE, early, end, 500, unit="m", extra='device="Watch A" creationDate="2024-01-01 01:00:00 +0200"'),
        record(DISTANCE, early, end, 500, unit="m", extra='device="Watch A"'),
        record(DISTANCE, end, later, 1, unit="km", extra='device="Watch A"'),
        record(DISTANCE, "2024-01-01 00:15:00 +0200", end, 0.2, unit="km", extra='device="Watch A"'),
        record(DISTANCE, early, later, 1.5, unit="km", source="Phone"),
        record(DISTANCE, early, end, 2000, unit="unknown"),
        record(DISTANCE, "2024-01-03 00:00:00 +0200", "2024-01-03 00:00:00 +0200", "Infinity", unit="km"),
        record(DISTANCE, "2024-01-08 11:00:00 -0700", "2024-01-08 11:00:00 -0700", 1, unit="mi"),
    )
    start, finish = date(2024, 1, 1), date(2024, 1, 8)
    result = metric_series(db, DISTANCE, None, start, finish, "week")
    assert result["excluded_samples"] == 5
    assert [point["date"] for point in result["points"]] == ["2024-01-01", "2024-01-08"]
    assert [point["value"] for point in result["points"]] == pytest.approx([1.5, 1.609344])
    assert result["points"][0]["sample_count"] == 2
    assert metric_series(db, DISTANCE, None, start, finish, source="Phone")["points"][0]["sample_count"] == 1
    assert metric_series(db, "HKQuantityTypeIdentifierUnknown", None)["points"] == []
    rows = paged_records(db, DISTANCE, 0, 50, start, start, "Watch")
    assert rows["total"] == 5
    assert rows["items"][0]["start_at"] == "2024-01-01T00:20:00+02:00"
    assert rows["items"][0]["device"] == "Watch A"


def test_sleep_uses_elapsed_time_and_excludes_conflicting_stages(tmp_path: Path):
    begin = "2024-10-26 23:00:00 +0200"
    core_end = "2024-10-27 03:00:00 +0100"
    wake = "2024-10-27 06:00:00 +0100"
    prefix = "HKCategoryValueSleepAnalysis"
    db = load(
        tmp_path,
        record(SLEEP, begin, core_end, prefix + "AsleepCore"),
        record(SLEEP, core_end, wake, prefix + "AsleepREM"),
        record(SLEEP, begin, wake, prefix + "AsleepUnspecified", source="Phone"),
        record(SLEEP, "2024-10-27 02:00:00 +0100", core_end, prefix + "AsleepDeep", source="Phone"),
        record(SLEEP, "2024-10-27 06:00:00 +0100", "2024-10-27 07:00:00 +0100", prefix + "InBed"),
    )
    result = sleep_summary(db, 7)
    assert result["nightly"] == [{"date": "2024-10-27", "hours": 8}]
    assert result["stages"] == [{"label": "Core", "hours": 4}, {"label": "REM", "hours": 3}]
    assert result["average_hours"] == 8


def test_workout_normalizes_export_statistics_and_preserves_missingness(tmp_path: Path):
    db = load(
        tmp_path,
        '<Workout workoutActivityType="HKWorkoutActivityTypeRunning" duration="30" durationUnit="min"'
        ' startDate="2024-05-02 12:00:00 +0000" endDate="2024-05-02 12:30:00 +0000">'
        '<WorkoutStatistics type="HKQuantityTypeIdentifierDistanceWalkingRunning" unit="m" sum="4500"/>'
        '<WorkoutStatistics type="HKQuantityTypeIdentifierHeartRate" unit="count/min" average="143"/>'
        '</Workout>',
    )
    result = workout_summary(db, 365)
    assert result["total_workouts"] == 1
    assert result["total_duration_hours"] == .5
    assert result["total_distance_km"] == 4.5
    assert result["total_energy_kcal"] is None
    assert result["sessions"][0]["bpm"] == 143


def test_legacy_profile_enriches_existing_record_without_duplicate(tmp_path: Path):
    xml = tmp_path / "original.xml"
    timestamp = "2024-01-01 00:30:00 +0200"
    xml.write_text("<HealthData>" + record(DISTANCE, timestamp, timestamp, 1, unit="km") + "</HealthData>")
    db = tmp_path / "legacy.duckdb"
    from apple_health_dashboard.ingest.apple_health_records import (
        iter_records_from_export_xml,
        stable_record_hash,
    )

    original, _ = next(iter_records_from_export_xml(xml))
    with duckdb.connect(str(db)) as con:
        con.execute("""
            CREATE TABLE health_record (
              type VARCHAR, start_at TIMESTAMP, end_at TIMESTAMP, creation_at TIMESTAMP,
              source_name VARCHAR, unit VARCHAR, value DOUBLE, value_str VARCHAR, record_hash VARCHAR UNIQUE
            )
        """)
        con.execute("""
            INSERT INTO health_record VALUES (?, '2023-12-31 23:30:00', '2023-12-31 23:30:00',
              NULL, 'Watch', 'km', 1, NULL, ?)
        """, [DISTANCE, stable_record_hash(original)])
        init_db(con)
    assert metric_series(db, DISTANCE, None)["legacy_samples"] == 1
    assert import_export_xml_to_duckdb_all(xml, db)["records_inserted"] == 0
    result = metric_series(db, DISTANCE, None)
    assert result["legacy_samples"] == 0
    assert result["points"][0]["date"] == "2024-01-01"
    assert paged_records(db, DISTANCE, 0, 10)["items"][0]["start_at"] == "2024-01-01T00:30:00+02:00"


def test_preview_checks_root_and_compares_instants(tmp_path: Path):
    file = tmp_path / "source.xml"
    file.write_text("<Unexpected/>")
    with pytest.raises(ImportValidationError):
        preview_export(file)
    file.write_text(
        "<HealthData>"
        + record(DISTANCE, "2024-01-02 00:00:00 +0200", "2024-01-02 00:00:00 +0200", 1)
        + record(DISTANCE, "2024-01-01 23:00:00 +0000", "2024-01-01 23:00:00 +0000", 1)
        + "</HealthData>"
    )
    assert preview_export(file).earliest_start == "2024-01-02 00:00:00 +0200"
    assert preview_export(file).latest_end == "2024-01-01 23:00:00 +0000"
