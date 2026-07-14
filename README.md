<div align="center">

# Apple Health Analyzer

**A private, locally hosted analyzer for Apple Health exports**

Import an Apple Health XML or ZIP export, inspect the measurements you own, and explore clear daily trends across activity, heart, sleep, workouts, body, nutrition, mobility, and more. A local FastAPI API, a clean React web application, and no account, trackers, or cloud upload required.

[![CI](https://github.com/Thijsn04/AppleHealthDashboard/actions/workflows/ci.yml/badge.svg)](https://github.com/Thijsn04/AppleHealthDashboard/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-20232A.svg?logo=react&logoColor=61DAFB)](https://react.dev/)
[![DuckDB](https://img.shields.io/badge/DuckDB-FFF000.svg?logo=duckdb&logoColor=000000)](https://duckdb.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

</div>

---

## Quick start

```powershell
git clone https://github.com/Thijsn04/AppleHealthDashboard.git
cd AppleHealthDashboard
python -m pip install -e ".[dev]"
npm --prefix frontend install

# Terminal 1: local API and interactive documentation
apple-health serve

# Terminal 2: product web application
npm --prefix frontend run dev
```

Then open:

- Web application: `http://localhost:5173`
- API documentation: `http://127.0.0.1:8000/api/docs`

In Apple Health on iPhone, open your profile and choose **Export All Health Data**. Select the generated ZIP or `export.xml` in the web application, review the local preview, then confirm the import.

## Four ways to use it

**Web application.** Import an export, review profile totals, inspect activity, heart, sleep, workout, ring, body, nutrition, mobility, and symptom metrics, and verify source observations in the Explorer.

**Local REST API.** Use the documented `/api/v1` contract to preview imports, confirm an import, list observed metric types, retrieve daily series, and browse bounded record pages. Interactive reference is available at `/api/docs`.

**Command line.** Start the local service with:

```powershell
apple-health serve
apple-health serve --port 8100
```

**Extensible analytics layer.** Add a metric definition, its method, and a tested aggregation policy in Python. The API catalog and React metric routes use that shared metadata rather than duplicating health logic in the UI.

## What it analyzes

Apple Health exports are heterogeneous. The analyzer preserves raw source records in local DuckDB storage and presents them through documented aggregation policies.

- Activity: steps, distance, energy, exercise, stand time, flights, and running metrics.
- Heart and respiratory: heart rate, resting heart rate, HRV, cardio fitness, blood pressure, blood oxygen, and respiratory rate.
- Sleep: nightly asleep duration and exported sleep-stage totals.
- Workouts and rings: session totals, training volume, workout-type mix, and Apple Activity summaries.
- Body and nutrition: weight, BMI, body composition, dietary energy, macros, water, sodium, and caffeine when exported.
- Mobility, symptoms, environment, mind, and other exported record types through catalog-driven metric views and the raw-record Explorer.

Every profile differs. A missing screen value means the selected export did not contain a compatible record, not that the analyzer inferred a value.

## Highlights

- Local-first by default. No account, cloud sync, analytics, telemetry, remote fonts, or cloud AI integration.
- Safe Apple Health XML and ZIP handling with archive path, size, and compression-ratio checks.
- Preview and explicit confirmation before health records are persisted.
- Atomic, idempotent local imports backed by DuckDB.
- Bounded API responses and paginated raw-record inspection for large histories.
- Typed FastAPI contract with interactive OpenAPI documentation.
- Responsive React interface with semantic controls, focus states, charts, tables, empty states, and method context.
- Clear separation between wellness data exploration and medical advice.

## Documentation

| Guide | What it covers |
|---|---|
| [Architecture](docs/ARCHITECTURE.md) | System boundaries and engineering rules |
| [Data model](docs/DATA_MODEL.md) | Local DuckDB tables and data flow |
| [Capability matrix](docs/CAPABILITY_MATRIX.md) | Current support and planned areas |
| [Metric methodology](docs/METRICS.md) | Source types, aggregation, caveats, and units |
| [Privacy](docs/PRIVACY.md) | Local-only data handling and security boundaries |
| [Roadmap](docs/ROADMAP.md) | Import, analytics, and interoperability work ahead |
| [Contributing](CONTRIBUTING.md) | Development setup and contribution expectations |
| [Security policy](SECURITY.md) | Responsible vulnerability reporting |

## Development

```powershell
python -m pip install -e ".[dev]"
npm --prefix frontend install
python -m pytest
python -m ruff check .
npm --prefix frontend run build
```

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md), keep all fixtures synthetic, and do not commit personal health exports, databases, credentials, or identifiable screenshots.

## A note on health data

Apple Health records can come from different devices and apps, may overlap, and are not necessarily clinically validated. Apple Health Analyzer is for personal wellness exploration and data inspection. It is not a medical device, a diagnostic service, or a replacement for qualified clinical care.

The repository disallows em dashes in tracked text. This is enforced by `tests/test_repository_style.py`.

## License

MIT. Free to use in personal, educational, open-source, and commercial projects.

---

<div align="center">
<sub>Built by <a href="https://github.com/Thijsn04">Thijs Nannings</a> · Medical Informatics @ UvA · <a href="https://lythos.nl">Lythos</a></sub>
</div>
