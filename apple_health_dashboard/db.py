from __future__ import annotations

from pathlib import Path


def default_db_path() -> Path:
    """Default location for the local DuckDB database.

    We keep it inside the project folder by default. If you want a different
    location later (e.g., user home), we can make this configurable.
    """
    return Path.cwd() / "health.duckdb"
