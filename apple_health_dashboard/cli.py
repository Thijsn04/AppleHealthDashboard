"""Command-line interface for the local API and diagnostics."""

from __future__ import annotations

import argparse

import uvicorn

from apple_health_dashboard.api.app import create_app


def main() -> None:
    """Run a local development server or print the available command help."""
    parser = argparse.ArgumentParser(prog="apple-health", description="Apple Health Analyzer")
    subparsers = parser.add_subparsers(dest="command")
    serve_parser = subparsers.add_parser("serve", help="Start the local API server")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8000)

    args = parser.parse_args()
    if args.command == "serve":
        uvicorn.run(create_app(), host=args.host, port=args.port)
        return
    parser.print_help()


if __name__ == "__main__":
    main()
