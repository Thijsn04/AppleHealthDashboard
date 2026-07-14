"""ASGI entry point for local development and production packaging."""

from apple_health_dashboard.api.app import app
from apple_health_dashboard.cli import main

__all__ = ["app"]


if __name__ == "__main__":
    main()
