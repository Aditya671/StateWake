#!/usr/bin/env python3
"""Independently verify a portable StateWake reliability proof package."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
from pathlib import Path
from typing import Protocol, cast
from zipfile import BadZipFile, ZipFile

MAX_INPUT_BYTES = 1_048_576
MAX_ARCHIVE_MEMBERS = 256
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 16 * 1024 * 1024
MAX_ARCHIVE_COMPRESSION_RATIO = 100.0
MAX_JSON_DEPTH = 64
MAX_JSON_NODES = 10_000
MAX_STRING_BYTES = 256 * 1024

HEXDIGEST = set("0123456789abcdef")


class _SignatureVerifier(Protocol):
    """Minimal verifier protocol used to avoid importing PyNaCl at module load."""

    def verify(self, message: bytes, signature: bytes | None = None) -> bytes:
        """Verify a detached signature and return the verified message bytes."""
        ...


class _VerifyKeyFactory(Protocol):
    """Callable factory for signature verifier instances."""

    def __call__(self, key: bytes) -> _SignatureVerifier:
        """Create a verifier for the supplied public key bytes."""
        ...


class _NaclSignatureVerifier:
    """Typed adapter around a lazily-created PyNaCl VerifyKey instance."""

    def __init__(self, verifier: object) -> None:
        self._verifier = verifier

    def verify(self, message: bytes, signature: bytes | None = None) -> bytes:
        """Verify a signature and normalize the PyNaCl return value to bytes."""
        verify_method = getattr(self._verifier, "verify", None)
        if not callable(verify_method):
            raise TypeError("PyNaCl verifier does not expose a callable verify method")
        result = verify_method(message, signature)
        if not isinstance(result, bytes):
            raise TypeError("PyNaCl verifier returned a non-bytes result")
        return result


def _load_nacl_verifier() -> tuple[type[Exception], _VerifyKeyFactory]:
    """Load PyNaCl verification primitives only when signature checks are needed."""
    try:
        from nacl.exceptions import (
            BadSignatureError as bad_signature_error,  # noqa: N813
        )
        from nacl.signing import VerifyKey as verify_key_type  # noqa: N813
    except ModuleNotFoundError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "PyNaCl is required for portable proof signature verification"
        ) from exc

    def make_verify_key(key: bytes) -> _SignatureVerifier:
        return _NaclSignatureVerifier(verify_key_type(key))

    return cast(type[Exception], bad_signature_error), make_verify_key


def canonical(value: object) -> bytes:
    """Return StateWake-compatible canonical JSON bytes."""
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()


def digest(data: bytes) -> str:
    """Return a SHA-256 digest."""
    return hashlib.sha256(data).hexdigest()


def load_json(data: bytes, *, label: str) -> dict[str, object]:
    """Parse a bounded JSON object."""
    if len(data) > MAX_INPUT_BYTES:
        raise ValueError(f"{label} exceeds maximum input size")

    def walk(value: object, depth: int, nodes: list[int]) -> None:
        nodes[0] += 1
        if nodes[0] > MAX_JSON_NODES:
            raise ValueError("JSON node count exceeds containment limit")
        if depth > MAX_JSON_DEPTH:
            raise ValueError("JSON nesting depth exceeds containment limit")
        if isinstance(value, str):
            if len(value.encode("utf-8")) > MAX_STRING_BYTES:
                raise ValueError("JSON string exceeds containment limit")
        elif isinstance(value, dict):
            for key, child in value.items():
                if len(str(key).encode("utf-8")) > MAX_STRING_BYTES:
                    raise ValueError("JSON key exceeds containment limit")
                walk(child, depth + 1, nodes)
        elif isinstance(value, list):
            for child in value:
                walk(child, depth + 1, nodes)

    def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, child in pairs:
            if key in result:
                raise ValueError(f"{label} contains duplicate JSON key: {key}")
            result[key] = child
        return result

    value = json.loads(
        data.decode("utf-8"),
        object_pairs_hook=unique_object,
        parse_constant=lambda value: (_ for _ in ()).throw(
            ValueError(f"invalid JSON constant: {value}")
        ),
    )
    walk(value, 0, [0])
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def check_hex(value: object, *, label: str) -> None:
    """Validate a SHA-256 hexadecimal value."""
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(c not in HEXDIGEST for c in value)
    ):
        raise ValueError(f"{label} must be lowercase SHA-256 hex")


def validate_reference(value: str) -> None:
    """Reject URI-bearing evidence references unless explicitly approved."""
    from urllib.parse import urlparse

    parsed = urlparse(value)
    scheme = parsed.scheme.lower()
    if scheme or parsed.netloc:
        raise ValueError(f"external reference scheme is not approved: {scheme}")
    normalized = value.replace("\\", "/")
    if normalized.startswith("/") or ".." in normalized.split("/"):
        raise ValueError("absolute or traversing evidence references are not permitted")


def artifact_member(artifact: dict[str, object]) -> str:
    """Return the canonical ZIP member for one manifest artifact."""
    artifact_id = str(artifact["artifact_id"])
    path = str(artifact["path"]).replace("\\", "/")
    if (
        not artifact_id
        or any(separator in artifact_id for separator in ("/", "\\", ":", "\x00"))
        or artifact_id in {".", ".."}
    ):
        raise ValueError(f"invalid artifact id: {artifact_id!r}")
    parts = path.split("/")
    if (
        not path
        or path.startswith("/")
        or any(part in {"", ".", ".."} for part in parts)
        or "\x00" in path
    ):
        raise ValueError(f"invalid artifact path: {path!r}")
    return f"artifacts/{artifact_id}/{path}"


def verify_manifest(archive: ZipFile) -> tuple[dict[str, object], dict[str, bytes]]:
    """Verify manifest identity, package membership, sizes, and digests."""
    names = archive.namelist()
    if len(names) > MAX_ARCHIVE_MEMBERS:
        raise ValueError("archive member count exceeds containment limit")
    total_size = 0
    for info in archive.infolist():
        if info.file_size > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
            raise ValueError("archive member size exceeds containment limit")
        total_size += info.file_size
        if total_size > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
            raise ValueError("archive aggregate size exceeds containment limit")
        compressed = max(info.compress_size, 1)
        if info.file_size / compressed > MAX_ARCHIVE_COMPRESSION_RATIO:
            raise ValueError("archive compression ratio exceeds containment limit")
        mode = (info.external_attr >> 16) & 0xFFFF
        if mode and (mode & 0o170000) == 0o120000:
            raise ValueError("archive symlinks are not permitted")
    if len(names) != len(set(names)):
        raise ValueError("duplicate ZIP member names")
    if "manifest.json" not in names:
        raise ValueError("missing manifest.json")
    manifest = load_json(archive.read("manifest.json"), label="manifest")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise ValueError("manifest artifacts must be a non-empty array")
    artifact_ids: set[str] = set()
    expected: set[str] = set()
    contents: dict[str, bytes] = {}
    for raw in artifacts:
        if not isinstance(raw, dict):
            raise ValueError("artifact entry must be an object")
        artifact_id = str(raw.get("artifact_id", ""))
        if artifact_id in artifact_ids:
            raise ValueError(f"duplicate artifact id: {artifact_id}")
        artifact_ids.add(artifact_id)
        member = artifact_member(raw)
        expected.add(member)
        raw_digest = raw.get("sha256")
        check_hex(raw_digest, label=f"artifact {artifact_id} sha256")
        size = raw.get("size_bytes")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise ValueError(f"invalid artifact size: {artifact_id}")
        try:
            info = archive.getinfo(member)
            data = archive.read(member)
        except KeyError as exc:
            raise ValueError(f"missing artifact member: {member}") from exc
        if info.file_size != size or len(data) != size:
            raise ValueError(f"artifact size mismatch: {artifact_id}")
        if digest(data) != raw_digest:
            raise ValueError(f"artifact digest mismatch: {artifact_id}")
        contents[artifact_id] = data
    actual = set(names) - {"manifest.json"}
    if actual != expected:
        raise ValueError("ZIP members do not exactly match manifest")
    manifest_id = manifest.get("manifest_id")
    if not isinstance(manifest_id, str):
        raise ValueError("manifest_id missing")
    manifest_payload = dict(manifest)
    manifest_payload.pop("bundle_id", None)
    manifest_payload.pop("manifest_id", None)
    if digest(canonical(manifest_payload)) != manifest_id:
        raise ValueError("manifest_id integrity check failed")
    bundle_id = manifest.get("bundle_id")
    if not isinstance(bundle_id, str):
        raise ValueError("bundle_id missing")
    recompute = dict(manifest)
    recompute.pop("bundle_id", None)
    recompute["manifest_id"] = manifest_id
    if digest(canonical(recompute)) != bundle_id:
        raise ValueError("bundle_id integrity check failed")
    return manifest, contents


def verify_descriptor(
    manifest: dict[str, object], contents: dict[str, bytes]
) -> dict[str, object]:
    """Verify the portable proof descriptor and package completeness contract."""
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        raise ValueError("manifest artifacts must be an array")
    descriptor_entries = [
        a
        for a in artifacts
        if isinstance(a, dict) and a.get("kind") == "reliability-proof-descriptor"
    ]
    if len(descriptor_entries) != 1:
        raise ValueError("exactly one proof descriptor is required")
    descriptor_id = str(descriptor_entries[0]["artifact_id"])
    descriptor = load_json(contents[descriptor_id], label="proof descriptor")
    raw_digest = descriptor.get("digest")
    descriptor_payload = dict(descriptor)
    descriptor_payload.pop("digest", None)
    if digest(canonical(descriptor_payload)) != raw_digest:
        raise ValueError("proof descriptor digest mismatch")
    if (
        descriptor.get("format_version") != "3"
        or descriptor.get("bundle_type") != "reliability-proof"
    ):
        raise ValueError("Tier 9 requires reliability-proof format version 3")
    for field in (
        "attestation_digest",
        "evidence_chain_digest",
        "transition_digest",
        "verification_report_digest",
        "completeness_digest",
    ):
        check_hex(descriptor.get(field), label=field)
    required = {
        str(descriptor["attestation_artifact_id"]),
        str(descriptor["evidence_chain_artifact_id"]),
        str(descriptor["state_history_artifact_id"]),
        str(descriptor["verification_report_artifact_id"]),
        descriptor_id,
        str(descriptor["completeness_artifact_id"]),
    }
    lineage_entries = [
        a
        for a in artifacts
        if isinstance(a, dict) and a.get("kind") == "reliability-lineage-closure"
    ]
    if len(lineage_entries) != 1:
        raise ValueError("exactly one lineage closure is required")
    lineage_id = str(lineage_entries[0]["artifact_id"])
    required.add(lineage_id)
    lineage = load_json(contents[lineage_id], label="lineage closure")
    lineage_digest = lineage.get("digest")
    lineage_payload = dict(lineage)
    lineage_payload.pop("digest", None)
    if digest(canonical(lineage_payload)) != lineage_digest:
        raise ValueError("lineage closure digest mismatch")
    if descriptor.get("lineage_closure") != lineage:
        raise ValueError("descriptor lineage closure binding mismatch")
    trust_context = descriptor.get("attestation_trust_context")
    if trust_context is not None:
        if not isinstance(trust_context, dict):
            raise ValueError("attestation trust context must be an object")
        context_payload = dict(trust_context)
        context_digest = context_payload.pop("digest", None)
        if digest(canonical(context_payload)) != context_digest:
            raise ValueError("attestation trust context digest mismatch")
        context_entries = [
            a
            for a in artifacts
            if isinstance(a, dict)
            and a.get("kind") == "reliability-attestation-trust-context"
        ]
        if len(context_entries) != 1:
            raise ValueError("trust context requires exactly one context artifact")
        required.add(str(context_entries[0]["artifact_id"]))
        for field in (
            "envelope_artifact_id",
            "trust_state_artifact_id",
            "authority_store_artifact_id",
        ):
            required.add(str(trust_context[field]))
    missing = sorted(required - set(contents))
    if missing:
        raise ValueError("portable proof is incomplete: " + ", ".join(missing))
    completeness_id = str(descriptor["completeness_artifact_id"])
    completeness = load_json(contents[completeness_id], label="proof completeness")
    c_digest = completeness.get("digest")
    c_payload = dict(completeness)
    c_payload.pop("digest", None)
    if (
        digest(canonical(c_payload)) != c_digest
        or c_digest != descriptor["completeness_digest"]
    ):
        raise ValueError("proof completeness digest mismatch")
    covered = completeness.get("covered_artifact_ids")
    if not isinstance(covered, list) or set(map(str, covered)) != set(contents):
        raise ValueError(
            "proof completeness does not cover the exact package artifact set"
        )
    sources = descriptor.get("sources")
    if not isinstance(sources, list):
        raise ValueError("descriptor sources must be an array")
    source_keys = [str(s.get("reference_key")) for s in sources if isinstance(s, dict)]
    if len(source_keys) != len(set(source_keys)):
        raise ValueError("duplicate proof source reference keys")
    artifact_metadata = {
        str(artifact.get("artifact_id")): artifact
        for artifact in artifacts
        if isinstance(artifact, dict)
    }
    for source in sources:
        if not isinstance(source, dict):
            raise ValueError("proof source must be an object")
        reference = source.get("source")
        if not isinstance(reference, str):
            raise ValueError("proof source reference must be text")
        validate_reference(reference)
        source_artifact_id = str(source.get("artifact_id", ""))
        source_artifact = artifact_metadata.get(source_artifact_id)
        if source_artifact is None:
            raise ValueError("proof source artifact is not in the package")
        check_hex(source.get("digest"), label="proof source digest")
        check_hex(source.get("reference_digest"), label="proof source reference digest")
        if source.get("digest") != source_artifact.get("sha256"):
            raise ValueError("proof source digest does not match its packaged artifact")
    # Bind each required artifact to the digest carried by the descriptor.
    for field, artifact_field in (
        ("attestation_digest", "attestation_artifact_id"),
        ("evidence_chain_digest", "evidence_chain_artifact_id"),
        ("verification_report_digest", "verification_report_artifact_id"),
    ):
        artifact_id = str(descriptor[artifact_field])
        payload = load_json(contents[artifact_id], label=artifact_field)
        supplied = payload.get("digest")
        if supplied != descriptor[field]:
            raise ValueError(f"{field} does not match its packaged artifact")
    return descriptor


def verify_attestation(
    manifest: dict[str, object],
    contents: dict[str, bytes],
    descriptor: dict[str, object],
    trust_root: dict[str, bytes] | None,
) -> str:
    """Verify attestation integrity and, when supplied, its Ed25519 trust root."""
    att_id = str(descriptor["attestation_artifact_id"])
    attestation = load_json(contents[att_id], label="attestation")
    att_payload = dict(attestation)
    supplied = att_payload.pop("digest", "")
    att_payload.pop("format_version", None)
    if (
        digest(canonical(att_payload)) != supplied
        or supplied != descriptor["attestation_digest"]
    ):
        raise ValueError("attestation digest mismatch")
    if attestation.get("verification_status") != "verified":
        raise ValueError("attestation does not assert verified evidence")
    context = descriptor.get("attestation_trust_context")
    if context is None:
        return "TRUST_ANCHOR_UNAVAILABLE"
    if not isinstance(context, dict):
        raise ValueError("attestation trust context must be an object")
    envelope = load_json(
        contents[str(context["envelope_artifact_id"])],
        label="signed attestation envelope",
    )
    trust_state = load_json(
        contents[str(context["trust_state_artifact_id"])],
        label="attestation trust state",
    )
    authority = load_json(
        contents[str(context["authority_store_artifact_id"])],
        label="attestation authority store",
    )
    if trust_root is None:
        return "TRUST_ANCHOR_UNAVAILABLE"
    authority_id = str(trust_state.get("authority_key_id"))
    key_text = trust_root.get(authority_id)
    if key_text is None:
        return "TRUST_ANCHOR_UNAVAILABLE"
    manifest_artifacts = manifest.get("artifacts")
    if not isinstance(manifest_artifacts, list):
        raise ValueError("manifest artifacts must be an array")
    context_entries = [
        artifact
        for artifact in manifest_artifacts
        if isinstance(artifact, dict)
        and artifact.get("kind") == "reliability-attestation-trust-context"
    ]
    if len(context_entries) != 1:
        raise ValueError("exactly one packaged attestation trust context is required")
    context_id = str(context_entries[0]["artifact_id"])
    context_payload = load_json(contents[context_id], label="attestation trust context")
    if context_payload != context:
        raise ValueError("packaged attestation trust context mismatch")
    # The descriptor embeds this contract; the separate artifact is checked by
    # its manifest hash. Verify all cross-artifact bindings before signatures.
    expected = {
        "authority_key_id": authority_id,
        "trust_state_version": trust_state.get("version"),
        "attestation_id": descriptor.get("attestation_id"),
        "attestation_digest": attestation.get("digest"),
        "signing_key_id": envelope.get("key_id"),
    }
    for field, value in expected.items():
        if context.get(field) != value:
            raise ValueError(f"attestation trust context {field} binding mismatch")
    bad_signature_error, verify_key = _load_nacl_verifier()
    envelope_bytes = canonical(envelope)
    trust_state_payload = dict(trust_state)
    trust_state_signature = trust_state_payload.pop("signature", None)
    if trust_state_signature is None:
        raise ValueError("attestation trust state has no signature")
    authority_keys = authority.get("keys")
    if not isinstance(authority_keys, dict):
        raise ValueError("attestation authority store keys must be an object")
    encoded_authority = authority_keys.get(authority_id)
    if not isinstance(encoded_authority, str):
        raise ValueError("authority key is missing from packaged authority store")
    authority_key = base64.urlsafe_b64decode(
        encoded_authority + "=" * (-len(encoded_authority) % 4)
    )
    if authority_key != key_text:
        raise ValueError("external trust root does not match packaged authority key")
    signed_payload = dict(trust_state)
    signature = signed_payload.pop("signature", "")
    try:
        verify_key(key_text).verify(
            canonical(signed_payload),
            base64.urlsafe_b64decode(str(signature) + "=" * (-len(str(signature)) % 4)),
        )
    except (bad_signature_error, ValueError) as exc:
        raise ValueError(
            "attestation trust-state signature verification failed"
        ) from exc
    anchors = trust_state.get("anchors")
    if not isinstance(anchors, list):
        raise ValueError("trust state anchors must be an array")
    key_id = str(envelope.get("key_id"))
    anchor = next(
        (a for a in anchors if isinstance(a, dict) and a.get("key_id") == key_id), None
    )
    if anchor is None:
        raise ValueError("attestation signing key is absent from trust state")
    if anchor.get("status") != "active":
        raise ValueError("attestation signing key is not active")
    public_key_b64 = str(anchor.get("public_key"))
    public_key = base64.urlsafe_b64decode(
        public_key_b64 + "=" * (-len(public_key_b64) % 4)
    )
    bindings = {
        "envelope_digest": digest(envelope_bytes),
        "trust_state_digest": digest(canonical(trust_state_payload)),
        "authority_key_digest": digest(key_text),
        "signing_key_digest": digest(public_key),
    }
    for field, value in bindings.items():
        if context.get(field) != value:
            raise ValueError(f"attestation trust context {field} mismatch")
    envelope_att = envelope.get("attestation")
    if not isinstance(envelope_att, dict):
        raise ValueError("signed attestation payload missing")
    payload_digest = str(envelope.get("payload_digest"))
    if digest(canonical(envelope_att)) != payload_digest:
        raise ValueError("signed attestation payload digest mismatch")
    if envelope_att.get("digest") != attestation.get("digest"):
        raise ValueError("signed attestation does not match packaged attestation")
    try:
        verify_key(public_key).verify(
            canonical({"attestation": envelope_att, "payload_digest": payload_digest}),
            base64.urlsafe_b64decode(
                str(envelope.get("signature"))
                + "=" * (-len(str(envelope.get("signature"))) % 4)
            ),
        )
    except (bad_signature_error, ValueError) as exc:
        raise ValueError(
            "signed reliability attestation signature verification failed"
        ) from exc
    return "VERIFIED"


def verify_package(
    path: Path, trust_root_path: Path | None = None
) -> tuple[str, list[str]]:
    """Verify a portable proof package without importing StateWake."""
    warnings: list[str] = []
    try:
        if path.stat().st_size > MAX_INPUT_BYTES:
            return "INVALID", ["portable proof package exceeds maximum input size"]
        with ZipFile(path) as archive:
            manifest, contents = verify_manifest(archive)
            descriptor = verify_descriptor(manifest, contents)
            report_id = str(descriptor["verification_report_artifact_id"])
            report = load_json(contents[report_id], label="verification report")
            if report.get("verified") is not True or report.get("failures") != []:
                raise ValueError(
                    "packaged verification report is not a successful verification"
                )
            attestation_id = str(descriptor["attestation_artifact_id"])
            attestation = load_json(contents[attestation_id], label="attestation")
            if attestation.get("attestation_id") != descriptor.get("attestation_id"):
                raise ValueError("attestation identity mismatch")
            if attestation.get("evidence_chain_id") != descriptor.get(
                "evidence_chain_id"
            ):
                raise ValueError("evidence-chain identity mismatch")
            if attestation.get("transition_id") != descriptor.get("transition_id"):
                raise ValueError("transition identity mismatch")
            for field in (
                "evidence_chain_digest",
                "transition_digest",
                "reliability_state",
                "decision",
            ):
                if attestation.get(field) != descriptor.get(field):
                    raise ValueError(f"attestation {field} binding mismatch")
            chain = load_json(
                contents[str(descriptor["evidence_chain_artifact_id"])],
                label="evidence chain",
            )
            chain_digest = str(chain.get("digest", ""))
            chain_payload = dict(chain)
            chain_payload.pop("digest", None)
            chain_payload.pop("format_version", None)
            if digest(canonical(chain_payload)) != chain_digest:
                raise ValueError("evidence-chain digest integrity failure")
            if chain.get("chain_id") != descriptor.get(
                "evidence_chain_id"
            ) or chain_digest != descriptor.get("evidence_chain_digest"):
                raise ValueError("evidence-chain binding mismatch")
            state_history = contents[
                str(descriptor["state_history_artifact_id"])
            ].decode("utf-8")
            transitions = [
                load_json(line.encode("utf-8"), label="state-history transition")
                for line in state_history.splitlines()
                if line.strip()
            ]
            if not transitions:
                raise ValueError("state history is incomplete")
            if len(transitions) > MAX_JSON_NODES:
                raise ValueError(
                    "state history transition count exceeds containment limit"
                )
            matches = [
                item
                for item in transitions
                if item.get("transition_id") == descriptor.get("transition_id")
            ]
            if len(matches) != 1:
                raise ValueError(
                    "state history transition identity is missing or ambiguous"
                )
            transition = matches[0]
            if transition.get("digest") != descriptor.get("transition_digest"):
                raise ValueError("state transition binding mismatch")
            transition_digest = str(transition.get("digest", ""))
            transition_payload = dict(transition)
            transition_payload.pop("digest", None)
            if digest(canonical(transition_payload)) != transition_digest:
                raise ValueError("state transition digest integrity failure")
            if transition.get("evidence_chain_digest") != descriptor.get(
                "evidence_chain_digest"
            ):
                raise ValueError("state transition evidence binding mismatch")
            trust_root = None
            if trust_root_path is not None:
                if trust_root_path.stat().st_size > MAX_INPUT_BYTES:
                    raise ValueError("trust root exceeds maximum input size")
                payload = load_json(trust_root_path.read_bytes(), label="trust root")
                keys = payload.get("keys")
                if not isinstance(keys, dict):
                    raise ValueError("trust root must contain a keys object")
                trust_root = {
                    str(key): base64.urlsafe_b64decode(
                        str(value) + "=" * (-len(str(value)) % 4)
                    )
                    for key, value in keys.items()
                }
            status = verify_attestation(manifest, contents, descriptor, trust_root)
            if status == "TRUST_ANCHOR_UNAVAILABLE":
                warnings.append(
                    "integrity/provenance/transition verified, but no explicit external trust root was supplied"
                )
                return "VERIFIED_WITH_LIMITATIONS", warnings
            return status, warnings
    except (
        ValueError,
        KeyError,
        json.JSONDecodeError,
        BadZipFile,
        OSError,
        RuntimeError,
    ) as exc:
        message = str(exc)
        lowered = message.lower()
        if "digest" in lowered or "tamper" in lowered or "mismatch" in lowered:
            return "TAMPERED", [message]
        if "missing" in lowered or "incomplete" in lowered:
            return "INCOMPLETE", [message]
        return "INVALID", [message]


def main() -> int:
    """Run independent portable-proof verification."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("--trust-root", type=Path)
    args = parser.parse_args()
    status, messages = verify_package(args.package, args.trust_root)
    print(status)
    for message in messages:
        print(message, file=sys.stderr)
    return 0 if status in {"VERIFIED", "VERIFIED_WITH_LIMITATIONS"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
