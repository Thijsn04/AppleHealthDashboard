from __future__ import annotations

from collections.abc import Iterable

import pandas as pd


def activity_summaries_to_dataframe(rows: Iterable[dict]) -> pd.DataFrame:
    df = pd.DataFrame(list(rows))
    if df.empty:
        return pd.DataFrame(
            columns=[
                "day",
                "active_energy_burned_kcal",
                "active_energy_burned_goal_kcal",
                "apple_exercise_time_min",
                "apple_exercise_time_goal_min",
                "apple_stand_hours",
                "apple_stand_hours_goal",
            ]
        )

    df["day"] = pd.to_datetime(df["day"], errors="coerce")
    df = df.sort_values("day")
    return df
