from __future__ import annotations

import pandas as pd
from pathlib import Path

NOTES_FILE = Path("health_notes.csv")

def load_notes() -> pd.DataFrame:
    if not NOTES_FILE.exists():
        return pd.DataFrame(columns=["date", "note", "metric_context"])
    try:
        df = pd.read_csv(NOTES_FILE)
        df["date"] = pd.to_datetime(df["date"])
        return df
    except Exception:
        return pd.DataFrame(columns=["date", "note", "metric_context"])

def save_note(date, note, metric_context="General"):
    df = load_notes()
    new_note = pd.DataFrame({"date": [pd.to_datetime(date)], "note": [note], "metric_context": [metric_context]})
    df = pd.concat([df, new_note], ignore_index=True)
    df.to_csv(NOTES_FILE, index=False)

def get_notes_for_chart(metric_context=None):
    df = load_notes()
    if metric_context:
        return df[df["metric_context"] == metric_context]
    return df
