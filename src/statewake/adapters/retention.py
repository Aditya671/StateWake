"""In-process retention policy adapter for host-managed evidence stores."""

from __future__ import annotations

from datetime import datetime

from ..domain.retention import EvidenceRetentionRequirement


class InMemoryEvidenceRetentionAdapter:
    """Reference retention contract for artifact lifecycle management."""

    def __init__(self) -> None:
        """Initialize the instance."""
        self._requirements: dict[str, EvidenceRetentionRequirement] = {}

    def require_retention(self, requirement: EvidenceRetentionRequirement) -> None:
        """Apply a retention requirement to evidence."""
        existing = self._requirements.get(requirement.artifact_id)
        if existing is None or requirement.retain_until >= existing.retain_until:
            self._requirements[requirement.artifact_id] = requirement

    def release_retention(self, artifact_id: str) -> None:
        """Release a previously applied retention requirement."""
        existing = self._requirements.get(artifact_id)
        if existing is not None and not existing.legal_hold:
            del self._requirements[artifact_id]

    def can_delete(self, artifact_id: str, *, now: datetime) -> bool:
        """Return whether evidence can be deleted under current holds."""
        if now.tzinfo is None:
            raise ValueError("now must be timezone-aware.")
        requirement = self._requirements.get(artifact_id)
        if requirement is None:
            return True
        if requirement.legal_hold:
            return False
        return now >= requirement.retain_until

    def is_held(self, artifact_id: str) -> bool:
        """Return whether evidence is currently held."""
        requirement = self._requirements.get(artifact_id)
        return bool(requirement and requirement.legal_hold)
