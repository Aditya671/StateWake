"""Build and verify the V1 material-completeness witness for portable reliability proofs."""

from __future__ import annotations

from pathlib import Path

from statewake.utils.json_support import load_object

from ..domain.reliability_proof_bundle import ReliabilityProofBundleDescriptor
from ..domain.reliability_proof_completeness import ReliabilityProofCompleteness


def build_reliability_proof_completeness(
    descriptor: ReliabilityProofBundleDescriptor,
    *,
    artifact_ids: tuple[str, ...],
    expected_source_reference_keys: tuple[str, ...] | None = None,
) -> ReliabilityProofCompleteness:
    """Build the deterministic material-artifact requirement set for a v3 proof."""
    if descriptor.format_version != "3":
        raise ValueError(
            "proof completeness requires a version 3 reliability proof descriptor"
        )
    descriptor_source_keys = tuple(
        sorted(item.reference_key for item in descriptor.sources)
    )
    source_keys = tuple(
        sorted(
            expected_source_reference_keys
            if expected_source_reference_keys is not None
            else descriptor_source_keys
        )
    )
    if descriptor_source_keys != source_keys:
        missing = sorted(set(source_keys) - set(descriptor_source_keys))
        extra = sorted(set(descriptor_source_keys) - set(source_keys))
        raise ValueError(
            f"proof completeness source references differ from canonical chain: missing={missing}, extra={extra}"
        )
    source_artifact_ids = tuple(
        sorted({item.artifact_id for item in descriptor.sources})
    )
    required = {
        descriptor.attestation_artifact_id,
        descriptor.evidence_chain_artifact_id,
        descriptor.state_history_artifact_id,
        descriptor.verification_report_artifact_id,
        descriptor.completeness_artifact_id or "",
        "proof-descriptor",
        "proof-lineage-closure",
    }
    required.discard("")
    if descriptor.attestation_trust_context is not None:
        required.update(
            {
                descriptor.attestation_trust_context.envelope_artifact_id,
                descriptor.attestation_trust_context.trust_state_artifact_id,
                descriptor.attestation_trust_context.authority_store_artifact_id,
                "proof-attestation-trust-context",
            }
        )
    covered = tuple(sorted(set(artifact_ids)))
    expected = set(required) | set(source_artifact_ids)
    missing = sorted(expected - set(covered))
    if missing:
        raise ValueError(
            f"proof completeness cannot be built; expected artifacts are absent: {missing}"
        )
    unexpected = sorted(set(covered) - expected)
    if unexpected:
        raise ValueError(
            f"proof completeness cannot classify extra artifacts: {unexpected}"
        )
    return ReliabilityProofCompleteness(
        format_version="1",
        proof_format_version="3",
        required_proof_artifact_ids=tuple(sorted(required)),
        required_source_reference_keys=source_keys,
        material_source_artifact_ids=source_artifact_ids,
        covered_artifact_ids=covered,
        lineage_required=True,
        trust_context_required=descriptor.attestation_trust_context is not None,
    )


def verify_reliability_proof_completeness(
    descriptor: ReliabilityProofBundleDescriptor,
    completeness: ReliabilityProofCompleteness,
    *,
    artifact_ids: tuple[str, ...],
    expected_source_reference_keys: tuple[str, ...] | None = None,
) -> ReliabilityProofCompleteness:
    """Recompute and compare the material-artifact witness."""
    expected = build_reliability_proof_completeness(
        descriptor,
        artifact_ids=artifact_ids,
        expected_source_reference_keys=expected_source_reference_keys,
    )
    if completeness != expected:
        raise ValueError(
            "packaged reliability proof completeness does not match the proof contents"
        )
    if completeness.digest != expected.digest:
        raise ValueError("reliability proof completeness digest mismatch")
    return expected


def load_reliability_proof_completeness(path: Path) -> ReliabilityProofCompleteness:
    """Load and validate a persisted proof-completeness report."""
    payload = load_object(path)
    if not isinstance(payload, dict):
        raise ValueError("reliability proof completeness must be a JSON object")
    return ReliabilityProofCompleteness.from_dict(payload)
