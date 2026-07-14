"""FastAPI application factory for the local analyzer API."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apple_health_dashboard.api.routes import router


def create_app() -> FastAPI:
    """Create the local-only API application.

    The API intentionally accepts requests only from the bundled local frontend during
    development. Deployments that expose it beyond localhost must configure an explicit
    trusted origin list and an authenticated transport.
    """
    app = FastAPI(
        title="Apple Health Analyzer API",
        version="0.2.0",
        description=(
            "A local-only API for importing, inspecting, and analyzing Apple Health exports. "
            "It is not a medical device and does not provide medical advice."
        ),
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    app.include_router(router, prefix="/api/v1")
    return app


app = create_app()
