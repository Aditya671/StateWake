"""Canonical StateWake release-source identity generation and verification."""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

from scripts.common.release_scope import release_input_files

MANIFEST_NAME = "verification_manifest.txt"
FINGERPRINT_NAME = "candidate-fingerprint.txt"
_SHA256 = re.compile(r"[0-9a-f]{64}")


class ReleaseIdentityError(ValueError):
    """Raised when persisted release identity does not match the source tree."""


def sha256_bytes(data: bytes) -> str:
    """Return the SHA-256 hexadecimal digest for bytes."""
    return hashlib.sha256(data).hexdigest()


def file_sha256(path: Path) -> str:
    """Return the SHA-256 digest of one file."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_tree_digest(root: Path) -> str:
    """Return the deterministic digest of all selected release inputs."""
    digest = hashlib.sha256()
    for path in release_input_files(root):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        data = path.read_bytes()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


def expected_manifest(root: Path) -> dict[str, str]:
    """Return the exact path-to-digest map for the current release-input tree."""
    return {
        path.relative_to(root).as_posix(): file_sha256(path)
        for path in release_input_files(root)
    }


def read_manifest(root: Path) -> dict[str, str]:
    """Read and validate the persisted release-input manifest syntax."""
    manifest_path = root / MANIFEST_NAME
    if not manifest_path.is_file():
        raise ReleaseIdentityError("verification manifest is missing")
    records: dict[str, str] = {}
    for line_number, raw_line in enumerate(
        manifest_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not raw_line.strip():
            continue
        parts = raw_line.split("  ", 1)
        if len(parts) != 2:
            raise ReleaseIdentityError(
                f"invalid verification manifest record at line {line_number}"
            )
        digest, relative = parts
        if _SHA256.fullmatch(digest) is None:
            raise ReleaseIdentityError(
                f"invalid verification manifest digest at line {line_number}"
            )
        relative_path = Path(relative)
        if not relative or relative_path.is_absolute() or ".." in relative_path.parts:
            raise ReleaseIdentityError(
                f"invalid verification manifest path at line {line_number}"
            )
        if relative in records:
            raise ReleaseIdentityError(
                f"duplicate verification manifest path: {relative}"
            )
        records[relative] = digest
    return records


def _manifest_text(records: dict[str, str]) -> str:
    return "".join(f"{digest}  {path}\n" for path, digest in sorted(records.items()))


def _atomic_write_text(path: Path, text: str) -> bool:
    """Atomically replace one generated identity file only when bytes changed."""
    encoded = text.encode("utf-8")
    if path.is_file() and path.read_bytes() == encoded:
        return False
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_bytes(encoded)
    os.replace(temporary, path)
    return True


def refresh_release_identity(root: Path) -> dict[str, object]:
    """Regenerate manifest and candidate fingerprint from the current source tree."""
    root = root.resolve()
    records = expected_manifest(root)
    source_digest = source_tree_digest(root)
    manifest_changed = _atomic_write_text(root / MANIFEST_NAME, _manifest_text(records))
    fingerprint_changed = _atomic_write_text(
        root / FINGERPRINT_NAME, f"{source_digest}\n"
    )
    return {
        "manifest_records": len(records),
        "source_tree_sha256": source_digest,
        "manifest_changed": manifest_changed,
        "fingerprint_changed": fingerprint_changed,
    }


def validate_verification_manifest(root: Path) -> None:
    """Verify manifest membership and content digests against the current tree."""
    recorded = read_manifest(root)
    actual = expected_manifest(root)
    if recorded == actual:
        return
    missing = sorted(set(actual) - set(recorded))
    unexpected = sorted(set(recorded) - set(actual))
    mismatched = sorted(
        path for path in set(actual) & set(recorded) if actual[path] != recorded[path]
    )
    details: list[str] = []
    if missing:
        details.append("missing=" + ",".join(missing))
    if unexpected:
        details.append("unexpected=" + ",".join(unexpected))
    if mismatched:
        details.append("mismatched=" + ",".join(mismatched))
    raise ReleaseIdentityError(
        "verification manifest does not match source tree: " + "; ".join(details)
    )


def validate_candidate_fingerprint(root: Path) -> None:
    """Verify the persisted candidate fingerprint against current release inputs."""
    fingerprint_path = root / FINGERPRINT_NAME
    if not fingerprint_path.is_file():
        raise ReleaseIdentityError("candidate fingerprint is missing")
    fingerprint = fingerprint_path.read_text(encoding="utf-8").strip()
    if _SHA256.fullmatch(fingerprint) is None:
        raise ReleaseIdentityError("candidate fingerprint is not a SHA-256 digest")
    actual = source_tree_digest(root)
    if fingerprint != actual:
        raise ReleaseIdentityError("candidate fingerprint does not match source tree")


def validate_release_identity(root: Path) -> None:
    """Verify both persisted release identity artifacts without mutating them."""
    validate_verification_manifest(root)
    validate_candidate_fingerprint(root)
