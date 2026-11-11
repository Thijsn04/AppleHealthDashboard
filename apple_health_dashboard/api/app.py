"""Local API and the optional built React application."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from apple_health_dashboard.api import routes
from apple_health_dashboard.db import default_db_path
from apple_health_dashboard.ingest.safe_import import ImportLimits
from apple_health_dashboard.storage.duckdb_store import init_db, open_db

_LOOPBACK = {"localhost", "127.0.0.1", "::1"}


async def _prune_staging() -> None:
    while True:
        await asyncio.sleep(60)
        await routes._staging.prune()


@asynccontextmanager
async def _lifespan(app: FastAPI):
    path = default_db_path()
    if path.exists():
        connection = open_db(path)
        try:
            init_db(connection)
        finally:
            connection.close()
    worker = asyncio.create_task(_prune_staging())
    try:
        yield
    finally:
        worker.cancel()
        with suppress(asyncio.CancelledError):
            await worker
        await routes._staging.close()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Apple Health Analyzer API",
        version="0.2.0",
        lifespan=_lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1"])

    @app.middleware("http")
    async def local_requests(request: Request, call_next):
        if request.url.path.startswith("/api/"):
            origin = request.headers.get("origin")
            if origin:
                try:
                    parsed = urlsplit(origin)
                    allowed = parsed.scheme == "http" and parsed.hostname in _LOOPBACK
                except ValueError:
                    allowed = False
                if not allowed:
                    return JSONResponse({"detail": "A local origin is required."}, status_code=403)
            if request.headers.get("sec-fetch-site") == "cross-site":
                return JSONResponse({"detail": "Cross-site requests are unavailable."}, status_code=403)
            if request.method == "POST" and request.url.path == "/api/v1/imports/preview":
                size = request.headers.get("content-length", "")
                if not size.isascii() or not size.isdecimal():
                    return JSONResponse({"detail": "Upload size is required."}, status_code=411)
                if len(size) > 12 or int(size) > ImportLimits().max_input_bytes + 1_048_576:
                    return JSONResponse({"detail": "The selected export is too large."}, status_code=413)
            response = await call_next(request)
            response.headers["Cache-Control"] = "no-store"
            return response
        return await call_next(request)

    app.include_router(routes.router, prefix="/api/v1")
    dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if (dist / "index.html").is_file() and (dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def frontend(path: str):
            if path == "api" or path.startswith("api/"):
                return JSONResponse({"detail": "Not found"}, status_code=404)
            return FileResponse(dist / "index.html", headers={"Cache-Control": "no-cache"})

    return app


app = create_app()
