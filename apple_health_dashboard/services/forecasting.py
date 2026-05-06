from __future__ import annotations

import pandas as pd
import numpy as np
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from datetime import timedelta

def forecast_metric(
    df: pd.DataFrame, 
    date_col: str, 
    value_col: str, 
    days_to_forecast: int = 30
) -> pd.DataFrame:
    """
    Forecasts a metric using Holt-Winters Exponential Smoothing.
    Returns a DataFrame with original data + forecast.
    """
    if df.empty or len(df) < 5:
        return pd.DataFrame()

    # Prepare data
    df_ts = df[[date_col, value_col]].copy()
    df_ts[date_col] = pd.to_datetime(df_ts[date_col])
    df_ts = df_ts.sort_values(date_col).set_index(date_col)
    
    # Resample to daily to fill gaps
    df_ts = df_ts.resample("D").mean().ffill()

    try:
        # Simple Holt model (linear trend)
        model = ExponentialSmoothing(
            df_ts[value_col], 
            trend="add", 
            seasonal=None, 
            initialization_method="estimated"
        ).fit()
        
        forecast = model.forecast(days_to_forecast)
        
        # Create forecast dataframe
        last_date = df_ts.index[-1]
        forecast_dates = [last_date + timedelta(days=i) for i in range(1, days_to_forecast + 1)]
        
        df_forecast = pd.DataFrame({
            "day": forecast_dates,
            "value": forecast.values,
            "is_forecast": True
        })
        
        # Original data
        df_orig = df_ts.reset_index().rename(columns={date_col: "day", value_col: "value"})
        df_orig["is_forecast"] = False
        
        return pd.concat([df_orig, df_forecast], ignore_index=True)
    except Exception:
        # Fallback to simple linear regression if Holt-Winters fails
        from sklearn.linear_model import LinearRegression
        
        X = np.arange(len(df_ts)).reshape(-1, 1)
        y = df_ts[value_col].values
        reg = LinearRegression().fit(X, y)
        
        last_date = df_ts.index[-1]
        forecast_dates = [last_date + timedelta(days=i) for i in range(1, days_to_forecast + 1)]
        X_pred = np.arange(len(df_ts), len(df_ts) + days_to_forecast).reshape(-1, 1)
        y_pred = reg.predict(X_pred)
        
        df_forecast = pd.DataFrame({
            "day": forecast_dates,
            "value": y_pred,
            "is_forecast": True
        })
        
        df_orig = df_ts.reset_index().rename(columns={date_col: "day", value_col: "value"})
        df_orig["is_forecast"] = False
        
        return pd.concat([df_orig, df_forecast], ignore_index=True)

def predict_goal_date(
    df: pd.DataFrame, 
    date_col: str, 
    value_col: str, 
    target_value: float
) -> datetime | None:
    """
    Predicts the date when a target value will be reached based on current trend.
    """
    if df.empty or len(df) < 5:
        return None

    df_ts = df[[date_col, value_col]].copy()
    df_ts[date_col] = pd.to_datetime(df_ts[date_col])
    df_ts = df_ts.sort_values(date_col)
    
    # Linear trend
    from sklearn.linear_model import LinearRegression
    X = np.array([(d - df_ts[date_col].min()).days for d in df_ts[date_col]]).reshape(-1, 1)
    y = df_ts[value_col].values
    
    model = LinearRegression().fit(X, y)
    slope = model.coef_[0]
    intercept = model.intercept_
    
    if abs(slope) < 1e-6:
        return None # No trend
        
    # target = slope * days + intercept => days = (target - intercept) / slope
    days_from_start = (target_value - intercept) / slope
    if days_from_start < X[-1][0]:
        return None # Already past or moving away from goal
        
    predicted_date = df_ts[date_col].min() + timedelta(days=float(days_from_start))
    
    # Don't predict more than 2 years out
    if predicted_date > datetime.now() + timedelta(days=730):
        return None
        
    return predicted_date
