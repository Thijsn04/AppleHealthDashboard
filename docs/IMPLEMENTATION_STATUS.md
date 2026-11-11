# Implementation status

## Delivered

- Retained the existing React/Vite, FastAPI and embedded DuckDB stack. Replaced the import hot path and product interface, and added a single-process launch path for the built client.
- Added bounded XML and ZIP preview, isolated staging, transactional batch import, additive provenance and reimport enrichment. Kept the existing profile location and record hash identity.
- Shipped the overview, activity, heart, body, sleep, workout and ring views. The Explorer covers other observed types, with source and date filters, comparison, distributions, CSV and paged raw observations.
- Replaced CDN-backed API documentation with the local OpenAPI schema. Added synthetic demo data, desktop and mobile screenshots, browser verification, and frontend CI.
- Removed unused network weather code and generated TypeScript files. Forecasting dependencies are now optional and the legacy helpers remain available with the `forecast` extra.

## Follow-up backlog

| Priority | Limit and possible next milestone |
| --- | --- |
| 1 | Quantify overlap and unit exclusions by reason, expose original metadata on demand, and add import manifests so users can trace changes between exports. |
| 2 | Evaluate source-priority configuration and interval apportionment against more varied, synthetic multi-device fixtures. Legacy offsets require original exports to recover. |
| 3 | Improve long-import progress reporting and evaluate peak memory, temp disk and import cancellation on low-memory hardware. Pending previews can be cancelled. |
| 4 | Extend browser coverage to Firefox, Safari and real devices, including manual screen reader tests. |
| 5 | Consider standalone packaging and opt-in adapters for specialized exports after representative fixtures and privacy boundaries are available. |

The current product targets one local profile and descriptive analysis. The [testing guide](TESTING.md) lists the measured sizes and verification environment.
