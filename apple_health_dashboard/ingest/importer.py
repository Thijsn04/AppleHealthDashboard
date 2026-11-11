from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from threading import Lock

import duckdb

from apple_health_dashboard.ingest.apple_health_activity_summary import parse_activity_summary
from apple_health_dashboard.ingest.apple_health_records import parse_records
from apple_health_dashboard.ingest.apple_health_workouts import parse_workouts
from apple_health_dashboard.ingest.xml_stream import export_elements
from apple_health_dashboard.storage.duckdb_store import (
    init_db,
    merge_records,
    open_db,
    stage_record_metadata,
    stage_records,
    upsert_activity_summaries,
    upsert_workouts,
)

_IMPORT_LOCK = Lock()
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
    batch_size: int = 8000,
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
    record_batch_size: int = 8000,
    workout_batch_size: int = 300,
    on_progress: Callable[[str, int], None] | None = None,
) -> dict[str, int]:
    """Import records, metadata, workouts, and activity summaries in one transaction.

    Returned counts represent rows actually added during this import. Re-importing an
    unchanged export therefore reports zero newly inserted rows.
    """
    if min(record_batch_size, workout_batch_size) < 1:
        raise ValueError("Import batches must contain at least one row.")
    with _IMPORT_LOCK:
        con = open_db(db_path)
        try:
            init_db(con)
            con.execute("BEGIN TRANSACTION")
            try:
                counts_before = _table_counts(con)
                con.execute("CREATE TEMP TABLE incoming_record AS FROM health_record LIMIT 0")
                con.execute("CREATE TEMP TABLE incoming_metadata AS FROM record_metadata LIMIT 0")
                skipped = _import_elements(con, export_xml_path, record_batch_size, workout_batch_size, on_progress)
                merge_records(con)
                con.execute("INSERT INTO record_metadata FROM incoming_metadata ON CONFLICT DO NOTHING")
                counts_after = _table_counts(con)
                con.execute("COMMIT")
            except Exception:
                con.execute("ROLLBACK")
                raise

            return {
                "entries_skipped": skipped,
                "records_inserted": counts_after["health_record"] - counts_before["health_record"],
                "record_metadata_inserted": counts_after["record_metadata"] - counts_before["record_metadata"],
                "activity_summaries_inserted": counts_after["activity_summary"] - counts_before["activity_summary"],
                "workouts_inserted": counts_after["workout"] - counts_before["workout"],
                "workout_metadata_inserted": counts_after["workout_metadata"] - counts_before["workout_metadata"],
            }
        finally:
            con.close()


def _import_elements(con, export_xml_path, record_batch_size, workout_batch_size, on_progress) -> int:
    records, record_metadata, workouts, workout_metadata, rings = [], [], [], [], []
    processed_records = processed_workouts = skipped = 0
    for element in export_elements(export_xml_path):
        if element.tag == "Record":
            parsed = parse_records(element)
            if parsed is None:
                skipped += 1
                continue
            record, metadata = parsed
            records.append(record)
            record_metadata.extend((m.record_hash, m.key, m.value) for m in metadata)
            processed_records += 1
            if len(records) >= record_batch_size:
                stage_records(con, records)
                stage_record_metadata(con, record_metadata)
                records.clear()
                record_metadata.clear()
                if on_progress:
                    on_progress("records", processed_records)
        elif element.tag == "Workout":
            parsed = parse_workouts(element)
            if parsed is None:
                skipped += 1
                continue
            workout, metadata = parsed
            workouts.append(workout)
            workout_metadata.extend(metadata)
            processed_workouts += 1
            if len(workouts) >= workout_batch_size:
                upsert_workouts(con, workouts, workout_metadata)
                workouts.clear()
                workout_metadata.clear()
                if on_progress:
                    on_progress("workouts", processed_workouts)
        elif element.tag == "ActivitySummary":
            summary = parse_activity_summary(element)
            if summary is None:
                skipped += 1
                continue
            rings.append((
                summary.day.isoformat(), summary.active_energy_burned_kcal,
                summary.active_energy_burned_goal_kcal, summary.apple_exercise_time_min,
                summary.apple_exercise_time_goal_min, summary.apple_stand_hours, summary.apple_stand_hours_goal,
            ))
            if len(rings) >= 365:
                upsert_activity_summaries(con, rings)
                rings.clear()

    stage_records(con, records)
    stage_record_metadata(con, record_metadata)
    upsert_workouts(con, workouts, workout_metadata)
    upsert_activity_summaries(con, rings)
    if on_progress:
        on_progress("records", processed_records)
        on_progress("workouts", processed_workouts)
    return skipped


def _table_counts(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    """Return table cardinalities for accurate import deltas."""
    return {
        table: int(con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        for table in _COUNTED_TABLES
    }
