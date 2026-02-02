from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


def _parse_apple_datetime(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S %z")


def _to_float(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


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

    context = ET.iterparse(export_xml_path, events=("end",))
    for _event, elem in context:
        if elem.tag != "Workout":
            continue

        attrib = elem.attrib
        workout_type = attrib.get("workoutActivityType")
        start = attrib.get("startDate")
        end = attrib.get("endDate")

        if not workout_type or not start or not end:
            elem.clear()
            continue

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

        yield workout, metadata
        elem.clear()
