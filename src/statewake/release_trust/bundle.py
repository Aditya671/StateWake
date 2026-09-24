"""Build, load, verify, and bridge release-trust bundles."""

from __future__ import annotations

import json
from pathlib import Path

from statewake.domain.reliability_evidence import (
    EvidenceReference,
    ReliabilityEvidenceChain,
)
from statewake.services.persistence import atomic_write_text
from statewake.services.reliability_claim_profile_service import (
    ClaimProfileEvaluation,
    evaluate_claim_profile,
    get_builtin_claim_profile,
)

from .model import ReleaseTrustBundle


def write_release_trust_bundle(bundle: ReleaseTrustBundle, path: Path) -> None:
    """Persist a release-trust bundle as deterministic JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(
        path, json.dumps(bundle.to_dict(), indent=2, sort_keys=True) + "\n"
    )


def load_release_trust_bundle(path: Path) -> ReleaseTrustBundle:
    """Load and verify a release-trust bundle from JSON."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("release trust bundle root must be an object.")
    return ReleaseTrustBundle.from_dict(payload)


def release_trust_evidence_reference(
    bundle: ReleaseTrustBundle,
    *,
    source: str | None = None,
) -> EvidenceReference:
    """Return an evidence reference for use in StateWake evidence chains."""
    return EvidenceReference(
        kind="release-trust",
        identity=f"release-trust:{bundle.source.distribution}:{bundle.source.version}",
        digest=bundle.digest,
        source=source,
    )


def _ref(
    kind: str, identity: str, digest: str, source: str | None = None
) -> EvidenceReference:
    return EvidenceReference(kind=kind, identity=identity, digest=digest, source=source)


def release_claim_chain_from_bundle(
    bundle: ReleaseTrustBundle,
    *,
    chain_id: str = "release-trust-chain",
) -> ReliabilityEvidenceChain:
    """Create a claim-profile-compatible chain from release-trust evidence.

    The chain references the release-trust bundle and synthetic StateWake evidence
    references. It does not copy SBOM, scan, or signature contents into the chain.
    """
    artifact = bundle.artifacts[0]
    run_digest = bundle.provenance.digest if bundle.provenance else bundle.digest
    state_digest = bundle.source.source_tree_sha256
    integrity_digest = artifact.sha256
    vulnerability_scan = bundle.vulnerability_scan
    sbom = bundle.sbom
    signature = bundle.signature
    if sbom is None or vulnerability_scan is None or signature is None:
        raise ValueError("release trust bundle is missing required external evidence.")
    policy_digest = vulnerability_scan.digest
    approval_digest = bundle.human_decision.basis_digest or bundle.digest
    evidence: list[EvidenceReference] = [
        release_trust_evidence_reference(bundle),
        _ref(
            "evidence",
            "ai-contract:policy_evidence:release-trust:v1",
            policy_digest,
            "statewake.release_trust.vulnerability_scan",
        ),
        _ref(
            "sbom",
            f"sbom:{bundle.source.distribution}:{bundle.source.version}",
            sbom.digest,
            sbom.reference,
        ),
        _ref(
            "vulnerability-scan",
            f"vulnerability-scan:{bundle.source.distribution}:{bundle.source.version}",
            vulnerability_scan.digest,
            vulnerability_scan.reference,
        ),
    ]
    if bundle.human_decision.decision == "approved":
        evidence.append(
            _ref(
                "evidence",
                "ai-contract:human_approval:release-trust:v1",
                approval_digest,
                "statewake.release_trust.human_decision",
            )
        )
    evidence.append(
        _ref(
            "signature",
            f"signature:{bundle.source.distribution}:{bundle.source.version}",
            signature.digest,
            signature.reference,
        )
    )
    return ReliabilityEvidenceChain(
        chain_id=chain_id,
        run=_ref("run", f"release-build:{bundle.source.version}", run_digest),
        state=_ref(
            "state", f"source-tree:{bundle.source.source_revision}", state_digest
        ),
        evidence=tuple(evidence),
        provenance=_ref(
            "provenance",
            f"build-provenance:{bundle.source.version}",
            bundle.provenance.digest if bundle.provenance else bundle.digest,
        ),
        integrity=_ref("integrity", f"artifact:{artifact.name}", integrity_digest),
        verification_status="verified",
        reliability_state="reliable",
        reconciliation_state="verified",
        decision="accept" if bundle.human_decision.decision == "approved" else "review",
        decision_rationale=(
            "Release-trust references supplied; content and trust must be checked separately.",
            *bundle.limitations,
        ),
    )


def evaluate_release_trust_bundle(bundle: ReleaseTrustBundle) -> ClaimProfileEvaluation:
    """Evaluate bundle *structure*; this does not verify referenced files or signatures."""
    profile = get_builtin_claim_profile("release_evidence_complete.v1")
    return evaluate_claim_profile(release_claim_chain_from_bundle(bundle), profile)


def verify_release_trust_bundle(bundle: ReleaseTrustBundle) -> tuple[str, ...]:
    """Return deterministic verification notes for a release-trust bundle."""
    notes = [
        "artifact-digest-present",
        "source-identity-present",
        "dependency-lock-digest-present",
        "build-provenance-present",
        "sbom-evidence-present",
        "vulnerability-scan-evidence-present",
        "human-release-decision-separated",
    ]
    signature = bundle.signature
    if signature is None:
        raise ValueError("release trust bundle is missing signature evidence.")
    if signature.status == "limitation":
        notes.append("signature-limitation-recorded")
    else:
        notes.append("signature-evidence-present")
    if bundle.human_decision.decision == "approved":
        notes.append("human-release-approval-present")
    else:
        notes.append("human-release-approval-not-granted")
    return tuple(notes)
