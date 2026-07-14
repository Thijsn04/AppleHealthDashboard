# Apple Health Analyzer

A private, local-first, open-source analyzer for Apple Health exports.

Apple Health Analyzer helps you inspect the data you already own without sending it to an account, an analytics service, or an advertising network. It is a wellness and data-exploration tool, not a medical device and not a substitute for clinical care.

> [!NOTE]
> The product frontend is React and TypeScript, backed by the local FastAPI service. The earlier Streamlit user interface and cloud-backed health chat have been removed rather than carried forward as privacy debt.

## Why it exists

- Your health export stays on your machine by default.
- Every derived metric should state its method and limitations.
- Raw data, sources, units, and import provenance should remain inspectable.
- The project should be useful to users and maintainable by contributors.

## Quick start

### Local API and web application

```powershell
git clone https://github.com/Thijsn04/AppleHealthDashboard.git
cd AppleHealthDashboard
python -m pip install -e ".[dev]"
npm --prefix frontend install

# Terminal 1: local API with interactive documentation at /api/docs
apple-health serve

# Terminal 2: web frontend
npm --prefix frontend run dev
```

Open the address shown by Vite, normally `http://localhost:5173`. The frontend communicates only with the local API.

## Current capabilities

| Area | Current state |
| --- | --- |
| Apple Health XML and ZIP input | Supported by the local API with preview and explicit confirmation |
| Local DuckDB storage | Supported |
| Activity, heart, body, nutrition, mobility, respiratory, symptoms, environment, mind, and other observed types | Supported through catalog-driven metric routes |
| Sleep, workouts, rings, raw record explorer | Supported by dedicated API-backed frontend routes |
| Local REST API | Available at `/api/v1`, with interactive documentation at `/api/docs` |
| React and TypeScript frontend | Available in `frontend/` |
| Import preview and atomic persistence | Supported by the local API |
| Import manifests, profiles, migration system, data-quality reports | Planned |
| Optional AI | Not included. Any future integration must be opt-in and make every external data transfer visible. |

Read the detailed [capability matrix](docs/CAPABILITY_MATRIX.md) before relying on a metric.

## Create an Apple Health export

On iPhone, open Health, choose your profile, then choose **Export All Health Data**. Apple creates a ZIP that contains `apple_health_export/export.xml`.

The export may contain data from many sources and devices. A record in the analyzer is not necessarily an Apple Watch measurement, and it is not necessarily clinically validated. Always inspect the source and record context.

## Privacy

- No account, cloud sync, analytics, or telemetry is required.
- The default database is local and excluded from Git.
- The new API binds to `127.0.0.1` by default.
- The frontend ships without remote fonts, trackers, telemetry, or cloud AI integrations.
- Do not expose the local API on a network interface unless you add authentication and transport security.

See the full [privacy policy and data-handling model](docs/PRIVACY.md).

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Data model](docs/DATA_MODEL.md)
- [Capability matrix](docs/CAPABILITY_MATRIX.md)
- [Metric methodology](docs/METRICS.md)
- [Privacy and security](docs/PRIVACY.md)
- [Roadmap](docs/ROADMAP.md)
- [Contributing](CONTRIBUTING.md)
- [Security policy](SECURITY.md)

## Development

```powershell
python -m pytest
python -m ruff check .
npm --prefix frontend run build
```

The repository disallows em dashes. This is enforced by `tests/test_repository_style.py`.

## Project layout

```text
apple_health_dashboard/
  api/                 FastAPI app and local API contract
  ingest/              Streaming Apple Health parsers
  services/            Domain analytics and metric logic
  storage/             DuckDB persistence
frontend/              React and TypeScript frontend
docs/                  Product, data, privacy, and engineering documentation
tests/                 Unit and integration tests using synthetic data only
```

## Contributing

Issues and pull requests are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md), keep fixtures synthetic, and do not commit personal health exports, databases, credentials, or screenshots containing identifiable data.

## License

[MIT](LICENSE)
