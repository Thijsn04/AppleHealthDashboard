"""Measure one isolated synthetic import and a representative metric query."""

import argparse
import json
import sys
import tempfile
from pathlib import Path
from time import perf_counter

from generate_demo import generate

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    def peak_rss() -> int:
        class Counters(ctypes.Structure):
            _fields_ = [
                ("size", wintypes.DWORD), ("faults", wintypes.DWORD),
                ("peak_rss", ctypes.c_size_t), ("rss", ctypes.c_size_t),
                ("remaining", ctypes.c_size_t * 6),
            ]

        counters = Counters()
        counters.size = ctypes.sizeof(counters)
        kernel = ctypes.WinDLL("kernel32")
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        query = ctypes.WinDLL("psapi").GetProcessMemoryInfo
        query.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
        if not query(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.size):
            raise OSError("Could not read the peak process working set.")
        return counters.peak_rss
else:
    import resource

    def peak_rss() -> int:
        value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return value if sys.platform == "darwin" else value * 1024


def measure(records: int, checkout: Path) -> None:
    sys.path.insert(0, str(checkout.resolve()))
    from apple_health_dashboard.api.analytics import metric_series
    from apple_health_dashboard.ingest.importer import import_export_xml_to_duckdb_all
    from apple_health_dashboard.ingest.safe_import import preview_export

    with tempfile.TemporaryDirectory(prefix="apple-health-bench-") as directory:
        xml = Path(directory) / "synthetic.xml"
        db = xml.with_suffix(".duckdb")
        generate(xml, days=min(1825, records // 7 + 1), records=records)
        start = perf_counter()
        assert preview_export(xml).record_count == records
        preview_seconds = perf_counter() - start
        start = perf_counter()
        assert import_export_xml_to_duckdb_all(xml, db)["records_inserted"] == records
        elapsed = perf_counter() - start
        start = perf_counter()
        result = metric_series(db, "HKQuantityTypeIdentifierStepCount", None)
        query_ms = (perf_counter() - start) * 1000
        assert result["points"]
        print(json.dumps({
            "records": records, "preview_s": round(preview_seconds, 3), "import_s": round(elapsed, 3),
            "peak_mib": round(peak_rss() / 1048576, 1), "xml_mib": round(xml.stat().st_size / 1048576, 2),
            "db_mib": round(db.stat().st_size / 1048576, 2), "query_ms": round(query_ms, 1),
            "points": len(result["points"]),
        }))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("records", type=int)
    parser.add_argument("--checkout", type=Path, default=Path.cwd())
    args = parser.parse_args()
    if args.records < 1:
        parser.error("Record count must be positive.")
    measure(args.records, args.checkout)
