"""Deterministic operational bundles, provenance, and retention decisions."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any

from .governance import SENSITIVITIES, SENSITIVITY_ORDER


def _canonical_json(payload: dict[str, Any]) -> bytes:
    """Return the canonical JSON representation used for deterministic hashing."""
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


@dataclass(frozen=True, slots=True)
class RetentionPolicy:
    """Explicit lifecycle policy for an operational bundle."""

    policy_id: str
    max_age_days: int | None = None
    max_sensitivity: str = "restricted"

    def __post_init__(self) -> None:
        """Validate and normalize the initialized object state."""
        if not self.policy_id.strip():
            raise ValueError("policy_id must not be empty.")
        if self.max_age_days is not None and self.max_age_days < 0:
            raise ValueError("max_age_days must be non-negative when provided.")
        if self.max_sensitivity not in SENSITIVITY_ORDER:
            raise ValueError(
                f"max_sensitivity must be one of {', '.join(SENSITIVITIES)}."
            )

    def to_dict(self) -> dict[str, Any]:
        """Serialize this object to its canonical dictionary representation."""
        return {
            "policy_id": self.policy_id,
            "max_age_days": self.max_age_days,
            "max_sensitivity": self.max_sensitivity,
        }


@dataclass(frozen=True, slots=True)
class OperationalArtifact:
    """One immutable artifact included in an operational package."""

    artifact_id: str
    path: str
    kind: str
    sha256: str
    size_bytes: int
    sensitivity: str = "internal"
    derived_from: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Validate and normalize the initialized object state."""
        artifact_id = self.artifact_id.replace("\\", "/")
        if (
            not artifact_id.strip()
            or artifact_id.startswith("/")
            or "/" in artifact_id
            or artifact_id in {".", ".."}
        ):
            raise ValueError("artifact_id must be a single relative path component.")
        path = self.path.replace("\\", "/")
        if not path.strip() or path.startswith("/") or ".." in path.split("/"):
            raise ValueError(
                "artifact path must be relative and must not contain '..'."
            )
        if not self.kind.strip():
            raise ValueError("kind must not be empty.")
        if len(self.sha256) != 64 or any(
            ch not in "0123456789abcdef" for ch in self.sha256
        ):
            raise ValueError("sha256 must be a lowercase SHA-256 hexadecimal string.")
        if self.size_bytes < 0:
            raise ValueError("size_bytes must be non-negative.")
        if self.sensitivity not in SENSITIVITY_ORDER:
            raise ValueError(f"sensitivity must be one of {', '.join(SENSITIVITIES)}.")
        if any(not item.strip() for item in self.derived_from):
            raise ValueError("derived_from must not contain blank values.")

    def to_dict(self) -> dict[str, Any]:
        """Serialize this object to its canonical dictionary representation."""
        return {
            "artifact_id": self.artifact_id,
            "path": self.path,
            "kind": self.kind,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "sensitivity": self.sensitivity,
            "derived_from": list(self.derived_from),
        }


@dataclass(frozen=True, slots=True)
class OperationalBundle:
    """Auditable package manifest for operational handoff and inspection."""

    bundle_id: str
    manifest_id: str
    agent_name: str
    engine_version: str
    created_at: datetime
    artifacts: tuple[OperationalArtifact, ...]
    retention_policy: RetentionPolicy | None = None

    def __post_init__(self) -> None:
        """Validate and normalize the initialized object state."""
        for field_name in ("bundle_id", "manifest_id", "agent_name", "engine_version"):
            if not getattr(self, field_name).strip():
                raise ValueError(f"{field_name} must not be empty.")
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware.")
        ids = [item.artifact_id for item in self.artifacts]
        if len(ids) != len(set(ids)):
            raise ValueError("artifact IDs must be unique.")
        known = set(ids)
        for item in self.artifacts:
            unknown = [source for source in item.derived_from if source not in known]
            if unknown:
                raise ValueError(
                    f"artifact {item.artifact_id} references unknown provenance: {', '.join(unknown)}"
                )

    def manifest_payload(self) -> dict[str, Any]:
        """Return the canonical manifest payload for this proof bundle."""
        return {
            "manifest_id": self.manifest_id,
            "agent_name": self.agent_name,
            "engine_version": self.engine_version,
            "created_at": self.created_at.astimezone(UTC).isoformat(),
            "artifacts": [item.to_dict() for item in self.artifacts],
            "retention_policy": None
            if self.retention_policy is None
            else self.retention_policy.to_dict(),
        }

    def computed_manifest_id(self) -> str:
        """Return the deterministic manifest identifier."""
        payload = dict(self.manifest_payload())
        payload.pop("manifest_id", None)
        return sha256(_canonical_json(payload)).hexdigest()

    def computed_bundle_id(self) -> str:
        """Return the deterministic proof-bundle identifier."""
        payload = self.manifest_payload()
        payload["manifest_id"] = self.computed_manifest_id()
        return sha256(_canonical_json(payload)).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        """Serialize this object to its canonical dictionary representation."""
        return {
            "bundle_id": self.bundle_id,
            **self.manifest_payload(),
        }


@dataclass(frozen=True, slots=True)
class RetentionDecision:
    """Deterministic lifecycle decision at a requested point in time."""

    bundle_id: str
    policy_id: str
    state: str
    eligible_at: str | None
    reason: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize this object to its canonical dictionary representation."""
        return {
            "bundle_id": self.bundle_id,
            "policy_id": self.policy_id,
            "state": self.state,
            "eligible_at": self.eligible_at,
            "reason": self.reason,
        }


def assess_retention(
    bundle: OperationalBundle,
    policy: RetentionPolicy,
    *,
    as_of: datetime,
) -> RetentionDecision:
    """Determine whether a bundle remains inside its explicit retention window."""
    if as_of.tzinfo is None:
        raise ValueError("as_of must be timezone-aware.")
    if not bundle.artifacts:
        return RetentionDecision(
            bundle.bundle_id,
            policy.policy_id,
            "retain",
            None,
            "bundle contains no artifacts",
        )
    maximum_rank = SENSITIVITY_ORDER[policy.max_sensitivity]
    above_ceiling = [
        item.artifact_id
        for item in bundle.artifacts
        if SENSITIVITY_ORDER[item.sensitivity] > maximum_rank
    ]
    if above_ceiling:
        return RetentionDecision(
            bundle.bundle_id,
            policy.policy_id,
            "quarantine",
            None,
            "artifacts exceed retention sensitivity ceiling: "
            + ", ".join(sorted(above_ceiling)),
        )
    if policy.max_age_days is None:
        return RetentionDecision(
            bundle.bundle_id,
            policy.policy_id,
            "retain",
            None,
            "no maximum age configured",
        )
    eligible = bundle.created_at.astimezone(UTC) + timedelta(days=policy.max_age_days)
    if as_of.astimezone(UTC) >= eligible:
        return RetentionDecision(
            bundle.bundle_id,
            policy.policy_id,
            "expired",
            eligible.isoformat(),
            f"bundle is {policy.max_age_days} days or older",
        )
    return RetentionDecision(
        bundle.bundle_id,
        policy.policy_id,
        "retain",
        eligible.isoformat(),
        f"bundle remains within the {policy.max_age_days}-day retention window",
    )
