"""Bounded read models for the local analyzer API.

This module keeps SQL and response shaping out of route handlers. Every query
is read-only, parameterized, and deliberately bounded so a browser never has
to download an entire Apple Health export to render one screen.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

import duckdb

from apple_health_dashboard.services.metrics import (
    metric_aggregation,
    metric_category,
    metric_label,
    metric_unit_hint,
)
from apple_health_dashboard.services.workouts import workout_label

MAX_PAGE_SIZE = 200
MAX_SERIES_DAYS = 3_650


class AnalyticsNotReadyError(RuntimeError):
    """Raised when the local database has not been created by an import yet."""


def metric_series(db_path: Path, record_type: str, days: int | None) -> dict[str, Any]:
    """Return daily metric points using the catalog's safe aggregation policy."""
    aggregation = metric_aggregation(record_type)
    aggregate_sql = {"sum": "SUM(value)", "mean": "AVG(value)", "last": "ARG_MAX(value, start_at)"}[aggregation]
    where_sql, parameters = _record_filter(record_type, days)
    rows = _query(
        db_path,
        f"""
        SELECT CAST(start_at AS DATE) AS day, {aggregate_sql} AS value, MIN(unit) AS unit, COUNT(*) AS sample_count
        FROM health_record
        {where_sql}
        GROUP BY CAST(start_at AS DATE)
        ORDER BY day
        """,
        parameters,
    )
    points = [
        {
            "date": _iso(row[0]),
            "value": _number(row[1]),
            "unit": row[2] or metric_unit_hint(record_type),
            "sample_count": int(row[3]),
        }
        for row in rows
        if row[1] is not None
    ]
    return {"record_type": record_type, "aggregation": aggregation, "points": points}


def available_types(db_path: Path) -> list[dict[str, Any]]:
    """Return only metric types that exist in this profile, with compact counts."""
    rows = _query(
        db_path,
        """
        SELECT type, COUNT(*) AS count, MIN(start_at) AS first_record_at, MAX(start_at) AS last_record_at, MIN(unit) AS unit
        FROM health_record
        GROUP BY type
        ORDER BY count DESC, type
        """,
        [],
    )
    return [
        {
            "record_type": row[0],
            "label": metric_label(row[0]),
            "category": metric_category(row[0]),
            "count": int(row[1]),
            "first_record_at": _iso(row[2]),
            "last_record_at": _iso(row[3]),
            "unit": row[4],
        }
        for row in rows
    ]


def paged_records(db_path: Path, record_type: str | None, offset: int, limit: int) -> dict[str, Any]:
    """Return a capped, newest-first source-data page for the Explorer."""
    clauses: list[str] = []
    parameters: list[Any] = []
    if record_type:
        clauses.append("type = ?")
        parameters.append(record_type)
    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    total = int(_query(db_path, f"SELECT COUNT(*) FROM health_record {where_sql}", parameters)[0][0])
    rows = _query(
        db_path,
        f"""
        SELECT type, start_at, end_at, source_name, unit, value, value_str
        FROM health_record
        {where_sql}
        ORDER BY start_at DESC
        LIMIT ? OFFSET ?
        """,
        [*parameters, limit, offset],
    )
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": [
            {
                "record_type": row[0],
                "start_at": _iso(row[1]),
                "end_at": _iso(row[2]),
                "source_name": row[3],
                "unit": row[4],
                "value": _number(row[5]),
                "value_str": row[6],
            }
            for row in rows
        ],
    }


def workout_summary(db_path: Path, days: int | None) -> dict[str, Any]:
    """Return workout totals, trend points, and type distribution for one view."""
    where_sql, parameters = _date_filter("start_at", days)
    totals = _query(
        db_path,
        f"""
        SELECT COUNT(*), COALESCE(SUM(duration_s), 0), COALESCE(SUM(total_distance_m), 0), COALESCE(SUM(total_energy_kcal), 0)
        FROM workout {where_sql}
        """,
        parameters,
    )[0]
    weekly = _query(
        db_path,
        f"""
        SELECT DATE_TRUNC('week', start_at) AS week, COUNT(*) AS count, COALESCE(SUM(duration_s), 0) / 3600 AS duration_hours
        FROM workout {where_sql}
        GROUP BY week ORDER BY week
        """,
        parameters,
    )
    by_type = _query(
        db_path,
        f"""
        SELECT workout_activity_type, COUNT(*) AS count, COALESCE(SUM(duration_s), 0) / 3600 AS duration_hours
        FROM workout {where_sql}
        GROUP BY workout_activity_type ORDER BY count DESC LIMIT 12
        """,
        parameters,
    )
    return {
        "total_workouts": int(totals[0]),
        "total_duration_hours": round(float(totals[1]) / 3600, 1),
        "total_distance_km": round(float(totals[2]) / 1000, 1),
        "total_energy_kcal": round(float(totals[3]), 0),
        "weekly": [{"date": _iso(row[0]), "count": int(row[1]), "duration_hours": round(float(row[2]), 1)} for row in weekly],
        "by_type": [
            {"label": workout_label(row[0]), "count": int(row[1]), "duration_hours": round(float(row[2]), 1)}
            for row in by_type
        ],
    }


def rings(db_path: Path, days: int | None) -> list[dict[str, Any]]:
    """Return daily Apple Activity ring summaries when present in the export."""
    where_sql, parameters = _date_filter("day", days)
    rows = _query(
        db_path,
        f"""
        SELECT day, active_energy_burned_kcal, active_energy_burned_goal_kcal,
               apple_exercise_time_min, apple_exercise_time_goal_min, apple_stand_hours, apple_stand_hours_goal
        FROM activity_summary {where_sql} ORDER BY day
        """,
        parameters,
    )
    fields = ["date", "active_energy_kcal", "active_energy_goal_kcal", "exercise_minutes", "exercise_goal_minutes", "stand_hours", "stand_goal_hours"]
    return [dict(zip(fields, [_iso(row[0]), *[_number(value) for value in row[1:]]], strict=True)) for row in rows]


def sleep_summary(db_path: Path, days: int | None) -> dict[str, Any]:
    """Return nightly actual-sleep duration and stage totals without raw intervals."""
    sleep_type = "HKCategoryTypeIdentifierSleepAnalysis"
    where_sql, parameters = _record_filter(sleep_type, days)
    stage_filter = """
        value_str IN (
          'HKCategoryValueSleepAnalysisAsleepUnspecified', 'HKCategoryValueSleepAnalysisAsleep',
          'HKCategoryValueSleepAnalysisAsleepCore', 'HKCategoryValueSleepAnalysisAsleepDeep',
          'HKCategoryValueSleepAnalysisAsleepREM'
        )
    """
    conjunction = "AND" if where_sql else "WHERE"
    rows = _query(
        db_path,
        f"""
        SELECT CAST(end_at AS DATE) AS day, SUM(EXTRACT(EPOCH FROM end_at - start_at)) / 3600 AS hours
        FROM health_record {where_sql} {conjunction} {stage_filter}
        GROUP BY day ORDER BY day
        """,
        parameters,
    )
    stages = _query(
        db_path,
        f"""
        SELECT value_str, SUM(EXTRACT(EPOCH FROM end_at - start_at)) / 3600 AS hours
        FROM health_record {where_sql} {conjunction} {stage_filter}
        GROUP BY value_str ORDER BY hours DESC
        """,
        parameters,
    )
    labels = {
        "HKCategoryValueSleepAnalysisAsleepUnspecified": "Asleep",
        "HKCategoryValueSleepAnalysisAsleep": "Asleep",
        "HKCategoryValueSleepAnalysisAsleepCore": "Core sleep",
        "HKCategoryValueSleepAnalysisAsleepDeep": "Deep sleep",
        "HKCategoryValueSleepAnalysisAsleepREM": "REM sleep",
    }
    nightly = [{"date": _iso(row[0]), "hours": round(float(row[1]), 2)} for row in rows]
    average = round(sum(point["hours"] for point in nightly) / len(nightly), 2) if nightly else None
    return {
        "average_hours": average,
        "night_count": len(nightly),
        "nightly": nightly,
        "stages": [{"label": labels.get(row[0], row[0] or "Unknown"), "hours": round(float(row[1]), 1)} for row in stages],
    }


def _record_filter(record_type: str, days: int | None) -> tuple[str, list[Any]]:
    where_sql, parameters = _date_filter("start_at", days)
    if where_sql:
        return f"{where_sql} AND type = ?", [*parameters, record_type]
    return "WHERE type = ?", [record_type]


def _date_filter(column: str, days: int | None) -> tuple[str, list[Any]]:
    if days is None:
        return "", []
    return f"WHERE {column} >= CURRENT_TIMESTAMP - (? * INTERVAL '1 day')", [days]


def _query(db_path: Path, sql: str, parameters: Sequence[Any]) -> list[tuple[Any, ...]]:
    if not db_path.exists():
        raise AnalyticsNotReadyError("Import an Apple Health export before opening analytics.")
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        return con.execute(sql, parameters).fetchall()
    except duckdb.CatalogException as exc:
        raise AnalyticsNotReadyError("The local database has not been initialized yet.") from exc
    finally:
        con.close()


def _iso(value: datetime | Any) -> str | None:
    return value.isoformat() if value is not None else None


def _number(value: Any) -> float | int | None:
    if value is None:
        return None
    numeric = float(value)
    return int(numeric) if numeric.is_integer() else round(numeric, 4)
