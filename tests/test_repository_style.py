from __future__ import annotations

from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_DIRECTORIES = {
    ".git",
    ".idea",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "apple_health_dashboard.egg-info",
    "dist",
    "node_modules",
}


def test_repository_contains_no_em_dashes() -> None:
    """Keep the project typography rule enforceable instead of relying on review alone."""
    em_dash = chr(0x2014)
    offenders: list[str] = []
    for path in REPOSITORY_ROOT.rglob("*"):
        if not path.is_file() or EXCLUDED_DIRECTORIES.intersection(path.parts):
            continue
        try:
            if em_dash in path.read_text(encoding="utf-8"):
                offenders.append(str(path.relative_to(REPOSITORY_ROOT)))
        except UnicodeDecodeError:
            continue

    assert not offenders, f"Em dashes are not permitted: {', '.join(offenders)}"
