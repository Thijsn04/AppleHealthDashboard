from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from apple_health_dashboard.api.app import create_app

SINGLE_RECORD_XML = """<?xml version="1.0" encoding="UTF-8"?>
<HealthData><Record type="HKQuantityTypeIdentifierStepCount" unit="count" value="42"
startDate="2024-01-01 10:00:00 +0000" endDate="2024-01-01 10:05:00 +0000"/></HealthData>"""


def test_health_endpoint_is_local_only() -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.2.0", "network_mode": "local-only"}


def test_metric_catalog_has_unique_record_types() -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/catalog/metrics")

    assert response.status_code == 200
    record_types = [metric["record_type"] for metric in response.json()]
    assert len(record_types) == len(set(record_types))
    assert "HKQuantityTypeIdentifierStepCount" in record_types


def test_import_requires_preview_then_explicit_confirmation(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("apple_health_dashboard.api.routes.default_db_path", lambda: tmp_path / "health.duckdb")
    client = TestClient(create_app())

    preview = client.post(
        "/api/v1/imports/preview",
        files={"file": ("export.xml", SINGLE_RECORD_XML, "application/xml")},
    )

    assert preview.status_code == 201
    assert preview.json()["record_count"] == 1
    completed = client.post("/api/v1/imports", json={"ticket_id": preview.json()["ticket_id"]})
    assert completed.status_code == 200
    assert completed.json()["records_inserted"] == 1


def test_analytics_endpoints_are_bounded_and_use_the_local_import(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("apple_health_dashboard.api.routes.default_db_path", lambda: tmp_path / "health.duckdb")
    client = TestClient(create_app())
    preview = client.post(
        "/api/v1/imports/preview",
        files={"file": ("export.xml", SINGLE_RECORD_XML, "application/xml")},
    )
    client.post("/api/v1/imports", json={"ticket_id": preview.json()["ticket_id"]})

    types = client.get("/api/v1/analytics/types")
    series = client.get("/api/v1/analytics/metrics/HKQuantityTypeIdentifierStepCount/series")
    records = client.get("/api/v1/analytics/records?record_type=HKQuantityTypeIdentifierStepCount&limit=1")
    sleep = client.get("/api/v1/analytics/sleep")

    assert types.status_code == 200
    assert types.json()[0]["category"] == "Activity"
    assert series.json()["points"] == [{"date": "2024-01-01", "value": 42, "unit": "count", "sample_count": 1}]
    assert records.json()["total"] == 1
    assert records.json()["items"][0]["value"] == 42
    assert sleep.json() == {"average_hours": None, "night_count": 0, "nightly": [], "stages": []}
