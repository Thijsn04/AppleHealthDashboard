# Apple Health Dashboard
- Add timezone-aware filtering and weekly/monthly rollups.
- Add more metrics and correlation insights.
- Cache/import parsed data to a local SQLite database for fast reloads.
## Next steps

- `tests/` — unit tests
- `apple_health_dashboard/` — reusable library code
- `app.py` — Streamlit entrypoint
## Project layout

```
ruff check .
```powershell

Run lint:

```
pytest
```powershell

Run tests:
## Development

This app is designed to run locally. Your export can contain sensitive health data.
## Notes & privacy

- `app.py` is a Streamlit UI that calls the ingest + services layers.
- `apple_health_dashboard/services/` builds pandas dataframes + summary stats.
- `apple_health_dashboard/ingest/` handles reading Apple’s `export.xml`.
## How it works (high level)

Then open the URL Streamlit prints.

```
streamlit run app.py
python -m pip install -e .
python -m pip install -U pip
```powershell

3) Run the dashboard.
2) Install dependencies.
1) Create/activate a virtual env.
## Quickstart

You’ll get a zip with a folder like `apple_health_export/` that contains `export.xml`.
On iPhone: **Health** → your profile picture → **Export All Health Data**.
## Getting your Apple Health export

- Shows an interactive dashboard (steps, heart rate, sleep, workouts — and more later).
- Parses the data locally (no cloud upload).
- Lets you upload an Apple Health export (`export.xml` or the full `export.zip`).
## What this project does

Local dashboard for exploring your exported Apple Health data.

