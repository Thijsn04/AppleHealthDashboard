"""Pydantic schemas for stable, explicit local API responses."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Metadata returned by the unauthenticated local health endpoint."""

    status: str
    version: str
    network_mode: str


class MetricResponse(BaseModel):
    """A metric that the analyzer can label and aggregate."""

    record_type: str
    label: str
    category: str
    aggregation: str
    unit_hint: str | None = None
    description: str | None = None


class OverviewResponse(BaseModel):
    """Aggregate facts about the current local import, never raw observations."""

    has_data: bool
    database_path: str
    record_count: int = Field(ge=0)
    workout_count: int = Field(ge=0)
    ring_day_count: int = Field(ge=0)
    first_record_at: datetime | None = None
    last_record_at: datetime | None = None
    category_counts: dict[str, int] = Field(default_factory=dict)

    @classmethod
    def empty(cls, database_path: str) -> OverviewResponse:
        """Create the canonical response for a profile that has no import yet."""
        return cls(
            has_data=False,
            database_path=database_path,
            record_count=0,
            workout_count=0,
            ring_day_count=0,
        )


class ImportPreviewResponse(BaseModel):
    """A local-only inspection returned before any data is persisted."""

    ticket_id: str
    file_name: str
    source_size_bytes: int = Field(ge=0)
    extracted_from_zip: bool
    record_count: int = Field(ge=0)
    workout_count: int = Field(ge=0)
    activity_summary_count: int = Field(ge=0)
    record_type_count: int = Field(ge=0)
    earliest_start: str | None = None
    latest_end: str | None = None


class ImportStartRequest(BaseModel):
    """An explicit confirmation to persist a previously inspected local export."""

    ticket_id: str = Field(min_length=1, max_length=64)


class ImportResultResponse(BaseModel):
    """Counts of newly persisted records from one completed import."""

    entries_skipped: int = Field(default=0, ge=0)
    records_inserted: int = Field(ge=0)
    record_metadata_inserted: int = Field(ge=0)
    activity_summaries_inserted: int = Field(ge=0)
    workouts_inserted: int = Field(ge=0)
    workout_metadata_inserted: int = Field(ge=0)
