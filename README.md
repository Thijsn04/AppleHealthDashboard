<div align="center">

# 📊 Apple Health Dashboard

**A privacy-first, local-by-default dashboard for your entire Apple Health export**

Explore **all** your Apple Health data — from sleep stages and heart rate variability to VO₂ max, workout personal records and body composition trends. Parsing, storage and analytics run entirely on your machine. The only exception is the **optional AI features** (Health Chat & AI Insights), which you must explicitly enable with your own API key — see [Privacy](#privacy-local-by-default).

[![CI](https://github.com/Thijsn04/AppleHealthDashboard/actions/workflows/ci.yml/badge.svg)](https://github.com/Thijsn04/AppleHealthDashboard/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B.svg?logo=streamlit&logoColor=white)](https://streamlit.io/)
[![DuckDB](https://img.shields.io/badge/DuckDB-FFF000.svg?logo=duckdb&logoColor=black)](https://duckdb.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

</div>

---

## Tech Stack

| Layer | Technology |
|---|---|
| **UI** | Streamlit (multipage) · Altair charts |
| **Data** | DuckDB (local database) · streaming XML parsers |
| **Language** | Python 3.11+ |
| **Tooling** | pytest · ruff |

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
| 📈 **Trends** | Year-over-year overlays and month-over-month change summaries across your longest-running metrics |
| 🥗 **Nutrition** | Dietary energy, macronutrients and hydration tracking (when logged) |
| 🚶 **Mobility** | Walking steadiness, asymmetry and speed analytics |
| 🤒 **Symptoms** | Logged symptoms such as headaches and fever over time |
| 🤖 **Health Chat** | *(Optional)* Ask questions about your data in natural language via an AI model — requires your own API key |
| ⚙️ **Settings** | Import, refresh and delete your local database |

## Privacy (local by default)

- Parsing, storage and every chart run **entirely on your machine** — no telemetry, no accounts, no cloud.
- Uploads are stored temporarily in `./.tmp/`; data is imported into a local DuckDB database (`./health.duckdb`).
- Your export, the temp folder and all local databases (`*.duckdb`, `*.db`, `*.sqlite`) are listed in `.gitignore` so they can't be committed by accident.

> [!IMPORTANT]
> **The only features that send data off your machine are the optional AI features** — the 🤖 **Health Chat** page and the AI summaries on the Insights page. They are **disabled unless you provide your own `GEMINI_API_KEY`**, and when used they send the relevant slice of your health data to Google's Gemini API. If you want a strictly offline setup, simply don't configure a key and these features stay off.

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
1. Open the **⚙️ Settings** page from the sidebar
2. Upload `export.zip` or `export.xml` and click **Import** (may take 1–5 minutes for large exports)
3. Navigate to any page from the sidebar

### Optional: enable AI features

The 🤖 **Health Chat** page and the AI summaries on the Insights page are **off by default**. To turn them on, provide a [Google AI Studio](https://aistudio.google.com/) key:

```bash
cp .env.template .env
# then edit .env and set GEMINI_API_KEY=your_key
```

When enabled, these features send the relevant slice of your health data to Google's Gemini API. Leave the key unset to keep the app fully offline.

## Project layout

```
app.py                          — Home dashboard (Streamlit entry point)
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
  10_⚙️_Settings.py             — Import, refresh & delete local data
  11_📈_Trends.py               — Year-over-year & month-over-month trends
  12_🤖_Health_Chat.py          — Optional AI chat over your data
  13_🥗_Nutrition.py            — Nutrition & hydration
  14_🚶_Mobility.py             — Walking steadiness & gait
  15_🤒_Symptoms.py             — Logged symptoms
apple_health_dashboard/
  db.py                         — Default database path helper
  local_data.py                 — Local data cleanup utilities
  logging_config.py             — Logging setup (console + file)
  ingest/
    apple_health.py             — Core HealthRecord dataclass & XML loader
    apple_health_records.py     — Streaming record parser
    apple_health_workouts.py    — Streaming workout parser
    apple_health_activity_summary.py — Activity summary (rings) parser
    importer.py                 — Orchestrates full import into DuckDB
  storage/
    duckdb_store.py             — DuckDB schema, read helpers & upsert writers
    notes_store.py              — User annotations store
  services/
    metrics.py                  — 50+ MetricSpec definitions with labels & units
    heart.py                    — HR, HRV, VO₂ max, BP, SpO₂ aggregations
    sleep.py                    — Sleep stages & consistency analytics
    body.py                     — Weight, BMI, body fat computations
    activity_summary.py         — Activity ring aggregations
    workouts.py                 — Workout aggregations & personal records
    streaks.py                  — Streaks & personal-best helpers
    insights.py                 — Cross-metric analysis & correlations
    readiness.py                — Daily readiness score
    forecasting.py              — Trend forecasting & goal-date prediction
    ai_insights.py              — Optional AI summaries (Gemini)
    weather.py                  — Weather enrichment helpers
    stats.py                    — Low-level record-to-DataFrame helpers
    filters.py                  — Date filtering utilities
    records_view.py             — Record view helpers for Explorer
    units.py                    — Unit conversion helpers
  web/
    charts.py                   — Altair chart builders (area, line, bar, etc.)
    heatmaps.py                 — Calendar & weekly heatmap builders
    body_map.py                 — Interactive body-map visual
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


---

<div align="center">
<sub>Built by <a href="https://github.com/Thijsn04">Thijs Nannings</a> · Medical Informatics @ UvA · <a href="https://lythos.nl">Lythos</a></sub>
</div>
