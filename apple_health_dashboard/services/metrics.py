from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MetricSpec:
    record_type: str
    label: str
    category: str
    aggregation: str  # "sum" | "mean" | "last"
    unit_hint: str | None = None
    description: str | None = None


# Comprehensive curated set covering all major Apple Health data types.
# Everything else is still available under the Explorer page.
METRICS: list[MetricSpec] = [
    # ── Activity ────────────────────────────────────────────────────────────
    MetricSpec(
        record_type="HKQuantityTypeIdentifierStepCount",
        label="Steps",
        category="Activity",
        aggregation="sum",
        unit_hint="count",
        description="Total steps walked/run per day.",
    ),
    MetricSpec(
        record_type="HKQuantityTypeIdentifierDistanceWalkingRunning",
        label="Walking + Running Distance",
        category="Activity",
        aggregation="sum",
        unit_hint="km",
        description="Total walking and running distance per day.",
    ),
    MetricSpec(
        record_type="HKQuantityTypeIdentifierDistanceCycling",
        label="Cycling Distance",
        category="Activity",
        aggregation="sum",
        unit_hint="km",
        description="Total cycling distance per day.",
    ),
    MetricSpec(
        record_type="HKQuantityTypeIdentifierDistanceSwimming",
        label="Swimming Distance",
        category="Activity",
        aggregation="sum",
        unit_hint="m",
        description="Total swimming distance per day.",
    ),
    MetricSpec(
        record_type="HKQuantityTypeIdentifierActiveEnergyBurned",
        label="Active Energy",
        category="Activity",
        aggregation="sum",
        unit_hint="kcal",
        description="Active calories burned from movement and exercise.",
    ),
    MetricSpec(
        record_type="HKQuantityTypeIdentifierBasalEnergyBurned",
        label="Basal Energy",
        category="Activity",
        aggregation="sum",
        unit_hint="kcal",
        description="Resting metabolic rate (calories burned at rest).",
    ),
    MetricSpec(
        record_type="HKQuantityTypeIdentifierAppleStandTime",
        label="Stand Time",
        category="Activity",
        aggregation="sum",
        unit_hint="min",
        description="Minutes spent standing per day.",
    ),
    MetricSpec(
        record_type="HKQuantityTypeIdentifierAppleExerciseTime",
        label="Exercise Time",
        category="Activity",
        aggregation="sum",
        unit_hint="min",
        description="Minutes of brisk activity per day.",
    ),
    MetricSpec(
        record_type="HKQuantityTypeIdentifierFlightsClimbed",
        label="Flights Climbed",
        category="Activity",
        aggregation="sum",
        unit_hint="count",
        description="Number of flights of stairs climbed per day.",
    ),
    MetricSpec(
        record_type="HKQuantityTypeIdentifierWalkingSpeed",
        label="Walking Speed",
        category="Activity",
        aggregation="mean",
        unit_hint="km/h",
        description="Average walking speed.",
    ),
    MetricSpec(
        record_type="HKQuantityTypeIdentifierWalkingStepLength",
        label="Walking Step Length",
        category="Activity",
        aggregation="mean",
        unit_hint="cm",
        description="Average step length while walking.",
    ),
    MetricSpec(
        record_type="HKQuantityTypeIdentifierRunningSpeed",
        label="Running Speed",
        category="Activity",
        aggregation="mean",
        unit_hint="km/h",
        description="Average running speed.",
    ),
    MetricSpec(
        record_type="HKQuantityTypeIdentifierRunningPower",
        label="Running Power",
        category="Activity",
        aggregation="mean",
        unit_hint="W",
        description="Average running power output.",
    ),
    MetricSpec(
        record_type="HKQuantityTypeIdentifierRunningGroundContactTime",
        label="Ground Contact Time",
        category="Activity",
        aggregation="mean",
        unit_hint="ms",
        description="Average ground contact time while running.",
    ),
    MetricSpec(
        record_type="HKQuantityTypeIdentifierRunningStrideLength",
        label="Running Stride Length",
        category="Activity",
        aggregation="mean",
        unit_hint="m",
        description="Average running stride length.",
    ),
    MetricSpec(
        record_type="HKQuantityTypeIdentifierRunningVerticalOscillation",
        label="Vertical Oscillation",
        category="Activity",
        aggregation="mean",
        unit_hint="cm",
        description="Average vertical bounce while running.",
    ),
    # ── Heart ────────────────────────────────────────────────────────────────
    MetricSpec(
        record_type="HKQuantityTypeIdentifierHeartRate",
        label="Heart Rate",
        category="Heart",
        aggregation="mean",
        unit_hint="bpm",
        description="Instantaneous heart rate measurements.",
    ),
    MetricSpec(
        record_type="HKQuantityTypeIdentifierRestingHeartRate",
        label="Resting Heart Rate",
        category="Heart",
        aggregation="mean",
        unit_hint="bpm",
        description="Daily resting heart rate – a key cardiovascular fitness indicator.",
    ),
    MetricSpec(
        record_type="HKQuantityTypeIdentifierWalkingHeartRateAverage",
        label="Walking Heart Rate",
        category="Heart",
        aggregation="mean",
        unit_hint="bpm",
        description="Average heart rate during casual walking.",
    ),
    MetricSpec(
        record_type="HKQuantityTypeIdentifierHeartRateVariabilitySDNN",
        label="Heart Rate Variability (HRV)",
        category="Heart",
        aggregation="mean",
        unit_hint="ms",
        description="SDNN – higher values generally indicate better recovery and fitness.",
    ),
    MetricSpec(
        record_type="HKQuantityTypeIdentifierVO2Max",
        label="VO₂ Max",
        category="Heart",
        aggregation="last",
        unit_hint="mL/kg/min",
        description="Cardiorespiratory fitness estimate. Higher is better.",
    ),
    MetricSpec(
        record_type="HKQuantityTypeIdentifierBloodPressureSystolic",
        label="Blood Pressure (Systolic)",
        category="Heart",
        aggregation="mean",
        unit_hint="mmHg",
        description="Upper blood pressure number.",
    ),
    MetricSpec(
        record_type="HKQuantityTypeIdentifierBloodPressureDiastolic",
        label="Blood Pressure (Diastolic)",
        category="Heart",
        aggregation="mean",
        unit_hint="mmHg",
        description="Lower blood pressure number.",
    ),
    MetricSpec(
        record_type="HKQuantityTypeIdentifierOxygenSaturation",
        label="Blood Oxygen (SpO₂)",
        category="Heart",
        aggregation="mean",
        unit_hint="%",
        description="Blood oxygen saturation. Normal is 95–100%.",
    ),
    MetricSpec(
        record_type="HKQuantityTypeIdentifierHeartRateRecoveryOneMinute",
        label="HR Recovery (1 min)",
        category="Heart",
        aggregation="mean",
        unit_hint="bpm",
        description="Heart rate drop 1 minute after peak exercise.",
    ),
    MetricSpec(
        record_type="HKQuantityTypeIdentifierAtrialFibrillationBurden",
        label="AFib Burden",
        category="Heart",
        aggregation="mean",
        unit_hint="%",
        description="Percentage of time in atrial fibrillation.",
    ),
    # ── Body ─────────────────────────────────────────────────────────────────
    MetricSpec(
        record_type="HKQuantityTypeIdentifierBodyMass",
        label="Weight",
        category="Body",
        aggregation="last",
        unit_hint="kg",
        description="Body weight.",
    ),
    MetricSpec(
        record_type="HKQuantityTypeIdentifierBodyMassIndex",
        label="BMI",
        category="Body",
        aggregation="last",
        description="Body mass index.",
    ),
    MetricSpec(
        record_type="HKQuantityTypeIdentifierHeight",
        label="Height",
        category="Body",
        aggregation="last",
        unit_hint="cm",
        description="Height.",
    ),
    MetricSpec(
        record_type="HKQuantityTypeIdentifierBodyFatPercentage",
        label="Body Fat %",
        category="Body",
        aggregation="last",
        unit_hint="%",
        description="Body fat percentage.",
    ),
    MetricSpec(
        record_type="HKQuantityTypeIdentifierLeanBodyMass",
        label="Lean Body Mass",
        category="Body",
        aggregation="last",
        unit_hint="kg",
        description="Lean (fat-free) body mass.",
    ),
    MetricSpec(
        record_type="HKQuantityTypeIdentifierWaistCircumference",
        label="Waist Circumference",
        category="Body",
        aggregation="last",
        unit_hint="cm",
        description="Waist circumference.",
    ),
    # ── Sleep ─────────────────────────────────────────────────────────────────
    MetricSpec(
        record_type="HKCategoryTypeIdentifierSleepAnalysis",
        label="Sleep",
        category="Sleep",
        aggregation="sum",
        description="Sleep intervals with stage labels.",
    ),
    # ── Mindfulness ──────────────────────────────────────────────────────────
    MetricSpec(
        record_type="HKCategoryTypeIdentifierMindfulSession",
        label="Mindful Minutes",
        category="Mind",
        aggregation="sum",
        unit_hint="min",
        description="Mindfulness and meditation sessions.",
    ),
    # ── Nutrition ────────────────────────────────────────────────────────────
    MetricSpec(
        record_type="HKQuantityTypeIdentifierDietaryEnergyConsumed",
        label="Calories Consumed",
        category="Nutrition",
        aggregation="sum",
        unit_hint="kcal",
        description="Total dietary calories consumed per day.",
    ),
    MetricSpec(
        record_type="HKQuantityTypeIdentifierDietaryProtein",
        label="Protein",
        category="Nutrition",
        aggregation="sum",
        unit_hint="g",
        description="Dietary protein intake per day.",
    ),
    MetricSpec(
        record_type="HKQuantityTypeIdentifierDietaryCarbohydrates",
        label="Carbohydrates",
        category="Nutrition",
        aggregation="sum",
        unit_hint="g",
        description="Dietary carbohydrate intake per day.",
    ),
    MetricSpec(
        record_type="HKQuantityTypeIdentifierDietaryFatTotal",
        label="Fat",
        category="Nutrition",
        aggregation="sum",
        unit_hint="g",
        description="Dietary fat intake per day.",
    ),
    MetricSpec(
        record_type="HKQuantityTypeIdentifierDietaryFiber",
        label="Fiber",
        category="Nutrition",
        aggregation="sum",
        unit_hint="g",
        description="Dietary fiber intake per day.",
    ),
    MetricSpec(
        record_type="HKQuantityTypeIdentifierDietaryWater",
        label="Water",
        category="Nutrition",
        aggregation="sum",
        unit_hint="mL",
        description="Water intake per day.",
    ),
    MetricSpec(
        record_type="HKQuantityTypeIdentifierDietarySodium",
        label="Sodium",
        category="Nutrition",
        aggregation="sum",
        unit_hint="mg",
        description="Dietary sodium intake per day.",
    ),
    MetricSpec(
        record_type="HKQuantityTypeIdentifierDietaryCaffeine",
        label="Caffeine",
        category="Nutrition",
        aggregation="sum",
        unit_hint="mg",
        description="Caffeine intake per day.",
    ),
    # ── Respiratory ──────────────────────────────────────────────────────────
    MetricSpec(
        record_type="HKQuantityTypeIdentifierRespiratoryRate",
        label="Respiratory Rate",
        category="Respiratory",
        aggregation="mean",
        unit_hint="breaths/min",
        description="Breathing rate.",
    ),
    MetricSpec(
        record_type="HKQuantityTypeIdentifierForcedVitalCapacity",
        label="Forced Vital Capacity",
        category="Respiratory",
        aggregation="mean",
        unit_hint="L",
        description="Maximum breath volume.",
    ),
    MetricSpec(
        record_type="HKQuantityTypeIdentifierPeakExpiratoryFlowRate",
        label="Peak Flow",
        category="Respiratory",
        aggregation="mean",
        unit_hint="L/min",
        description="Peak expiratory flow rate.",
    ),
    # ── Other ─────────────────────────────────────────────────────────────────
    MetricSpec(
        record_type="HKQuantityTypeIdentifierBloodGlucose",
        label="Blood Glucose",
        category="Other",
        aggregation="mean",
        unit_hint="mg/dL",
        description="Blood glucose level.",
    ),
    MetricSpec(
        record_type="HKQuantityTypeIdentifierBodyTemperature",
        label="Body Temperature",
        category="Other",
        aggregation="mean",
        unit_hint="°C",
        description="Body temperature.",
    ),
    MetricSpec(
        record_type="HKQuantityTypeIdentifierUVExposure",
        label="UV Exposure",
        category="Other",
        aggregation="sum",
        unit_hint="count",
        description="UV index exposure.",
    ),
    MetricSpec(
        record_type="HKQuantityTypeIdentifierNumberOfTimesFallen",
        label="Falls",
        category="Other",
        aggregation="sum",
        unit_hint="count",
        description="Number of falls detected.",
    ),
    MetricSpec(
        record_type="HKQuantityTypeIdentifierHandwashingEvent",
        label="Handwashing Events",
        category="Other",
        aggregation="sum",
        unit_hint="count",
        description="Handwashing events detected.",
    ),
    MetricSpec(
        record_type="HKQuantityTypeIdentifierNikeFuel",
        label="Nike Fuel",
        category="Activity",
        aggregation="sum",
        description="Nike Fuel points.",
    ),
    # ── Mobility ─────────────────────────────────────────────────────────────
    MetricSpec(
        record_type="HKQuantityTypeIdentifierWalkingDoubleSupportPercentage",
        label="Double Support %",
        category="Mobility",
        aggregation="mean",
        unit_hint="%",
        description="Percentage of time both feet are on the ground while walking.",
    ),
    MetricSpec(
        record_type="HKQuantityTypeIdentifierWalkingAsymmetryPercentage",
        label="Walking Asymmetry %",
        category="Mobility",
        aggregation="mean",
        unit_hint="%",
        description="Percentage of time step cadence is asymmetrical.",
    ),
    MetricSpec(
        record_type="HKQuantityTypeIdentifierWalkingSteadiness",
        label="Walking Steadiness",
        category="Mobility",
        aggregation="last",
        unit_hint="%",
        description="A score of walking stability and fall risk.",
    ),
    MetricSpec(
        record_type="HKQuantityTypeIdentifierStairAscentSpeed",
        label="Stair Ascent Speed",
        category="Mobility",
        aggregation="mean",
        unit_hint="m/s",
        description="Speed of climbing stairs.",
    ),
    MetricSpec(
        record_type="HKQuantityTypeIdentifierStairDescentSpeed",
        label="Stair Descent Speed",
        category="Mobility",
        aggregation="mean",
        unit_hint="m/s",
        description="Speed of descending stairs.",
    ),
    # ── Symptoms ─────────────────────────────────────────────────────────────
    MetricSpec(
        record_type="HKCategoryTypeIdentifierHeadache",
        label="Headache",
        category="Symptoms",
        aggregation="sum",
        description="Presence and severity of headache.",
    ),
    MetricSpec(
        record_type="HKCategoryTypeIdentifierSoreThroat",
        label="Sore Throat",
        category="Symptoms",
        aggregation="sum",
        description="Presence of sore throat.",
    ),
    MetricSpec(
        record_type="HKCategoryTypeIdentifierCoughing",
        label="Coughing",
        category="Symptoms",
        aggregation="sum",
        description="Frequency or severity of coughing.",
    ),
    MetricSpec(
        record_type="HKCategoryTypeIdentifierFever",
        label="Fever",
        category="Symptoms",
        aggregation="sum",
        description="Presence of fever.",
    ),
    # ── Environmental ────────────────────────────────────────────────────────
    MetricSpec(
        record_type="HKQuantityTypeIdentifierEnvironmentalAudioExposure",
        label="Environmental Noise",
        category="Environment",
        aggregation="mean",
        unit_hint="dB",
        description="Exposure to environmental sound levels.",
    ),
]

# Build a fast lookup dict
_METRIC_BY_TYPE: dict[str, MetricSpec] = {m.record_type: m for m in METRICS}

# Category → emoji mapping for UI
CATEGORY_EMOJI: dict[str, str] = {
    "Activity": "🏃",
    "Heart": "❤️",
    "Body": "⚖️",
    "Sleep": "😴",
    "Mind": "🧘",
    "Nutrition": "🥗",
    "Respiratory": "🫁",
    "Mobility": "🚶",
    "Symptoms": "🤒",
    "Environment": "🌍",
    "Other": "🔬",
}


def metric_label(record_type: str) -> str:
    m = _METRIC_BY_TYPE.get(record_type)
    if m:
        return m.label
    # Fallback: keep it readable-ish
    if "Identifier" in record_type:
        return record_type.split("Identifier", 1)[-1]
    return record_type


def metric_category(record_type: str) -> str:
    m = _METRIC_BY_TYPE.get(record_type)
    return m.category if m else "Other"


def metric_aggregation(record_type: str) -> str:
    m = _METRIC_BY_TYPE.get(record_type)
    return m.aggregation if m else "sum"


def metric_unit_hint(record_type: str) -> str | None:
    m = _METRIC_BY_TYPE.get(record_type)
    return m.unit_hint if m else None


def metric_description(record_type: str) -> str | None:
    m = _METRIC_BY_TYPE.get(record_type)
    return m.description if m else None


def metrics_by_category() -> dict[str, list[MetricSpec]]:
    """Return metrics grouped by category, preserving order."""
    result: dict[str, list[MetricSpec]] = {}
    for m in METRICS:
        result.setdefault(m.category, []).append(m)
    return result
