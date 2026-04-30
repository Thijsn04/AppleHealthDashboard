from __future__ import annotations

import pandas as pd

# Heart rate zone thresholds as fractions of max HR (220 - age)
HR_ZONES = {
    "Zone 1 – Recovery": (0.50, 0.60),
    "Zone 2 – Aerobic Base": (0.60, 0.70),
    "Zone 3 – Aerobic": (0.70, 0.80),
    "Zone 4 – Threshold": (0.80, 0.90),
    "Zone 5 – VO₂ Max": (0.90, 1.00),
}

# VO₂ max classification for males/females by age group (mL/kg/min)
# Source: American College of Sports Medicine
VO2MAX_CLASSIFICATIONS = {
    "Very Poor": (0, 28),
    "Poor": (28, 34),
    "Fair": (34, 42),
    "Good": (42, 50),
    "Excellent": (50, 60),
    "Superior": (60, 999),
}

HEART_RATE_TYPE = "HKQuantityTypeIdentifierHeartRate"
RESTING_HR_TYPE = "HKQuantityTypeIdentifierRestingHeartRate"
WALKING_HR_TYPE = "HKQuantityTypeIdentifierWalkingHeartRateAverage"
HRV_TYPE = "HKQuantityTypeIdentifierHeartRateVariabilitySDNN"
VO2MAX_TYPE = "HKQuantityTypeIdentifierVO2Max"
SYSTOLIC_TYPE = "HKQuantityTypeIdentifierBloodPressureSystolic"
DIASTOLIC_TYPE = "HKQuantityTypeIdentifierBloodPressureDiastolic"
SPO2_TYPE = "HKQuantityTypeIdentifierOxygenSaturation"
HR_RECOVERY_TYPE = "HKQuantityTypeIdentifierHeartRateRecoveryOneMinute"


def filter_type(df: pd.DataFrame, record_type: str) -> pd.DataFrame:
    if df.empty or "type" not in df.columns:
        return pd.DataFrame()
    return df[df["type"] == record_type].copy()


def hr_daily_stats(df: pd.DataFrame) -> pd.DataFrame:
    """Compute daily min/mean/max heart rate.

    Returns columns: day, hr_min, hr_mean, hr_max, count
    """
    hr = filter_type(df, HEART_RATE_TYPE)
    if hr.empty or "value" not in hr.columns:
        return pd.DataFrame(columns=["day", "hr_min", "hr_mean", "hr_max", "count"])

    hr = hr[hr["value"].notna() & hr["start_at"].notna()].copy()
    hr["day"] = hr["start_at"].dt.floor("D")

    out = (
        hr.groupby("day")["value"]
        .agg(hr_min="min", hr_mean="mean", hr_max="max", count="count")
        .reset_index()
        .sort_values("day")
    )
    return out


def resting_hr_trend(df: pd.DataFrame) -> pd.DataFrame:
    """Return daily resting HR. Falls back to daily mean HR if no dedicated records.

    Returns columns: day, value
    """
    rhr = filter_type(df, RESTING_HR_TYPE)
    if not rhr.empty and "value" in rhr.columns:
        rhr = rhr[rhr["value"].notna() & rhr["start_at"].notna()].copy()
        rhr["day"] = rhr["start_at"].dt.floor("D")
        out = rhr.groupby("day")["value"].mean().reset_index().rename(columns={"value": "rhr"})
        return out.sort_values("day")

    # fallback to mean HR
    stats = hr_daily_stats(df)
    if stats.empty:
        return pd.DataFrame(columns=["day", "rhr"])
    return stats[["day", "hr_mean"]].rename(columns={"hr_mean": "rhr"})


def hrv_trend(df: pd.DataFrame) -> pd.DataFrame:
    """Return daily HRV (SDNN) averages.

    Returns columns: day, hrv
    """
    hrv = filter_type(df, HRV_TYPE)
    if hrv.empty or "value" not in hrv.columns:
        return pd.DataFrame(columns=["day", "hrv"])

    hrv = hrv[hrv["value"].notna() & hrv["start_at"].notna()].copy()
    hrv["day"] = hrv["start_at"].dt.floor("D")

    out = hrv.groupby("day")["value"].mean().reset_index().rename(columns={"value": "hrv"})
    return out.sort_values("day")


def vo2max_trend(df: pd.DataFrame) -> pd.DataFrame:
    """Return VO₂ max estimates over time.

    Returns columns: day, vo2max
    """
    vo2 = filter_type(df, VO2MAX_TYPE)
    if vo2.empty or "value" not in vo2.columns:
        return pd.DataFrame(columns=["day", "vo2max"])

    vo2 = vo2[vo2["value"].notna() & vo2["start_at"].notna()].copy()
    vo2["day"] = vo2["start_at"].dt.floor("D")

    out = vo2.groupby("day")["value"].last().reset_index().rename(columns={"value": "vo2max"})
    return out.sort_values("day")


def classify_vo2max(value: float) -> str:
    """Return a fitness classification label for a VO₂ max value."""
    for label, (lo, hi) in VO2MAX_CLASSIFICATIONS.items():
        if lo <= value < hi:
            return label
    return "Unknown"


def blood_pressure_trend(df: pd.DataFrame) -> pd.DataFrame:
    """Return daily mean systolic and diastolic blood pressure.

    Returns columns: day, systolic, diastolic
    """
    sys = filter_type(df, SYSTOLIC_TYPE)
    dia = filter_type(df, DIASTOLIC_TYPE)

    results = []

    for bp_df, col in [(sys, "systolic"), (dia, "diastolic")]:
        if bp_df.empty or "value" not in bp_df.columns:
            continue
        bp_df = bp_df[bp_df["value"].notna() & bp_df["start_at"].notna()].copy()
        bp_df["day"] = bp_df["start_at"].dt.floor("D")
        daily = bp_df.groupby("day")["value"].mean().reset_index().rename(columns={"value": col})
        results.append(daily)

    if not results:
        return pd.DataFrame(columns=["day", "systolic", "diastolic"])

    if len(results) == 1:
        return results[0].sort_values("day")

    merged = results[0].merge(results[1], on="day", how="outer").sort_values("day")
    return merged


def spo2_trend(df: pd.DataFrame) -> pd.DataFrame:
    """Return daily mean blood oxygen saturation.

    Returns columns: day, spo2
    """
    spo2 = filter_type(df, SPO2_TYPE)
    if spo2.empty or "value" not in spo2.columns:
        return pd.DataFrame(columns=["day", "spo2"])

    spo2 = spo2[spo2["value"].notna() & spo2["start_at"].notna()].copy()
    spo2["day"] = spo2["start_at"].dt.floor("D")

    out = spo2.groupby("day")["value"].mean().reset_index().rename(columns={"value": "spo2"})
    # Convert fraction to percentage if stored as 0-1
    if not out.empty and out["spo2"].max() <= 1.0:
        out["spo2"] = out["spo2"] * 100
    return out.sort_values("day")


def hr_zone_distribution(df: pd.DataFrame, *, max_hr: int = 185) -> pd.DataFrame:
    """Compute time (minutes) spent in each heart rate zone.

    Uses record duration as time weight. Falls back to count if duration is tiny.

    Returns columns: zone, minutes, pct
    """
    hr = filter_type(df, HEART_RATE_TYPE)
    if hr.empty or "value" not in hr.columns:
        return pd.DataFrame(columns=["zone", "minutes", "pct"])

    hr = hr[hr["value"].notna() & hr["start_at"].notna() & hr["end_at"].notna()].copy()
    if hr.empty:
        return pd.DataFrame(columns=["zone", "minutes", "pct"])

    hr["duration_min"] = (hr["end_at"] - hr["start_at"]).dt.total_seconds() / 60.0
    hr["duration_min"] = hr["duration_min"].clip(lower=0, upper=30)  # cap unrealistic durations

    zone_rows = []
    for zone_name, (lo_frac, hi_frac) in HR_ZONES.items():
        lo_bpm = max_hr * lo_frac
        hi_bpm = max_hr * hi_frac
        mask = (hr["value"] >= lo_bpm) & (hr["value"] < hi_bpm)
        minutes = float(hr.loc[mask, "duration_min"].sum())
        zone_rows.append({"zone": zone_name, "minutes": minutes})

    out = pd.DataFrame(zone_rows)
    total = out["minutes"].sum()
    out["pct"] = (out["minutes"] / total * 100).round(1) if total > 0 else 0.0
    return out


def heart_summary_stats(df: pd.DataFrame) -> dict[str, float | str]:
    """Return a dict of headline heart stats for the overview page."""
    stats: dict[str, float | str] = {}

    rhr = filter_type(df, RESTING_HR_TYPE)
    if not rhr.empty and "value" in rhr.columns:
        v = rhr["value"].dropna()
        if not v.empty:
            stats["avg_resting_hr"] = round(float(v.mean()), 1)
            stats["latest_resting_hr"] = round(float(v.iloc[-1]), 1)

    hrv = filter_type(df, HRV_TYPE)
    if not hrv.empty and "value" in hrv.columns:
        v = hrv["value"].dropna()
        if not v.empty:
            stats["avg_hrv"] = round(float(v.mean()), 1)
            stats["latest_hrv"] = round(float(v.iloc[-1]), 1)

    vo2 = filter_type(df, VO2MAX_TYPE)
    if not vo2.empty and "value" in vo2.columns:
        v = vo2["value"].dropna()
        if not v.empty:
            latest = float(v.iloc[-1])
            stats["latest_vo2max"] = round(latest, 1)
            stats["vo2max_classification"] = classify_vo2max(latest)

    return stats
