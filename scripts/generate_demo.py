"""Generate deterministic, fictional Apple Health data for demos and benchmarks."""

import argparse
import math
from datetime import UTC, datetime, timedelta
from pathlib import Path
from xml.etree.ElementTree import Element, tostring

METRICS = (
    ("StepCount", "count", 6400, 2200),
    ("DistanceWalkingRunning", "km", 4.7, 1.6),
    ("ActiveEnergyBurned", "kcal", 415, 110),
    ("RestingHeartRate", "count/min", 62, 4),
    ("HeartRateVariabilitySDNN", "ms", 46, 8),
    ("BodyMass", "kg", 72, 1.1),
    ("DietaryWater", "mL", 1720, 420),
)


def stamp(instant: datetime) -> str:
    return instant.strftime("%Y-%m-%d %H:%M:%S %z")


def generate(path: Path, days: int, records: int | None = None) -> None:
    start = datetime(2025, 11, 1, 12, tzinfo=UTC) - timedelta(days=days)
    with path.open("wb") as output:
        output.write(b'<?xml version="1.0" encoding="UTF-8"?>\n<HealthData>\n')

        def emit(tag: str, attributes: dict[str, str]) -> None:
            output.write(tostring(Element(tag, attributes), encoding="utf-8") + b"\n")

        for i in range(records if records is not None else days * len(METRICS)):
            metric, unit, base, amplitude = METRICS[i % len(METRICS)]
            day, tick = divmod(i // len(METRICS), days)
            instant = start + timedelta(days=tick, seconds=day)
            value = base + amplitude * (0.65 * math.sin(tick / 2.8) + 0.25 * math.cos(tick * 1.62 + i % 7))
            emit("Record", {
                "type": f"HKQuantityTypeIdentifier{metric}", "unit": unit,
                "value": str(round(value) if unit == "count" else round(value, 2)),
                "sourceName": "Demo Watch", "device": "Synthetic sensor",
                "startDate": stamp(instant), "endDate": stamp(instant),
            })

        if records is None:
            for i in range(days):
                day = start + timedelta(days=i)
                if i % 13 != 0:
                    wake = day - timedelta(hours=5) + timedelta(minutes=round(36 * math.sin(i)))
                    start_sleep = wake - timedelta(hours=7, minutes=round(49 * math.sin(i / 2.8)))
                    duration = wake - start_sleep
                    for stage, fraction in (("Core", .55), ("Deep", .20), ("REM", .25)):
                        end_sleep = min(wake, start_sleep + duration * fraction)
                        emit("Record", {
                            "type": "HKCategoryTypeIdentifierSleepAnalysis",
                            "value": f"HKCategoryValueSleepAnalysisAsleep{stage}", "sourceName": "Demo Watch",
                            "startDate": stamp(start_sleep), "endDate": stamp(end_sleep),
                        })
                        start_sleep = end_sleep
                if i % 3 == 0:
                    emit("Workout", {
                        "workoutActivityType": "HKWorkoutActivityTypeRunning" if i % 2 else "HKWorkoutActivityTypeCycling",
                        "startDate": stamp(day), "endDate": stamp(day + timedelta(minutes=36)),
                        "sourceName": "Demo Watch", "duration": "36", "durationUnit": "min",
                        "totalDistance": "5.4", "totalDistanceUnit": "km", "totalEnergyBurned": "290",
                        "totalEnergyBurnedUnit": "kcal",
                    })
                emit("ActivitySummary", {
                    "dateComponents": day.date().isoformat(), "activeEnergyBurned": str(390 + i % 20 * 5),
                    "activeEnergyBurnedGoal": "430", "appleExerciseTime": "34",
                    "appleExerciseTimeGoal": "30", "appleStandHours": "10", "appleStandHoursGoal": "12",
                })

        output.write(b"</HealthData>\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--days", type=int, default=84)
    parser.add_argument("--records", type=int)
    args = parser.parse_args()
    if args.days < 1 or (args.records is not None and args.records < 1):
        parser.error("Days and record count must be positive.")
    generate(args.output, args.days, args.records)
