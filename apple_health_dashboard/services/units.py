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
