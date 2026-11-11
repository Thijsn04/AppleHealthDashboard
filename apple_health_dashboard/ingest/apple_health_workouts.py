from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from xml.etree.ElementTree import Element

from apple_health_dashboard.ingest.apple_health_records import _parse_apple_datetime, _to_float
from apple_health_dashboard.ingest.xml_stream import export_elements


@dataclass(frozen=True)
class Workout:
    """Normalized representation of an Apple Health <Workout/>."""

    workout_activity_type: str
    start_at: datetime
    end_at: datetime
    creation_at: datetime | None
    source_name: str | None
    device: str | None
    duration_s: float | None
    total_energy_kcal: float | None
    total_distance_m: float | None
    duration_unit: str | None = None
    energy_unit: str | None = None
    distance_unit: str | None = None
    units_known: bool = False
    statistics: tuple[tuple[str, str, str], ...] = ()


@dataclass(frozen=True)
class WorkoutMetadata:
    workout_hash: str
    key: str
    value: str


def stable_workout_hash(workout: Workout) -> str:
    import hashlib

    payload = (
        workout.workout_activity_type,
        workout.start_at.isoformat(),
        workout.end_at.isoformat(),
        workout.creation_at.isoformat() if workout.creation_at else "",
        workout.source_name or "",
        workout.device or "",
        "" if workout.duration_s is None else repr(workout.duration_s),
        "" if workout.total_energy_kcal is None else repr(workout.total_energy_kcal),
        "" if workout.total_distance_m is None else repr(workout.total_distance_m),
    )
    return hashlib.sha256("|".join(payload).encode("utf-8")).hexdigest()


def iter_workouts_from_export_xml(
    export_xml_path: Path,
) -> Iterator[tuple[Workout, list[WorkoutMetadata]]]:
    """Stream workouts (and their metadata) from an Apple Health export.xml."""

    for element in export_elements(export_xml_path):
        if element.tag == "Workout" and (parsed := parse_workouts(element)) is not None:
            yield parsed


def parse_workouts(elem: Element) -> tuple[Workout, list[WorkoutMetadata]] | None:
    attrib = elem.attrib
    workout_type = attrib.get("workoutActivityType")
    start = attrib.get("startDate")
    end = attrib.get("endDate")

    if not workout_type or not start or not end:
        return None

    workout = Workout(
        workout_activity_type=workout_type,
        start_at=_parse_apple_datetime(start),
        end_at=_parse_apple_datetime(end),
        creation_at=_parse_apple_datetime(attrib.get("creationDate"))
        if attrib.get("creationDate")
        else None,
        source_name=attrib.get("sourceName"),
        device=attrib.get("device"),
        duration_s=_to_float(attrib.get("duration")),
        total_energy_kcal=_to_float(attrib.get("totalEnergyBurned")),
        total_distance_m=_to_float(attrib.get("totalDistance")),
        duration_unit=attrib.get("durationUnit"),
        energy_unit=attrib.get("totalEnergyBurnedUnit"),
        distance_unit=attrib.get("totalDistanceUnit"),
        units_known=True,
        statistics=tuple(
            (child.get("type", ""), child.get("unit", ""), child.get(field, ""))
            for child in elem.findall("WorkoutStatistics")
            for field in ["average" if child.get("type") == "HKQuantityTypeIdentifierHeartRate" else "sum"]
        ),
    )

    w_hash = stable_workout_hash(workout)

    metadata: list[WorkoutMetadata] = []
    for child in list(elem):
        if child.tag != "MetadataEntry":
            continue
        key = child.attrib.get("key")
        value = child.attrib.get("value")
        if key is None or value is None:
            continue
        metadata.append(WorkoutMetadata(workout_hash=w_hash, key=key, value=value))

    return workout, metadata
