from __future__ import annotations

from apple_health_dashboard.ingest.apple_health import _parse_apple_datetime


def test_parse_apple_datetime_has_tzinfo() -> None:
    dt = _parse_apple_datetime("2020-01-01 12:34:56 +0100")
    assert dt.tzinfo is not None
