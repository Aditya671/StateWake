"""Portable V1 reliability-proof bundle contracts built on OperationalBundle."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from statewake.utils.json_support import JsonValue

from .cryptographic_trust import CryptographicProfile
from .reliability_attestation_trust_context import ReliabilityAttestationTrustContext
from .reliability_lineage import ReliabilityLineageClosure


def _canonical(payload: Mapping[str, JsonValue]) -> bytes:
    """Return the canonical representation used for deterministic identity and signing."""
    return json.dumps(
        dict(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


@dataclass(frozen=True, slots=True)
class ReliabilityProofSource:
    """Mapping from one evidence-chain source reference to one packaged artifact."""

    reference_key: str
    source: str
    artifact_id: str
    digest: str
    reference_digest: str | None = None

    def __post_init__(self) -> None:
        """Validate and normalize the initialized object state."""
        if (
            not self.reference_key.strip()
            or not self.source.strip()
            or not self.artifact_id.strip()
        ):
            raise ValueError(
                "reference_key, source, and artifact_id must not be empty."
            )
        if len(self.digest) != 64 or any(
            ch not in "0123456789abcdef" for ch in self.digest
        ):
            raise ValueError("digest must be lowercase SHA-256 hex.")
        if self.reference_digest is not None and (
            len(self.reference_digest) != 64
            or any(ch not in "0123456789abcdef" for ch in self.reference_digest)
        ):
            raise ValueError("reference_digest must be lowercase SHA-256 hex.")

    @property
    def bound_digest(self) -> str:
        """Digest bound to this proof-bundle reference."""
        return self.digest if self.reference_digest is None else self.reference_digest

    def to_dict(self) -> dict[str, str]:
        """Serialize this object to its canonical dictionary representation."""
        return {
            "reference_key": self.reference_key,
            "source": self.source,
            "artifact_id": self.artifact_id,
            "digest": self.digest,
            "reference_digest": self.bound_digest,
        }


@dataclass(frozen=True, slots=True)
class ReliabilityProofBundleDescriptor:
    """Deterministic index describing exactly what an offline proof bundle contains."""

    format_version: str
    bundle_type: str
    subject_id: str
    attestation_artifact_id: str
    evidence_chain_artifact_id: str
    state_history_artifact_id: str
    verification_report_artifact_id: str
    attestation_id: str
    attestation_digest: str
    evidence_chain_id: str
    evidence_chain_digest: str
    transition_id: str
    transition_digest: str
    reliability_state: str
    decision: str
    verification_report_digest: str
    sources: tuple[ReliabilityProofSource, ...]
    attestation_trust_context: ReliabilityAttestationTrustContext | None = None
    lineage_closure: ReliabilityLineageClosure | None = None
    completeness_artifact_id: str | None = None
    completeness_digest: str | None = None
    cryptographic_profile: CryptographicProfile | None = None

    def __post_init__(self) -> None:
        """Validate and normalize the initialized object state."""
        if self.format_version not in {"1", "2", "3"}:
            raise ValueError("unsupported reliability proof bundle format version.")
        if self.format_version == "1" and self.lineage_closure is not None:
            raise ValueError(
                "format version 1 proof bundles cannot carry lineage closure"
            )
        if self.format_version == "3":
            if not self.completeness_artifact_id or not self.completeness_digest:
                raise ValueError(
                    "format version 3 proof bundles require completeness binding"
                )
            if len(self.completeness_digest) != 64 or any(
                ch not in "0123456789abcdef" for ch in self.completeness_digest
            ):
                raise ValueError("completeness_digest must be lowercase SHA-256 hex")
        elif (
            self.completeness_artifact_id is not None
            or self.completeness_digest is not None
        ):
            raise ValueError("completeness binding is only valid for format version 3")
        if self.bundle_type != "reliability-proof":
            raise ValueError("unsupported reliability proof bundle type.")
        for name in (
            "subject_id",
            "attestation_artifact_id",
            "evidence_chain_artifact_id",
            "state_history_artifact_id",
            "verification_report_artifact_id",
            "attestation_id",
            "evidence_chain_id",
            "transition_id",
            "reliability_state",
            "decision",
        ):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} must not be empty.")
        for name in (
            "attestation_digest",
            "evidence_chain_digest",
            "transition_digest",
            "verification_report_digest",
        ):
            value = getattr(self, name)
            if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
                raise ValueError(f"{name} must be lowercase SHA-256 hex.")
        if (
            len(
                {
                    self.attestation_artifact_id,
                    self.evidence_chain_artifact_id,
                    self.state_history_artifact_id,
                    self.verification_report_artifact_id,
                }
            )
            != 4
        ):
            raise ValueError("proof component artifact IDs must be unique.")
        keys = [item.reference_key for item in self.sources]
        if len(keys) != len(set(keys)):
            raise ValueError("proof source reference keys must be unique.")

    def payload(self) -> dict[str, Any]:
        """Return the canonical payload represented by this object."""
        payload = {
            "format_version": self.format_version,
            "bundle_type": self.bundle_type,
            "subject_id": self.subject_id,
            "attestation_artifact_id": self.attestation_artifact_id,
            "evidence_chain_artifact_id": self.evidence_chain_artifact_id,
            "state_history_artifact_id": self.state_history_artifact_id,
            "verification_report_artifact_id": self.verification_report_artifact_id,
            "attestation_id": self.attestation_id,
            "attestation_digest": self.attestation_digest,
            "evidence_chain_id": self.evidence_chain_id,
            "evidence_chain_digest": self.evidence_chain_digest,
            "transition_id": self.transition_id,
            "transition_digest": self.transition_digest,
            "reliability_state": self.reliability_state,
            "decision": self.decision,
            "verification_report_digest": self.verification_report_digest,
            "sources": [item.to_dict() for item in self.sources],
            "attestation_trust_context": None
            if self.attestation_trust_context is None
            else self.attestation_trust_context.to_dict(),
            "lineage_closure": None
            if self.lineage_closure is None
            else self.lineage_closure.to_dict(),
        }
        if self.format_version == "3":
            payload["completeness_artifact_id"] = self.completeness_artifact_id
            payload["completeness_digest"] = self.completeness_digest
        if self.cryptographic_profile is not None:
            payload["cryptographic_profile"] = self.cryptographic_profile.to_dict()
        return payload

    @property
    def digest(self) -> str:
        """Deterministic digest of this object."""
        return sha256(_canonical(self.payload())).hexdigest()

    def to_dict(self, *, include_digest: bool = True) -> dict[str, Any]:
        """Serialize this object to its canonical dictionary representation."""
        payload = self.payload()
        if include_digest:
            payload["digest"] = self.digest
        return payload

    @classmethod
    def from_dict(
        cls, payload: Mapping[str, JsonValue]
    ) -> ReliabilityProofBundleDescriptor:
        """Construct this object from its serialized dictionary representation."""
        raw_sources = payload.get("sources", [])
        if not isinstance(raw_sources, list):
            raise ValueError("sources must be an array.")
        parsed_sources: list[ReliabilityProofSource] = []
        for item in raw_sources:
            if not isinstance(item, Mapping):
                raise ValueError("each proof source must be a JSON object.")
            parsed_sources.append(
                ReliabilityProofSource(
                    reference_key=str(item["reference_key"]),
                    source=str(item["source"]),
                    artifact_id=str(item["artifact_id"]),
                    digest=str(item["digest"]),
                    reference_digest=None
                    if item.get("reference_digest") is None
                    else str(item["reference_digest"]),
                )
            )
        sources = tuple(parsed_sources)
        raw_context = payload.get("attestation_trust_context")
        if raw_context is not None and not isinstance(raw_context, dict):
            raise ValueError(
                "attestation_trust_context must be an object when present."
            )
        context = (
            None
            if raw_context is None
            else ReliabilityAttestationTrustContext.from_dict(raw_context)
        )
        raw_crypto = payload.get("cryptographic_profile")
        if raw_crypto is not None and not isinstance(raw_crypto, dict):
            raise ValueError("cryptographic_profile must be an object when present.")
        crypto = (
            None if raw_crypto is None else CryptographicProfile.from_dict(raw_crypto)
        )
        raw_lineage = payload.get("lineage_closure")
        if raw_lineage is not None and not isinstance(raw_lineage, dict):
            raise ValueError("lineage_closure must be an object when present.")
        lineage = (
            None
            if raw_lineage is None
            else ReliabilityLineageClosure.from_dict(raw_lineage)
        )
        descriptor = cls(
            format_version=str(payload["format_version"]),
            bundle_type=str(payload["bundle_type"]),
            subject_id=str(payload["subject_id"]),
            attestation_artifact_id=str(payload["attestation_artifact_id"]),
            evidence_chain_artifact_id=str(payload["evidence_chain_artifact_id"]),
            state_history_artifact_id=str(payload["state_history_artifact_id"]),
            verification_report_artifact_id=str(
                payload["verification_report_artifact_id"]
            ),
            attestation_id=str(payload["attestation_id"]),
            attestation_digest=str(payload["attestation_digest"]),
            evidence_chain_id=str(payload["evidence_chain_id"]),
            evidence_chain_digest=str(payload["evidence_chain_digest"]),
            transition_id=str(payload["transition_id"]),
            transition_digest=str(payload["transition_digest"]),
            reliability_state=str(payload["reliability_state"]),
            decision=str(payload["decision"]),
            verification_report_digest=str(payload["verification_report_digest"]),
            sources=sources,
            attestation_trust_context=context,
            lineage_closure=lineage,
            cryptographic_profile=crypto,
            completeness_artifact_id=None
            if payload.get("completeness_artifact_id") is None
            else str(payload.get("completeness_artifact_id")),
            completeness_digest=None
            if payload.get("completeness_digest") is None
            else str(payload.get("completeness_digest")),
        )
        supplied = str(payload.get("digest", ""))
        if supplied and supplied != descriptor.digest:
            raise ValueError("reliability proof bundle descriptor digest mismatch.")
        return descriptor
