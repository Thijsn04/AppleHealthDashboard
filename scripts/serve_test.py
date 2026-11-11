"""Run the built app against an isolated synthetic profile."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory

import uvicorn

from apple_health_dashboard.api import routes
from apple_health_dashboard.api.app import create_app
from apple_health_dashboard.api.imports import LocalImportStaging

if __name__ == "__main__":
    with TemporaryDirectory(prefix="apple-health-browser-") as profile:
        previous = Path.cwd()
        os.chdir(profile)
        try:
            routes._staging = LocalImportStaging(Path(profile) / ".tmp" / "api-imports")
            uvicorn.run(create_app(), host="127.0.0.1", port=8765)
        finally:
            os.chdir(previous)
