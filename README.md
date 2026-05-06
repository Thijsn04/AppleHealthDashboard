# Apple Health Dashboard

A local, privacy-first dashboard to explore **all** your Apple Health data — from sleep stages
and heart rate variability to VO₂ max, workout personal records and body composition trends.

## Features

| Page | What you'll find |
|------|-----------------|
| 📊 **Overview** | Key metrics at a glance — steps, resting HR, sleep, rings, weight |
| ❤️ **Heart Health** | HR trends & daily ranges, HRV (SDNN), VO₂ max, blood pressure, SpO₂, HR zone distribution |
| 🏃 **Activity** | Steps, distance (walk/run/cycle/swim), active energy, exercise time, stand time, flights, running metrics — with streaks and personal bests |
| 😴 **Sleep** | Duration, sleep stages (Core / Deep / REM / Awake), nightly efficiency, weekly heatmap, consistency stats |
| 🏋️ **Workouts** | All 40+ workout types, weekly trends, personal records (longest, farthest, most kcal), calendar heatmap |
| 🔥 **Rings** | Move / Exercise / Stand ring completion rates, goal tracking, all-rings streak |
| ⚖️ **Body** | Weight trend, BMI classification, body fat %, lean mass, goal calculator |
| 🔬 **Explorer** | Browse & filter every one of 50+ record types with paginated raw data and auto-generated daily charts |
| 💡 **Insights** | Cross-metric analysis — daily readiness score, sleep/HRV correlations, circadian profile, correlation matrix |

## Privacy (100% local)

- Your data is **never** uploaded anywhere.
- Uploads are stored temporarily in `./.tmp/`.
- Data is imported into a local DuckDB database: `./health.duckdb`.
- Both are listed in `.gitignore`.

## Requirements

- Python 3.11 or newer
- Works on macOS, Linux, and Windows

## Create an Apple Health export

On your iPhone:
1. Open **Health**
2. Tap your **profile** (top-right)
3. Choose **Export All Health Data**

You'll receive a `.zip` containing `apple_health_export/export.xml`.

## Quickstart

```bash
# Clone the repository
git clone https://github.com/Thijsn04/AppleHealthDashboard.git
cd AppleHealthDashboard

# Install dependencies
pip install -e ".[dev]"

# Run the dashboard
python -m streamlit run app.py
```

Then:
1. Upload `export.zip` or `export.xml` in the **Home** page sidebar
2. Click **Import →** (may take 1–5 minutes for large exports)
3. Navigate to any page from the sidebar

## Project layout

```
app.py                          — Home / import page (Streamlit entry point)
main.py                         — CLI helper (quick parse smoke-test)
pages/
  1_📊_Overview.py              — Key metrics summary
  2_❤️_Heart.py                 — Heart health analysis
  3_🏃_Activity.py              — Activity & steps
  4_😴_Sleep.py                 — Sleep analysis
  5_🏋️_Workouts.py              — Workout details
  6_🔥_Rings.py                 — Activity rings
  7_⚖️_Body.py                  — Body metrics
  8_🔬_Explorer.py              — Raw data explorer
  9_💡_Insights.py              — Cross-metric insights & correlations
apple_health_dashboard/
  db.py                         — Default database path helper
  local_data.py                 — Local data cleanup utilities
  logging_config.py             — Logging setup (console + file)
  ingest/
    apple_health.py             — Core HealthRecord dataclass & XML loader
    apple_health_records.py     — Streaming record parser
    apple_health_workouts.py    — Streaming workout parser
    apple_health_activity_summary.py — Activity summary (rings) parser
    importer.py                 — Orchestrates full import into SQLite
  storage/
    sqlite_store.py             — SQLite schema, read helpers & upsert writers
  services/
    metrics.py                  — 50+ MetricSpec definitions with labels & units
    heart.py                    — HR, HRV, VO₂ max, BP, SpO₂ aggregations
    sleep.py                    — Sleep stages & consistency analytics
    body.py                     — Weight, BMI, body fat computations
    activity_summary.py         — Activity ring aggregations
    workouts.py                 — Workout aggregations & personal records
    streaks.py                  — Streaks & personal-best helpers
    insights.py                 — Cross-metric analysis & readiness score
    stats.py                    — Low-level record-to-DataFrame helpers
    filters.py                  — Date filtering utilities
    records_view.py             — Record view helpers for Explorer
    units.py                    — Unit conversion helpers
  web/
    charts.py                   — Altair chart builders (area, line, bar, etc.)
    page_utils.py               — Shared sidebar, date filter & data loading
    ui.py                       — Base UI helpers (cards, branding)
    explore.py                  — Explorer page helpers
    i18n.py                     — Internationalisation / label helpers
tests/                          — Unit tests (pytest)
```

## Development

```bash
# Run tests
python -m pytest

# Lint
python -m ruff check .

# Auto-fix lint issues
python -m ruff check . --fix
```

### CLI smoke-test

A small CLI helper is included for quickly verifying that an export file can be parsed without starting the full Streamlit server:

```bash
python main.py path/to/export.xml
```

### Deleting local data

All locally stored data (database + temporary files) can be deleted from the Home page via the **🗑️ Delete local data** expander in the sidebar, or programmatically:

```python
from apple_health_dashboard.local_data import delete_local_data
delete_local_data()  # removes ./health.duckdb and ./.tmp/
```

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `Streamlit not found` | Run `python -m streamlit run app.py` instead of `streamlit run app.py` |
| Import is slow | Large exports (500k+ records) take 2–5 minutes; a progress bar is shown |
| No data visible | Go to Home, import first, then navigate to a page |
| No sleep stages | Detailed stages require Apple Watch Series 4+ with watchOS 9+ |
| No VO₂ max | Requires an outdoor run or walk with Apple Watch GPS enabled |
| Charts look empty after re-import | Click **Refresh** in the Home sidebar to clear the Streamlit data cache |

## License

This project is released under the [MIT License](LICENSE).
