from __future__ import annotations

import duckdb
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from collections.abc import Iterator

from apple_health_dashboard.ingest.apple_health import HealthRecord
from apple_health_dashboard.ingest.apple_health_workouts import (
    Workout,
    WorkoutMetadata,
    stable_workout_hash,
)

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
    active_energy_burned_kcal INTEGER,
    active_energy_burned_goal_kcal INTEGER,
    apple_exercise_time_min INTEGER,
    apple_exercise_time_goal_min INTEGER,
    apple_stand_hours INTEGER,
    apple_stand_hours_goal INTEGER
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
    for stmt in _SCHEMA_SQL.strip().split(';'):
        if stmt.strip():
            con.execute(stmt)


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


def upsert_records(con: duckdb.DuckDBPyConnection, records: list[HealthRecord]) -> int:
    if not records:
        return 0

    rows = []
    for r in records:
        d = asdict(r)
        rows.append(
            (
                d["type"],
                d["start_at"],
                d["end_at"],
                d["creation_at"],
                d["source_name"],
                d["unit"],
                d["value"],
                d["value_str"],
                stable_record_hash(r),
            )
        )

    con.executemany(
        """
        INSERT INTO health_record(
            type, start_at, end_at, creation_at, source_name, unit, value, value_str, record_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (record_hash) DO NOTHING
        """,
        rows,
    )
    return len(rows)


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

    workout_rows = []
    for w in workouts:
        d = asdict(w)
        workout_rows.append(
            (
                d["workout_activity_type"],
                d["start_at"],
                d["end_at"],
                d["creation_at"],
                d["source_name"],
                d["device"],
                d["duration_s"],
                d["total_energy_kcal"],
                d["total_distance_m"],
                stable_workout_hash(w),
            )
        )

    workouts_inserted = 0
    if workout_rows:
        con.executemany(
            """
            INSERT INTO workout(
                workout_activity_type, start_at, end_at, creation_at, source_name, device,
                duration_s, total_energy_kcal, total_distance_m, workout_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (workout_hash) DO NOTHING
            """,
            workout_rows,
        )
        workouts_inserted = len(workout_rows)

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


def upsert_record_metadata(con: duckdb.DuckDBPyConnection, metadata: list[tuple[str, str, str]]) -> int:
    if not metadata:
        return 0

    con.executemany(
        """
        INSERT INTO record_metadata(record_hash, key, value)
        VALUES (?, ?, ?)
        ON CONFLICT (record_hash, key, value) DO NOTHING
        """,
        metadata,
    )
    return len(metadata)


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
