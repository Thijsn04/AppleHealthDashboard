from __future__ import annotations

import argparse
from pathlib import Path

from apple_health_dashboard.ingest.apple_health import load_export_xml_from_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Apple Health Dashboard helper CLI")
    parser.add_argument(
        "export_xml",
        nargs="?",
        type=Path,
        help="Path to Apple Health export.xml (optional; used for a quick parse smoke-test)",
    )

    args = parser.parse_args()

    if args.export_xml is None:
        print(
            "This project is primarily a Streamlit dashboard.\n"
            "Run: streamlit run app.py\n"
            "Optionally: python main.py path\\to\\export.xml (quick parse smoke-test)"
        )
        return

    records = load_export_xml_from_path(args.export_xml)
    print(f"Parsed {len(records):,} records from {args.export_xml}")


if __name__ == "__main__":
    main()
