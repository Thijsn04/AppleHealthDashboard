from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from apple_health_dashboard.ingest.apple_health_activity_summary import (
    iter_activity_summaries_from_export_xml,
)
from apple_health_dashboard.ingest.apple_health_records import (
    iter_records_from_export_xml,
)
from apple_health_dashboard.ingest.apple_health_workouts import iter_workouts_from_export_xml
from apple_health_dashboard.storage.sqlite_store import (
    init_db,
    open_db,
    upsert_activity_summaries,
    upsert_record_metadata,
    upsert_records,
    upsert_workouts,
)

# Backwards-compatible helper: imports only records (no metadata, no workouts).
# Kept for earlier callers, but the app uses import_export_xml_to_sqlite_all.

def import_export_xml_to_sqlite(
    export_xml_path: Path,
    db_path: Path,
    *,
    batch_size: int = 2000,
    on_progress: Callable[[int], None] | None = None,
) -> int:
    processed = 0
    inserted_total = 0

    con = open_db(db_path)
    try:
        init_db(con)

        batch: list = []
        for rec, _meta in iter_records_from_export_xml(export_xml_path):
            # Convert to legacy HealthRecord shape by reusing existing SQLite writer.
            # (We keep the storage layer stable by continuing to write HealthRecord rows.)
            from apple_health_dashboard.ingest.apple_health import HealthRecord

            batch.append(
                HealthRecord(
                    type=rec.record_type,
                    start_at=rec.start_at,
                    end_at=rec.end_at,
                    creation_at=rec.creation_at,
                    source_name=rec.source_name,
                    unit=rec.unit,
                    value=rec.value,
                    value_str=rec.value_str,
                )
            )
            processed += 1

            if on_progress and processed % 250 == 0:
                on_progress(processed)

            if len(batch) >= batch_size:
                inserted_total += upsert_records(con, batch)
                batch.clear()

        if batch:
            inserted_total += upsert_records(con, batch)

        if on_progress:
            on_progress(processed)

        return inserted_total
    finally:
        con.close()


def import_export_xml_to_sqlite_all(
    export_xml_path: Path,
    db_path: Path,
    *,
    record_batch_size: int = 2000,
    workout_batch_size: int = 300,
    on_progress: Callable[[str, int], None] | None = None,
) -> dict[str, int]:
    """Import Records (+metadata) + Workouts (+metadata) + ActivitySummary into SQLite."""

    con = open_db(db_path)
    try:
        init_db(con)

        # Records (+ metadata)
        from apple_health_dashboard.ingest.apple_health import HealthRecord

        records_processed = 0
        records_inserted = 0
        record_metadata_inserted = 0

        record_batch: list[HealthRecord] = []
        record_meta_rows: list[tuple[str, str, str]] = []

        for rec, meta in iter_records_from_export_xml(export_xml_path):
            record_batch.append(
                HealthRecord(
                    type=rec.record_type,
                    start_at=rec.start_at,
                    end_at=rec.end_at,
                    creation_at=rec.creation_at,
                    source_name=rec.source_name,
                    unit=rec.unit,
                    value=rec.value,
                    value_str=rec.value_str,
                )
            )
            record_meta_rows.extend([(m.record_hash, m.key, m.value) for m in meta])

            records_processed += 1
            if on_progress and records_processed % 500 == 0:
                on_progress("records", records_processed)

            if len(record_batch) >= record_batch_size:
                records_inserted += upsert_records(con, record_batch)
                record_metadata_inserted += upsert_record_metadata(con, record_meta_rows)
                record_batch.clear()
                record_meta_rows.clear()

        if record_batch or record_meta_rows:
            records_inserted += upsert_records(con, record_batch)
            record_metadata_inserted += upsert_record_metadata(con, record_meta_rows)

        if on_progress:
            on_progress("records", records_processed)

        # ActivitySummary (rings)
        activity_processed = 0
        activity_inserted = 0
        activity_rows = []

        for s in iter_activity_summaries_from_export_xml(export_xml_path):
            activity_rows.append(
                (
                    s.day.isoformat(),
                    s.active_energy_burned_kcal,
                    s.active_energy_burned_goal_kcal,
                    s.apple_exercise_time_min,
                    s.apple_exercise_time_goal_min,
                    s.apple_stand_hours,
                    s.apple_stand_hours_goal,
                )
            )
            activity_processed += 1

            if len(activity_rows) >= 365:
                activity_inserted += upsert_activity_summaries(con, activity_rows)
                activity_rows.clear()

        if activity_rows:
            activity_inserted += upsert_activity_summaries(con, activity_rows)

        # Workouts (+ metadata)
        workouts_processed = 0
        workouts_inserted_total = 0
        workout_meta_inserted_total = 0

        workout_batch = []
        meta_batch = []

        for workout, metadata in iter_workouts_from_export_xml(export_xml_path):
            workout_batch.append(workout)
            meta_batch.extend(metadata)
            workouts_processed += 1

            if on_progress and workouts_processed % 50 == 0:
                on_progress("workouts", workouts_processed)

            if len(workout_batch) >= workout_batch_size:
                w_i, m_i = upsert_workouts(con, workout_batch, meta_batch)
                workouts_inserted_total += w_i
                workout_meta_inserted_total += m_i
                workout_batch.clear()
                meta_batch.clear()

        if workout_batch or meta_batch:
            w_i, m_i = upsert_workouts(con, workout_batch, meta_batch)
            workouts_inserted_total += w_i
            workout_meta_inserted_total += m_i

        if on_progress:
            on_progress("workouts", workouts_processed)

        return {
            "records_inserted": records_inserted,
            "record_metadata_inserted": record_metadata_inserted,
            "activity_summaries_inserted": activity_inserted,
            "workouts_inserted": workouts_inserted_total,
            "workout_metadata_inserted": workout_meta_inserted_total,
        }
    finally:
        con.close()
