from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from xml.etree.ElementTree import Element

from apple_health_dashboard.ingest.apple_health_records import _to_float
from apple_health_dashboard.ingest.xml_stream import export_elements


@dataclass(frozen=True)
class ActivitySummary:
    day: date
    active_energy_burned_kcal: float | None
    active_energy_burned_goal_kcal: float | None
    apple_exercise_time_min: float | None
    apple_exercise_time_goal_min: float | None
    apple_stand_hours: float | None
    apple_stand_hours_goal: float | None


def iter_activity_summaries_from_export_xml(export_xml_path: Path) -> Iterator[ActivitySummary]:
    """Stream <ActivitySummary/> rows from an Apple Health export.xml."""

    for element in export_elements(export_xml_path):
        if element.tag == "ActivitySummary" and (parsed := parse_activity_summary(element)) is not None:
            yield parsed


def parse_activity_summary(elem: Element) -> ActivitySummary | None:
    attrib = elem.attrib
    day = attrib.get("dateComponents")
    if not day:
        return None

    energy_unit = attrib.get("activeEnergyBurnedUnit", "kcal")
    factor = {"kcal": 1, "kJ": 1 / 4.184, "J": 1 / 4184}.get(energy_unit)

    def energy(attribute: str) -> float | None:
        value = _to_float(attrib.get(attribute))
        return value * factor if value is not None and factor is not None else None

    return ActivitySummary(
        day=date.fromisoformat(day),
        active_energy_burned_kcal=energy("activeEnergyBurned"),
        active_energy_burned_goal_kcal=energy("activeEnergyBurnedGoal"),
        apple_exercise_time_min=_to_float(attrib.get("appleExerciseTime")),
        apple_exercise_time_goal_min=_to_float(attrib.get("appleExerciseTimeGoal")),
        apple_stand_hours=_to_float(attrib.get("appleStandHours")),
        apple_stand_hours_goal=_to_float(attrib.get("appleStandHoursGoal")),
    )
