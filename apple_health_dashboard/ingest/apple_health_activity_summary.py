from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from xml.etree.ElementTree import Element

from apple_health_dashboard.ingest.xml_stream import export_elements


def _to_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(float(value))
    except (ValueError, OverflowError):
        return None


def _parse_apple_date(value: str) -> date:
    # Apple uses YYYY-MM-DD
    return date.fromisoformat(value)


@dataclass(frozen=True)
class ActivitySummary:
    day: date
    active_energy_burned_kcal: int | None
    active_energy_burned_goal_kcal: int | None
    apple_exercise_time_min: int | None
    apple_exercise_time_goal_min: int | None
    apple_stand_hours: int | None
    apple_stand_hours_goal: int | None


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

    return ActivitySummary(
        day=_parse_apple_date(day),
        active_energy_burned_kcal=_to_int(attrib.get("activeEnergyBurned")),
        active_energy_burned_goal_kcal=_to_int(attrib.get("activeEnergyBurnedGoal")),
        apple_exercise_time_min=_to_int(attrib.get("appleExerciseTime")),
        apple_exercise_time_goal_min=_to_int(attrib.get("appleExerciseTimeGoal")),
        apple_stand_hours=_to_int(attrib.get("appleStandHours")),
        apple_stand_hours_goal=_to_int(attrib.get("appleStandHoursGoal")),
    )
