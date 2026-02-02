from __future__ import annotations

import pandas as pd

from apple_health_dashboard.services.stats import summarize_by_day_agg


def test_summarize_by_day_agg_missing_value_column() -> None:
    df = pd.DataFrame({"start_at": [pd.Timestamp("2020-01-01", tz="UTC")]})
    out = summarize_by_day_agg(df, agg="sum")
    assert list(out.columns) == ["day", "value", "count"]
    assert out.empty


def test_summarize_by_day_agg_value_as_dataframe_is_handled() -> None:
    df = pd.DataFrame(
        {
            "start_at": [pd.Timestamp("2020-01-01", tz="UTC")],
            "value": [1.0],
        }
    )

    # Force a weird shape that would normally break pd.to_numeric.
    df["value"] = pd.DataFrame({"v": ["1"]})

    out = summarize_by_day_agg(df, agg="sum")
    assert not out.empty
    assert out.iloc[0]["value"] == 1.0
