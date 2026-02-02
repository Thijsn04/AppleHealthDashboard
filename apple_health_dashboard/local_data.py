from __future__ import annotations

import shutil
from pathlib import Path


def local_tmp_dir() -> Path:
    return Path.cwd() / ".tmp"


def local_db_path() -> Path:
    return Path.cwd() / "health.db"


def delete_local_data() -> None:
    """Delete local-only data artifacts.

    Removes:
      - ./health.db
      - ./.tmp/

    Safe to call even if they don't exist.
    """
    db = local_db_path()
    if db.exists():
        db.unlink()

    tmp = local_tmp_dir()
    if tmp.exists():
        shutil.rmtree(tmp, ignore_errors=True)
