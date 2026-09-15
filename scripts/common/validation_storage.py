"""Provide deterministic repository-local storage for validation harnesses."""

from __future__ import annotations

from pathlib import Path


def prepare_validation_database(path: Path) -> Path:
    """Create the validation directory and remove stale SQLite database sidecars."""
    path.parent.mkdir(parents=True, exist_ok=True)
    for candidate in (path, Path(f"{path}-wal"), Path(f"{path}-shm")):
        candidate.unlink(missing_ok=True)
    return path
