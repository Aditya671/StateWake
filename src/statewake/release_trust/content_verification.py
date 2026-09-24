"""Verify release evidence *content*, separately from bundle structure and trust.

This verifier checks local bytes and sizes only. It does not attest the builder,
validate CI execution, scan software, or verify cryptographic signatures.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath

from .model import ReleaseTrustBundle


@dataclass(frozen=True, slots=True)
class ReleaseContentVerification:
    """Result of verifying digest-bound files against one exact bundle."""

    bundle_digest: str
    matched: tuple[str, ...]
    missing: tuple[str, ...]
    mismatched: tuple[str, ...]
    limitations: tuple[str, ...]

    @property
    def content_complete(self) -> bool:
        """Whether each required local file was found with its declared bytes."""
        return not self.missing and not self.mismatched


def verify_release_trust_files(
    bundle: ReleaseTrustBundle, root: Path
) -> ReleaseContentVerification:
    """Verify local artifact and external evidence digests, never trust a path hint.

    ``reference`` is used only as a relative path under ``root``. It does not
    supply an authority for signatures, vulnerability results, or approvals.
    Missing references and symlink traversal fail closed.
    """
    matched: list[str] = []
    missing: list[str] = []
    mismatched: list[str] = []
    limitations: list[str] = list(bundle.limitations)
    base = root.resolve(strict=True)

    def check(
        name: str, relative: str | None, digest: str, size: int | None = None
    ) -> None:
        if not relative:
            missing.append(name)
            return
        candidate = PurePosixPath(relative)
        if (
            candidate.is_absolute()
            or not candidate.parts
            or any(part in {"", ".", ".."} for part in candidate.parts)
            or "\\\\" in relative
        ):
            mismatched.append(name)
            return
        path = base.joinpath(*candidate.parts)
        if any(part.is_symlink() for part in (path, *path.parents) if part != base):
            mismatched.append(name)
            return
        if not path.is_file() or not path.resolve().is_relative_to(base):
            missing.append(name)
            return
        data = path.read_bytes()
        if sha256(data).hexdigest() != digest or (
            size is not None and len(data) != size
        ):
            mismatched.append(name)
        else:
            matched.append(name)

    for item in bundle.artifacts:
        check(f"artifact:{item.name}", item.name, item.sha256, item.size_bytes)
    for item in (
        *bundle.tests,
        bundle.sbom,
        bundle.vulnerability_scan,
        bundle.provenance,
        bundle.signature,
    ):
        if item is None:
            continue
        if item.status == "limitation":
            limitations.append(f"{item.evidence_type}: {item.limitation}")
        else:
            check(f"{item.evidence_type}:{item.name}", item.reference, item.digest)
    limitations.extend(
        (
            "External evidence status was asserted by its producer, not independently replayed.",
            "Signature authenticity and trust anchor were not verified by this digest check.",
        )
    )
    return ReleaseContentVerification(
        bundle_digest=bundle.digest,
        matched=tuple(matched),
        missing=tuple(missing),
        mismatched=tuple(mismatched),
        limitations=tuple(limitations),
    )


__all__ = ["ReleaseContentVerification", "verify_release_trust_files"]
