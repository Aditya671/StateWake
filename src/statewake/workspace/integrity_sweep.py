"""Workspace payload integrity sweep helpers."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path


class WorkspaceIntegritySweepError(ValueError):
    """Raised when workspace content-addressed payload integrity fails."""


@dataclass(frozen=True, slots=True)
class WorkspaceIntegritySweepResult:
    """Summarize content-addressed payload verification."""

    checked_payloads: int
    modified_payloads: tuple[str, ...] = ()
    invalid_paths: tuple[str, ...] = ()

    @property
    def healthy(self) -> bool:
        """Return whether all checked payloads matched their content address."""
        return not self.modified_payloads and not self.invalid_paths


def sweep_workspace_payload_integrity(
    workspace_root: Path,
) -> WorkspaceIntegritySweepResult:
    """Verify every content-addressed artifact filename matches its SHA-256 bytes."""
    artifact_root = workspace_root / "artifacts"
    if not artifact_root.exists():
        return WorkspaceIntegritySweepResult(checked_payloads=0)
    checked = 0
    modified: list[str] = []
    invalid: list[str] = []
    for path in sorted(artifact_root.rglob("*")):
        if not path.is_file() or path.name.startswith("."):
            continue
        relative = path.relative_to(artifact_root)
        expected = "".join(relative.parts)
        if len(expected) != 64 or any(ch not in "0123456789abcdef" for ch in expected):
            invalid.append(str(path))
            continue
        actual = _sha256_file(path)
        checked += 1
        if actual != expected:
            modified.append(str(path))
    result = WorkspaceIntegritySweepResult(
        checked_payloads=checked,
        modified_payloads=tuple(modified),
        invalid_paths=tuple(invalid),
    )
    if not result.healthy:
        raise WorkspaceIntegritySweepError("workspace payload integrity sweep failed")
    return result


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


__all__ = [
    "WorkspaceIntegritySweepError",
    "WorkspaceIntegritySweepResult",
    "sweep_workspace_payload_integrity",
]
