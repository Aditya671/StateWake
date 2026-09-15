"""Independent persistent checkpoint trust-anchor contracts for StateWake."""

from __future__ import annotations

import base64
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from typing import Protocol

from statewake.utils.json_support import JsonValue, require_int, require_string
from statewake.utils.signatures import verify_ed25519_signature


class TrustAnchorError(ValueError):
    """Base error for trust-anchor protocol violations."""


class AnchorDiscrepancyError(TrustAnchorError):
    """Indicate disagreement between local history and an independent anchor."""


_HEX = set("0123456789abcdef")


def _canonical(payload: Mapping[str, JsonValue]) -> bytes:
    """Encode a JSON object deterministically for hashing and signing."""
    return json.dumps(
        dict(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _b64encode(value: bytes) -> str:
    """Encode bytes as unpadded URL-safe base64."""
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str, *, field: str) -> bytes:
    """Decode unpadded URL-safe base64 with a useful field error."""
    if not value:
        raise TrustAnchorError(f"{field} must not be empty.")
    try:
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except (ValueError, UnicodeEncodeError) as exc:
        raise TrustAnchorError(f"{field} contains invalid base64.") from exc


def _require_sha256(value: str, *, field: str) -> None:
    """Require a lowercase SHA-256 digest."""
    if len(value) != 64 or any(character not in _HEX for character in value):
        raise TrustAnchorError(f"{field} must be lowercase SHA-256 hex.")


@dataclass(frozen=True, slots=True)
class TrustCheckpoint:
    """Signed statement that a particular local history tip existed at a time."""

    checkpoint_id: str
    subject_id: str
    issued_at: str
    history_tip_digest: str
    history_record_count: int
    signing_key_id: str
    signing_key_digest: str
    signature: str
    previous_checkpoint_digest: str | None = None
    format_version: str = "1"

    def __post_init__(self) -> None:
        """Validate checkpoint identity, ordering fields, and cryptographic bindings."""
        if self.format_version != "1":
            raise TrustAnchorError("unsupported trust-checkpoint format version.")
        for field in (
            "checkpoint_id",
            "subject_id",
            "issued_at",
            "signing_key_id",
            "signature",
        ):
            if not getattr(self, field).strip():
                raise TrustAnchorError(f"{field} must not be empty.")
        _require_sha256(self.history_tip_digest, field="history_tip_digest")
        _require_sha256(self.signing_key_digest, field="signing_key_digest")
        if self.history_record_count < 0:
            raise TrustAnchorError("history_record_count must be >= 0.")
        if self.previous_checkpoint_digest is not None:
            _require_sha256(
                self.previous_checkpoint_digest, field="previous_checkpoint_digest"
            )

    def payload(self) -> dict[str, JsonValue]:
        """Return the unsigned checkpoint payload."""
        return {
            "format_version": self.format_version,
            "checkpoint_id": self.checkpoint_id,
            "subject_id": self.subject_id,
            "issued_at": self.issued_at,
            "history_tip_digest": self.history_tip_digest,
            "history_record_count": self.history_record_count,
            "signing_key_id": self.signing_key_id,
            "signing_key_digest": self.signing_key_digest,
            "previous_checkpoint_digest": self.previous_checkpoint_digest,
        }

    def payload_bytes(self) -> bytes:
        """Return canonical bytes used by the checkpoint signature."""
        return _canonical(self.payload())

    def digest(self) -> str:
        """Return the deterministic digest of the signed checkpoint payload."""
        return sha256(self.payload_bytes()).hexdigest()

    def to_dict(self) -> dict[str, JsonValue]:
        """Serialize the checkpoint without changing its signed payload."""
        return {**self.payload(), "signature": self.signature}

    @classmethod
    def from_dict(cls, payload: Mapping[str, JsonValue]) -> TrustCheckpoint:
        """Construct a checkpoint from a validated JSON object."""
        return cls(
            format_version=require_string(
                payload.get("format_version", "1"), field="format_version"
            ),
            checkpoint_id=require_string(
                payload["checkpoint_id"], field="checkpoint_id"
            ),
            subject_id=require_string(payload["subject_id"], field="subject_id"),
            issued_at=require_string(payload["issued_at"], field="issued_at"),
            history_tip_digest=require_string(
                payload["history_tip_digest"], field="history_tip_digest"
            ),
            history_record_count=require_int(
                payload["history_record_count"], field="history_record_count"
            ),
            signing_key_id=require_string(
                payload["signing_key_id"], field="signing_key_id"
            ),
            signing_key_digest=require_string(
                payload["signing_key_digest"], field="signing_key_digest"
            ),
            signature=require_string(payload["signature"], field="signature"),
            previous_checkpoint_digest=None
            if payload.get("previous_checkpoint_digest") is None
            else require_string(
                payload["previous_checkpoint_digest"],
                field="previous_checkpoint_digest",
            ),
        )


class TrustAnchor(Protocol):
    """Persist and retrieve independently stored signed checkpoints."""

    def publish(self, checkpoint: TrustCheckpoint) -> None:
        """Persist a new checkpoint without overwriting an existing checkpoint."""
        ...

    def retrieve(self, checkpoint_id: str) -> TrustCheckpoint:
        """Retrieve one previously published checkpoint."""
        ...

    def verify(self, checkpoint: TrustCheckpoint) -> TrustCheckpoint:
        """Verify the checkpoint signature against separately supplied public keys."""
        ...


class CheckpointSigner(Protocol):
    """Sign checkpoint payloads using a separately managed private key."""

    def sign(self, key_id: str, payload: bytes) -> bytes:
        """Return a raw signature for the supplied payload."""
        ...


class TrustCheckpointVerifier(Protocol):
    """Verify signed checkpoints against a separately managed verification boundary."""

    def verify(self, checkpoint: TrustCheckpoint) -> TrustCheckpoint:
        """Verify a checkpoint and return it when valid."""
        ...


class Ed25519TrustCheckpointVerifier:
    """Verify checkpoints with public keys held outside the local history store."""

    def __init__(self, public_keys: Mapping[str, bytes]) -> None:
        """Initialize the verifier with trusted public keys keyed by signing ID."""
        self._public_keys = dict(public_keys)

    def verify(self, checkpoint: TrustCheckpoint) -> TrustCheckpoint:
        """Verify the signed payload and signing-key digest binding."""
        try:
            public_key = self._public_keys[checkpoint.signing_key_id]
        except KeyError as exc:
            raise TrustAnchorError(
                f"unknown trust-checkpoint signing key: {checkpoint.signing_key_id}"
            ) from exc
        if sha256(public_key).hexdigest() != checkpoint.signing_key_digest:
            raise TrustAnchorError("trust-checkpoint signing key digest mismatch.")
        try:
            verify_ed25519_signature(
                public_key,
                checkpoint.payload_bytes(),
                _b64decode(checkpoint.signature, field="signature"),
            )
        except (RuntimeError, ValueError) as exc:
            raise TrustAnchorError(
                "trust-checkpoint signature verification failed."
            ) from exc
        return checkpoint


def create_trust_checkpoint(
    *,
    checkpoint_id: str,
    subject_id: str,
    issued_at: str,
    history_tip_digest: str,
    history_record_count: int,
    signing_key_id: str,
    signing_key_digest: str,
    signature: bytes,
    previous_checkpoint_digest: str | None = None,
) -> TrustCheckpoint:
    """Create a signed-checkpoint value from externally produced signature bytes."""
    return TrustCheckpoint(
        checkpoint_id=checkpoint_id,
        subject_id=subject_id,
        issued_at=issued_at,
        history_tip_digest=history_tip_digest,
        history_record_count=history_record_count,
        signing_key_id=signing_key_id,
        signing_key_digest=signing_key_digest,
        signature=_b64encode(signature),
        previous_checkpoint_digest=previous_checkpoint_digest,
    )


def compare_local_tip(
    checkpoint: TrustCheckpoint,
    *,
    history_tip_digest: str,
    history_record_count: int,
) -> None:
    """Reject local history that disagrees with an independently anchored checkpoint."""
    _require_sha256(history_tip_digest, field="history_tip_digest")
    if history_record_count < 0:
        raise TrustAnchorError("history_record_count must be >= 0.")
    if (
        checkpoint.history_tip_digest != history_tip_digest
        or checkpoint.history_record_count != history_record_count
    ):
        raise AnchorDiscrepancyError(
            "local history disagrees with the independent trust checkpoint; "
            "investigation and reconciliation are required."
        )


def ensure_checkpoint_sequence(
    previous: TrustCheckpoint | None,
    current: TrustCheckpoint,
) -> None:
    """Require monotonic checkpoint continuity without silent repair."""
    if previous is None:
        if current.previous_checkpoint_digest is not None:
            raise AnchorDiscrepancyError(
                "first checkpoint unexpectedly references a previous checkpoint."
            )
        return
    if current.previous_checkpoint_digest != previous.digest():
        raise AnchorDiscrepancyError("trust checkpoint sequence is discontinuous.")
    if current.history_record_count < previous.history_record_count:
        raise AnchorDiscrepancyError("trust checkpoint sequence rolled back history.")


__all__: Sequence[str] = (
    "AnchorDiscrepancyError",
    "CheckpointSigner",
    "Ed25519TrustCheckpointVerifier",
    "TrustAnchor",
    "TrustAnchorError",
    "TrustCheckpoint",
    "TrustCheckpointVerifier",
    "compare_local_tip",
    "create_trust_checkpoint",
    "ensure_checkpoint_sequence",
)
