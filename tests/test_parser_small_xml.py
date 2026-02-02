from __future__ import annotations

from pathlib import Path

from apple_health_dashboard.ingest.apple_health import iter_health_records_from_export_xml


def test_iterparse_small_fixture(tmp_path: Path) -> None:
    xml = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<HealthData locale=\"en_US\">
  <Record type=\"HKQuantityTypeIdentifierStepCount\" sourceName=\"iPhone\"
          unit=\"count\" value=\"42\"
          startDate=\"2020-01-01 10:00:00 +0100\" endDate=\"2020-01-01 10:05:00 +0100\"
          creationDate=\"2020-01-01 10:06:00 +0100\"/>
  <Record type=\"HKQuantityTypeIdentifierHeartRate\" sourceName=\"Watch\"
          unit=\"count/min\" value=\"60\"
          startDate=\"2020-01-01 10:00:00 +0100\" endDate=\"2020-01-01 10:00:05 +0100\"
          creationDate=\"2020-01-01 10:00:06 +0100\"/>
</HealthData>
"""

    export_xml = tmp_path / "export.xml"
    export_xml.write_text(xml, encoding="utf-8")

    records = list(iter_health_records_from_export_xml(export_xml))
    assert len(records) == 2
    assert records[0].type == "HKQuantityTypeIdentifierStepCount"
    assert records[0].value == 42.0
