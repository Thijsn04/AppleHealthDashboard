from __future__ import annotations

import subprocess
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {".css", ".html", ".js", ".json", ".md", ".py", ".toml", ".ts", ".tsx", ".yaml", ".yml"}


def test_repository_contains_no_em_dashes() -> None:
    """Check versioned source and documentation without opening user data files."""
    paths = subprocess.check_output(
        ["git", "ls-files", "-z"], cwd=REPOSITORY_ROOT, text=True, encoding="utf-8",
    ).split("\0")
    offenders = []
    for name in paths:
        path = REPOSITORY_ROOT / name
        if path.suffix in TEXT_SUFFIXES and path.is_file() and chr(0x2014) in path.read_text(encoding="utf-8"):
            offenders.append(name)
    assert not offenders, f"Em dashes are not permitted: {', '.join(offenders)}"
