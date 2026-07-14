# Architecture

## Target system

```text
Apple Health XML or ZIP
          |
          v
Validation and import pipeline
          |
          v
DuckDB: raw records, provenance, derived tables, import reports
          |
          +--------------------+
          |                    |
          v                    v
Typed Python services      FastAPI local contract
                               |
                               v
                     React and TypeScript application
```

## Design goals

1. Local-first operation with no required account or remote service.
2. Traceability from every displayed value to its source records and transformation.
3. Deterministic analytics that can be tested with synthetic fixtures.
4. A fast and accessible interface that remains usable with large exports.
5. Clear capability boundaries for Apple Health data that is unavailable or incompletely represented in an export.

## Current system boundaries

The supported application uses these stable boundaries:

- `apple_health_dashboard/api/` for explicit local HTTP contracts.
- `frontend/` for product UI and presentation.
- `ingest/`, `storage/`, and `services/` for source processing and deterministic analysis.

New feature work belongs in these boundaries. The project does not ship a second user interface.

## API contract rules

- API routes live under `/api/v1`.
- Schema models are explicit Pydantic types.
- List endpoints must paginate before serving potentially large local datasets.
- Default responses return aggregates or bounded samples.
- New routes need OpenAPI descriptions, contract tests, and privacy review.
- The API is local-only. Network exposure needs a separate authenticated deployment design.

## Frontend rules

- React components are typed and own presentation only.
- Use semantic HTML before custom controls.
- Keyboard navigation, focus states, responsive layouts, color contrast, and meaningful empty states are required.
- Avoid remote fonts, trackers, decorative emoji navigation, and raw HTML injection.
- Charts must expose values in accessible text or a data-table alternative.

## Service rules

Services accept typed or tabular inputs and return deterministic results. They must declare input assumptions, record-source caveats, aggregation rules, and limitations. A score without its methodology is not a product feature.
