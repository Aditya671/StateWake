"""Opt-in release signature authenticity after independent local content checks.

The signature is detached to avoid circularly signing its own digest. This
module authenticates an externally trusted release signer, not CI execution,
scan correctness, or the identity/authority of the human approver.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import Any

from statewake.utils.signatures import verify_ed25519_signature

from .content_verification import ReleaseContentVerification, verify_release_trust_files
from .model import ReleaseTrustBundle


@dataclass(frozen=True, slots=True)
class ReleaseAuthenticityVerification:
    """An independently configured signer authenticated a content-bound bundle."""

    bundle_digest: str
    signer_key_id: str
    content: ReleaseContentVerification
    signature_authenticated: bool
    human_approval_authenticated: bool = False
    ci_execution_verified: bool = False
    scan_findings_independently_verified: bool = False


def release_signature_payload(bundle: ReleaseTrustBundle) -> bytes:
    """Return canonical signed bytes excluding the detached signature reference.

    The signature's digest is stored in the bundle and verified separately.
    Everything else, including the human decision *claim*, is in scope. A
    signature on that claim does not separately authenticate its human actor.
    """
    payload: dict[str, Any] = bundle.payload()
    payload["signature"] = None
    return json.dumps(
        {"domain": "statewake-release-signature-v1", "bundle": payload},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def verify_release_authenticity(
    bundle: ReleaseTrustBundle,
    root: Path,
    *,
    trusted_signers: Mapping[str, bytes],
) -> ReleaseAuthenticityVerification:
    """Require content matches and a detached Ed25519 signature by a trusted key.

    Signature evidence must reference JSON with exactly ``key_id`` and
    ``signature_hex``. Its SHA-256 is checked by the existing file verifier;
    the key must be independently configured by the relying application.
    Missing/limited signatures, unknown keys and modified bytes fail closed.
    """
    content = verify_release_trust_files(bundle, root)
    if not content.content_complete:
        raise ValueError("release referenced content is not verified")
    signature_evidence = bundle.signature
    if signature_evidence is None or signature_evidence.status != "present":
        raise ValueError("release has no signature evidence for authentication")
    relative = signature_evidence.reference
    if not relative:
        raise ValueError("release signature reference is missing")
    # The content verifier checks relative path traversal and symlink safety.
    # The exact signature reference must have passed that verifier.
    reference_name = f"{signature_evidence.evidence_type}:{signature_evidence.name}"
    if reference_name not in content.matched:
        raise ValueError("release signature bytes are not content verified")
    path = root.resolve(strict=True).joinpath(*PurePosixPath(relative).parts)
    signed_file = path.read_bytes()
    if sha256(signed_file).hexdigest() != signature_evidence.digest:
        raise ValueError("release signature file changed after content verification")
    document = json.loads(signed_file)
    if not isinstance(document, dict) or set(document) != {"key_id", "signature_hex"}:
        raise ValueError("release signature document has invalid structure")
    key_id = document["key_id"]
    signature_hex = document["signature_hex"]
    if not isinstance(key_id, str) or not key_id.strip():
        raise ValueError("release signature key_id must be nonblank")
    if not isinstance(signature_hex, str) or len(signature_hex) != 128:
        raise ValueError("release signature must be 64 bytes of hex")
    try:
        signature = bytes.fromhex(signature_hex)
    except ValueError as exc:
        raise ValueError("release signature is not valid hex") from exc
    key = trusted_signers.get(key_id)
    if key is None or len(key) != 32:
        raise ValueError("release signer is not independently trusted")
    verify_ed25519_signature(key, release_signature_payload(bundle), signature)
    return ReleaseAuthenticityVerification(
        bundle_digest=bundle.digest,
        signer_key_id=key_id,
        content=content,
        signature_authenticated=True,
    )


@dataclass(frozen=True, slots=True)
class AuthenticatedReleaseAssessment:
    """Structural profile and observed authenticity without invented approvals."""

    bundle_digest: str
    structural_profile_satisfied: bool
    content_verified: bool
    signer_authenticated: bool
    human_approval_claimed: bool
    human_approval_authenticated: bool = False
    publication_authorized: bool = False


def assess_authenticated_release(
    bundle: ReleaseTrustBundle,
    root: Path,
    *,
    trusted_signers: Mapping[str, bytes],
) -> AuthenticatedReleaseAssessment:
    """Verify files and a trusted release signer before evaluating the profile.

    Structural profile acceptance is separate from authorization to publish.
    The signature covers a *claim* of human approval, not an independently
    authenticated human decision. Publication therefore remains unauthorized.
    """
    from .bundle import evaluate_release_trust_bundle

    authentic = verify_release_authenticity(
        bundle, root, trusted_signers=trusted_signers
    )
    profile = evaluate_release_trust_bundle(bundle)
    return AuthenticatedReleaseAssessment(
        bundle_digest=bundle.digest,
        structural_profile_satisfied=profile.satisfied,
        content_verified=authentic.content.content_complete,
        signer_authenticated=authentic.signature_authenticated,
        human_approval_claimed=bundle.human_decision.decision == "approved",
    )


__all__ = [
    "ReleaseAuthenticityVerification",
    "AuthenticatedReleaseAssessment",
    "assess_authenticated_release",
    "release_signature_payload",
    "verify_release_authenticity",
]
