from __future__ import annotations

import logging
from pathlib import Path


def configure_logging(log_dir: Path | None = None) -> None:
    """Configure basic local logging.

    - Logs to console
    - Logs to a local file (default: ./.tmp/app.log)

    This is intentionally simple and local-only.
    """
    if log_dir is None:
        log_dir = Path.cwd() / ".tmp"
    log_dir.mkdir(parents=True, exist_ok=True)

    log_path = log_dir / "app.log"

    root = logging.getLogger()
    if root.handlers:
        # Avoid duplicate handlers on Streamlit reruns.
        return

    root.setLevel(logging.INFO)

    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s - %(message)s")

    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)

    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setLevel(logging.INFO)
    fh.setFormatter(fmt)

    root.addHandler(ch)
    root.addHandler(fh)
