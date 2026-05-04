from __future__ import annotations

import pandas as pd


def daily_streak(daily_df: pd.DataFrame, *, day_col: str = "day", threshold: float = 0.0) -> int:
    """Return the current consecutive-day streak for a metric.

    A day 'counts' if its value exceeds the threshold.
    The streak is counted backward from the most recent day in the data.

    Args:
        daily_df: DataFrame with at least a 'day' column and a value column.
        day_col: Column containing dates.
        threshold: Minimum value to count a day.

    Returns:
        Number of consecutive days at the end of the series.
    """
    if daily_df.empty or day_col not in daily_df.columns:
        return 0

    value_cols = [c for c in daily_df.columns if c != day_col]
    if not value_cols:
        return 0

    val_col = value_cols[0]
    df = daily_df[[day_col, val_col]].copy()
    df[day_col] = pd.to_datetime(df[day_col])
    df = df.sort_values(day_col)

    # Check if the last day is yesterday or today (allow one day gap for "today not yet complete")
    last_day = df[day_col].max()
    today = pd.Timestamp.now(tz=last_day.tzinfo).floor("D")
    if (today - last_day).days > 1:
        return 0  # Data is stale, no current streak

    streak = 0
    prev_day = None

    for _, row in df[::-1].iterrows():
        val = row[val_col]
        day = row[day_col]

        if pd.isna(val) or float(val) <= threshold:
            break

        if prev_day is not None and (prev_day - day).days > 1:
            break  # Gap in consecutive days

        streak += 1
        prev_day = day

    return streak


def longest_streak(daily_df: pd.DataFrame, *, day_col: str = "day", threshold: float = 0.0) -> int:
    """Return the longest consecutive-day streak over the entire history.

    Args:
        daily_df: DataFrame with at least a 'day' and value column.
        day_col: Column name for dates.
        threshold: Minimum value to count a day.

    Returns:
        Length of the longest streak.
    """
    if daily_df.empty or day_col not in daily_df.columns:
        return 0

    value_cols = [c for c in daily_df.columns if c != day_col]
    if not value_cols:
        return 0

    val_col = value_cols[0]
    df = daily_df[[day_col, val_col]].copy()
    df[day_col] = pd.to_datetime(df[day_col])
    df = df.sort_values(day_col)

    best = 0
    current = 0
    prev_day = None

    for _, row in df.iterrows():
        val = row[val_col]
        day = row[day_col]

        meets = not pd.isna(val) and float(val) > threshold
        consecutive = prev_day is None or (day - prev_day).days == 1

        if meets and consecutive:
            current += 1
        elif meets and not consecutive:
            current = 1
        else:
            current = 0

        best = max(best, current)
        prev_day = day

    return best


def personal_bests(daily_df: pd.DataFrame, *, day_col: str = "day") -> dict[str, object]:
    """Return personal bests from a daily aggregated DataFrame.

    Returns a dict with:
      - max_value: highest single-day value
      - max_day: date of that max
      - avg_value: overall average
      - total_days: number of data-points
    """
    if daily_df.empty or day_col not in daily_df.columns:
        return {}

    value_cols = [c for c in daily_df.columns if c != day_col]
    if not value_cols:
        return {}

    val_col = value_cols[0]
    df = daily_df[[day_col, val_col]].dropna(subset=[val_col])
    if df.empty:
        return {}

    idx = df[val_col].idxmax()
    return {
        "max_value": float(df[val_col].max()),
        "max_day": df.loc[idx, day_col],
        "avg_value": float(df[val_col].mean()),
        "total_days": len(df),
    }


def ring_streak(activity_df: pd.DataFrame) -> dict[str, int]:
    """Return current and longest ring-completion streaks.

    A day is 'closed' when all three rings meet their goal.
    activity_df must have columns: day, active_energy_burned_kcal, active_energy_burned_goal_kcal,
    apple_exercise_time_min, apple_exercise_time_goal_min, apple_stand_hours, apple_stand_hours_goal.

    Returns: {current_streak, longest_streak}
    """
    if activity_df.empty:
        return {"current_streak": 0, "longest_streak": 0}

    needed_cols = [
        "day",
        "active_energy_burned_kcal",
        "active_energy_burned_goal_kcal",
        "apple_exercise_time_min",
        "apple_exercise_time_goal_min",
        "apple_stand_hours",
        "apple_stand_hours_goal",
    ]
    if not all(c in activity_df.columns for c in needed_cols):
        return {"current_streak": 0, "longest_streak": 0}

    df = activity_df.copy()
    df["day"] = pd.to_datetime(df["day"])
    df = df.sort_values("day")

    # A ring is "closed" if actual >= goal (where goal > 0)
    def _closed(actual_col: str, goal_col: str) -> pd.Series:
        goal = df[goal_col].fillna(0)
        actual = df[actual_col].fillna(0)
        return (goal > 0) & (actual >= goal)

    df["all_rings"] = (
        _closed("active_energy_burned_kcal", "active_energy_burned_goal_kcal")
        & _closed("apple_exercise_time_min", "apple_exercise_time_goal_min")
        & _closed("apple_stand_hours", "apple_stand_hours_goal")
    )

    # Current streak (from end)
    current = 0
    prev_day = None
    for _, row in df[::-1].iterrows():
        if not row["all_rings"]:
            break
        day = row["day"]
        if prev_day is not None and (prev_day - day).days > 1:
            break
        current += 1
        prev_day = day

    # Longest streak
    best = 0
    running = 0
    prev_day = None
    for _, row in df.iterrows():
        day = row["day"]
        consecutive = prev_day is None or (day - prev_day).days == 1
        if row["all_rings"] and consecutive:
            running += 1
        elif row["all_rings"]:
            running = 1
        else:
            running = 0
        best = max(best, running)
        prev_day = day

    return {"current_streak": current, "longest_streak": best}
