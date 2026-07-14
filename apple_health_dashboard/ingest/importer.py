from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import duckdb

from apple_health_dashboard.ingest.apple_health_activity_summary import (
    iter_activity_summaries_from_export_xml,
)
from apple_health_dashboard.ingest.apple_health_records import iter_records_from_export_xml
from apple_health_dashboard.ingest.apple_health_workouts import iter_workouts_from_export_xml
from apple_health_dashboard.storage.duckdb_store import (
    init_db,
    open_db,
    upsert_activity_summaries,
    upsert_record_metadata,
    upsert_records,
    upsert_workouts,
)

_COUNTED_TABLES = (
    "health_record",
    "record_metadata",
    "activity_summary",
    "workout",
    "workout_metadata",
)


def import_export_xml_to_duckdb(
    export_xml_path: Path,
    db_path: Path,
    *,
    batch_size: int = 2000,
    on_progress: Callable[[int], None] | None = None,
) -> int:
    """Import records atomically and return the number of newly stored records."""
    counters = import_export_xml_to_duckdb_all(
        export_xml_path,
        db_path,
        record_batch_size=batch_size,
        on_progress=lambda _stage, processed: on_progress(processed) if on_progress else None,
    )
    return counters["records_inserted"]


def import_export_xml_to_duckdb_all(
    export_xml_path: Path,
    db_path: Path,
    *,
    record_batch_size: int = 2000,
    workout_batch_size: int = 300,
    on_progress: Callable[[str, int], None] | None = None,
) -> dict[str, int]:
    """Import records, metadata, workouts, and activity summaries in one transaction.

    Returned counts represent rows actually added during this import. Re-importing an
    unchanged export therefore reports zero newly inserted rows.
    """
    con = open_db(db_path)
    try:
        init_db(con)
        counts_before = _table_counts(con)
        con.execute("BEGIN TRANSACTION")
        try:
            _import_records(con, export_xml_path, record_batch_size, on_progress)
            _import_activity_summaries(con, export_xml_path)
            _import_workouts(con, export_xml_path, workout_batch_size, on_progress)
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise

        counts_after = _table_counts(con)
        return {
            "records_inserted": counts_after["health_record"] - counts_before["health_record"],
            "record_metadata_inserted": counts_after["record_metadata"] - counts_before["record_metadata"],
            "activity_summaries_inserted": counts_after["activity_summary"] - counts_before["activity_summary"],
            "workouts_inserted": counts_after["workout"] - counts_before["workout"],
            "workout_metadata_inserted": counts_after["workout_metadata"] - counts_before["workout_metadata"],
        }
    finally:
        con.close()


def _import_records(
    con: duckdb.DuckDBPyConnection,
    export_xml_path: Path,
    batch_size: int,
    on_progress: Callable[[str, int], None] | None,
) -> None:
    from apple_health_dashboard.ingest.apple_health import HealthRecord

    processed = 0
    records: list[HealthRecord] = []
    metadata_rows: list[tuple[str, str, str]] = []
    for record, metadata in iter_records_from_export_xml(export_xml_path):
        records.append(
            HealthRecord(
                type=record.record_type,
                start_at=record.start_at,
                end_at=record.end_at,
                creation_at=record.creation_at,
                source_name=record.source_name,
                unit=record.unit,
                value=record.value,
                value_str=record.value_str,
            )
        )
        metadata_rows.extend((item.record_hash, item.key, item.value) for item in metadata)
        processed += 1
        if on_progress and processed % 500 == 0:
            on_progress("records", processed)
        if len(records) >= batch_size:
            upsert_records(con, records)
            upsert_record_metadata(con, metadata_rows)
            records.clear()
            metadata_rows.clear()

    if records or metadata_rows:
        upsert_records(con, records)
        upsert_record_metadata(con, metadata_rows)
    if on_progress:
        on_progress("records", processed)


def _import_activity_summaries(con: duckdb.DuckDBPyConnection, export_xml_path: Path) -> None:
    rows = []
    for summary in iter_activity_summaries_from_export_xml(export_xml_path):
        rows.append(
            (
                summary.day.isoformat(),
                summary.active_energy_burned_kcal,
                summary.active_energy_burned_goal_kcal,
                summary.apple_exercise_time_min,
                summary.apple_exercise_time_goal_min,
                summary.apple_stand_hours,
                summary.apple_stand_hours_goal,
            )
        )
        if len(rows) >= 365:
            upsert_activity_summaries(con, rows)
            rows.clear()
    if rows:
        upsert_activity_summaries(con, rows)


def _import_workouts(
    con: duckdb.DuckDBPyConnection,
    export_xml_path: Path,
    batch_size: int,
    on_progress: Callable[[str, int], None] | None,
) -> None:
    processed = 0
    workouts = []
    metadata_rows = []
    for workout, metadata in iter_workouts_from_export_xml(export_xml_path):
        workouts.append(workout)
        metadata_rows.extend(metadata)
        processed += 1
        if on_progress and processed % 50 == 0:
            on_progress("workouts", processed)
        if len(workouts) >= batch_size:
            upsert_workouts(con, workouts, metadata_rows)
            workouts.clear()
            metadata_rows.clear()

    if workouts or metadata_rows:
        upsert_workouts(con, workouts, metadata_rows)
    if on_progress:
        on_progress("workouts", processed)


def _table_counts(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    """Return table cardinalities for accurate import deltas."""
    return {
        table: int(con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        for table in _COUNTED_TABLES
    }
