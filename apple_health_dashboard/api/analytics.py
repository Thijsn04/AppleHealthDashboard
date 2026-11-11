"""Bounded read models for the local analyzer API.

This module keeps SQL and response shaping out of route handlers. Every query
is read-only, parameterized, and deliberately bounded so a browser never has
to download an entire Apple Health export to render one screen.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime
from math import isfinite
from pathlib import Path
from typing import Any

import duckdb

from apple_health_dashboard.services.metrics import (
    METRICS,
    metric_aggregation,
    metric_category,
    metric_label,
    metric_unit_hint,
)
from apple_health_dashboard.services.units import UNIT_CONVERSIONS
from apple_health_dashboard.services.workouts import workout_label

MAX_PAGE_SIZE = 200
MAX_SERIES_DAYS = 3_650


class AnalyticsNotReadyError(RuntimeError):
    """Raised when the local database has not been created by an import yet."""


_CATALOG = {metric.record_type: metric for metric in METRICS}
_RECORD_DAY = "COALESCE(TRY_CAST(LEFT(source_start, 10) AS DATE), CAST(start_at AS DATE))"
_WORKOUT_DAY = _RECORD_DAY


def metric_series(
    db_path: Path,
    record_type: str,
    days: int | None,
    start: date | None = None,
    end: date | None = None,
    grain: str = "day",
    source: str | None = None,
) -> dict[str, Any]:
    """Aggregate a known metric using one source/device per calendar day."""
    aggregation = metric_aggregation(record_type)
    result: dict[str, Any] = {
        "record_type": record_type, "aggregation": aggregation, "grain": grain,
        "points": [], "excluded_samples": 0, "legacy_samples": 0, "sources": [],
    }
    if record_type not in _CATALOG:
        return result

    end = end or _query(db_path, f"SELECT MAX({_RECORD_DAY}) FROM health_record WHERE type = ?", [record_type])[0][0]
    if end is None:
        return result
    start = start or date.fromordinal(max(1, end.toordinal() - (days or MAX_SERIES_DAYS) + 1))
    result.update(start=start.isoformat(), end=end.isoformat())
    target = metric_unit_hint(record_type)
    conversions = [(target, 1, 0), *UNIT_CONVERSIONS.get(target, [])]
    values = ", ".join("(CAST(? AS VARCHAR), CAST(? AS DOUBLE), CAST(? AS DOUBLE))" for _ in conversions)
    valid_unit = "u.factor IS NOT NULL" if target else "r.unit IS NULL"
    percentage = "CASE WHEN r.value BETWEEN 0 AND 1 THEN r.value * 100 END" if target == "%" else "r.value"
    cte = f"""
      WITH source_rows AS (
        SELECT *, {_RECORD_DAY} AS day FROM health_record WHERE type = ?
      ), scoped AS (
        SELECT r.*, COALESCE(r.source_name, '') AS source,
               CASE WHEN {valid_unit} AND isfinite(r.value)
                    THEN {percentage} * COALESCE(u.factor, 1) + COALESCE(u.shift, 0)
               END AS normalized
        FROM source_rows r
        LEFT JOIN (VALUES {values}) u(unit, factor, shift) ON r.unit = u.unit
        WHERE day BETWEEN ? AND ?
          AND (? IS NULL OR r.source_name IS NOT DISTINCT FROM NULLIF(?, ''))
          AND end_at >= start_at
      ), unique_samples AS (
        SELECT * FROM scoped WHERE isfinite(normalized)
        QUALIFY ROW_NUMBER() OVER (
          PARTITION BY day, source, device, start_at, end_at, normalized ORDER BY record_hash
        ) = 1
      ), preferred AS (
        SELECT day, source, device FROM unique_samples GROUP BY day, source, device
        QUALIFY ROW_NUMBER() OVER (PARTITION BY day ORDER BY COUNT(*) DESC, source, device NULLS LAST) = 1
      ), selected AS (
        SELECT u.*, MAX(end_at) FILTER (WHERE end_at > start_at) OVER (
          PARTITION BY u.day ORDER BY start_at, end_at DESC, record_hash
          ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
        ) AS prior_end
        FROM unique_samples u JOIN preferred p
          ON u.day = p.day AND u.source = p.source AND u.device IS NOT DISTINCT FROM p.device
      ), accepted AS (
        SELECT * FROM selected
        {"WHERE prior_end IS NULL OR start_at >= prior_end OR start_at = end_at" if aggregation == "sum" else ""}
      )
    """
    parameters = [
        record_type, *(value for row in conversions for value in row), start, end, source, source,
    ]
    bucket = {"day": "day", "week": "CAST(DATE_TRUNC('week', day) AS DATE)", "month": "CAST(DATE_TRUNC('month', day) AS DATE)"}[grain]
    aggregate = {
        "sum": "SUM(normalized)", "mean": "AVG(normalized)",
        "last": "FIRST(normalized ORDER BY start_at DESC, record_hash)",
    }[aggregation]
    rows = _query(db_path, cte + f"""
      , buckets AS (
        SELECT {bucket} AS bucket_day, {aggregate} AS value, COUNT(*) AS samples
        FROM accepted GROUP BY bucket_day
      ), quality AS (
        SELECT (SELECT COUNT(*) FROM scoped) - COUNT(*) AS excluded,
               COUNT(*) FILTER (WHERE source_start IS NULL) AS legacy,
               LIST(DISTINCT NULLIF(source, '') ORDER BY NULLIF(source, '')) AS sources
        FROM accepted
      )
      SELECT bucket_day, value, samples, excluded, legacy, sources
      FROM quality LEFT JOIN buckets ON TRUE ORDER BY bucket_day
    """, parameters)
    result.update(
        points=[
            {"date": _iso(day), "value": _number(value), "unit": target, "sample_count": count}
            for day, value, count, *_ in rows if _number(value) is not None
        ],
        excluded_samples=rows[0][3],
        legacy_samples=rows[0][4],
        sources=rows[0][5] or [],
    )
    return result


def available_types(db_path: Path) -> list[dict[str, Any]]:
    """Return only metric types that exist in this profile, with compact counts."""
    rows = _query(
        db_path,
        f"""
        SELECT type, COUNT(*) AS count, MIN(start_at) AS first_record_at, MAX(start_at) AS last_record_at, CASE WHEN COUNT(DISTINCT unit) = 1 THEN MIN(unit) END AS unit,
               LIST(DISTINCT source_name ORDER BY source_name) AS sources,
               COUNT(*) FILTER (WHERE isfinite(value)) AS numeric_count,
               MIN({_RECORD_DAY}), MAX({_RECORD_DAY})
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
            "sources": row[5],
            "numeric_count": row[6],
            "chartable": row[0] in _CATALOG and row[6] > 0,
            "first_day": _iso(row[7]),
            "last_day": _iso(row[8]),
        }
        for row in rows
    ]


def paged_records(
    db_path: Path, record_type: str | None, offset: int, limit: int,
    start: date | None = None, end: date | None = None, source: str | None = None,
) -> dict[str, Any]:
    """Return a capped, newest-first source-data page for the Explorer."""
    clauses: list[str] = []
    parameters: list[Any] = []
    if record_type:
        clauses.append("type = ?")
        parameters.append(record_type)
    if start is not None:
        clauses.append(f"{_RECORD_DAY} >= ?")
        parameters.append(start)
    if end is not None:
        clauses.append(f"{_RECORD_DAY} <= ?")
        parameters.append(end)
    if source is not None:
        clauses.append("source_name IS NOT DISTINCT FROM NULLIF(?, '')")
        parameters.append(source)
    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    total = int(_query(db_path, f"SELECT COUNT(*) FROM health_record {where_sql}", parameters)[0][0])
    rows = _query(
        db_path,
        f"""
        SELECT type, COALESCE(source_start, CAST(start_at AS VARCHAR)),
               COALESCE(source_end, CAST(end_at AS VARCHAR)), source_name, unit, value, value_str,
               device, source_version, source_start IS NULL
        FROM health_record
        {where_sql}
        ORDER BY start_at DESC, record_hash
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
                "start_at": row[1],
                "end_at": row[2],
                "source_name": row[3],
                "unit": row[4],
                "value": _number(row[5]),
                "value_str": row[6],
                "device": row[7],
                "source_version": row[8],
                "legacy_timestamp": row[9],
            }
            for row in rows
        ],
    }


def workout_summary(db_path: Path, days: int | None) -> dict[str, Any]:
    """Aggregate compatible reported quantities over deduplicated workout sessions."""
    where_sql, parameters = _date_filter(_WORKOUT_DAY, days, "workout")
    normalized = f"""
      WITH ordered AS (
        SELECT {_WORKOUT_DAY} AS day, workout_activity_type, start_at, end_at, source_name, source_start, workout_hash,
               reported_hours AS hours, reported_km AS km, reported_kcal AS kcal, reported_bpm AS bpm,
               MAX(end_at) OVER (
                 PARTITION BY workout_activity_type ORDER BY start_at, end_at DESC, workout_hash
                 ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
               ) AS prior_end
        FROM workout {where_sql} AND end_at > start_at
      ), clusters AS (
        SELECT *, SUM(CASE WHEN prior_end IS NULL OR start_at >= prior_end THEN 1 ELSE 0 END) OVER (
          PARTITION BY workout_activity_type ORDER BY start_at, end_at DESC, workout_hash
        ) AS overlap_group
        FROM ordered
      ), workouts AS (
        SELECT * FROM clusters
        QUALIFY ROW_NUMBER() OVER (
          PARTITION BY workout_activity_type, overlap_group
          ORDER BY (hours IS NOT NULL) DESC, (km IS NOT NULL) DESC, (kcal IS NOT NULL) DESC,
                   end_at - start_at DESC, source_name, workout_hash
        ) = 1
      )
    """
    totals = _query(db_path, normalized + "SELECT COUNT(*), SUM(hours), SUM(km), SUM(kcal) FROM workouts", parameters)[0]
    weekly = _query(db_path, normalized + """
        SELECT CAST(DATE_TRUNC('week', day) AS DATE), COUNT(*), SUM(hours)
        FROM workouts GROUP BY 1 ORDER BY 1
    """, parameters)
    by_type = _query(db_path, normalized + """
        SELECT workout_activity_type, COUNT(*), SUM(hours)
        FROM workouts GROUP BY 1 ORDER BY 2 DESC, 1 LIMIT 12
    """, parameters)
    sessions = _query(db_path, normalized + """
        SELECT COALESCE(source_start, CAST(start_at AS VARCHAR)), workout_activity_type, source_name, hours, km, kcal, bpm
        FROM workouts ORDER BY start_at DESC, workout_activity_type, source_name LIMIT 20
    """, parameters)
    return {
        "total_workouts": totals[0],
        "total_duration_hours": _number(totals[1]),
        "total_distance_km": _number(totals[2]),
        "total_energy_kcal": _number(totals[3]),
        "weekly": [{"date": _iso(day), "count": count, "duration_hours": _number(hours)} for day, count, hours in weekly],
        "by_type": [{"label": workout_label(kind), "count": count, "duration_hours": _number(hours)} for kind, count, hours in by_type],
        "sessions": [
            {"start": start, "label": workout_label(kind), "source": source,
             "hours": _number(hours), "km": _number(km), "kcal": _number(kcal), "bpm": _number(bpm)}
            for start, kind, source, hours, km, kcal, bpm in sessions
        ],
    }


def rings(db_path: Path, days: int | None) -> list[dict[str, Any]]:
    """Return daily Apple Activity ring summaries when present in the export."""
    where_sql, parameters = _date_filter("day", days, "activity_summary")
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
    """Union elapsed asleep intervals and report unambiguous stage durations."""
    end_day = "COALESCE(TRY_CAST(LEFT(source_end, 10) AS DATE), CAST(end_at AS DATE))"
    rows = _query(db_path, f"""
      WITH intervals AS (
        SELECT DISTINCT start_at, end_at, {end_day} AS day,
          CASE value_str
            WHEN 'HKCategoryValueSleepAnalysisAsleepCore' THEN 'Core'
            WHEN 'HKCategoryValueSleepAnalysisAsleepDeep' THEN 'Deep'
            WHEN 'HKCategoryValueSleepAnalysisAsleepREM' THEN 'REM'
          END AS stage
        FROM health_record
        WHERE type = 'HKCategoryTypeIdentifierSleepAnalysis'
          AND value_str IN (
            'HKCategoryValueSleepAnalysisAsleep', 'HKCategoryValueSleepAnalysisAsleepUnspecified',
            'HKCategoryValueSleepAnalysisAsleepCore', 'HKCategoryValueSleepAnalysisAsleepDeep',
            'HKCategoryValueSleepAnalysisAsleepREM'
          )
          AND end_at > start_at
      ), events AS (
        SELECT start_at AS t, stage, 1 AS delta, NULL AS end_day FROM intervals
        UNION ALL
        SELECT end_at, stage, -1, day FROM intervals
      ), ticks AS (
        SELECT t, SUM(delta) AS delta,
               COALESCE(SUM(delta) FILTER (WHERE stage = 'Core'), 0) AS core,
               COALESCE(SUM(delta) FILTER (WHERE stage = 'Deep'), 0) AS deep,
               COALESCE(SUM(delta) FILTER (WHERE stage = 'REM'), 0) AS rem,
               MAX(end_day) AS end_day
        FROM events GROUP BY t
      ), sweep AS (
        SELECT *, LEAD(t) OVER (ORDER BY t) AS next_t,
               SUM(delta) OVER (ORDER BY t) AS asleep,
               SUM(core) OVER (ORDER BY t) > 0 AS in_core,
               SUM(deep) OVER (ORDER BY t) > 0 AS in_deep,
               SUM(rem) OVER (ORDER BY t) > 0 AS in_rem
        FROM ticks
      ), segments AS (
        SELECT *, MIN(CASE WHEN asleep = 0 THEN t END) OVER (
          ORDER BY t ROWS BETWEEN CURRENT ROW AND UNBOUNDED FOLLOWING
        ) AS episode_end,
        EXTRACT(EPOCH FROM next_t - t) / 3600 AS hours
        FROM sweep
      ), daily AS (
        SELECT e.end_day AS day, SUM(s.hours) AS hours,
               SUM(s.hours) FILTER (WHERE in_core AND NOT in_deep AND NOT in_rem) AS core,
               SUM(s.hours) FILTER (WHERE in_deep AND NOT in_core AND NOT in_rem) AS deep,
               SUM(s.hours) FILTER (WHERE in_rem AND NOT in_core AND NOT in_deep) AS rem
        FROM segments s JOIN ticks e ON s.episode_end = e.t
        WHERE asleep > 0 GROUP BY day
      )
      SELECT day, hours, core, deep, rem FROM daily
      WHERE day >= (SELECT MAX(day) FROM daily) - CAST(? AS INTEGER) + 1 ORDER BY day
    """, [days or MAX_SERIES_DAYS])
    nightly = [{"date": _iso(row[0]), "hours": round(row[1], 2)} for row in rows]
    return {
        "average_hours": round(sum(row[1] for row in rows) / len(rows), 2) if rows else None,
        "night_count": len(rows),
        "nightly": nightly,
        "stages": [
            {"label": stage, "hours": round(total, 2)}
            for index, stage in enumerate(("Core", "Deep", "REM"), start=2)
            if (total := sum(row[index] or 0 for row in rows)) > 0
        ],
    }


def _date_filter(column: str, days: int | None, table: str) -> tuple[str, list[Any]]:
    return f"WHERE {column} >= (SELECT MAX({column}) FROM {table}) - CAST(? AS INTEGER) + 1", [days or MAX_SERIES_DAYS]


def _query(db_path: Path, sql: str, parameters: Sequence[Any]) -> list[tuple[Any, ...]]:
    if not db_path.exists():
        raise AnalyticsNotReadyError("Import an Apple Health export before opening analytics.")
    con = duckdb.connect(str(db_path))
    try:
        return con.execute(sql, parameters).fetchall()
    except duckdb.CatalogException as exc:
        raise AnalyticsNotReadyError("The local database has not been initialized yet.") from exc
    finally:
        con.close()


def _iso(value: datetime | Any) -> str | None:
    return value.isoformat() if value is not None else None


def _number(value: Any) -> float | int | None:
    if value is None or not isfinite(value):
        return None
    numeric = float(value)
    return int(numeric) if numeric.is_integer() else numeric
