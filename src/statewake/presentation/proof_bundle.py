"""Read-only investigation projection for portable reliability proof bundles.

The projection reuses StateWake's existing operational-bundle and reliability-proof
verification authorities.  It deliberately does not expose ZIP member paths or raw
artifact contents and does not reinterpret proof verification as factual correctness,
human approval, or release authorization.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256

from statewake.domain.operations import OperationalBundle
from statewake.domain.reliability_outcome_verification import (
    ReliabilityOutcomeVerificationReport,
)
from statewake.domain.reliability_proof_bundle import ReliabilityProofBundleDescriptor

PROOF_BUNDLE_INVESTIGATION_SCHEMA_VERSION = "proof-bundle-investigation.v1"


def _digest(payload: dict[str, object]) -> str:
    """Return a deterministic digest for one JSON-compatible projection."""
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class ReliabilityProofInvestigationProjection:
    """Bounded operator view of one independently verified portable proof bundle."""

    payload: dict[str, object]

    @property
    def digest(self) -> str:
        """Return the deterministic ETag digest for this projection."""
        return _digest(self.payload)

    def to_dict(self) -> dict[str, object]:
        """Serialize the projection without exposing bundle-internal paths/content."""
        return dict(self.payload)


def build_reliability_proof_investigation(
    bundle: OperationalBundle,
    report: ReliabilityOutcomeVerificationReport,
    descriptor: ReliabilityProofBundleDescriptor,
) -> ReliabilityProofInvestigationProjection:
    """Project an already verified portable proof without inventing extra assurance."""
    if descriptor.bundle_type != "reliability-proof":
        raise ValueError("proof investigation requires a reliability-proof bundle")
    if not report.verified:
        raise ValueError("proof investigation requires a verified proof result")

    artifacts = [
        {
            "artifact_id": item.artifact_id,
            "kind": item.kind,
            "sha256": item.sha256,
            "size_bytes": item.size_bytes,
            "sensitivity": item.sensitivity,
            "derived_from": list(item.derived_from),
        }
        for item in sorted(bundle.artifacts, key=lambda value: value.artifact_id)
    ]
    sources = [
        {
            "reference_key": item.reference_key,
            "source_label": item.source,
            "artifact_id": item.artifact_id,
            "packaged_digest": item.digest,
            "bound_digest": item.bound_digest,
        }
        for item in sorted(descriptor.sources, key=lambda value: value.reference_key)
    ]

    lineage_required = descriptor.format_version in {"2", "3"}
    completeness_required = descriptor.format_version == "3"
    trust_context = descriptor.attestation_trust_context

    payload: dict[str, object] = {
        "schema_version": PROOF_BUNDLE_INVESTIGATION_SCHEMA_VERSION,
        "bundle": {
            "bundle_id": bundle.bundle_id,
            "manifest_id": bundle.manifest_id,
            "engine_version": bundle.engine_version,
            "created_at": bundle.created_at.isoformat(),
            "artifact_count": len(bundle.artifacts),
        },
        "proof": {
            "format_version": descriptor.format_version,
            "bundle_type": descriptor.bundle_type,
            "descriptor_digest": descriptor.digest,
            "subject_id": descriptor.subject_id,
            "attestation_id": descriptor.attestation_id,
            "attestation_digest": descriptor.attestation_digest,
            "evidence_chain_id": descriptor.evidence_chain_id,
            "evidence_chain_digest": descriptor.evidence_chain_digest,
            "transition_id": descriptor.transition_id,
            "transition_digest": descriptor.transition_digest,
            "reliability_state": descriptor.reliability_state,
            "decision": descriptor.decision,
            "verification_report_digest": descriptor.verification_report_digest,
        },
        "verification": {
            "verified": report.verified,
            "checks": list(report.checks),
            "failures": list(report.failures),
            "offline_reverification_succeeded": True,
            "source_set_complete": True,
        },
        "lineage": {
            "required_by_format": lineage_required,
            "present": descriptor.lineage_closure is not None,
            "status": "verified" if lineage_required else "not-required-by-format",
            "digest": (
                None
                if descriptor.lineage_closure is None
                else descriptor.lineage_closure.digest
            ),
        },
        "completeness": {
            "required_by_format": completeness_required,
            "present": descriptor.completeness_artifact_id is not None,
            "status": (
                "verified" if completeness_required else "not-required-by-format"
            ),
            "artifact_id": descriptor.completeness_artifact_id,
            "digest": descriptor.completeness_digest,
        },
        "trust_context": {
            "present": trust_context is not None,
            "portable_cryptographic_consistency_verified": trust_context is not None,
            "external_authority_trust_established": False,
            "signing_key_id": (
                None if trust_context is None else trust_context.signing_key_id
            ),
            "signing_key_digest": (
                None if trust_context is None else trust_context.signing_key_digest
            ),
            "trust_state_version": (
                None if trust_context is None else trust_context.trust_state_version
            ),
            "trust_state_digest": (
                None if trust_context is None else trust_context.trust_state_digest
            ),
            "authority_key_id": (
                None if trust_context is None else trust_context.authority_key_id
            ),
            "authority_key_digest": (
                None if trust_context is None else trust_context.authority_key_digest
            ),
        },
        "cryptographic_profile": (
            None
            if descriptor.cryptographic_profile is None
            else descriptor.cryptographic_profile.to_dict()
        ),
        "sources": sources,
        "artifacts": artifacts,
        "portable_dataset_boundary": {
            "this_is_reliability_proof": True,
            "workspace_portable_dataset_is_distinct": True,
            "note": (
                "A workspace portable dataset bundle is a different format and "
                "explicitly marks proof_bundle=false; it is not a reliability "
                "proof bundle."
            ),
        },
        "authorization": {
            "human_approval_evaluated": False,
            "publication_authorized": False,
            "release_authorized": False,
        },
        "limitations": [
            (
                "A verified portable proof establishes the bounded StateWake "
                "relationships and checks recorded by the proof verifier; it does not "
                "prove factual correctness of an external system."
            ),
            (
                "Packaged trust context verifies portable cryptographic consistency "
                "against the authority material carried in the bundle; it does not "
                "independently establish that authority as trusted by this operator."
            ),
            (
                "ZIP member paths and raw embedded proof/source bytes are "
                "intentionally "
                "omitted from this read-only projection."
            ),
            (
                "This read-only surface does not build, export, sign, approve, "
                "publish, "
                "or modify proof bundles."
            ),
        ],
    }
    return ReliabilityProofInvestigationProjection(payload)


__all__ = [
    "PROOF_BUNDLE_INVESTIGATION_SCHEMA_VERSION",
    "ReliabilityProofInvestigationProjection",
    "build_reliability_proof_investigation",
]
