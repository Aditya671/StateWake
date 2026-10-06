"""Persistence and lifecycle projection for canonical human-approval evidence."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from filelock import FileLock, Timeout

from statewake.adapters.content_store import ContentAddressedArtifactStore
from statewake.adapters.evidence_ingestion import (
    JsonEvidenceReceiptStore,
    LocalEvidenceIngestionAdapter,
)
from statewake.ai_contracts.base import canonical_json_bytes
from statewake.ai_contracts.human import (
    HumanApprovalContract,
    HumanApprovalRevocationContract,
)
from statewake.domain.evidence_receipt import ExternalEvidenceReceipt
from statewake.utils.json_support import loads_object

_APPROVAL_PRODUCER_TYPE = "statewake-human-approval"
_REVOCATION_PRODUCER_TYPE = "statewake-human-approval-revocation"
_DEFAULT_MAX_RECEIPTS = 2_000
ApprovalLifecycleStatus = Literal["active", "revoked", "superseded"]


class ApprovalIdempotencyConflictError(ValueError):
    """Raised when one approval idempotency key is reused for changed intent."""


class ApprovalAlreadyRecordedError(ValueError):
    """Raised when the same actor/action/scope already has an active approval."""


class ApprovalLifecycleConflictError(ValueError):
    """Raised when a lifecycle transition is invalid for the approval's current state."""


class ApprovalLifecycleTargetError(ValueError):
    """Raised when a lifecycle transition targets incompatible approval evidence."""


@dataclass(frozen=True, slots=True)
class HumanApprovalEvidenceRecord:
    """One canonical human-approval contract with its durable evidence receipt."""

    contract: HumanApprovalContract
    receipt: ExternalEvidenceReceipt

    def to_dict(self) -> dict[str, object]:
        """Return a bounded API representation of approval evidence and receipt."""
        return {
            "contract": self.contract.to_dict(),
            "receipt": _receipt_payload(self.receipt),
        }


@dataclass(frozen=True, slots=True)
class HumanApprovalRevocationEvidenceRecord:
    """One immutable approval-revocation contract and durable evidence receipt."""

    contract: HumanApprovalRevocationContract
    receipt: ExternalEvidenceReceipt

    def to_dict(self) -> dict[str, object]:
        """Return a bounded API representation of revocation evidence and receipt."""
        return {
            "contract": self.contract.to_dict(),
            "receipt": _receipt_payload(self.receipt),
        }


@dataclass(frozen=True, slots=True)
class HumanApprovalLifecycleItem:
    """Project one approval together with its effective lifecycle state."""

    approval: HumanApprovalEvidenceRecord
    status: ApprovalLifecycleStatus
    superseded_by_receipt_id: str | None = None
    revocation: HumanApprovalRevocationEvidenceRecord | None = None

    def to_dict(self) -> dict[str, object]:
        """Return approval evidence plus lifecycle status without mutating history."""
        payload = self.approval.to_dict()
        payload["lifecycle"] = {
            "status": self.status,
            "superseded_by_receipt_id": self.superseded_by_receipt_id,
            "revocation": None
            if self.revocation is None
            else self.revocation.to_dict(),
        }
        return payload


def _receipt_payload(receipt: ExternalEvidenceReceipt) -> dict[str, object]:
    """Return the bounded receipt projection shared by lifecycle API records."""
    return {
        "receipt_id": receipt.receipt_id,
        "receipt_digest": receipt.digest,
        "artifact_digest": receipt.artifact_digest,
        "captured_at": receipt.captured_at.astimezone(UTC).isoformat(),
        "producer_id": receipt.producer_id,
        "run_id": receipt.run_id,
    }


def approval_request_fingerprint(
    *,
    target_record_id: str,
    candidate_digest: str,
    report_digest: str,
    actor_identity_ref: str,
    actor_role: str,
    producer_id: str,
    run_id: str,
    approval_action: str,
    scope: str,
    reason: str,
    supersedes_approval_receipt_id: str | None = None,
) -> str:
    """Return a deterministic fingerprint for one approval request intent."""
    payload = {
        "operation": "approve",
        "target_record_id": target_record_id,
        "candidate_digest": candidate_digest,
        "report_digest": report_digest,
        "actor_identity_ref": actor_identity_ref,
        "actor_role": actor_role,
        "producer_id": producer_id,
        "run_id": run_id,
        "approval_action": approval_action,
        "scope": scope,
        "reason": reason,
        "supersedes_approval_receipt_id": supersedes_approval_receipt_id,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def revocation_request_fingerprint(
    *,
    target_record_id: str,
    candidate_digest: str,
    report_digest: str,
    target_approval_receipt_id: str,
    actor_identity_ref: str,
    actor_role: str,
    producer_id: str,
    run_id: str,
    approval_action: str,
    scope: str,
    reason: str,
) -> str:
    """Return a deterministic fingerprint for one approval-revocation intent."""
    payload = {
        "operation": "revoke",
        "target_record_id": target_record_id,
        "candidate_digest": candidate_digest,
        "report_digest": report_digest,
        "target_approval_receipt_id": target_approval_receipt_id,
        "actor_identity_ref": actor_identity_ref,
        "actor_role": actor_role,
        "producer_id": producer_id,
        "run_id": run_id,
        "approval_action": approval_action,
        "scope": scope,
        "reason": reason,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class WorkspaceHumanApprovalStore:
    """Persist immutable approvals and project their revocation/supersession lifecycle."""

    def __init__(
        self,
        workspace_root: Path,
        *,
        max_receipts: int = _DEFAULT_MAX_RECEIPTS,
        lock_timeout_seconds: float = 5.0,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        """Initialize the bounded workspace-backed approval adapter."""
        self.workspace_root = workspace_root.expanduser().resolve()
        self.max_receipts = max_receipts
        self.lock_timeout_seconds = lock_timeout_seconds
        self._now = now or (lambda: datetime.now(UTC))
        self._artifact_store = ContentAddressedArtifactStore(
            self.workspace_root / "artifacts"
        )
        self._receipt_store = JsonEvidenceReceiptStore(self.workspace_root / "receipts")
        self._ingestion = LocalEvidenceIngestionAdapter(
            self._artifact_store,
            self._receipt_store,
        )
        self._lock_path = self.workspace_root / ".human-approval.lock"
        if self.max_receipts <= 0:
            raise ValueError("max_receipts must be positive")

    def for_target(
        self,
        target_record_id: str,
        *,
        report_digest: str,
    ) -> list[HumanApprovalEvidenceRecord]:
        """Return all verified historical approvals for one exact report basis."""
        with self._lock():
            approvals, _revocations = self._records_unlocked()
            return self._approvals_for_target(
                approvals,
                target_record_id=target_record_id,
                report_digest=report_digest,
            )

    def lifecycle_for_target(
        self,
        target_record_id: str,
        *,
        report_digest: str,
    ) -> list[HumanApprovalLifecycleItem]:
        """Return fail-closed lifecycle state for approvals on one exact basis."""
        with self._lock():
            approvals, revocations = self._records_unlocked()
            return self._lifecycle_unlocked(
                target_record_id=target_record_id,
                report_digest=report_digest,
                approvals=approvals,
                revocations=revocations,
            )

    def active_for_target(
        self,
        target_record_id: str,
        *,
        report_digest: str,
    ) -> list[HumanApprovalEvidenceRecord]:
        """Return only currently effective approvals for one immutable report basis."""
        return [
            item.approval
            for item in self.lifecycle_for_target(
                target_record_id, report_digest=report_digest
            )
            if item.status == "active"
        ]

    def append(
        self,
        *,
        target_record_id: str,
        candidate_identity: str,
        candidate_digest: str,
        report_digest: str,
        profile_id: str,
        profile_version: str,
        actor_identity_ref: str,
        actor_role: str,
        producer_id: str,
        run_id: str,
        approval_action: str,
        scope: str,
        reason: str,
        idempotency_key: str,
        supersedes_approval_receipt_id: str | None = None,
    ) -> tuple[HumanApprovalEvidenceRecord, bool]:
        """Append approval evidence, optionally superseding one active predecessor."""
        fingerprint = approval_request_fingerprint(
            target_record_id=target_record_id,
            candidate_digest=candidate_digest,
            report_digest=report_digest,
            actor_identity_ref=actor_identity_ref,
            actor_role=actor_role,
            producer_id=producer_id,
            run_id=run_id,
            approval_action=approval_action,
            scope=scope,
            reason=reason,
            supersedes_approval_receipt_id=supersedes_approval_receipt_id,
        )
        with self._lock():
            approvals, revocations = self._records_unlocked()
            retry = self._find_idempotent_retry(
                idempotency_key=idempotency_key,
                fingerprint=fingerprint,
                approvals=approvals,
                revocations=revocations,
                expected="approval",
            )
            if isinstance(retry, HumanApprovalEvidenceRecord):
                return retry, False

            lifecycle = self._lifecycle_unlocked(
                target_record_id=target_record_id,
                report_digest=report_digest,
                approvals=approvals,
                revocations=revocations,
            )
            predecessor: HumanApprovalLifecycleItem | None = None
            if supersedes_approval_receipt_id is not None:
                predecessor = next(
                    (
                        item
                        for item in lifecycle
                        if item.approval.receipt.receipt_id
                        == supersedes_approval_receipt_id
                    ),
                    None,
                )
                if predecessor is None:
                    raise ApprovalLifecycleTargetError(
                        "superseded approval is not part of this exact report basis"
                    )
                if predecessor.status != "active":
                    raise ApprovalLifecycleConflictError(
                        "only an active approval may be superseded"
                    )
                self._require_authority_match(
                    predecessor.approval,
                    producer_id=producer_id,
                    approval_action=approval_action,
                    scope=scope,
                )
                self._require_candidate_match(
                    predecessor.approval,
                    candidate_identity=candidate_identity,
                    candidate_digest=candidate_digest,
                    profile_id=profile_id,
                    profile_version=profile_version,
                )

            for item in lifecycle:
                if item.status != "active":
                    continue
                existing = item.approval
                if (
                    predecessor is not None
                    and existing.receipt.receipt_id
                    == predecessor.approval.receipt.receipt_id
                ):
                    continue
                contract = existing.contract
                if (
                    contract.actor_identity_ref == actor_identity_ref
                    and contract.approval_action == approval_action
                    and contract.scope == scope
                ):
                    raise ApprovalAlreadyRecordedError(
                        "an active approval is already recorded for this actor, action, scope, and basis"
                    )

            captured_at = self._captured_at()
            metadata: dict[str, object] = {
                "candidate_identity": candidate_identity,
                "candidate_digest": candidate_digest,
                "profile_id": profile_id,
                "profile_version": profile_version,
                "reason": reason,
                "target_record_id": target_record_id,
            }
            receipt_metadata: dict[str, str] = {
                "contract_type": "human_approval",
                "target_record_id": target_record_id,
                "candidate_digest": candidate_digest,
                "report_digest": report_digest,
                "request_fingerprint": fingerprint,
                "idempotency_key": idempotency_key,
            }
            if predecessor is not None:
                predecessor_receipt = predecessor.approval.receipt
                metadata["supersedes_approval_receipt_id"] = (
                    predecessor_receipt.receipt_id
                )
                metadata["supersedes_approval_receipt_digest"] = (
                    predecessor_receipt.digest
                )
                receipt_metadata["supersedes_approval_receipt_id"] = (
                    predecessor_receipt.receipt_id
                )
                receipt_metadata["supersedes_approval_receipt_digest"] = (
                    predecessor_receipt.digest
                )

            contract = HumanApprovalContract(
                contract_version="1",
                producer_id=producer_id,
                run_id=run_id,
                actor_identity_ref=actor_identity_ref,
                role=actor_role,
                approval_action=approval_action,
                approval_basis_digest=report_digest,
                scope=scope,
                captured_at=captured_at,
                metadata=metadata,
            )
            content = canonical_json_bytes(contract.to_dict())
            receipt = self._ingestion.ingest_bytes(
                content,
                producer_type=_APPROVAL_PRODUCER_TYPE,
                producer_id=producer_id,
                producer_version=None,
                source_ref=f"human-approval:{target_record_id}",
                source_event_id=idempotency_key,
                run_id=run_id,
                captured_at=captured_at,
                metadata=receipt_metadata,
            )
            return HumanApprovalEvidenceRecord(contract=contract, receipt=receipt), True

    def revoke(
        self,
        *,
        target_record_id: str,
        target_approval_receipt_id: str,
        candidate_identity: str,
        candidate_digest: str,
        report_digest: str,
        profile_id: str,
        profile_version: str,
        actor_identity_ref: str,
        actor_role: str,
        producer_id: str,
        run_id: str,
        approval_action: str,
        scope: str,
        reason: str,
        idempotency_key: str,
    ) -> tuple[HumanApprovalRevocationEvidenceRecord, bool]:
        """Append immutable revocation evidence for one active approval."""
        fingerprint = revocation_request_fingerprint(
            target_record_id=target_record_id,
            candidate_digest=candidate_digest,
            report_digest=report_digest,
            target_approval_receipt_id=target_approval_receipt_id,
            actor_identity_ref=actor_identity_ref,
            actor_role=actor_role,
            producer_id=producer_id,
            run_id=run_id,
            approval_action=approval_action,
            scope=scope,
            reason=reason,
        )
        with self._lock():
            approvals, revocations = self._records_unlocked()
            retry = self._find_idempotent_retry(
                idempotency_key=idempotency_key,
                fingerprint=fingerprint,
                approvals=approvals,
                revocations=revocations,
                expected="revocation",
            )
            if isinstance(retry, HumanApprovalRevocationEvidenceRecord):
                return retry, False

            lifecycle = self._lifecycle_unlocked(
                target_record_id=target_record_id,
                report_digest=report_digest,
                approvals=approvals,
                revocations=revocations,
            )
            target = next(
                (
                    item
                    for item in lifecycle
                    if item.approval.receipt.receipt_id == target_approval_receipt_id
                ),
                None,
            )
            if target is None:
                raise ApprovalLifecycleTargetError(
                    "revoked approval is not part of this exact report basis"
                )
            if target.status != "active":
                raise ApprovalLifecycleConflictError(
                    "only an active approval may be revoked"
                )
            self._require_authority_match(
                target.approval,
                producer_id=producer_id,
                approval_action=approval_action,
                scope=scope,
            )
            self._require_candidate_match(
                target.approval,
                candidate_identity=candidate_identity,
                candidate_digest=candidate_digest,
                profile_id=profile_id,
                profile_version=profile_version,
            )

            captured_at = self._captured_at()
            contract = HumanApprovalRevocationContract(
                contract_version="1",
                producer_id=producer_id,
                run_id=run_id,
                actor_identity_ref=actor_identity_ref,
                role=actor_role,
                approval_action=approval_action,
                approval_basis_digest=report_digest,
                scope=scope,
                target_approval_receipt_id=target.approval.receipt.receipt_id,
                target_approval_receipt_digest=target.approval.receipt.digest,
                reason=reason,
                captured_at=captured_at,
                metadata={
                    "candidate_identity": candidate_identity,
                    "candidate_digest": candidate_digest,
                    "profile_id": profile_id,
                    "profile_version": profile_version,
                    "target_record_id": target_record_id,
                },
            )
            content = canonical_json_bytes(contract.to_dict())
            receipt = self._ingestion.ingest_bytes(
                content,
                producer_type=_REVOCATION_PRODUCER_TYPE,
                producer_id=producer_id,
                producer_version=None,
                source_ref=f"human-approval-revocation:{target_record_id}",
                source_event_id=idempotency_key,
                run_id=run_id,
                captured_at=captured_at,
                metadata={
                    "contract_type": "human_approval_revocation",
                    "lifecycle_action": "revoke",
                    "target_record_id": target_record_id,
                    "candidate_digest": candidate_digest,
                    "report_digest": report_digest,
                    "target_approval_receipt_id": target.approval.receipt.receipt_id,
                    "target_approval_receipt_digest": target.approval.receipt.digest,
                    "request_fingerprint": fingerprint,
                    "idempotency_key": idempotency_key,
                },
            )
            return (
                HumanApprovalRevocationEvidenceRecord(
                    contract=contract, receipt=receipt
                ),
                True,
            )

    def _find_idempotent_retry(
        self,
        *,
        idempotency_key: str,
        fingerprint: str,
        approvals: list[HumanApprovalEvidenceRecord],
        revocations: list[HumanApprovalRevocationEvidenceRecord],
        expected: Literal["approval", "revocation"],
    ) -> HumanApprovalEvidenceRecord | HumanApprovalRevocationEvidenceRecord | None:
        """Resolve exact retry or reject cross-intent/cross-operation key reuse."""
        records: list[
            HumanApprovalEvidenceRecord | HumanApprovalRevocationEvidenceRecord
        ] = [*approvals, *revocations]
        for record in records:
            metadata = record.receipt.metadata
            if metadata.get("idempotency_key") != idempotency_key:
                continue
            if metadata.get("request_fingerprint") != fingerprint:
                raise ApprovalIdempotencyConflictError(
                    "idempotency key was already used for a different approval lifecycle request"
                )
            if expected == "approval" and isinstance(
                record, HumanApprovalEvidenceRecord
            ):
                return record
            if expected == "revocation" and isinstance(
                record, HumanApprovalRevocationEvidenceRecord
            ):
                return record
            raise ApprovalIdempotencyConflictError(
                "idempotency key was already used for a different approval lifecycle operation"
            )
        return None

    @staticmethod
    def _approvals_for_target(
        approvals: list[HumanApprovalEvidenceRecord],
        *,
        target_record_id: str,
        report_digest: str,
    ) -> list[HumanApprovalEvidenceRecord]:
        """Filter approval history to one exact report basis."""
        return [
            record
            for record in approvals
            if record.receipt.metadata.get("target_record_id") == target_record_id
            and record.receipt.metadata.get("report_digest") == report_digest
        ]

    def _lifecycle_unlocked(
        self,
        *,
        target_record_id: str,
        report_digest: str,
        approvals: list[HumanApprovalEvidenceRecord],
        revocations: list[HumanApprovalRevocationEvidenceRecord],
    ) -> list[HumanApprovalLifecycleItem]:
        """Project one immutable approval history into effective lifecycle states."""
        selected = self._approvals_for_target(
            approvals,
            target_record_id=target_record_id,
            report_digest=report_digest,
        )
        by_id = {record.receipt.receipt_id: record for record in selected}
        statuses: dict[str, ApprovalLifecycleStatus] = dict.fromkeys(by_id, "active")
        successors: dict[str, str] = {}
        applied_revocations: dict[str, HumanApprovalRevocationEvidenceRecord] = {}

        for successor in selected:
            metadata = successor.contract.metadata or {}
            predecessor_id_raw = metadata.get("supersedes_approval_receipt_id")
            predecessor_digest_raw = metadata.get("supersedes_approval_receipt_digest")
            if predecessor_id_raw is None and predecessor_digest_raw is None:
                continue
            if not isinstance(predecessor_id_raw, str) or not isinstance(
                predecessor_digest_raw, str
            ):
                raise ValueError("approval supersession metadata is incomplete")
            predecessor = by_id.get(predecessor_id_raw)
            if predecessor is None:
                raise ValueError(
                    "superseding approval references an unknown predecessor"
                )
            if predecessor.receipt.receipt_id == successor.receipt.receipt_id:
                raise ValueError("approval cannot supersede itself")
            if predecessor.receipt.digest != predecessor_digest_raw:
                raise ValueError(
                    "approval supersession predecessor digest does not match"
                )
            if (
                successor.receipt.metadata.get("supersedes_approval_receipt_id")
                != predecessor_id_raw
            ):
                raise ValueError(
                    "approval supersession does not match receipt metadata"
                )
            if (
                successor.receipt.metadata.get("supersedes_approval_receipt_digest")
                != predecessor_digest_raw
            ):
                raise ValueError(
                    "approval supersession digest does not match receipt metadata"
                )
            self._require_authority_match(
                predecessor,
                producer_id=successor.contract.producer_id,
                approval_action=successor.contract.approval_action,
                scope=successor.contract.scope,
            )
            if successor.contract.captured_at < predecessor.contract.captured_at:
                raise ValueError("approval supersession precedes its predecessor")
            if predecessor_id_raw in successors:
                raise ValueError("approval has more than one superseding successor")
            successors[predecessor_id_raw] = successor.receipt.receipt_id
            statuses[predecessor_id_raw] = "superseded"

        for revocation in revocations:
            receipt_metadata = revocation.receipt.metadata
            if (
                receipt_metadata.get("target_record_id") != target_record_id
                or receipt_metadata.get("report_digest") != report_digest
            ):
                continue
            target_id = revocation.contract.target_approval_receipt_id
            target = by_id.get(target_id)
            if target is None:
                raise ValueError("approval revocation references an unknown approval")
            if (
                target.receipt.digest
                != revocation.contract.target_approval_receipt_digest
            ):
                raise ValueError("approval revocation target digest does not match")
            self._require_authority_match(
                target,
                producer_id=revocation.contract.producer_id,
                approval_action=revocation.contract.approval_action,
                scope=revocation.contract.scope,
            )
            if revocation.contract.captured_at < target.contract.captured_at:
                raise ValueError("approval revocation precedes its target approval")
            if statuses[target_id] != "active":
                raise ValueError(
                    "approval lifecycle contains conflicting revocation/supersession transitions"
                )
            statuses[target_id] = "revoked"
            applied_revocations[target_id] = revocation

        return [
            HumanApprovalLifecycleItem(
                approval=record,
                status=statuses[record.receipt.receipt_id],
                superseded_by_receipt_id=successors.get(record.receipt.receipt_id),
                revocation=applied_revocations.get(record.receipt.receipt_id),
            )
            for record in sorted(
                selected,
                key=lambda value: (
                    value.contract.captured_at,
                    value.receipt.receipt_id,
                ),
            )
        ]

    @staticmethod
    def _require_authority_match(
        record: HumanApprovalEvidenceRecord,
        *,
        producer_id: str,
        approval_action: str,
        scope: str,
    ) -> None:
        """Require lifecycle transitions to remain inside the approved authority."""
        contract = record.contract
        if (
            contract.producer_id != producer_id
            or contract.approval_action != approval_action
            or contract.scope != scope
        ):
            raise ApprovalLifecycleTargetError(
                "approval lifecycle transition does not match predecessor authority"
            )

    @staticmethod
    def _require_candidate_match(
        record: HumanApprovalEvidenceRecord,
        *,
        candidate_identity: str,
        candidate_digest: str,
        profile_id: str,
        profile_version: str,
    ) -> None:
        """Require lifecycle transitions to preserve exact candidate/profile binding."""
        metadata = record.contract.metadata or {}
        if (
            metadata.get("candidate_identity") != candidate_identity
            or metadata.get("candidate_digest") != candidate_digest
            or metadata.get("profile_id") != profile_id
            or metadata.get("profile_version") != profile_version
        ):
            raise ApprovalLifecycleTargetError(
                "approval lifecycle transition does not match predecessor candidate/profile basis"
            )

    def _captured_at(self) -> datetime:
        """Return a normalized UTC lifecycle timestamp from the configured clock."""
        captured_at = self._now()
        if captured_at.tzinfo is None:
            raise ValueError("approval clock must return a timezone-aware datetime")
        return captured_at.astimezone(UTC)

    def _records_unlocked(
        self,
    ) -> tuple[
        list[HumanApprovalEvidenceRecord],
        list[HumanApprovalRevocationEvidenceRecord],
    ]:
        """Read and verify every persisted approval lifecycle receipt under the lock."""
        receipt_root = self.workspace_root / "receipts"
        if not receipt_root.exists():
            return [], []
        paths = sorted(receipt_root.glob("*.json"))
        if len(paths) > self.max_receipts:
            raise OverflowError("approval receipt scan exceeds configured maximum")
        approvals: list[HumanApprovalEvidenceRecord] = []
        revocations: list[HumanApprovalRevocationEvidenceRecord] = []
        for path in paths:
            payload = loads_object(path.read_bytes(), field="evidence receipt")
            receipt = ExternalEvidenceReceipt.from_dict(payload)
            if receipt.producer_type not in {
                _APPROVAL_PRODUCER_TYPE,
                _REVOCATION_PRODUCER_TYPE,
            }:
                continue
            content = self._artifact_store.get(receipt.artifact_digest)
            if len(content) != receipt.artifact_size:
                raise ValueError(
                    "approval lifecycle artifact size does not match its receipt"
                )
            if receipt.producer_type == _APPROVAL_PRODUCER_TYPE:
                contract = HumanApprovalContract.from_dict(
                    loads_object(content, field="human approval contract")
                )
                self._verify_common_contract_receipt(contract, receipt)
                if contract.approval_basis_digest != receipt.metadata.get(
                    "report_digest"
                ):
                    raise ValueError(
                        "approval basis does not match its receipt metadata"
                    )
                approvals.append(
                    HumanApprovalEvidenceRecord(contract=contract, receipt=receipt)
                )
                continue

            revocation = HumanApprovalRevocationContract.from_dict(
                loads_object(content, field="human approval revocation contract")
            )
            self._verify_common_contract_receipt(revocation, receipt)
            if revocation.approval_basis_digest != receipt.metadata.get(
                "report_digest"
            ):
                raise ValueError(
                    "approval revocation basis does not match its receipt metadata"
                )
            if revocation.target_approval_receipt_id != receipt.metadata.get(
                "target_approval_receipt_id"
            ) or revocation.target_approval_receipt_digest != receipt.metadata.get(
                "target_approval_receipt_digest"
            ):
                raise ValueError(
                    "approval revocation target does not match its receipt metadata"
                )
            revocations.append(
                HumanApprovalRevocationEvidenceRecord(
                    contract=revocation,
                    receipt=receipt,
                )
            )
        return approvals, revocations

    @staticmethod
    def _verify_common_contract_receipt(
        contract: HumanApprovalContract | HumanApprovalRevocationContract,
        receipt: ExternalEvidenceReceipt,
    ) -> None:
        """Verify contract identity and timestamp against its durable receipt."""
        if contract.producer_id != receipt.producer_id:
            raise ValueError("approval lifecycle producer does not match its receipt")
        if contract.run_id != receipt.run_id:
            raise ValueError("approval lifecycle run does not match its receipt")
        if contract.captured_at != receipt.captured_at:
            raise ValueError("approval lifecycle timestamp does not match its receipt")

    class _Lock:
        """Wrap the process-shared approval persistence lock."""

        def __init__(self, owner: WorkspaceHumanApprovalStore) -> None:
            """Bind the file lock to its owning approval store."""
            self.owner = owner
            self._lock = FileLock(str(owner._lock_path))

        def __enter__(self) -> WorkspaceHumanApprovalStore._Lock:
            """Acquire the approval lock or fail closed on timeout."""
            try:
                self._lock.acquire(timeout=self.owner.lock_timeout_seconds)
            except Timeout as exc:
                raise TimeoutError(
                    f"timed out acquiring human-approval lock: {self.owner._lock_path}"
                ) from exc
            return self

        def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc: BaseException | None,
            traceback: object | None,
        ) -> None:
            """Release the process-shared approval lock."""
            del exc_type, exc, traceback
            self._lock.release()

    def _lock(self) -> WorkspaceHumanApprovalStore._Lock:
        """Return the process-shared approval lock context."""
        return self._Lock(self)


__all__ = [
    "ApprovalAlreadyRecordedError",
    "ApprovalIdempotencyConflictError",
    "ApprovalLifecycleConflictError",
    "ApprovalLifecycleStatus",
    "ApprovalLifecycleTargetError",
    "HumanApprovalEvidenceRecord",
    "HumanApprovalLifecycleItem",
    "HumanApprovalRevocationEvidenceRecord",
    "WorkspaceHumanApprovalStore",
    "approval_request_fingerprint",
    "revocation_request_fingerprint",
]
