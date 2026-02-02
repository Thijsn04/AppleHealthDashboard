from __future__ import annotations

import pandas as pd


def split_numeric_categorical(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split a record dataframe into numeric vs categorical/value_str.

    Apple Health exports contain both numeric values (e.g., steps) and categorical
    string values (e.g., sleep analysis states).
    """
    if df.empty:
        return df, df

    numeric_value = pd.to_numeric(df.get("value"), errors="coerce")
    numeric = df.copy()
    numeric["value_num"] = numeric_value
    numeric = numeric[numeric["value_num"].notna()].copy()

    categorical = df.copy()
    categorical = categorical[categorical.get("value_str").notna()].copy()

    # Also include rows where numeric couldn't be parsed but 'value' exists as a string.
    if "value" in df.columns:
        value_as_obj = df["value"].astype("string")
        categorical_extra = df[numeric_value.isna() & value_as_obj.notna()].copy()
        if not categorical_extra.empty:
            mask = numeric_value.isna() & value_as_obj.notna()
            categorical_extra["value_str"] = value_as_obj[mask]
            categorical = pd.concat([categorical, categorical_extra], ignore_index=True)

    categorical = categorical.drop_duplicates()
    return numeric, categorical


def top_value_counts(df: pd.DataFrame, *, limit: int = 25) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["value", "count"])

    s = df.get("value_str")
    if s is None:
        return pd.DataFrame(columns=["value", "count"])

    out = (
        s.astype("string")
        .fillna("(null)")
        .value_counts(dropna=False)
        .head(limit)
        .reset_index()
    )
    out.columns = ["value", "count"]
    return out
