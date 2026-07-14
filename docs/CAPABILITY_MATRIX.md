# Capability matrix

This matrix is deliberately conservative. Apple Health availability varies by device, region, operating-system version, source app, and export content.

| Capability | Current support | Target behavior | Notes |
| --- | --- | --- | --- |
| Quantity and category `Record` entries | Local API previews and imports normalized values atomically | Provenance and unit normalization | Main source for existing analytics |
| Workouts | Legacy importer stores summary and metadata | Activity-level drill-down and source linkage | Associated samples need careful overlap handling |
| Activity summaries | Legacy importer stores daily rings | Goal history and source-quality context | Apple Watch data is required |
| Unknown record types | Explorer can surface many types | Catalog status and raw inspection | Unknown is not silently discarded |
| Sleep stages | Legacy analytics available | Transparent stage overlap and quality reporting | Device and OS dependent |
| Heart and HRV metrics | Legacy analytics available | Source-aware trends and uncertainty | Consumer data is not diagnostic |
| Nutrition and symptoms | Legacy pages available when data exists | Structured daily context and source caveats | Often sparse or manually entered |
| Workout routes | Not currently supported | Explicit opt-in import and privacy controls | Location data is highly sensitive |
| ECG and heartbeat series | Not currently supported | Capability detection and bounded metadata support | Export representation must be verified |
| Clinical FHIR records | Not currently supported | Separate opt-in import adapter | Requires its own privacy and data-model review |
| Multiple local profiles | Not currently supported | Separate profile stores and import histories | No cross-profile data mixing |
| Data-quality report | Not currently supported | First-class import artifact | Required before advanced recommendations |

## Important limitations

- ZIP imports stream only the selected `export.xml` member after path, file-size, and compression-ratio checks. The importer does not extract an archive wholesale.
- Previewing an export does not persist observations. A second, explicit local confirmation is required before import.
- Not every HealthKit type is necessarily present in an Apple Health export.
- A metric can have contributions from multiple devices and third-party apps.
- Record timestamps, duplication, and overlap materially affect daily totals.
- No classification, score, or trend in this project should be interpreted as a diagnosis.
