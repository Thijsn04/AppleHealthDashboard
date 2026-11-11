"""Read-only endpoints that form the first stable API contract."""

from __future__ import annotations

import asyncio
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Annotated, Literal

import duckdb
from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status

from apple_health_dashboard.api.analytics import (
    MAX_PAGE_SIZE,
    MAX_SERIES_DAYS,
    AnalyticsNotReadyError,
    available_types,
    metric_series,
    paged_records,
    rings,
    sleep_summary,
    workout_summary,
)
from apple_health_dashboard.api.imports import LocalImportStaging, StagedImport
from apple_health_dashboard.api.schemas import (
    HealthResponse,
    ImportPreviewResponse,
    ImportResultResponse,
    ImportStartRequest,
    MetricResponse,
    OverviewResponse,
)
from apple_health_dashboard.db import default_db_path
from apple_health_dashboard.ingest.importer import import_export_xml_to_duckdb_all
from apple_health_dashboard.ingest.safe_import import ImportValidationError
from apple_health_dashboard.services.metrics import METRICS

router = APIRouter(tags=["analyzer"])
_staging = LocalImportStaging(Path.cwd() / ".tmp" / "api-imports")


@router.get("/health", response_model=HealthResponse, summary="Check local API availability")
def health() -> HealthResponse:
    """Return service metadata without reading personal health data."""
    return HealthResponse(status="ok", version="0.2.0", network_mode="local-only")


@router.get("/catalog/metrics", response_model=list[MetricResponse], summary="List known metrics")
def metric_catalog() -> list[MetricResponse]:
    """Return the curated metric catalog used by the user interface."""
    return [
        MetricResponse(
            record_type=metric.record_type,
            label=metric.label,
            category=metric.category,
            aggregation=metric.aggregation,
            unit_hint=metric.unit_hint,
            description=metric.description,
        )
        for metric in METRICS
    ]


@router.get("/analytics/types", summary="List metric types available in the active profile")
def analytics_types() -> list[dict[str, object]]:
    """List only types present in the local import, never their raw measurements."""
    return _analytics_response(available_types, default_db_path())


@router.get("/analytics/metrics/{record_type}/series", summary="Get a bounded daily metric series")
def analytics_metric_series(
    record_type: str,
    days: int | None = Query(default=None, ge=1, le=MAX_SERIES_DAYS),
    start: date | None = None,
    end: date | None = None,
    grain: Literal["day", "week", "month"] = "day",
    source: str | None = Query(default=None, max_length=1024),
) -> dict[str, object]:
    """Aggregate one metric into the requested calendar buckets."""
    if start and (not end or not 0 <= (end - start).days < MAX_SERIES_DAYS):
        raise HTTPException(status_code=422, detail="Select an ordered date range of at most 3,650 days.")
    return _analytics_response(metric_series, default_db_path(), record_type, days, start, end, grain, source)


@router.get("/analytics/sleep", summary="Get nightly sleep duration and stages")
def analytics_sleep(
    days: int | None = Query(default=90, ge=1, le=MAX_SERIES_DAYS),
) -> dict[str, object]:
    """Return aggregate sleep context without exposing every raw interval by default."""
    return _analytics_response(sleep_summary, default_db_path(), days)


@router.get("/analytics/workouts", summary="Get workout totals, weekly trend, and type mix")
def analytics_workouts(
    days: int | None = Query(default=365, ge=1, le=MAX_SERIES_DAYS),
) -> dict[str, object]:
    """Return compact workout analytics for the selected local history window."""
    return _analytics_response(workout_summary, default_db_path(), days)


@router.get("/analytics/rings", summary="Get Apple Activity ring days")
def analytics_rings(
    days: int | None = Query(default=90, ge=1, le=MAX_SERIES_DAYS),
) -> list[dict[str, object]]:
    """Return daily ring values only when Apple Activity summaries were exported."""
    return _analytics_response(rings, default_db_path(), days)


@router.get("/analytics/records", summary="Browse a bounded page of source records")
def analytics_records(
    record_type: str | None = Query(default=None, max_length=255),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=MAX_PAGE_SIZE),
    start: date | None = None,
    end: date | None = None,
    source: str | None = Query(default=None, max_length=1024),
) -> dict[str, object]:
    """Expose paginated source observations for verification and export workflows."""
    return _analytics_response(paged_records, default_db_path(), record_type, offset, limit, start, end, source)


@router.post(
    "/imports/preview",
    response_model=ImportPreviewResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Inspect a selected local export before importing it",
)
async def preview_import(file: Annotated[UploadFile, File(...)]) -> ImportPreviewResponse:
    """Stage and inspect an explicitly selected file without writing health records."""
    try:
        staged = await _staging.stage(file)
    except ImportValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _preview_response(staged)


@router.delete("/imports/{ticket_id}", status_code=204, summary="Discard an unconfirmed export")
async def discard_import(ticket_id: str) -> None:
    staged = await _staging.consume(ticket_id)
    if staged is not None:
        _staging.discard(staged)


@router.post("/imports", response_model=ImportResultResponse, summary="Confirm a local Apple Health import")
async def import_staged_export(request: ImportStartRequest) -> ImportResultResponse:
    """Persist one previously previewed local export in an atomic transaction."""
    staged = await _staging.consume(request.ticket_id)
    if staged is None:
        raise HTTPException(status_code=404, detail="The import preview expired or was already used.")
    try:
        counters = await asyncio.to_thread(
            import_export_xml_to_duckdb_all,
            staged.prepared_export.xml_path,
            default_db_path(),
        )
    except Exception as exc:
        raise HTTPException(status_code=422, detail="The export could not be imported safely.") from exc
    finally:
        _staging.discard(staged)
    return ImportResultResponse(**counters)


@router.get("/overview", response_model=OverviewResponse, summary="Get local import overview")
def overview() -> OverviewResponse:
    """Return a compact, privacy-preserving summary of the active local database."""
    db_path = default_db_path()
    if not db_path.exists():
        return OverviewResponse.empty(database_path=str(db_path))

    try:
        return _load_overview(db_path)
    except duckdb.Error as exc:
        raise HTTPException(status_code=503, detail="The local health database is unavailable.") from exc


def _load_overview(db_path: Path) -> OverviewResponse:
    """Load only aggregate database facts required by the landing screen."""
    con = duckdb.connect(str(db_path))
    try:
        record_count = int(con.execute("SELECT COUNT(*) FROM health_record").fetchone()[0])
        workout_count = int(con.execute("SELECT COUNT(*) FROM workout").fetchone()[0])
        ring_day_count = int(con.execute("SELECT COUNT(*) FROM activity_summary").fetchone()[0])
        date_range = con.execute("SELECT MIN(start_at), MAX(start_at) FROM health_record").fetchone()
        categories = _category_counts(con)
    finally:
        con.close()

    return OverviewResponse(
        has_data=bool(record_count or workout_count or ring_day_count),
        database_path=str(db_path),
        record_count=record_count,
        workout_count=workout_count,
        ring_day_count=ring_day_count,
        first_record_at=date_range[0],
        last_record_at=date_range[1],
        category_counts=categories,
    )


def _category_counts(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    """Map stored record types onto the curated category catalog."""
    category_by_type = {metric.record_type: metric.category for metric in METRICS}
    rows = con.execute("SELECT type, COUNT(*) FROM health_record GROUP BY type").fetchall()
    counts: Counter[str] = Counter()
    for record_type, count in rows:
        counts[category_by_type.get(record_type, "Other")] += int(count)
    return dict(sorted(counts.items()))


def _preview_response(staged: StagedImport) -> ImportPreviewResponse:
    """Translate domain-level inspection results into the public API contract."""
    preview = staged.preview
    prepared = staged.prepared_export
    return ImportPreviewResponse(
        ticket_id=staged.ticket_id,
        file_name=staged.display_name,
        source_size_bytes=prepared.source_size_bytes,
        extracted_from_zip=prepared.extracted_from_zip,
        record_count=preview.record_count,
        workout_count=preview.workout_count,
        activity_summary_count=preview.activity_summary_count,
        record_type_count=preview.record_type_count,
        earliest_start=preview.earliest_start,
        latest_end=preview.latest_end,
    )


def _analytics_response(function, *args):  # type: ignore[no-untyped-def]
    """Translate an uninitialized local profile into one consistent API response."""
    try:
        return function(*args)
    except AnalyticsNotReadyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except duckdb.Error as exc:
        raise HTTPException(status_code=503, detail="The local health database is unavailable.") from exc
