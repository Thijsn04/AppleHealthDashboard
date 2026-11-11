from __future__ import annotations

import shutil
from pathlib import Path


def local_tmp_dir() -> Path:
    return Path.cwd() / ".tmp"


def local_db_path() -> Path:
    return Path.cwd() / "health.duckdb"


def delete_local_data() -> None:
    """Remove the database and API staging files with the app stopped."""
    db = local_db_path()
    db.unlink(missing_ok=True)
    db.with_suffix(".duckdb.wal").unlink(missing_ok=True)
    for folder in (db.with_suffix(".duckdb.tmp"), local_tmp_dir() / "api-imports"):
        if folder.exists():
            shutil.rmtree(folder)
