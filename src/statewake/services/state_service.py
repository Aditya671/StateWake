"""Application services for system-state snapshots."""

from pathlib import Path

from statewake.utils.json_support import load_object

from ..domain.state import SystemState


def load_state(path: Path) -> SystemState:
    """Load and validate a persisted reliability state."""
    payload = load_object(path)
    if not isinstance(payload, dict):
        raise ValueError("State root must be a JSON object.")
    return SystemState.from_dict(payload)
