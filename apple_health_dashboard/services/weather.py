import requests
import pandas as pd

def fetch_historical_weather(lat, lon, start_date, end_date):
    """
    Fetches historical weather from Open-Meteo.
    """
    url = f"https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}&start_date={start_date}&end_date={end_date}&daily=temperature_2m_max,precipitation_sum&timezone=auto"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            df = pd.DataFrame(data["daily"])
            df["time"] = pd.to_datetime(df["time"])
            return df
    except Exception:
        return pd.DataFrame()
    return pd.DataFrame()
