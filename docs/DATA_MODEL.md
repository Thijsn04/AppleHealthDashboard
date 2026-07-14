# Data model and provenance

## Existing schema

The legacy DuckDB schema contains these primary tables:

| Table | Purpose |
| --- | --- |
| `health_record` | Normalized Apple Health `Record` observations |
| `record_metadata` | Key-value metadata linked to a record hash |
| `workout` | Workout summaries |
| `workout_metadata` | Key-value metadata linked to a workout hash |
| `activity_summary` | Daily Activity ring summaries |

## Target schema additions

| Table or concept | Why it matters |
| --- | --- |
| `schema_migration` | Reproducible and auditable database upgrades |
| `profile` | Separate local people and databases without data mixing |
| `import_run` | Import time, source checksum, parser version, counts, warnings, and status |
| `source` and `device` | Normalize source names and preserve device metadata |
| `record_type_catalog` | Versioned type, unit, category, aggregation, and support status |
| `data_quality_issue` | Store gaps, invalid values, duplicates, unit conflicts, and parser warnings |
| `derived_dataset` | Record method version, inputs, time range, and refresh state for every derivation |
| `annotation` | User-owned notes that are distinct from imported source data |

## Record identity

A source record should preserve its source identifier whenever the export provides one. When it does not, the importer must create a documented deterministic hash. Identity must include enough fields to prevent accidental collision across equal readings from different sources.

## Unit handling

Raw values and original units are retained. Canonical values are derived for analysis only, with conversion code and target unit documented in the metric catalog. The interface must clearly distinguish source values from converted values.

## Time handling

Apple Health timestamps contain offsets. The importer preserves the original instant and offset, stores canonical UTC instants for querying, and records the profile display time zone separately. Day-level metrics must document which local day boundary they use. Daylight-saving changes and travel are test cases, not edge cases to ignore.

## Provenance contract

Every displayed derived result must be able to answer:

1. Which imported records contributed?
2. Which source devices or apps produced them?
3. Which unit conversion and aggregation were used?
4. Which code or method version created the result?
5. What data-quality warnings apply?
