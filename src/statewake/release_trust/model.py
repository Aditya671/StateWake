"""Release-trust evidence contracts for StateWake package artifacts.

This package models trust evidence about StateWake releases. It intentionally
stays separate from StateWake evidence chains for external AI systems.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

_HEX64 = re.compile(r"[0-9a-f]{64}")


def _require_text(value: str, field: str) -> None:
    if not value.strip():
        raise ValueError(f"{field} must not be empty.")


def _require_digest(value: str, field: str) -> None:
    if not _HEX64.fullmatch(value):
        raise ValueError(f"{field} must be a lowercase SHA-256 hex digest.")


def _canonical(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(
        dict(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


@dataclass(frozen=True, slots=True)
class ArtifactDigest:
    """Identity and digest of one release artifact."""

    name: str
    sha256: str
    size_bytes: int
    media_type: str = "application/octet-stream"

    def __post_init__(self) -> None:
        """Validate artifact identity and digest fields."""
        _require_text(self.name, "artifact.name")
        _require_text(self.media_type, "artifact.media_type")
        _require_digest(self.sha256, "artifact.sha256")
        if self.size_bytes <= 0:
            raise ValueError("artifact.size_bytes must be positive.")

    def to_dict(self) -> dict[str, Any]:
        """Serialize artifact digest evidence."""
        return {
            "name": self.name,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "media_type": self.media_type,
        }


@dataclass(frozen=True, slots=True)
class SourceIdentity:
    """Source identity used to build a release artifact."""

    distribution: str
    version: str
    source_revision: str
    source_tree_sha256: str
    dependency_lock_sha256: str

    def __post_init__(self) -> None:
        """Validate source and dependency-lock digests."""
        for field in ("distribution", "version", "source_revision"):
            _require_text(str(getattr(self, field)), f"source.{field}")
        _require_digest(self.source_tree_sha256, "source.source_tree_sha256")
        _require_digest(self.dependency_lock_sha256, "source.dependency_lock_sha256")

    def to_dict(self) -> dict[str, Any]:
        """Serialize source identity evidence."""
        return {
            "distribution": self.distribution,
            "version": self.version,
            "source_revision": self.source_revision,
            "source_tree_sha256": self.source_tree_sha256,
            "dependency_lock_sha256": self.dependency_lock_sha256,
        }


@dataclass(frozen=True, slots=True)
class BuildProvenance:
    """Reconstructable build context for a release artifact."""

    builder: str
    build_type: str
    build_steps: tuple[str, ...]
    environment: Mapping[str, str]
    started_at: str | None = None
    finished_at: str | None = None

    def __post_init__(self) -> None:
        """Validate build provenance fields."""
        object.__setattr__(self, "build_steps", tuple(self.build_steps))
        object.__setattr__(self, "environment", dict(self.environment))
        _require_text(self.builder, "build.builder")
        _require_text(self.build_type, "build.build_type")
        if not self.build_steps:
            raise ValueError("build.build_steps must not be empty.")
        if any(not item.strip() for item in self.build_steps):
            raise ValueError("build.build_steps must not contain blank steps.")
        if not self.environment:
            raise ValueError("build.environment must not be empty.")
        if any(
            not key.strip() or not value.strip()
            for key, value in self.environment.items()
        ):
            raise ValueError(
                "build.environment must contain non-empty keys and values."
            )

    def to_dict(self) -> dict[str, Any]:
        """Serialize build provenance evidence."""
        return {
            "builder": self.builder,
            "build_type": self.build_type,
            "build_steps": list(self.build_steps),
            "environment": dict(sorted(self.environment.items())),
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


@dataclass(frozen=True, slots=True)
class ExternalEvidence:
    """Digest-bound external release evidence, such as SBOM, scan, or signature."""

    evidence_type: str
    name: str
    digest: str
    status: str
    reference: str | None = None
    limitation: str | None = None

    def __post_init__(self) -> None:
        """Validate external release evidence fields."""
        _require_text(self.evidence_type, "external_evidence.evidence_type")
        _require_text(self.name, "external_evidence.name")
        _require_digest(self.digest, "external_evidence.digest")
        if self.status not in {"present", "passed", "failed", "limitation"}:
            raise ValueError("external_evidence.status is unsupported.")
        if self.status == "limitation" and not (self.limitation or "").strip():
            raise ValueError("limitation evidence must explain the limitation.")
        if self.status in {"present", "passed"} and (self.limitation or "").strip():
            raise ValueError("present/passed evidence must not carry a limitation.")

    def to_dict(self) -> dict[str, Any]:
        """Serialize external release evidence."""
        return {
            "evidence_type": self.evidence_type,
            "name": self.name,
            "digest": self.digest,
            "status": self.status,
            "reference": self.reference,
            "limitation": self.limitation,
        }


@dataclass(frozen=True, slots=True)
class HumanReleaseDecision:
    """Human release decision boundary, separate from evidence verification."""

    actor_ref: str
    role: str
    decision: str
    decided_at: str | None = None
    scope: str = "release-publication"
    basis_digest: str | None = None

    def __post_init__(self) -> None:
        """Validate human release decision fields."""
        for field in ("actor_ref", "role", "scope"):
            _require_text(str(getattr(self, field)), f"human_decision.{field}")
        if self.decision not in {"approved", "rejected", "pending", "not-requested"}:
            raise ValueError("human_decision.decision is unsupported.")
        if self.basis_digest is not None:
            _require_digest(self.basis_digest, "human_decision.basis_digest")

    def to_dict(self) -> dict[str, Any]:
        """Serialize human release decision evidence."""
        return {
            "actor_ref": self.actor_ref,
            "role": self.role,
            "decision": self.decision,
            "decided_at": self.decided_at,
            "scope": self.scope,
            "basis_digest": self.basis_digest,
        }


@dataclass(frozen=True, slots=True)
class ReleaseTrustBundle:
    """Portable StateWake release-trust evidence bundle.

    The bundle verifies release evidence. It does not by itself authorize
    publishing; that remains a separate human decision.
    """

    schema_version: str
    source: SourceIdentity
    artifacts: tuple[ArtifactDigest, ...]
    build: BuildProvenance
    tests: tuple[ExternalEvidence, ...]
    sbom: ExternalEvidence | None
    vulnerability_scan: ExternalEvidence | None
    signature: ExternalEvidence | None
    provenance: ExternalEvidence | None
    human_decision: HumanReleaseDecision
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Validate the release-trust bundle as a complete claim unit."""
        if self.schema_version != "1":
            raise ValueError("unsupported release trust bundle schema_version.")
        if not self.artifacts:
            raise ValueError(
                "release trust bundle requires at least one artifact digest."
            )
        if not self.tests:
            raise ValueError(
                "release trust bundle requires at least one test evidence item."
            )
        if any(item.status != "passed" for item in self.tests):
            raise ValueError("all release trust test evidence must have passed status.")
        if any(not item.strip() for item in self.limitations):
            raise ValueError("limitations must not contain blank values.")
        if self.sbom is None:
            raise ValueError(
                "release trust bundle requires SBOM evidence or explicit limitation evidence."
            )
        if self.vulnerability_scan is None:
            raise ValueError(
                "release trust bundle requires vulnerability-scan evidence or explicit limitation evidence."
            )
        if self.provenance is None:
            raise ValueError("release trust bundle requires build-provenance evidence.")
        if self.signature is None:
            raise ValueError(
                "release trust bundle requires signature evidence or explicit limitation evidence."
            )
        for item in (
            self.sbom,
            self.vulnerability_scan,
            self.signature,
            self.provenance,
        ):
            if item.status == "failed":
                raise ValueError(f"release trust evidence failed: {item.evidence_type}")
        if self.signature.status == "passed":
            raise ValueError(
                "signature evidence must be present or limitation, not passed."
            )
        if (
            self.signature.status == "present"
            and self.signature.evidence_type != "signature"
        ):
            raise ValueError("signature evidence must use evidence_type='signature'.")
        if (
            self.signature.status == "limitation"
            and self.signature.limitation not in self.limitations
        ):
            raise ValueError(
                "signature limitation must also be listed in bundle limitations."
            )
        if (
            self.human_decision.decision == "approved"
            and not self.human_decision.basis_digest
        ):
            raise ValueError("approved release decision requires a basis digest.")

    def payload(self) -> dict[str, Any]:
        """Return the digest-bound bundle payload without the derived digest."""
        return {
            "schema_version": self.schema_version,
            "source": self.source.to_dict(),
            "artifacts": [item.to_dict() for item in self.artifacts],
            "build": self.build.to_dict(),
            "tests": [item.to_dict() for item in self.tests],
            "sbom": self.sbom.to_dict() if self.sbom else None,
            "vulnerability_scan": (
                self.vulnerability_scan.to_dict() if self.vulnerability_scan else None
            ),
            "signature": self.signature.to_dict() if self.signature else None,
            "provenance": self.provenance.to_dict() if self.provenance else None,
            "human_decision": self.human_decision.to_dict(),
            "limitations": list(self.limitations),
        }

    @property
    def digest(self) -> str:
        """Return the canonical release-trust bundle digest."""
        return sha256(_canonical(self.payload())).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        """Serialize the bundle with its derived digest."""
        return {**self.payload(), "digest": self.digest}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ReleaseTrustBundle:
        """Recreate and verify a release-trust bundle from serialized JSON."""
        bundle = cls(
            schema_version=str(payload["schema_version"]),
            source=SourceIdentity(**payload["source"]),
            artifacts=tuple(ArtifactDigest(**item) for item in payload["artifacts"]),
            build=BuildProvenance(**payload["build"]),
            tests=tuple(ExternalEvidence(**item) for item in payload["tests"]),
            sbom=ExternalEvidence(**payload["sbom"]) if payload.get("sbom") else None,
            vulnerability_scan=ExternalEvidence(**payload["vulnerability_scan"])
            if payload.get("vulnerability_scan")
            else None,
            signature=ExternalEvidence(**payload["signature"])
            if payload.get("signature")
            else None,
            provenance=ExternalEvidence(**payload["provenance"])
            if payload.get("provenance")
            else None,
            human_decision=HumanReleaseDecision(**payload["human_decision"]),
            limitations=tuple(str(item) for item in payload.get("limitations", ())),
        )
        supplied = str(payload.get("digest", ""))
        if supplied and supplied != bundle.digest:
            raise ValueError("release trust bundle digest mismatch.")
        return bundle


__all__ = [
    "ArtifactDigest",
    "BuildProvenance",
    "ExternalEvidence",
    "HumanReleaseDecision",
    "ReleaseTrustBundle",
    "SourceIdentity",
]
