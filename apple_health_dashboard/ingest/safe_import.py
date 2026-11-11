"""Safe preparation and inspection of Apple Health XML and ZIP exports."""

from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath

from apple_health_dashboard.ingest.apple_health_records import _parse_apple_datetime
from apple_health_dashboard.ingest.xml_stream import export_elements


class ImportValidationError(ValueError):
    """Raised when an uploaded export is invalid or exceeds safe import limits."""


@dataclass(frozen=True)
class ImportLimits:
    """Explicit limits that protect the local importer from accidental or hostile input."""

    max_input_bytes: int = 1_073_741_824
    max_uncompressed_xml_bytes: int = 2_147_483_648
    max_compression_ratio: int = 100


@dataclass(frozen=True)
class PreparedExport:
    """A validated XML path plus facts needed for an import manifest."""

    xml_path: Path
    source_sha256: str
    source_size_bytes: int
    extracted_from_zip: bool


@dataclass(frozen=True)
class ExportPreview:
    """A bounded, no-persistence inspection of an Apple Health export."""

    record_count: int
    workout_count: int
    activity_summary_count: int
    record_type_count: int
    earliest_start: str | None
    latest_end: str | None


def prepare_export(
    source_path: Path,
    temporary_dir: Path,
    *,
    limits: ImportLimits | None = None,
) -> PreparedExport:
    """Validate XML or ZIP input and return a safe path to the export XML.

    ZIP archives are never extracted wholesale. Only a single approved `export.xml`
    member is streamed to a generated temporary file after size and ratio checks.
    """
    limits = limits or ImportLimits()
    if not source_path.is_file():
        raise ImportValidationError("The selected export file does not exist.")
    if source_path.stat().st_size > limits.max_input_bytes:
        raise ImportValidationError("The selected export exceeds the configured input-size limit.")

    suffix = source_path.suffix.lower()
    if suffix == ".xml":
        return PreparedExport(
            xml_path=source_path,
            source_sha256=_sha256_file(source_path),
            source_size_bytes=source_path.stat().st_size,
            extracted_from_zip=False,
        )
    if suffix != ".zip":
        raise ImportValidationError("Select an Apple Health export.xml or export.zip file.")

    temporary_dir.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(source_path) as archive:
            member = _find_export_xml(archive, limits)
            destination = temporary_dir / f"apple-health-{_sha256_file(source_path)[:16]}.xml"
            _stream_member(archive, member, destination, limits)
    except zipfile.BadZipFile as exc:
        raise ImportValidationError("The selected ZIP file is invalid or corrupted.") from exc

    return PreparedExport(
        xml_path=destination,
        source_sha256=_sha256_file(source_path),
        source_size_bytes=source_path.stat().st_size,
        extracted_from_zip=True,
    )


def preview_export(xml_path: Path) -> ExportPreview:
    """Inspect top-level export elements without importing or retaining observations."""
    record_count = 0
    workout_count = 0
    activity_summary_count = 0
    record_types: set[str] = set()
    earliest: tuple[datetime, str] | None = None
    latest: tuple[datetime, str] | None = None

    try:
        for element in export_elements(xml_path):
            if element.tag == "Record":
                record_count += 1
                record_type = element.attrib.get("type")
                if record_type:
                    record_types.add(record_type)
            elif element.tag == "Workout":
                workout_count += 1
            elif element.tag == "ActivitySummary":
                activity_summary_count += 1
            if element.tag in {"Record", "Workout"}:
                if raw_start := element.get("startDate"):
                    instant = _parse_apple_datetime(raw_start)
                    if earliest is None or instant < earliest[0]:
                        earliest = (instant, raw_start)
                if raw_end := element.get("endDate"):
                    instant = _parse_apple_datetime(raw_end)
                    if latest is None or instant > latest[0]:
                        latest = (instant, raw_end)
    except (ET.ParseError, ValueError) as exc:
        raise ImportValidationError("The export XML is malformed or incomplete.") from exc

    return ExportPreview(
        record_count=record_count,
        workout_count=workout_count,
        activity_summary_count=activity_summary_count,
        record_type_count=len(record_types),
        earliest_start=earliest[1] if earliest else None,
        latest_end=latest[1] if latest else None,
    )


def _find_export_xml(archive: zipfile.ZipFile, limits: ImportLimits) -> zipfile.ZipInfo:
    candidates = []
    for info in archive.infolist():
        path = PurePosixPath(info.filename)
        if path.is_absolute() or ".." in path.parts:
            raise ImportValidationError("The ZIP contains an unsafe file path.")
        if path.name == "export.xml":
            candidates.append(info)

    if not candidates:
        raise ImportValidationError("No export.xml was found in the selected ZIP file.")
    member = min(candidates, key=lambda info: len(info.filename))
    if member.file_size > limits.max_uncompressed_xml_bytes:
        raise ImportValidationError("The export XML exceeds the configured uncompressed-size limit.")
    if member.file_size and not member.compress_size:
        raise ImportValidationError("The ZIP has an invalid compressed export member.")
    if member.compress_size and member.file_size / member.compress_size > limits.max_compression_ratio:
        raise ImportValidationError("The ZIP compression ratio exceeds the configured safety limit.")
    return member


def _stream_member(archive: zipfile.ZipFile, member: zipfile.ZipInfo, destination: Path, limits: ImportLimits) -> None:
    written = 0
    try:
        with archive.open(member) as source, destination.open("wb") as destination_file:
            while chunk := source.read(1_048_576):
                written += len(chunk)
                if written > limits.max_uncompressed_xml_bytes:
                    raise ImportValidationError("The extracted export exceeds the configured size limit.")
                destination_file.write(chunk)
    except Exception:
        destination.unlink(missing_ok=True)
        raise


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1_048_576):
            digest.update(chunk)
    return digest.hexdigest()
