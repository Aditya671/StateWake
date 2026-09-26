"""Optional authenticated producer receipts with externally supplied trust keys.

Receipt digests bind claimed bytes; a detached signature authenticates the
receipt assertion only when its producer's key is independently configured.
Neither operation attests that the producer's report is true or that artifact
bytes have been read and checked by the verifier.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass

from statewake.domain.evidence_receipt import ExternalEvidenceReceipt
from statewake.utils.signatures import verify_ed25519_signature


@dataclass(frozen=True, slots=True)
class AuthenticatedProducerReceipt:
    """A receipt whose assertion was signed by a configured producer key."""

    receipt_digest: str
    producer_type: str
    producer_id: str
    key_id: str
    authentication: str = "ed25519-signature-verified"
    artifact_bytes_verified: bool = False


def authenticate_producer_receipt(
    receipt: ExternalEvidenceReceipt,
    *,
    key_id: str,
    signature: bytes,
    trusted_producers: Mapping[tuple[str, str, str], bytes],
) -> AuthenticatedProducerReceipt:
    """Verify a detached signature over the exact canonical receipt payload.

    Trust keys are supplied by the relying application, never taken from the
    receipt or signature. A missing producer/key binding fails closed. The
    receipt's own digest is recomputed before signature verification, since a
    frozen dataclass may still contain mutable metadata supplied by a caller.
    """
    if not key_id or not key_id.strip():
        raise ValueError("producer key_id must be nonblank")
    if receipt.computed_digest() != receipt.digest:
        raise ValueError("producer receipt has been modified since capture")
    public_key = trusted_producers.get(
        (receipt.producer_type, receipt.producer_id, key_id)
    )
    if public_key is None or len(public_key) != 32:
        raise ValueError("producer key is not independently trusted")
    if len(signature) != 64:
        raise ValueError("producer signature must be 64 bytes")
    # Preserve the canonical serialization already used by the receipt model.
    message = json.dumps(
        receipt.payload(),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    verify_ed25519_signature(public_key, message, signature)
    return AuthenticatedProducerReceipt(
        receipt_digest=receipt.digest,
        producer_type=receipt.producer_type,
        producer_id=receipt.producer_id,
        key_id=key_id,
    )


__all__ = ["AuthenticatedProducerReceipt", "authenticate_producer_receipt"]
