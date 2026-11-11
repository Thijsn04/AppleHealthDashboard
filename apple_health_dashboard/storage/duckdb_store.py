from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from math import isfinite
from pathlib import Path

import duckdb
import pandas as pd

from apple_health_dashboard.ingest.apple_health import HealthRecord
from apple_health_dashboard.ingest.apple_health_records import Record, _to_float
from apple_health_dashboard.ingest.apple_health_records import stable_record_hash as record_hash
from apple_health_dashboard.ingest.apple_health_workouts import (
    Workout,
    WorkoutMetadata,
    stable_workout_hash,
)
from apple_health_dashboard.services.units import UNIT_CONVERSIONS

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS health_record (
    type VARCHAR NOT NULL,
    start_at TIMESTAMP NOT NULL,
    end_at TIMESTAMP NOT NULL,
    creation_at TIMESTAMP,
    source_name VARCHAR,
    unit VARCHAR,
    value DOUBLE,
    value_str VARCHAR,
    record_hash VARCHAR NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS record_metadata (
    record_hash VARCHAR NOT NULL,
    key VARCHAR NOT NULL,
    value VARCHAR NOT NULL,
    UNIQUE(record_hash, key, value)
);

CREATE TABLE IF NOT EXISTS activity_summary (
    day DATE PRIMARY KEY,
    active_energy_burned_kcal DOUBLE,
    active_energy_burned_goal_kcal DOUBLE,
    apple_exercise_time_min DOUBLE,
    apple_exercise_time_goal_min DOUBLE,
    apple_stand_hours DOUBLE,
    apple_stand_hours_goal DOUBLE
);

CREATE TABLE IF NOT EXISTS workout (
    workout_activity_type VARCHAR NOT NULL,
    start_at TIMESTAMP NOT NULL,
    end_at TIMESTAMP NOT NULL,
    creation_at TIMESTAMP,
    source_name VARCHAR,
    device VARCHAR,
    duration_s DOUBLE,
    total_energy_kcal DOUBLE,
    total_distance_m DOUBLE,
    workout_hash VARCHAR NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS workout_metadata (
    workout_hash VARCHAR NOT NULL,
    key VARCHAR NOT NULL,
    value VARCHAR NOT NULL,
    UNIQUE(workout_hash, key, value)
);
"""


def _dt_to_iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.isoformat()


def open_db(db_path: Path) -> duckdb.DuckDBPyConnection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    return con


def init_db(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(_SCHEMA_SQL)
    for table, columns in {
        "health_record": {
            name: "VARCHAR" for name in ("source_start", "source_end", "source_creation", "device", "source_version")
        },
        "workout": {
            **dict.fromkeys(("source_start", "source_end", "source_creation", "duration_unit", "energy_unit", "distance_unit"), "VARCHAR"),
            **dict.fromkeys(("reported_hours", "reported_km", "reported_kcal", "reported_bpm"), "DOUBLE"),
        },
    }.items():
        existing = {row[1] for row in con.execute(f"PRAGMA table_info('{table}')").fetchall()}
        for column, kind in columns.items():
            if column not in existing:
                con.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {kind}")

    for _, column, kind, *_ in con.execute("PRAGMA table_info('activity_summary')").fetchall():
        if kind == "INTEGER":
            con.execute(f"ALTER TABLE activity_summary ALTER COLUMN {column} TYPE DOUBLE")


def stable_record_hash(record: HealthRecord) -> str:
    import hashlib

    payload = (
        record.type,
        record.start_at.isoformat(),
        record.end_at.isoformat(),
        record.creation_at.isoformat() if record.creation_at else "",
        record.source_name or "",
        record.unit or "",
        "" if record.value is None else repr(record.value),
        record.value_str or "",
    )
    raw = "|".join(payload).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def stage_records(con: duckdb.DuckDBPyConnection, records: list[Record]) -> None:
    if not records:
        return

    rows = [
        (
            r.record_type,
            _utc_timestamp(r.start_at), _utc_timestamp(r.end_at), _utc_timestamp(r.creation_at),
            r.source_name, r.unit, r.value, r.value_str,
            record_hash(r),
            _dt_to_iso(r.start_at), _dt_to_iso(r.end_at), _dt_to_iso(r.creation_at),
            r.device, r.source_version,
        )
        for r in records
    ]
    batch = pd.DataFrame.from_records(rows, columns=[  # noqa: F841 (DuckDB replacement scan)
        "type", "start_at", "end_at", "creation_at", "source_name", "unit", "value", "value_str",
        "record_hash", "source_start", "source_end", "source_creation", "device", "source_version",
    ])
    con.execute("INSERT INTO incoming_record BY NAME SELECT * FROM batch")


def merge_records(con: duckdb.DuckDBPyConnection) -> None:
    # Bulk merge avoids repeatedly probing and rebuilding the unique index inside one transaction.
    con.execute("""
        INSERT INTO health_record BY NAME
        SELECT * FROM incoming_record
        QUALIFY ROW_NUMBER() OVER (
          PARTITION BY record_hash
          ORDER BY (device IS NOT NULL) DESC, (source_version IS NOT NULL) DESC, device, source_version
        ) = 1
        ON CONFLICT (record_hash) DO UPDATE SET
          start_at = excluded.start_at, end_at = excluded.end_at, creation_at = excluded.creation_at,
          source_start = excluded.source_start, source_end = excluded.source_end,
          source_creation = excluded.source_creation,
          device = COALESCE(health_record.device, excluded.device),
          source_version = COALESCE(health_record.source_version, excluded.source_version)
        WHERE health_record.source_start IS NULL
           OR (health_record.device IS NULL AND excluded.device IS NOT NULL)
           OR (health_record.source_version IS NULL AND excluded.source_version IS NOT NULL)
        """)


def _utc_timestamp(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).replace(tzinfo=None).isoformat() if value.tzinfo else value.isoformat()


def iter_records(con: duckdb.DuckDBPyConnection) -> Iterator[HealthRecord]:
    # Keeping this for backwards compatibility with tests or old code, 
    # but new code should use Polars direct query
    res = con.execute(
        """
        SELECT type, start_at, end_at, creation_at, source_name, unit, value, value_str
        FROM health_record
        ORDER BY start_at
        """
    ).fetchall()
    
    for row in res:
        yield HealthRecord(
            type=row[0],
            start_at=row[1],
            end_at=row[2],
            creation_at=row[3],
            source_name=row[4],
            unit=row[5],
            value=row[6],
            value_str=row[7],
        )


def upsert_workouts(
    con: duckdb.DuckDBPyConnection,
    workouts: list[Workout],
    metadata: list[WorkoutMetadata],
) -> tuple[int, int]:
    if not workouts and not metadata:
        return 0, 0

    workout_rows = [
        (
            w.workout_activity_type, _utc_timestamp(w.start_at), _utc_timestamp(w.end_at),
            _utc_timestamp(w.creation_at), w.source_name, w.device,
            w.duration_s, w.total_energy_kcal, w.total_distance_m, stable_workout_hash(w),
            _dt_to_iso(w.start_at) if w.units_known else None, _dt_to_iso(w.end_at),
            _dt_to_iso(w.creation_at), w.duration_unit, w.energy_unit, w.distance_unit,
            *_workout_quantities(w),
        )
        for w in workouts
    ]
    workouts_inserted = len(workout_rows)
    if workout_rows:
        batch = pd.DataFrame.from_records(workout_rows, columns=[  # noqa: F841 (DuckDB replacement scan)
            "workout_activity_type", "start_at", "end_at", "creation_at", "source_name", "device",
            "duration_s", "total_energy_kcal", "total_distance_m", "workout_hash",
            "source_start", "source_end", "source_creation", "duration_unit", "energy_unit", "distance_unit",
            "reported_hours", "reported_km", "reported_kcal", "reported_bpm",
        ])
        con.execute("""
            INSERT INTO workout BY NAME SELECT * FROM batch
            ON CONFLICT (workout_hash) DO UPDATE SET
              start_at = excluded.start_at, end_at = excluded.end_at, creation_at = excluded.creation_at,
              source_start = excluded.source_start, source_end = excluded.source_end,
              source_creation = excluded.source_creation, duration_unit = excluded.duration_unit,
              energy_unit = excluded.energy_unit, distance_unit = excluded.distance_unit,
              reported_hours = COALESCE(excluded.reported_hours, workout.reported_hours),
              reported_km = COALESCE(excluded.reported_km, workout.reported_km),
              reported_kcal = COALESCE(excluded.reported_kcal, workout.reported_kcal),
              reported_bpm = COALESCE(excluded.reported_bpm, workout.reported_bpm)
            WHERE workout.source_start IS NULL
               OR (workout.reported_hours IS NULL AND excluded.reported_hours IS NOT NULL)
               OR (workout.reported_km IS NULL AND excluded.reported_km IS NOT NULL)
               OR (workout.reported_kcal IS NULL AND excluded.reported_kcal IS NOT NULL)
               OR (workout.reported_bpm IS NULL AND excluded.reported_bpm IS NOT NULL)
            """)
    metadata_inserted = 0
    if metadata:
        meta_rows = [(m.workout_hash, m.key, m.value) for m in metadata]
        con.executemany(
            """
            INSERT INTO workout_metadata(workout_hash, key, value)
            VALUES (?, ?, ?)
            ON CONFLICT (workout_hash, key, value) DO NOTHING
            """,
            meta_rows,
        )
        metadata_inserted = len(meta_rows)

    return workouts_inserted, metadata_inserted


def _workout_quantities(workout: Workout) -> tuple[float | None, ...]:
    def reported(value: float | None, unit: str | None, target: str) -> float | None:
        if value is None or not isfinite(value) or value < 0:
            return None
        if unit == target:
            return value
        return next((value * scale + offset for origin, scale, offset in UNIT_CONVERSIONS.get(target, [])
                     if origin == unit), None)

    def statistic(kind: str, target: str) -> float | None:
        compatible = {
            converted for stat, unit, value in workout.statistics
            if stat == f"HKQuantityTypeIdentifier{kind}"
            and (converted := reported(_to_float(value), unit, target)) is not None
        }
        return next(iter(compatible)) if len(compatible) == 1 else None

    minutes = reported(workout.duration_s, workout.duration_unit, "min")
    km = reported(workout.total_distance_m, workout.distance_unit, "km")
    kcal = reported(workout.total_energy_kcal, workout.energy_unit, "kcal")
    if km is None:
        distances = [value for kind in ("DistanceWalkingRunning", "DistanceCycling", "DistanceSwimming",
                                       "DistanceDownhillSnowSports", "DistanceWheelchair")
                     if (value := statistic(kind, "km")) is not None]
        km = distances[0] if len(distances) == 1 else None
    if kcal is None:
        kcal = statistic("ActiveEnergyBurned", "kcal")
    return (minutes / 60 if minutes is not None else None, km, kcal, statistic("HeartRate", "bpm"))


def iter_workouts(con: duckdb.DuckDBPyConnection) -> Iterator[Workout]:
    res = con.execute(
        """
        SELECT workout_activity_type, start_at, end_at, creation_at, source_name, device,
               duration_s, total_energy_kcal, total_distance_m
        FROM workout
        ORDER BY start_at
        """
    ).fetchall()
    
    for row in res:
        yield Workout(
            workout_activity_type=row[0],
            start_at=row[1],
            end_at=row[2],
            creation_at=row[3],
            source_name=row[4],
            device=row[5],
            duration_s=row[6],
            total_energy_kcal=row[7],
            total_distance_m=row[8],
        )


def stage_record_metadata(con: duckdb.DuckDBPyConnection, metadata: list[tuple[str, str, str]]) -> None:
    if not metadata:
        return

    batch = pd.DataFrame.from_records(metadata, columns=["record_hash", "key", "value"])  # noqa: F841
    con.execute("INSERT INTO incoming_metadata BY NAME SELECT * FROM batch")


def get_record_metadata_for_hash(
    con: duckdb.DuckDBPyConnection,
    record_hash: str,
) -> list[tuple[str, str]]:
    res = con.execute(
        """
        SELECT key, value
        FROM record_metadata
        WHERE record_hash = ?
        ORDER BY key
        """,
        [record_hash],
    ).fetchall()
    return [(r[0], r[1]) for r in res]


def upsert_activity_summaries(con: duckdb.DuckDBPyConnection, rows: list[tuple]) -> int:
    if not rows:
        return 0

    con.executemany(
        """
        INSERT INTO activity_summary(
            day, active_energy_burned_kcal, active_energy_burned_goal_kcal,
            apple_exercise_time_min, apple_exercise_time_goal_min,
            apple_stand_hours, apple_stand_hours_goal
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (day) DO NOTHING
        """,
        rows,
    )
    return len(rows)


def iter_activity_summaries(con: duckdb.DuckDBPyConnection) -> Iterator[dict]:
    res = con.execute(
        """
        SELECT day, active_energy_burned_kcal, active_energy_burned_goal_kcal,
               apple_exercise_time_min, apple_exercise_time_goal_min,
               apple_stand_hours, apple_stand_hours_goal
        FROM activity_summary
        ORDER BY day
        """
    ).fetchall()
    
    for row in res:
        yield {
            "day": row[0],
            "active_energy_burned_kcal": row[1],
            "active_energy_burned_goal_kcal": row[2],
            "apple_exercise_time_min": row[3],
            "apple_exercise_time_goal_min": row[4],
            "apple_stand_hours": row[5],
            "apple_stand_hours_goal": row[6],
        }

def count_records(
    con: duckdb.DuckDBPyConnection,
    *,
    record_type: str | None = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
) -> int:
    where = []
    params: list[object] = []

    if record_type:
        where.append("type = ?")
        params.append(record_type)

    if start_at is not None:
        where.append("start_at >= ?")
        params.append(start_at)

    if end_at is not None:
        where.append("start_at <= ?")
        params.append(end_at)

    where_sql = "" if not where else "WHERE " + " AND ".join(where)
    row = con.execute(
        f"SELECT COUNT(*) FROM health_record {where_sql}",
        params,
    ).fetchone()
    return int(row[0]) if row else 0

def list_record_types(con: duckdb.DuckDBPyConnection) -> list[str]:
    res = con.execute(
        """
        SELECT DISTINCT type
        FROM health_record
        ORDER BY type
        """
    ).fetchall()
    return [r[0] for r in res]

def query_records_page(
    con: duckdb.DuckDBPyConnection,
    *,
    record_type: str | None = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    order: str = "start_at_desc",
    limit: int = 500,
    offset: int = 0,
) -> list[dict]:
    order_sql = "start_at DESC" if order == "start_at_desc" else "start_at ASC"

    where = []
    params: list[object] = []

    if record_type:
        where.append("type = ?")
        params.append(record_type)

    if start_at is not None:
        where.append("start_at >= ?")
        params.append(start_at)

    if end_at is not None:
        where.append("start_at <= ?")
        params.append(end_at)

    where_sql = "" if not where else "WHERE " + " AND ".join(where)

    res = con.execute(
        f"""
        SELECT type, start_at, end_at, creation_at, source_name, unit, value, value_str, record_hash
        FROM health_record
        {where_sql}
        ORDER BY {order_sql}
        LIMIT ? OFFSET ?
        """,
        [*params, limit, offset],
    ).fetchall()
    
    return [
        {
            "type": r[0],
            "start_at": r[1],
            "end_at": r[2],
            "creation_at": r[3],
            "source_name": r[4],
            "unit": r[5],
            "value": r[6],
            "value_str": r[7],
            "record_hash": r[8],
        }
        for r in res
    ]
