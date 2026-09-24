"""Release-trust evidence for StateWake package artifacts."""

from .authenticity import (
    AuthenticatedReleaseAssessment,
    ReleaseAuthenticityVerification,
    assess_authenticated_release,
    release_signature_payload,
    verify_release_authenticity,
)
from .bundle import (
    evaluate_release_trust_bundle,
    load_release_trust_bundle,
    release_claim_chain_from_bundle,
    release_trust_evidence_reference,
    verify_release_trust_bundle,
    write_release_trust_bundle,
)
from .content_verification import ReleaseContentVerification, verify_release_trust_files
from .model import (
    ArtifactDigest,
    BuildProvenance,
    ExternalEvidence,
    HumanReleaseDecision,
    ReleaseTrustBundle,
    SourceIdentity,
)

__all__ = [
    "ReleaseAuthenticityVerification",
    "AuthenticatedReleaseAssessment",
    "assess_authenticated_release",
    "release_signature_payload",
    "verify_release_authenticity",
    "ReleaseContentVerification",
    "verify_release_trust_files",
    "ArtifactDigest",
    "BuildProvenance",
    "ExternalEvidence",
    "HumanReleaseDecision",
    "ReleaseTrustBundle",
    "SourceIdentity",
    "evaluate_release_trust_bundle",
    "load_release_trust_bundle",
    "release_claim_chain_from_bundle",
    "release_trust_evidence_reference",
    "verify_release_trust_bundle",
    "write_release_trust_bundle",
]
