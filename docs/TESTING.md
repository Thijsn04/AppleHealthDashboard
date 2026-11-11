# Testing and benchmarks

Run from the repository root with Python 3.11–3.14 and Node.js 24.

```sh
python -m pip install -e ".[dev]"
python -m ruff check .
python -m pytest -q
npm --prefix frontend ci
npm --prefix frontend run build
npm --prefix frontend exec -- playwright install chromium
npm --prefix frontend run test:e2e
```

For Windows with Chrome installed, set `HEALTH_TEST_BROWSER=chrome` in the shell to use the system browser. Set `HEALTH_SCREENSHOTS=1` to refresh the three fictional-profile screenshots. The browser test runs the built app against a temporary synthetic database on port 8765. Keep that port available. GitHub Actions runs Python tests on 3.11 and 3.12 and browser tests with the Chrome installation on the Ubuntu 24.04 runner. [GitHub runner image manifest](https://github.com/actions/runner-images/blob/main/images/ubuntu/Ubuntu2404-Readme.md).

## Verification

- All 48 Python tests passed on Python 3.12 with DuckDB 2.0 and Python 3.14 with DuckDB 1.5.2. The tests cover parser metadata, ZIP member checks and isolation, malformed-input rollback, reimport identity, legacy enrichment, profile deletion scope, source selection, unit conversion, historical filters, elapsed time over a DST boundary, stage conflicts, and missing measurements.
- Chrome at 1440×1000 and 390×844 exercised import preview, cancellation and confirmation, a keyboard chart scrubber, Explorer filters, comparison, CSV download, source rows, theme persistence, and navigation. Automated axe scans returned zero violations in the tested Explorer states. The browser test observed no page errors or external requests.
- A 3,650-observation daily series ran through the actual import and query paths. The date filter change to a painted frame took 131 ms in the final Windows Chrome run, including local API and browser automation overhead.
- The initial repository baseline passed 40 Python tests and the Vite build. The updated frontend dependency audit returned zero npm advisories at verification time.

## Synthetic performance

Run each command in a separate process. The generator uses fictional points from seven metric types, with up to five years of distinct dates. It generates XML locally and deletes the benchmark's working files on normal completion.

```sh
python scripts/benchmark.py 10000
python scripts/benchmark.py 100000
python scripts/benchmark.py 1000000
```

Windows, Ryzen 5 7600X3D, 12 logical CPUs, 31.2 GiB RAM, Python 3.14, DuckDB 1.5.2. Single observations per size, with other development processes running. Import duration excludes preview and generation. Peak working set covers the Python process, DuckDB, and their libraries. Query time includes opening the local database and computing one daily series.

| Rows | XML MiB | Preview s | Import s | Peak MiB | DB MiB | Query ms |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 10,000 | 1.99 | 0.47 | 1.51 | 197 | 2.51 | 433 |
| 100,000 | 19.87 | 0.95 | 6.19 | 346 | 18.26 | 172 |
| 1,000,000 | 198.69 | 7.59 | 36.98 | 1,342 | 178.26 | 247 |

The original checkout (`9586501`) took 533 seconds in one 10,000-row run with the initial generator. Its query returned in 35 ms and used simpler aggregation rules. The first batched implementation reached one million rows in 451 seconds with 2,724 MiB peak working set. After staging and merging the indexed table once, the million-row import took 36.98 seconds at 1,342 MiB peak. These timings are observations on one machine.

Repeat the baseline with `python scripts/benchmark.py 10000 --checkout <baseline-worktree>`. The script uses that checkout's Python modules without changing the profile in either checkout.

Failure and recovery were tested with synthetic malformed XML, rollback after a partial write, invalid ZIP input, repeated imports, and cancellation. Large benchmarks exercised quantity records. Large ZIPs, nested-heavy exports, low-memory hardware, arbitrary source conflicts, Firefox, Safari, physical mobile devices, and manual screen-reader use remain unverified.
