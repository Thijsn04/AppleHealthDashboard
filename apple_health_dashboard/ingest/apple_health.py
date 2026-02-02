from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class HealthRecord:
    """A normalized representation of an Apple Health <Record/>."""

    type: str
    start_at: datetime
    end_at: datetime
    creation_at: datetime | None
    source_name: str | None
    unit: str | None
    value: float | None
    value_str: str | None


def _parse_apple_datetime(value: str) -> datetime:
    """Parse Apple Health datetime strings.

    Typical format: '2020-01-01 12:34:56 +0100'
    """
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S %z")


def iter_health_records_from_export_xml(export_xml_path: Path) -> Iterator[HealthRecord]:
    """Stream records from an Apple Health export.xml.

    This uses iterparse to avoid loading the full XML into memory.
    """
    context = ET.iterparse(export_xml_path, events=("end",))

    for _event, elem in context:
        if elem.tag != "Record":
            continue

        attrib = elem.attrib
        record_type = attrib.get("type")
        start = attrib.get("startDate")
        end = attrib.get("endDate")
        creation = attrib.get("creationDate")

        if not record_type or not start or not end:
            elem.clear()
            continue

        unit = attrib.get("unit")
        source_name = attrib.get("sourceName")

        raw_value = attrib.get("value")
        value: float | None
        value_str: str | None
        if raw_value is None:
            value = None
            value_str = None
        else:
            try:
                value = float(raw_value)
                value_str = None
            except ValueError:
                value = None
                value_str = raw_value

        rec = HealthRecord(
            type=record_type,
            start_at=_parse_apple_datetime(start),
            end_at=_parse_apple_datetime(end),
            creation_at=_parse_apple_datetime(creation) if creation else None,
            source_name=source_name,
            unit=unit,
            value=value,
            value_str=value_str,
        )

        yield rec
        elem.clear()


def load_export_xml_from_path(export_xml_path: Path) -> list[HealthRecord]:
    """Load all records into memory.

    Good for a first version; later we can persist to SQLite for speed.
    """
    return list(iter_health_records_from_export_xml(export_xml_path))


def load_export_xml(export_xml: str | Path) -> list[HealthRecord]:
    """Convenience overload."""
    path = Path(export_xml)
    return load_export_xml_from_path(path)


def iter_records(records: Iterable[HealthRecord]) -> Iterator[HealthRecord]:
    """A tiny helper to keep services decoupled from concrete container types."""
    yield from records
