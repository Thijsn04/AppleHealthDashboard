from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


def _parse_apple_datetime(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S %z")


def _to_float(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


@dataclass(frozen=True)
class Record:
    """Normalized representation of an Apple Health <Record/>."""

    record_type: str
    start_at: datetime
    end_at: datetime
    creation_at: datetime | None
    source_name: str | None
    unit: str | None
    value: float | None
    value_str: str | None


@dataclass(frozen=True)
class RecordMetadata:
    record_hash: str
    key: str
    value: str


def stable_record_hash(record: Record) -> str:
    import hashlib

    payload = (
        record.record_type,
        record.start_at.isoformat(),
        record.end_at.isoformat(),
        record.creation_at.isoformat() if record.creation_at else "",
        record.source_name or "",
        record.unit or "",
        "" if record.value is None else repr(record.value),
        record.value_str or "",
    )
    return hashlib.sha256("|".join(payload).encode("utf-8")).hexdigest()


def iter_records_from_export_xml(
    export_xml_path: Path,
) -> Iterator[tuple[Record, list[RecordMetadata]]]:
    """Stream records (and their metadata) from an Apple Health export.xml."""

    context = ET.iterparse(export_xml_path, events=("end",))
    for _event, elem in context:
        if elem.tag != "Record":
            continue

        attrib = elem.attrib
        record_type = attrib.get("type")
        start = attrib.get("startDate")
        end = attrib.get("endDate")

        if not record_type or not start or not end:
            elem.clear()
            continue

        raw_value = attrib.get("value")
        value = _to_float(raw_value)
        value_str = None if value is not None else raw_value

        record = Record(
            record_type=record_type,
            start_at=_parse_apple_datetime(start),
            end_at=_parse_apple_datetime(end),
            creation_at=_parse_apple_datetime(attrib.get("creationDate"))
            if attrib.get("creationDate")
            else None,
            source_name=attrib.get("sourceName"),
            unit=attrib.get("unit"),
            value=value,
            value_str=value_str,
        )

        r_hash = stable_record_hash(record)

        metadata: list[RecordMetadata] = []
        for child in list(elem):
            if child.tag != "MetadataEntry":
                continue
            key = child.attrib.get("key")
            m_value = child.attrib.get("value")
            if key is None or m_value is None:
                continue
            metadata.append(RecordMetadata(record_hash=r_hash, key=key, value=m_value))

        yield record, metadata
        elem.clear()
