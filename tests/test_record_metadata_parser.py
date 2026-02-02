from __future__ import annotations

from pathlib import Path

from apple_health_dashboard.ingest.apple_health_records import iter_records_from_export_xml


def test_record_metadata_fixture(tmp_path: Path) -> None:
    xml = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<HealthData locale=\"en_US\">
  <Record type=\"HKQuantityTypeIdentifierStepCount\" sourceName=\"iPhone\"
          unit=\"count\" value=\"42\"
          startDate=\"2020-01-01 10:00:00 +0100\" endDate=\"2020-01-01 10:05:00 +0100\"
          creationDate=\"2020-01-01 10:06:00 +0100\">
    <MetadataEntry key=\"HKMetadataKeySyncIdentifier\" value=\"abc\"/>
  </Record>
</HealthData>
"""

    export_xml = tmp_path / "export.xml"
    export_xml.write_text(xml, encoding="utf-8")

    items = list(iter_records_from_export_xml(export_xml))
    assert len(items) == 1
    rec, meta = items[0]
    assert rec.record_type == "HKQuantityTypeIdentifierStepCount"
    assert len(meta) == 1
    assert meta[0].key == "HKMetadataKeySyncIdentifier"
    assert meta[0].value == "abc"
