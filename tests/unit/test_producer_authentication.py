"""Producer key trust must originate outside caller-supplied evidence."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from hashlib import sha256

import pytest

from statewake.domain.evidence_receipt import ExternalEvidenceReceipt
from statewake.domain.producer_authentication import authenticate_producer_receipt


def receipt() -> ExternalEvidenceReceipt:
    return ExternalEvidenceReceipt(
        producer_type="integration",
        producer_id="producer-a",
        artifact_digest=sha256(b"payload").hexdigest(),
        artifact_size=7,
        captured_at=datetime(2026, 9, 23, tzinfo=UTC),
        source_ref="run:1",
    )


def test_identity_is_not_a_trust_key() -> None:
    with pytest.raises(ValueError, match="independently trusted"):
        authenticate_producer_receipt(
            receipt(), key_id="self-claimed", signature=b"a" * 64, trusted_producers={}
        )


def test_modified_receipt_metadata_fails_before_authentication() -> None:
    value = receipt()
    value.metadata["secret"] = "changed"
    with pytest.raises(ValueError, match="modified"):
        authenticate_producer_receipt(
            value,
            key_id="k",
            signature=b"a" * 64,
            trusted_producers={("integration", "producer-a", "k"): b"k" * 32},
        )


def test_signed_receipt_when_cryptography_dependency_available() -> None:
    signing = pytest.importorskip("nacl.signing")
    value = receipt()
    key = signing.SigningKey.generate()
    message = json.dumps(
        value.payload(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    signature = key.sign(message).signature
    report = authenticate_producer_receipt(
        value,
        key_id="k",
        signature=signature,
        trusted_producers={("integration", "producer-a", "k"): bytes(key.verify_key)},
    )
    assert report.receipt_digest == value.digest
    assert report.authentication == "ed25519-signature-verified"
    assert not report.artifact_bytes_verified
    with pytest.raises(ValueError, match="signature"):
        authenticate_producer_receipt(
            value,
            key_id="k",
            signature=b"0" * 64,
            trusted_producers={
                ("integration", "producer-a", "k"): bytes(key.verify_key)
            },
        )
