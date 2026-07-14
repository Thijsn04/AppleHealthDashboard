from __future__ import annotations

import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pytest

from apple_health_dashboard.ingest.importer import import_export_xml_to_duckdb_all
from apple_health_dashboard.ingest.safe_import import (
    ImportLimits,
    ImportValidationError,
    prepare_export,
    preview_export,
)
from apple_health_dashboard.storage.duckdb_store import init_db, open_db

VALID_XML = """<?xml version="1.0" encoding="UTF-8"?>
<HealthData>
  <Record type="HKQuantityTypeIdentifierStepCount" unit="count" value="42"
    startDate="2024-01-01 10:00:00 +0000" endDate="2024-01-01 10:05:00 +0000"/>
  <Workout workoutActivityType="HKWorkoutActivityTypeRunning"
    startDate="2024-01-02 10:00:00 +0000" endDate="2024-01-02 11:00:00 +0000"/>
  <ActivitySummary dateComponents="2024-01-03"/>
</HealthData>
"""


def test_prepare_zip_streams_export_xml_and_preview_is_bounded(tmp_path: Path) -> None:
    archive_path = tmp_path / "export.zip"
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("apple_health_export/export.xml", VALID_XML)

    prepared = prepare_export(archive_path, tmp_path / "temporary")
    preview = preview_export(prepared.xml_path)

    assert prepared.extracted_from_zip
    assert prepared.xml_path.read_text(encoding="utf-8") == VALID_XML
    assert preview.record_count == 1
    assert preview.workout_count == 1
    assert preview.activity_summary_count == 1
    assert preview.record_type_count == 1


def test_prepare_zip_rejects_unsafe_member_path(tmp_path: Path) -> None:
    archive_path = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("../export.xml", VALID_XML)

    with pytest.raises(ImportValidationError, match="unsafe file path"):
        prepare_export(archive_path, tmp_path / "temporary")


def test_prepare_zip_rejects_compression_ratio(tmp_path: Path) -> None:
    archive_path = tmp_path / "dense.zip"
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("apple_health_export/export.xml", "a" * 100_000)

    with pytest.raises(ImportValidationError, match="compression ratio"):
        prepare_export(
            archive_path,
            tmp_path / "temporary",
            limits=ImportLimits(max_compression_ratio=2),
        )


def test_import_is_atomic_and_reports_actual_inserted_rows(tmp_path: Path) -> None:
    valid_path = tmp_path / "valid.xml"
    valid_path.write_text(VALID_XML, encoding="utf-8")
    database_path = tmp_path / "health.duckdb"

    first = import_export_xml_to_duckdb_all(valid_path, database_path, record_batch_size=1)
    second = import_export_xml_to_duckdb_all(valid_path, database_path, record_batch_size=1)

    assert first["records_inserted"] == 1
    assert first["workouts_inserted"] == 1
    assert second["records_inserted"] == 0
    assert second["workouts_inserted"] == 0

    invalid_path = tmp_path / "invalid.xml"
    invalid_path.write_text(VALID_XML.replace("</HealthData>", ""), encoding="utf-8")
    with pytest.raises(ET.ParseError):
        import_export_xml_to_duckdb_all(invalid_path, tmp_path / "invalid.duckdb", record_batch_size=1)

    con = open_db(tmp_path / "invalid.duckdb")
    try:
        init_db(con)
        assert con.execute("SELECT COUNT(*) FROM health_record").fetchone()[0] == 0
    finally:
        con.close()
