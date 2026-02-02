from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MetricSpec:
    record_type: str
    label: str
    category: str
    aggregation: str  # "sum" | "mean" | "last"
    unit_hint: str | None = None


# Minimal curated set. Everything else will still be available under "All types".
METRICS: list[MetricSpec] = [
    MetricSpec(
        record_type="HKQuantityTypeIdentifierStepCount",
        label="Steps",
        category="Activity",
        aggregation="sum",
        unit_hint="count",
    ),
    MetricSpec(
        record_type="HKQuantityTypeIdentifierActiveEnergyBurned",
        label="Active Energy",
        category="Activity",
        aggregation="sum",
        unit_hint="kcal",
    ),
    MetricSpec(
        record_type="HKQuantityTypeIdentifierDistanceWalkingRunning",
        label="Walking + Running Distance",
        category="Activity",
        aggregation="sum",
        unit_hint="km",
    ),
    MetricSpec(
        record_type="HKQuantityTypeIdentifierBasalEnergyBurned",
        label="Basal Energy",
        category="Activity",
        aggregation="sum",
        unit_hint="kcal",
    ),
    MetricSpec(
        record_type="HKQuantityTypeIdentifierHeartRate",
        label="Heart Rate",
        category="Heart",
        aggregation="mean",
        unit_hint="bpm",
    ),
    MetricSpec(
        record_type="HKQuantityTypeIdentifierRestingHeartRate",
        label="Resting Heart Rate",
        category="Heart",
        aggregation="mean",
        unit_hint="bpm",
    ),
    MetricSpec(
        record_type="HKQuantityTypeIdentifierWalkingHeartRateAverage",
        label="Walking HR Avg",
        category="Heart",
        aggregation="mean",
        unit_hint="bpm",
    ),
    MetricSpec(
        record_type="HKQuantityTypeIdentifierBodyMass",
        label="Weight",
        category="Body",
        aggregation="last",
        unit_hint="kg",
    ),
    MetricSpec(
        record_type="HKQuantityTypeIdentifierBodyMassIndex",
        label="BMI",
        category="Body",
        aggregation="last",
    ),
    MetricSpec(
        record_type="HKQuantityTypeIdentifierHeight",
        label="Height",
        category="Body",
        aggregation="last",
        unit_hint="cm",
    ),
    MetricSpec(
        record_type="HKQuantityTypeIdentifierAppleStandTime",
        label="Stand Time",
        category="Activity",
        aggregation="sum",
        unit_hint="min",
    ),
]


def metric_label(record_type: str) -> str:
    for m in METRICS:
        if m.record_type == record_type:
            return m.label
    # Fallback: keep it readable-ish
    if record_type.startswith("HK"):  # Apple identifiers
        return record_type.split("Identifier", 1)[-1]
    return record_type


def metric_category(record_type: str) -> str:
    for m in METRICS:
        if m.record_type == record_type:
            return m.category
    return "Other"


def metric_aggregation(record_type: str) -> str:
    for m in METRICS:
        if m.record_type == record_type:
            return m.aggregation
    return "sum"  # safe default for quantities


def metric_unit_hint(record_type: str) -> str | None:
    for m in METRICS:
        if m.record_type == record_type:
            return m.unit_hint
    return None
