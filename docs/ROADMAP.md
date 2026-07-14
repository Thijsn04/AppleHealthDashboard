# Roadmap

## Phase 0: foundations

- [x] Audit the existing product and document target architecture.
- [x] Establish an explicit local API contract and React frontend.
- [x] Add repository enforcement for the no-em-dash rule.
- [x] Replace corrupted and legacy-oriented documentation completely.
- [ ] Add code of conduct, issue templates, dependency automation, and security scanning.

## Phase 1: trusted import core

- [ ] Introduce user-data directory configuration and safe migration from legacy paths.
- [ ] Add versioned DuckDB schema migrations.
- [ ] Add import manifests, cancellation, recovery, and expanded diagnostics.
- [ ] Add source, device, unit, time-zone, and duplicate handling.
- [ ] Add synthetic large-export and hostile-archive tests.

## Phase 2: product experience

- [x] Build the import workflow in React.
- [x] Migrate overview, activity, heart, sleep, workouts, rings, and raw explorer.
- [ ] Add design tokens, accessible charts, dark mode, responsive behavior, and visual regression tests.
- [x] Remove all Streamlit-only UI paths.

## Phase 3: trustworthy analysis

- [ ] Publish the full metric catalogue and methodology cards.
- [ ] Add data-quality workspace and source provenance inspection.
- [x] Migrate catalog-driven trends, body, nutrition, mobility, respiratory, symptoms, environment, mind, and other observed types.
- [ ] Redesign readiness, correlations, and forecasts around uncertainty and user configuration.

## Phase 4: advanced interoperability

- [ ] Evaluate explicit adapters for routes, ECG metadata, heartbeat series, and clinical FHIR data.
- [ ] Add controlled export to CSV, Parquet, and documented interoperable formats.
- [ ] Add a consent-first provider interface for optional AI and local-model support.

## Definition of done for a migrated feature

The feature has documented source types and method, API contract tests, analytics tests, accessible UI, empty and error states, performance coverage, privacy review, and user-facing limitations.
