from __future__ import annotations

from pathlib import Path

from apple_health_dashboard.ingest.apple_health_activity_summary import (
    iter_activity_summaries_from_export_xml,
)


def test_activity_summary_fixture(tmp_path: Path) -> None:
    xml = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<HealthData locale=\"en_US\">
  <ActivitySummary dateComponents=\"2020-01-01\"
                   activeEnergyBurned=\"500\" activeEnergyBurnedGoal=\"600\"
                   appleExerciseTime=\"30\" appleExerciseTimeGoal=\"40\"
                   appleStandHours=\"10\" appleStandHoursGoal=\"12\"/>
</HealthData>
"""

    export_xml = tmp_path / "export.xml"
    export_xml.write_text(xml, encoding="utf-8")

    rows = list(iter_activity_summaries_from_export_xml(export_xml))
    assert len(rows) == 1
    assert rows[0].day.isoformat() == "2020-01-01"
    assert rows[0].active_energy_burned_kcal == 500
