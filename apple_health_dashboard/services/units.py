from __future__ import annotations

import pandas as pd


def normalize_units(df: pd.DataFrame, *, record_type: str) -> pd.DataFrame:
    """Normalize common units for nicer display.

    This is intentionally conservative: only convert when we're confident.
    """
    if df.empty or "value" not in df.columns:
        return df

    out = df.copy()

    # Distance: m -> km
    if record_type in {"HKQuantityTypeIdentifierDistanceWalkingRunning"}:
        if "unit" in out.columns:
            unit = out["unit"].dropna().unique().tolist()
            if len(unit) == 1 and unit[0] in {"m"}:
                out["value"] = pd.to_numeric(out["value"], errors="coerce") / 1000.0
                out["unit"] = "km"

    # Height: m -> cm
    if record_type in {"HKQuantityTypeIdentifierHeight"}:
        if "unit" in out.columns:
            unit = out["unit"].dropna().unique().tolist()
            if len(unit) == 1 and unit[0] in {"m"}:
                out["value"] = pd.to_numeric(out["value"], errors="coerce") * 100.0
                out["unit"] = "cm"

    return out


# Values are (source unit, scale, offset) for each canonical display unit.
UNIT_CONVERSIONS = {
    "km": [("m", .001, 0), ("mi", 1.609344, 0)],
    "m": [("km", 1000, 0), ("cm", .01, 0), ("ft", .3048, 0)],
    "cm": [("m", 100, 0), ("in", 2.54, 0)],
    "kg": [("g", .001, 0), ("lb", .45359237, 0)],
    "g": [("mg", .001, 0), ("kg", 1000, 0)],
    "mg": [("g", 1000, 0), ("mcg", .001, 0), ("µg", .001, 0)],
    "mL": [("L", 1000, 0)],
    "L": [("mL", .001, 0)],
    "ms": [("s", 1000, 0)],
    "min": [("s", 1 / 60, 0), ("hr", 60, 0), ("h", 60, 0)],
    "bpm": [("count/min", 1, 0)],
    "breaths/min": [("count/min", 1, 0)],
    "kcal": [("kJ", 1 / 4.184, 0), ("J", 1 / 4184, 0)],
    "km/h": [("km/hr", 1, 0), ("m/s", 3.6, 0), ("mi/hr", 1.609344, 0)],
    "m/s": [("km/hr", 1 / 3.6, 0), ("km/h", 1 / 3.6, 0)],
    "mL/kg/min": [("ml/kg*min", 1, 0), ("mL/kg*min", 1, 0)],
    "°C": [("degC", 1, 0), ("degF", 5 / 9, -32 * 5 / 9), ("°F", 5 / 9, -32 * 5 / 9)],
    "dB": [("dBASPL", 1, 0)],
}
