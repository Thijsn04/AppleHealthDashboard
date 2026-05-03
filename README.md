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

## Privacy (100% local)

- Your data is **never** uploaded anywhere.
- Uploads are stored temporarily in `./.tmp/`.
- Data is imported into a local SQLite database: `./health.db`.
- Both are listed in `.gitignore`.

## Create an Apple Health export

On your iPhone:
1. Open **Health**
2. Tap your **profile** (top-right)
3. Choose **Export All Health Data**

You'll receive a `.zip` containing `apple_health_export/export.xml`.

## Quickstart

```bash
# Install
pip install -e ".[dev]"

# Run
python -m streamlit run app.py
```

Then:
1. Upload `export.zip` or `export.xml` in the **Home** page sidebar
2. Click **Import →** (may take 1–5 minutes for large exports)
3. Navigate to any page from the sidebar

## Project layout

```
app.py                          — Home / import page
pages/
  1_📊_Overview.py              — Key metrics summary
  2_❤️_Heart.py                 — Heart health analysis
  3_🏃_Activity.py              — Activity & steps
  4_😴_Sleep.py                 — Sleep analysis
  5_🏋️_Workouts.py              — Workout details
  6_🔥_Rings.py                 — Activity rings
  7_⚖️_Body.py                  — Body metrics
  8_🔬_Explorer.py              — Raw data explorer
apple_health_dashboard/
  ingest/                       — Streaming XML parsers + importer
  storage/                      — SQLite schema + read/write helpers
  services/                     — Pandas aggregations & analytics
    metrics.py                  — 50+ metric definitions
    heart.py                    — HR, HRV, VO₂ max, BP, SpO₂
    sleep.py                    — Sleep stages & consistency
    body.py                     — Weight, BMI, body fat
    streaks.py                  — Streaks & personal records
    workouts.py                 — Workout aggregations & PRs
  web/
    charts.py                   — Altair chart builders
    page_utils.py               — Shared sidebar & helpers
tests/                          — Unit tests (31 tests)
```

## Development

```bash
# Tests
python -m pytest

# Lint
python -m ruff check .
```

## Troubleshooting

- **Streamlit not found**: use `python -m streamlit run app.py`
- **Import is slow**: large exports (500k+ records) take 2–5 minutes; progress is shown
- **No data visible**: go to Home, import first, then navigate to a page
- **No sleep stages**: detailed stages require Apple Watch Series 4+ with watchOS 9+
- **No VO₂ max**: requires outdoor run or walk with Apple Watch GPS enabled
