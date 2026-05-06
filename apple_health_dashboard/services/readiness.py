from __future__ import annotations

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def calculate_readiness_score(
    df_records: pd.DataFrame, 
    df_sleep: pd.DataFrame, 
    df_activity: pd.DataFrame
) -> dict:
    """
    Calculates a Readiness Score (0-100) based on HRV, Sleep, RHR, and Activity patterns.
    """
    if df_records.empty:
        return {"score": None, "components": {}}

    # 1. HRV Component (Weight: 35%)
    # Heart Rate Variability (SDNN)
    hrv_type = "HKQuantityTypeIdentifierHeartRateVariabilitySDNN"
    hrv_data = df_records[df_records["type"] == hrv_type].copy()
    hrv_score = 50 # Default middle
    hrv_val = None
    
    if not hrv_data.empty:
        hrv_data["day"] = pd.to_datetime(hrv_data["start_at"]).dt.date
        daily_hrv = hrv_data.groupby("day")["value"].mean().reset_index()
        if len(daily_hrv) >= 1:
            latest_hrv = daily_hrv["value"].iloc[-1]
            hrv_val = latest_hrv
            if len(daily_hrv) >= 7:
                avg_hrv_7d = daily_hrv["value"].tail(7).mean()
                std_hrv_7d = daily_hrv["value"].tail(7).std() or 1.0
                # Z-score based scoring (clamped)
                z = (latest_hrv - avg_hrv_7d) / std_hrv_7d
                hrv_score = np.clip(50 + (z * 15), 0, 100)
            else:
                # Fallback to absolute scale if not enough history
                hrv_score = np.clip((latest_hrv / 70.0) * 100, 0, 100)

    # 2. Sleep Component (Weight: 35%)
    sleep_score = 50
    sleep_hours = None
    if not df_sleep.empty:
        # Assuming df_sleep has 'day' and 'hours'
        latest_sleep = df_sleep.sort_values("day").iloc[-1]
        sleep_hours = latest_sleep["hours"]
        # Score based on 8 hour target
        duration_score = np.clip((sleep_hours / 8.0) * 100, 0, 100)
        # Add bonus for deep/rem if available (simplified here)
        sleep_score = duration_score

    # 3. Resting HR Component (Weight: 20%)
    rhr_type = "HKQuantityTypeIdentifierRestingHeartRate"
    rhr_data = df_records[df_records["type"] == rhr_type].copy()
    rhr_score = 50
    rhr_val = None
    if not rhr_data.empty:
        rhr_data["day"] = pd.to_datetime(rhr_data["start_at"]).dt.date
        daily_rhr = rhr_data.groupby("day")["value"].mean().reset_index()
        if len(daily_rhr) >= 1:
            latest_rhr = daily_rhr["value"].iloc[-1]
            rhr_val = latest_rhr
            if len(daily_rhr) >= 7:
                avg_rhr_7d = daily_rhr["value"].tail(7).mean()
                # Lower RHR is usually better for readiness
                diff = avg_rhr_7d - latest_rhr
                rhr_score = np.clip(50 + (diff * 5), 0, 100)
            else:
                # Absolute scale (target ~60)
                rhr_score = np.clip(100 - (abs(latest_rhr - 60) * 2), 0, 100)

    # 4. Activity Balance Component (Weight: 10%)
    # Acute:Chronic Workload Ratio (ACWR)
    activity_score = 50
    acwr = None
    if not df_activity.empty and "active_energy_burned_kcal" in df_activity.columns:
        df_act = df_activity.sort_values("day")
        if len(df_act) >= 28:
            acute = df_act["active_energy_burned_kcal"].tail(7).mean()
            chronic = df_act["active_energy_burned_kcal"].tail(28).mean() or 1.0
            acwr = acute / chronic
            # Ideal ACWR is between 0.8 and 1.3
            if 0.8 <= acwr <= 1.3:
                activity_score = 100
            else:
                dist = min(abs(acwr - 0.8), abs(acwr - 1.3))
                activity_score = np.clip(100 - (dist * 100), 0, 100)

    # Final weighted score
    final_score = (
        (hrv_score * 0.35) + 
        (sleep_score * 0.35) + 
        (rhr_score * 0.20) + 
        (activity_score * 0.10)
    )

    return {
        "score": int(final_score),
        "label": _get_readiness_label(final_score),
        "hrv": hrv_val,
        "sleep_hours": sleep_hours,
        "rhr": rhr_val,
        "acwr": acwr,
        "components": {
            "hrv_score": int(hrv_score),
            "sleep_score": int(sleep_score),
            "rhr_score": int(rhr_score),
            "activity_score": int(activity_score)
        }
    }

def _get_readiness_label(score: float) -> str:
    if score >= 85: return "Optimal"
    if score >= 70: return "Good"
    if score >= 50: return "Fair"
    return "Pay Attention"
