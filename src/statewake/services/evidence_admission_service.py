"""Admission/conformance verification for external evidence adapter outputs."""

from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256
from pathlib import Path

from statewake.utils.json_support import load_object

from ..domain.evidence_admission import ExternalEvidenceAdmission
from ..domain.evidence_receipt import ExternalEvidenceReceipt
from ..domain.reliability_evidence import EvidenceReference


def _file_digest(path: Path) -> str:
    """Return the SHA-256 digest of a file."""
    return sha256(path.read_bytes()).hexdigest()


def admit_external_evidence(
    receipt: ExternalEvidenceReceipt,
    *,
    artifact_path: Path,
    receipt_path: Path | None = None,
    expected_run_id: str | None = None,
    expected_producer_type: str | None = None,
    expected_producer_id: str | None = None,
) -> ExternalEvidenceAdmission:
    """Prove that one external adapter receipt is safe to consume as V1 evidence."""
    if not artifact_path.is_file():
        raise FileNotFoundError(
            f"external evidence artifact not found: {artifact_path}"
        )
    content_digest = _file_digest(artifact_path)
    artifact_size = artifact_path.stat().st_size
    if content_digest != receipt.artifact_digest:
        raise ValueError(
            "external evidence receipt artifact digest does not match artifact"
        )
    if artifact_size != receipt.artifact_size:
        raise ValueError(
            "external evidence receipt artifact size does not match artifact"
        )
    if expected_run_id is not None and receipt.run_id != expected_run_id:
        raise ValueError("external evidence receipt run_id does not match expected run")
    if (
        expected_producer_type is not None
        and receipt.producer_type != expected_producer_type
    ):
        raise ValueError(
            "external evidence receipt producer_type does not match expected producer"
        )
    if expected_producer_id is not None and receipt.producer_id != expected_producer_id:
        raise ValueError(
            "external evidence receipt producer_id does not match expected producer"
        )
    if receipt_path is not None:
        if not receipt_path.is_file():
            raise FileNotFoundError(
                f"external evidence receipt not found: {receipt_path}"
            )
        persisted = ExternalEvidenceReceipt.from_dict(load_object(receipt_path))
        if persisted != receipt:
            raise ValueError(
                "persisted external evidence receipt does not match adapter receipt"
            )

    receipt_ref = receipt.receipt_reference(
        source=None if receipt_path is None else receipt_path.name
    )
    evidence_ref = EvidenceReference(
        kind="evidence",
        identity=receipt.receipt_id,
        digest=receipt.artifact_digest,
        source=None,
        receipt_ref=receipt_ref,
    )
    if evidence_ref.identity != receipt.receipt_id:
        raise ValueError(
            "external evidence reference identity does not match canonical receipt identity"
        )
    if evidence_ref.digest != receipt.artifact_digest:
        raise ValueError(
            "external evidence reference digest does not match canonical artifact digest"
        )
    if evidence_ref.receipt_ref != receipt_ref:
        raise ValueError(
            "external evidence reference does not preserve canonical receipt binding"
        )

    return ExternalEvidenceAdmission(
        receipt_id=receipt.receipt_id,
        receipt_digest=receipt.digest,
        artifact_digest=receipt.artifact_digest,
        artifact_size=receipt.artifact_size,
        producer_type=receipt.producer_type,
        producer_id=receipt.producer_id,
        source_event_id=receipt.source_event_id,
        run_id=receipt.run_id,
        evidence_reference=evidence_ref,
    )


def load_external_evidence_admission(path: Path) -> ExternalEvidenceAdmission:
    """Load and validate a persisted external-evidence admission."""
    payload = load_object(path)
    if not isinstance(payload, Mapping):  # type: ignore
        raise ValueError("external evidence admission must be a JSON object")
    return ExternalEvidenceAdmission.from_dict(payload)
