# Architecture decision

## Context and baseline

The previous Streamlit application was replaced by React, FastAPI and DuckDB in commit `51b02d6`. The main workflow is one person importing years of Apple Health data on a trusted computer. The system already has a catalog, transactional import, deterministic row hashes, archive validation, paged observations and API tests. Preserve those contracts and existing database contents.

## Findings in priority order

| Area | Evidence and consequence | Implementation |
| --- | --- | --- |
| Metric correctness | Daily SQL sums all sources and mixes units under the alphabetically first unit. Sleep adds overlapping intervals. Charts space dates by record index and render missing ring energy as zero. | Apply explicit source and unit policies, merge sleep intervals, and plot elapsed calendar time with gaps. |
| Timestamp provenance | DuckDB casts aware Python datetimes to naive timestamps using the writer time zone. The export offset is lost, so a legacy local timestamp cannot reliably be converted back. | Add nullable source offsets and source date context. Reimport upgrades matching records without changing hash identity. |
| Import scale | Three passes each retain at least part of the XML tree. DuckDB receives row-at-a-time inserts. | Detach consumed XML elements, share a single import pass, and use batch inserts. Measure real throughput. |
| Temporary files | ZIP previews with identical content can share an extracted file. Cancel only clears the browser state. | Give each staging ticket its own directory and provide cancellation and expiry. |
| Product | The landing page inventories data but gives few analytic entry points. Explorer only lists raw rows. CI omits the frontend build. | Build a profile overview and a time-range, source and granularity-aware comparison workspace. Verify the browser workflow and add CI coverage. |
| Data lifecycle | The profile is tied to the working directory, with an old internal deletion helper and no clear user workflow. | Keep default location compatibility and document safe retention and removal. |

Git history was inspected for suspicious artifact names and common private-key or token signatures. The checks returned no matching export/database artifacts or secret signatures. This is a targeted search. Historical IDE files and the environment template are present.

## Options

| Option | Benefits | Costs and risks |
| --- | --- | --- |
| A. Modernize in place | Least disruption and fastest incremental delivery. Existing tests and files remain useful. | CSS and isolated SQL fixes leave duplicated parsing, provenance gaps and a raw-only Explorer. |
| B. Restructure the import and analytics paths and replace the main UI | Retains local tooling, database continuity and contracts while addressing the actual bottlenecks. Can benchmark against the same baseline. | Requires additive schema evolution, source-policy tests, and browser verification. |
| C. Rebuild as browser-only React with a Worker, DuckDB-Wasm and origin-private storage | Removes the local Python process and provides a simple static delivery path. | Requires a new streaming XML reader, database migration and cross-browser durability and quota testing. Native versus Wasm throughput is unmeasured here. Recreates working import and API behavior. |

## Decision

Choose B. React/Vite and TypeScript fit a local interactive application with no server-rendering needs. Next.js would add a runtime without a corresponding rendering or routing requirement. Retain Python and FastAPI for bounded queries and import orchestration, and embedded DuckDB for columnar aggregates over an existing local profile. SQLite would simplify some write workflows but change storage and favor indexed row access. PostgreSQL would introduce a separate service. Parquet can serve as an interchange format, but mutable deduplication and atomic import already have a single owner in DuckDB. A small, bounded SVG chart can supply elapsed-time geometry and a table fallback without adding a visualization framework. Canvas or a dedicated library is worth reassessing if dense unaggregated rendering becomes a requirement.

## Migration and verification

Keep the five existing tables and stable hashes. Make new provenance fields additive and nullable. Preserve unresolved legacy timestamps and enrich them during reimport. Keep import atomic. Verify with a baseline checkout, synthetic parser and analytics fixtures, migration/reimport checks, import and query benchmarks, frontend build, and browser checks across desktop and mobile viewports. The implementation status tracks remaining limits.

See [DuckDB timestamp semantics](https://duckdb.org/docs/current/sql/data_types/timestamp) and [Python datetime conversion](https://www.duckdb.org/docs/current/clients/python/conversion).
