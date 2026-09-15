"""Evidence retention and legal-hold contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True, slots=True)
class EvidenceRetentionRequirement:
    """Host-facing retention requirement for evidence supporting a reliability claim."""

    artifact_id: str
    retain_until: datetime
    legal_hold: bool = False
    policy_id: str = "default"

    def __post_init__(self) -> None:
        """Validate and normalize the instance after initialization."""
        if not self.artifact_id.strip() or not self.policy_id.strip():
            raise ValueError("artifact_id and policy_id must not be empty.")
        if self.retain_until.tzinfo is None:
            raise ValueError("retain_until must be timezone-aware.")


class EvidenceRetentionAdapter(Protocol):
    """Adapter contract; actual storage deletion remains host-specific."""

    def require_retention(self, requirement: EvidenceRetentionRequirement) -> None:
        """Record or enforce a retention requirement."""
        ...

    def release_retention(self, artifact_id: str) -> None:
        """Release an ordinary retention marker; legal holds remain independently managed."""
        ...

    def can_delete(self, artifact_id: str, *, now: datetime) -> bool:
        """Return whether deletion is currently permitted."""
        ...
