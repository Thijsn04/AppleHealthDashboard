# Contributing to Apple Health Dashboard

Thank you for your interest in contributing! This guide covers everything you need to get started.

## Table of contents

1. [Getting started](#getting-started)
2. [Project structure](#project-structure)
3. [Development workflow](#development-workflow)
4. [Adding a new dashboard page](#adding-a-new-dashboard-page)
5. [Adding a new metric](#adding-a-new-metric)
6. [Writing tests](#writing-tests)
7. [Code style](#code-style)
8. [Pull request checklist](#pull-request-checklist)

---

## Getting started

### Prerequisites

- Python 3.11+
- `git`

### Setup

```bash
git clone https://github.com/Thijsn04/AppleHealthDashboard.git
cd AppleHealthDashboard

# Install the package with all dev dependencies
pip install -e ".[dev]"
```

Verify everything works:

```bash
python -m pytest          # run tests
python -m ruff check .    # run linter
python -m streamlit run app.py  # start the dashboard
```

---

## Project structure

```
apple_health_dashboard/
  ingest/         Streaming SAX parsers that read Apple Health XML
  storage/        SQLite schema, upsert writers and read iterators
  services/       Pure-Python / Pandas analytics (no Streamlit)
  web/            Streamlit UI helpers and Altair chart builders
pages/            One file per dashboard page
tests/            pytest unit tests
app.py            Home page and data import entrypoint
main.py           CLI smoke-test helper
```

The services layer is intentionally **decoupled from Streamlit**. Keep it that way: services accept `pd.DataFrame` and return `pd.DataFrame` (or simple Python objects). All Streamlit calls belong in `pages/` or `web/`.

---

## Development workflow

1. Create a feature branch from `main`:
   ```bash
   git checkout -b my-feature
   ```
2. Make your changes in small, focused commits.
3. Run the linter and tests before pushing:
   ```bash
   python -m ruff check . --fix
   python -m pytest
   ```
4. Open a pull request against `main`.

---

## Adding a new dashboard page

Streamlit loads pages from the `pages/` directory automatically, in alphabetical/numerical order.

1. Create `pages/N_<emoji>_<Name>.py` where `N` is the next available number.
2. Start the file with `st.set_page_config(...)` — copy the pattern from an existing page.
3. Use `from apple_health_dashboard.web.page_utils import require_data, sidebar_date_filter` to get the standard sidebar date filter and "no data" guard.
4. Load records with `load_all_records()` from `page_utils`; pass the result to service functions.
5. Render charts using helpers from `apple_health_dashboard.web.charts` for visual consistency.
6. Add the new page to the navigation cards in `app.py`.

---

## Adding a new metric

Apple Health data types are catalogued in `apple_health_dashboard/services/metrics.py`.

1. Append a `MetricSpec` entry to the `METRICS` list with the correct `record_type` (the raw `HKQuantityTypeIdentifier*` or `HKCategoryTypeIdentifier*` string), `label`, `category`, `aggregation`, and `unit_hint`.
2. The **Explorer** page will automatically pick up the new type.
3. If you want dedicated analysis (trends, stats), add a helper function to the appropriate service module (e.g., `services/heart.py` for heart metrics).

---

## Writing tests

Tests live in `tests/` and use **pytest**.

```bash
python -m pytest          # run all tests
python -m pytest -q       # quieter output
python -m pytest tests/test_new_services.py  # run a specific file
```

### Guidelines

- Test service functions (in `apple_health_dashboard/services/`) in isolation with small synthetic DataFrames.
- Do **not** test Streamlit page files directly — test the service functions they call.
- Use `pytest.fixture` for any shared test data.
- Aim for edge cases: empty DataFrames, missing columns, single-row inputs.

---

## Code style

This project uses [Ruff](https://docs.astral.sh/ruff/) for linting and formatting.

Configuration lives in `pyproject.toml`:

```toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP"]
```

Auto-fix most issues with:

```bash
python -m ruff check . --fix
```

Additional conventions:
- All source files use `from __future__ import annotations`.
- Service functions are pure (no side effects, no Streamlit imports).
- Type hints are required for public function signatures.
- Docstrings follow the Google-style format.

---

## Pull request checklist

Before opening a PR, verify:

- [ ] `python -m ruff check .` passes with no errors
- [ ] `python -m pytest` passes
- [ ] New public functions have docstrings
- [ ] The `README.md` project layout table is updated if new files were added
- [ ] No secrets, credentials, or personal health data are committed
