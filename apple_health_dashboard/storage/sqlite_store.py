from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from apple_health_dashboard.ingest.apple_health import HealthRecord
from apple_health_dashboard.ingest.apple_health_workouts import (
    Workout,
    WorkoutMetadata,
    stable_workout_hash,
)

_SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

CREATE TABLE IF NOT EXISTS health_record (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,
    start_at TEXT NOT NULL,
    end_at TEXT NOT NULL,
    creation_at TEXT,
    source_name TEXT,
    unit TEXT,
    value REAL,
    value_str TEXT,
    record_hash TEXT NOT NULL UNIQUE
);

CREATE INDEX IF NOT EXISTS idx_health_record_type_start
    ON health_record(type, start_at);

CREATE TABLE IF NOT EXISTS record_metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_hash TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    UNIQUE(record_hash, key, value)
);

CREATE INDEX IF NOT EXISTS idx_record_metadata_hash
    ON record_metadata(record_hash);

CREATE TABLE IF NOT EXISTS activity_summary (
    day TEXT PRIMARY KEY,
    active_energy_burned_kcal INTEGER,
    active_energy_burned_goal_kcal INTEGER,
    apple_exercise_time_min INTEGER,
    apple_exercise_time_goal_min INTEGER,
    apple_stand_hours INTEGER,
    apple_stand_hours_goal INTEGER
);

CREATE INDEX IF NOT EXISTS idx_activity_summary_day
    ON activity_summary(day);

CREATE TABLE IF NOT EXISTS workout (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workout_activity_type TEXT NOT NULL,
    start_at TEXT NOT NULL,
    end_at TEXT NOT NULL,
    creation_at TEXT,
    source_name TEXT,
    device TEXT,
    duration_s REAL,
    total_energy_kcal REAL,
    total_distance_m REAL,
    workout_hash TEXT NOT NULL UNIQUE
);

CREATE INDEX IF NOT EXISTS idx_workout_type_start
    ON workout(workout_activity_type, start_at);

CREATE TABLE IF NOT EXISTS workout_metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workout_hash TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    UNIQUE(workout_hash, key, value)
);

CREATE INDEX IF NOT EXISTS idx_workout_metadata_hash
    ON workout_metadata(workout_hash);
"""


def _dt_to_iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.isoformat()


def open_db(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    return con


def init_db(con: sqlite3.Connection) -> None:
    con.executescript(_SCHEMA_SQL)
    con.commit()


def stable_record_hash(record: HealthRecord) -> str:
    """Create a stable-ish hash to de-duplicate imports.

    Apple exports don't provide a single global ID for every record.
    This hash is good enough to avoid double-importing the same export.
    """
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


def upsert_records(con: sqlite3.Connection, records: list[HealthRecord]) -> int:
    """Insert records, ignoring duplicates. Returns number of inserted rows."""

    if not records:
        return 0

    rows = []
    for r in records:
        d = asdict(r)
        rows.append(
            (
                d["type"],
                _dt_to_iso(d["start_at"]),
                _dt_to_iso(d["end_at"]),
                _dt_to_iso(d["creation_at"]),
                d["source_name"],
                d["unit"],
                d["value"],
                d["value_str"],
                stable_record_hash(r),
            )
        )

    cur = con.cursor()
    cur.executemany(
        """
        INSERT OR IGNORE INTO health_record(
            type, start_at, end_at, creation_at, source_name, unit, value, value_str, record_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    con.commit()
    return cur.rowcount if cur.rowcount != -1 else 0


def iter_records(con: sqlite3.Connection) -> Iterator[HealthRecord]:
    cur = con.execute(
        """
        SELECT type, start_at, end_at, creation_at, source_name, unit, value, value_str
        FROM health_record
        ORDER BY start_at
        """
    )
    for row in cur:
        yield HealthRecord(
            type=row["type"],
            start_at=datetime.fromisoformat(row["start_at"]),
            end_at=datetime.fromisoformat(row["end_at"]),
            creation_at=datetime.fromisoformat(row["creation_at"]) if row["creation_at"] else None,
            source_name=row["source_name"],
            unit=row["unit"],
            value=row["value"],
            value_str=row["value_str"],
        )


# Remove duplicate stable_workout_hash defined in this module.
# The canonical implementation lives in apple_health_dashboard.ingest.apple_health_workouts.


def upsert_workouts(
    con: sqlite3.Connection,
    workouts: list[Workout],
    metadata: list[WorkoutMetadata],
) -> tuple[int, int]:
    """Insert workouts + metadata, ignoring duplicates.

    Returns: (workouts_inserted, metadata_inserted)
    """
    if not workouts and not metadata:
        return 0, 0

    workout_rows = []
    for w in workouts:
        d = asdict(w)
        workout_rows.append(
            (
                d["workout_activity_type"],
                _dt_to_iso(d["start_at"]),
                _dt_to_iso(d["end_at"]),
                _dt_to_iso(d["creation_at"]),
                d["source_name"],
                d["device"],
                d["duration_s"],
                d["total_energy_kcal"],
                d["total_distance_m"],
                stable_workout_hash(w),
            )
        )

    cur = con.cursor()
    workouts_inserted = 0
    if workout_rows:
        cur.executemany(
            """
            INSERT OR IGNORE INTO workout(
                workout_activity_type,
                start_at,
                end_at,
                creation_at,
                source_name,
                device,
                duration_s,
                total_energy_kcal,
                total_distance_m,
                workout_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            workout_rows,
        )
        workouts_inserted = cur.rowcount if cur.rowcount != -1 else 0

    metadata_inserted = 0
    if metadata:
        meta_rows = [(m.workout_hash, m.key, m.value) for m in metadata]
        cur.executemany(
            """
            INSERT OR IGNORE INTO workout_metadata(workout_hash, key, value)
            VALUES (?, ?, ?)
            """,
            meta_rows,
        )
        metadata_inserted = cur.rowcount if cur.rowcount != -1 else 0

    con.commit()
    return workouts_inserted, metadata_inserted


def iter_workouts(con: sqlite3.Connection) -> Iterator[Workout]:
    cur = con.execute(
        """
        SELECT workout_activity_type, start_at, end_at, creation_at, source_name, device,
               duration_s, total_energy_kcal, total_distance_m
        FROM workout
        ORDER BY start_at
        """
    )
    for row in cur:
        yield Workout(
            workout_activity_type=row["workout_activity_type"],
            start_at=datetime.fromisoformat(row["start_at"]),
            end_at=datetime.fromisoformat(row["end_at"]),
            creation_at=datetime.fromisoformat(row["creation_at"]) if row["creation_at"] else None,
            source_name=row["source_name"],
            device=row["device"],
            duration_s=row["duration_s"],
            total_energy_kcal=row["total_energy_kcal"],
            total_distance_m=row["total_distance_m"],
        )


def upsert_record_metadata(con: sqlite3.Connection, metadata: list[tuple[str, str, str]]) -> int:
    """Insert record metadata rows (record_hash, key, value), ignoring duplicates."""
    if not metadata:
        return 0

    cur = con.cursor()
    cur.executemany(
        """
        INSERT OR IGNORE INTO record_metadata(record_hash, key, value)
        VALUES (?, ?, ?)
        """,
        metadata,
    )
    con.commit()
    return cur.rowcount if cur.rowcount != -1 else 0


def get_record_metadata_for_hash(
    con: sqlite3.Connection,
    record_hash: str,
) -> list[tuple[str, str]]:
    cur = con.execute(
        """
        SELECT key, value
        FROM record_metadata
        WHERE record_hash = ?
        ORDER BY key
        """,
        (record_hash,),
    )
    return [(r["key"], r["value"]) for r in cur.fetchall()]


def upsert_activity_summaries(con: sqlite3.Connection, rows: list[tuple]) -> int:
    """Insert activity summary rows, ignoring duplicates by day."""
    if not rows:
        return 0

    cur = con.cursor()
    cur.executemany(
        """
        INSERT OR IGNORE INTO activity_summary(
            day,
            active_energy_burned_kcal,
            active_energy_burned_goal_kcal,
            apple_exercise_time_min,
            apple_exercise_time_goal_min,
            apple_stand_hours,
            apple_stand_hours_goal
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    con.commit()
    return cur.rowcount if cur.rowcount != -1 else 0


def iter_activity_summaries(con: sqlite3.Connection) -> Iterator[dict]:
    cur = con.execute(
        """
        SELECT day,
               active_energy_burned_kcal,
               active_energy_burned_goal_kcal,
               apple_exercise_time_min,
               apple_exercise_time_goal_min,
               apple_stand_hours,
               apple_stand_hours_goal
        FROM activity_summary
        ORDER BY day
        """
    )
    for row in cur:
        yield dict(row)


def count_records(
    con: sqlite3.Connection,
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
        params.append(start_at.isoformat())

    if end_at is not None:
        where.append("start_at <= ?")
        params.append(end_at.isoformat())

    where_sql = "" if not where else "WHERE " + " AND ".join(where)
    row = con.execute(
        f"SELECT COUNT(*) AS n FROM health_record {where_sql}",
        params,
    ).fetchone()
    return int(row["n"]) if row else 0


def list_record_types(con: sqlite3.Connection) -> list[str]:
    cur = con.execute(
        """
        SELECT DISTINCT type
        FROM health_record
        ORDER BY type
        """
    )
    return [r["type"] for r in cur.fetchall()]


def query_records_page(
    con: sqlite3.Connection,
    *,
    record_type: str | None = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    order: str = "start_at_desc",
    limit: int = 500,
    offset: int = 0,
) -> list[dict]:
    """Query a page of records as dicts.

    order: "start_at_desc" | "start_at_asc"
    """
    order_sql = "start_at DESC" if order == "start_at_desc" else "start_at ASC"

    where = []
    params: list[object] = []

    if record_type:
        where.append("type = ?")
        params.append(record_type)

    if start_at is not None:
        where.append("start_at >= ?")
        params.append(start_at.isoformat())

    if end_at is not None:
        where.append("start_at <= ?")
        params.append(end_at.isoformat())

    where_sql = "" if not where else "WHERE " + " AND ".join(where)

    cur = con.execute(
        f"""
        SELECT type, start_at, end_at, creation_at, source_name, unit, value, value_str, record_hash
        FROM health_record
        {where_sql}
        ORDER BY {order_sql}
        LIMIT ? OFFSET ?
        """,
        [*params, limit, offset],
    )
    return [dict(r) for r in cur.fetchall()]
