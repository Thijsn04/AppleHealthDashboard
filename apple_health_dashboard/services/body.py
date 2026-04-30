from __future__ import annotations

import pandas as pd

WEIGHT_TYPE = "HKQuantityTypeIdentifierBodyMass"
BMI_TYPE = "HKQuantityTypeIdentifierBodyMassIndex"
HEIGHT_TYPE = "HKQuantityTypeIdentifierHeight"
BODY_FAT_TYPE = "HKQuantityTypeIdentifierBodyFatPercentage"
LEAN_MASS_TYPE = "HKQuantityTypeIdentifierLeanBodyMass"
WAIST_TYPE = "HKQuantityTypeIdentifierWaistCircumference"


def _filter_type(df: pd.DataFrame, record_type: str) -> pd.DataFrame:
    if df.empty or "type" not in df.columns:
        return pd.DataFrame()
    return df[df["type"] == record_type].copy()


def _daily_last(df: pd.DataFrame, col: str = "value") -> pd.DataFrame:
    """Return daily last-value series, sorted by day."""
    if df.empty or col not in df.columns or "start_at" not in df.columns:
        return pd.DataFrame(columns=["day", col])
    df = df[df[col].notna() & df["start_at"].notna()].copy()
    if df.empty:
        return pd.DataFrame(columns=["day", col])
    df["day"] = df["start_at"].dt.floor("D")
    out = df.sort_values("start_at").groupby("day")[col].last().reset_index()
    return out.sort_values("day")


def weight_trend(df: pd.DataFrame) -> pd.DataFrame:
    """Return daily last weight measurement.

    Returns columns: day, weight_kg
    Also normalizes lbs → kg if unit is 'lb'.
    """
    w = _filter_type(df, WEIGHT_TYPE)
    if w.empty:
        return pd.DataFrame(columns=["day", "weight_kg"])

    w = w[w["value"].notna() & w["start_at"].notna()].copy()
    if w.empty:
        return pd.DataFrame(columns=["day", "weight_kg"])

    # Normalize lbs to kg
    if "unit" in w.columns:
        lb_mask = w["unit"].str.lower().isin(["lb", "lbs"]) if w["unit"].notna().any() else None
        if lb_mask is not None and lb_mask.any():
            w.loc[lb_mask, "value"] = w.loc[lb_mask, "value"] * 0.453592

    w["day"] = w["start_at"].dt.floor("D")
    out = w.sort_values("start_at").groupby("day")["value"].last().reset_index()
    out = out.rename(columns={"value": "weight_kg"})
    return out.sort_values("day")


def bmi_trend(df: pd.DataFrame) -> pd.DataFrame:
    """Return daily last BMI measurement.

    Returns columns: day, bmi
    """
    bmi = _filter_type(df, BMI_TYPE)
    daily = _daily_last(bmi)
    if daily.empty:
        return pd.DataFrame(columns=["day", "bmi"])
    return daily.rename(columns={"value": "bmi"})


def body_fat_trend(df: pd.DataFrame) -> pd.DataFrame:
    """Return daily last body fat percentage.

    Returns columns: day, body_fat_pct
    """
    bf = _filter_type(df, BODY_FAT_TYPE)
    daily = _daily_last(bf)
    if daily.empty:
        return pd.DataFrame(columns=["day", "body_fat_pct"])
    out = daily.rename(columns={"value": "body_fat_pct"})
    # Normalize fraction → percentage
    if not out.empty and out["body_fat_pct"].max() <= 1.0:
        out["body_fat_pct"] = out["body_fat_pct"] * 100
    return out


def lean_mass_trend(df: pd.DataFrame) -> pd.DataFrame:
    """Return daily last lean body mass.

    Returns columns: day, lean_mass_kg
    """
    lm = _filter_type(df, LEAN_MASS_TYPE)
    daily = _daily_last(lm)
    if daily.empty:
        return pd.DataFrame(columns=["day", "lean_mass_kg"])
    return daily.rename(columns={"value": "lean_mass_kg"})


def bmi_category(bmi: float) -> str:
    """Return WHO BMI category."""
    if bmi < 18.5:
        return "Underweight"
    if bmi < 25.0:
        return "Normal weight"
    if bmi < 30.0:
        return "Overweight"
    return "Obese"


def body_summary_stats(df: pd.DataFrame) -> dict[str, float | str]:
    """Return headline body stats."""
    stats: dict[str, float | str] = {}

    w = weight_trend(df)
    if not w.empty:
        latest = float(w["weight_kg"].iloc[-1])
        first = float(w["weight_kg"].iloc[0])
        stats["latest_weight_kg"] = round(latest, 1)
        stats["weight_change_kg"] = round(latest - first, 1)

    bmi = bmi_trend(df)
    if not bmi.empty:
        latest_bmi = float(bmi["bmi"].iloc[-1])
        stats["latest_bmi"] = round(latest_bmi, 1)
        stats["bmi_category"] = bmi_category(latest_bmi)

    bf = body_fat_trend(df)
    if not bf.empty:
        stats["latest_body_fat_pct"] = round(float(bf["body_fat_pct"].iloc[-1]), 1)

    return stats
