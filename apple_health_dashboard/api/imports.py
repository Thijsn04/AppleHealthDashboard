"""Short-lived local staging for explicitly selected import files."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from apple_health_dashboard.ingest.safe_import import (
    ExportPreview,
    ImportLimits,
    ImportValidationError,
    PreparedExport,
    prepare_export,
    preview_export,
)


@dataclass(frozen=True)
class StagedImport:
    """A temporary local export awaiting the user's explicit import confirmation."""

    ticket_id: str
    display_name: str
    prepared_export: PreparedExport
    preview: ExportPreview


class LocalImportStaging:
    """Keep explicit local uploads only until confirmation or process restart."""

    def __init__(self, temporary_dir: Path, *, limits: ImportLimits | None = None) -> None:
        self._temporary_dir = temporary_dir
        self._limits = limits or ImportLimits()
        self._tickets: dict[str, StagedImport] = {}
        self._lock = asyncio.Lock()

    async def stage(self, upload: UploadFile) -> StagedImport:
        """Stream one selected file to local temporary storage and inspect it."""
        suffix = Path(upload.filename or "export").suffix.lower()
        if suffix not in {".xml", ".zip"}:
            raise ImportValidationError("Select an Apple Health export.xml or export.zip file.")

        self._temporary_dir.mkdir(parents=True, exist_ok=True)
        upload_path = self._temporary_dir / f"upload-{uuid4().hex}{suffix}"
        try:
            await self._write_upload(upload, upload_path)
            prepared = await asyncio.to_thread(prepare_export, upload_path, self._temporary_dir, limits=self._limits)
            preview = await asyncio.to_thread(preview_export, prepared.xml_path)
            if prepared.extracted_from_zip:
                upload_path.unlink(missing_ok=True)
        except Exception:
            upload_path.unlink(missing_ok=True)
            raise
        finally:
            await upload.close()

        staged = StagedImport(
            ticket_id=uuid4().hex,
            display_name=Path(upload.filename or "Apple Health export").name,
            prepared_export=prepared,
            preview=preview,
        )
        async with self._lock:
            self._tickets[staged.ticket_id] = staged
        return staged

    async def consume(self, ticket_id: str) -> StagedImport | None:
        """Claim a ticket once so concurrent requests cannot import it twice."""
        async with self._lock:
            return self._tickets.pop(ticket_id, None)

    def discard(self, staged: StagedImport) -> None:
        """Delete all application-managed temporary data for one staged import."""
        staged.prepared_export.xml_path.unlink(missing_ok=True)

    async def _write_upload(self, upload: UploadFile, destination: Path) -> None:
        written = 0
        try:
            with destination.open("wb") as target:
                while chunk := await upload.read(1_048_576):
                    written += len(chunk)
                    if written > self._limits.max_input_bytes:
                        raise ImportValidationError("The selected export exceeds the configured input-size limit.")
                    target.write(chunk)
        except Exception:
            destination.unlink(missing_ok=True)
            raise
