"""Configuration for a local StateWake workspace."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class WorkspaceConfiguration:
    """Describe the filesystem root and manifest contract for a workspace."""

    root: Path
    schema_version: str = "1"

    def __post_init__(self) -> None:
        """Validate configuration values without creating filesystem state."""
        if not self.schema_version.strip():
            raise ValueError("schema_version must not be blank.")

    @property
    def manifest_path(self) -> Path:
        """Return the workspace manifest path."""
        return self.root / "manifest.json"

    @property
    def database_path(self) -> Path:
        """Return the reserved operational-index path."""
        return self.root / "statewake.db"

    @property
    def artifact_root(self) -> Path:
        """Return the existing StateWake artifact-store root."""
        return self.root / "artifacts"

    @property
    def receipt_root(self) -> Path:
        """Return the existing StateWake receipt-store root."""
        return self.root / "receipts"

    @property
    def state_root(self) -> Path:
        """Return the existing StateWake state-store root."""
        return self.root / "state"

    @property
    def proof_root(self) -> Path:
        """Return the existing StateWake proof-store root."""
        return self.root / "proofs"

    @property
    def export_root(self) -> Path:
        """Return the workspace export root."""
        return self.root / "exports"

    @property
    def manifest_root(self) -> Path:
        """Return the workspace manifest directory."""
        return self.root / "manifests"

    @property
    def lock_root(self) -> Path:
        """Return the workspace lock directory."""
        return self.root / "locks"

    def required_directories(self) -> tuple[Path, ...]:
        """Return directories created by workspace initialization."""
        return (
            self.root,
            self.artifact_root,
            self.receipt_root,
            self.state_root,
            self.proof_root,
            self.export_root,
            self.export_root / "parquet",
            self.export_root / "csv",
            self.export_root / "xlsx",
            self.export_root / "json",
            self.manifest_root,
            self.lock_root,
        )


__all__ = ["WorkspaceConfiguration"]
