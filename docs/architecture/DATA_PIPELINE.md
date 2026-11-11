# Data pipeline

## Ingestion

1. Preview accepts `export.xml` or a ZIP containing an `export.xml` member. Input is limited to 1 GiB, extracted XML to 2 GiB, and ZIP member compression ratio to 100:1. The server also bounds multipart request size. ZIP import streams one selected member into an isolated ticket directory.
2. The preview checks the `HealthData` root and counts direct `Record`, `Workout` and `ActivitySummary` children. It compares available start and end timestamps as instants. This is a separate pass from the confirmed import.
3. Confirmation claims a ticket once. The importer streams direct children and removes each processed child from the XML tree. It batches observations and metadata in DuckDB temporary tables, then merges the indexed observation table in bulk. Workouts and rings use smaller batches. Direct record and workout metadata is retained.
4. One transaction covers health records, workouts, summaries and metadata. Missing required attributes are counted as skipped entries. Invalid XML or a malformed timestamp that reaches import aborts the transaction. Unsupported child types are ignored. Numeric values that cannot be represented as finite numbers remain inspectable as text for health records.
5. The result reports newly added rows. Reimporting the same valid records reports zero new rows and can fill missing provenance. Cancelling, confirming, expiry, and graceful shutdown remove the staging copy. Expiry is 30 minutes with an approximately one-minute cleanup interval.

The file-size ceilings are admission limits. They describe allowed inputs, while [benchmarks](../TESTING.md) describe verified performance. Memory includes the largest top-level XML child, the DuckDB transaction and indexes, and the query working set. Allow disk space for the staged file, extracted XML, database and any temporary spill.

## DuckDB schema

| Table | Contents and identity |
| --- | --- |
| `health_record` | Raw exported value or text, original unit, source name, source version and device when present. Stable hash over type, offset-bearing timestamps, source name, unit and value. |
| `record_metadata` | Direct `MetadataEntry` values keyed by record hash, key and value. |
| `workout` | Type, timestamps, source and device, legacy quantity fields, reported units, and normalized reported hours, kilometers, kilocalories, and average bpm where available. |
| `workout_metadata` | Direct workout `MetadataEntry` values keyed by workout hash, key and value. |
| `activity_summary` | Exported Activity rings and targets, keyed by day. The first stored row for a day is retained. |

New records carry UTC instants in the query timestamp columns and retain the original numeric offsets in the source timestamp columns. Aggregates use the recorded local calendar date for day-level grouping. Sleep uses elapsed instants and the original end date of the interval that closes each episode. Workout statistics are used only for recognized compatible quantities. Workout routes, nested clinical records, ECG attachments, and native HealthKit ingestion are outside the current format.

## Existing profiles

The server adds missing columns and widens old integer ring quantities at startup without replacing the database or rewriting legacy rows. The importer uses the same additive schema initialization. Legacy rows retain their stored naive timestamps. The Explorer labels unknown offsets. Reimport the original export to match stable hashes and enrich those rows in place. Existing workout totals with unknown units remain absent from quantity aggregates until a compatible export supplies their units. Older hash identity cannot distinguish device metadata on otherwise identical observations, and the original record is kept.

Back up the profile with the app stopped before upgrading. An older application may read mixed timestamp conventions after an upgraded import. Restore the pre-upgrade backup when rolling back.
