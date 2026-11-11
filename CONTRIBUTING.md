# Contributing to Apple Health Analyzer

Thank you for improving a private and transparent way to understand Apple Health exports.

## Principles

- Health data is sensitive. Never commit exports, databases, API keys, screenshots with identifiable data, or real fixtures.
- Local-first is a product requirement. New network access requires an explicit privacy review.
- Explain methods and uncertainty. Do not present wellness heuristics as medical facts.
- Keep raw data, sources, units, and transformations traceable.
- Accessibility, responsive design, and clean interaction design are part of feature completion.
- Em dashes are not permitted anywhere in tracked text files.

## Set up the project

```powershell
python -m pip install -e ".[dev]"
npm --prefix frontend ci
python -m pytest
python -m ruff check .
npm --prefix frontend run build
```

Run the built app with `python -m apple_health_dashboard.cli serve`. Start `npm --prefix frontend run dev` for Vite development. See the [testing guide](docs/TESTING.md) for browser verification.

## Architecture boundaries

| Layer | Responsibility | Must not do |
| --- | --- | --- |
| `ingest/` | Parse and validate source exports | Render UI or apply medical interpretation |
| `storage/` | Persist raw and derived data with provenance | Contain presentation logic |
| `services/` | Perform deterministic domain analysis | Import FastAPI or React |
| `api/` | Expose explicit local contracts | Return unbounded raw datasets by default |
| `frontend/` | Present accessible product workflows | Reimplement business logic |

## Adding a metric

1. Add the metric definition and metadata to `services/metrics.py`.
2. Document the source record type, expected unit, aggregation, limitations, and source requirements in `docs/METRICS.md`.
3. Implement a pure service function with type hints and tests.
4. Add API contract coverage before frontend work.
5. Design an accessible chart with visible methodology and empty-state behavior.
6. Add synthetic fixtures for normal, missing, duplicate, unit-variant, and time-zone edge cases.

## Pull request checklist

- [ ] Scope is focused and documented.
- [ ] Tests cover the behavior and relevant failures.
- [ ] `python -m pytest` and `python -m ruff check .` pass.
- [ ] `npm --prefix frontend run build` passes for frontend changes.
- [ ] No personal health data, credentials, or generated databases are included.
- [ ] New calculations explain their method and limitations.
- [ ] Documentation and capability matrix are updated.
- [ ] No em dash was introduced.

## Reporting issues

Include the app version, operating system, Python version, a synthetic reproduction where possible, and expected versus actual behavior. For security issues, use [SECURITY.md](SECURITY.md) instead of a public issue.
