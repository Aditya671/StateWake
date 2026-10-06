"""Read-only projections for release trust, validation studies, and workspace operations.

This module is intentionally presentation-only. It never mutates workspace state,
re-runs a comparative study, authenticates a signer without an externally supplied
trust root, or converts a human release-decision claim into publication authority.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256

from statewake.release_trust.bundle import evaluate_release_trust_bundle
from statewake.release_trust.content_verification import ReleaseContentVerification
from statewake.release_trust.model import ReleaseTrustBundle
from statewake.release_trust.publication import PublicationAuthorizationState
from statewake.release_trust.registry import (
    RegistryPublicationLifecycleObservation,
    RegistryPublicationReceipt,
)
from statewake.validation_study.model import ComparativeValidationStudy
from statewake.workspace.models import WorkspaceExport, WorkspaceRecordQuery
from statewake.workspace.workspace import StateWakeWorkspace

_RELEASE_SCHEMA = "release-trust-view.v1"
_STUDY_SCHEMA = "validation-study-view.v1"
_WORKSPACE_SCHEMA = "workspace-operations.v1"


def _digest(payload: dict[str, object]) -> str:
    """Return the canonical digest for a JSON-compatible projection payload."""
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class ReleaseTrustProjection:
    """Keep structural, byte-level, signer, and human-decision signals separate."""

    payload: dict[str, object]

    @property
    def digest(self) -> str:
        """Return a deterministic digest for this display projection."""
        return _digest(self.payload)

    def to_dict(self) -> dict[str, object]:
        """Serialize the projection without altering StateWake trust semantics."""
        return dict(self.payload)


@dataclass(frozen=True, slots=True)
class ValidationStudyProjection:
    """Accessible table-first view of one already-recorded comparative study."""

    payload: dict[str, object]

    @property
    def digest(self) -> str:
        """Return a deterministic digest for this display projection."""
        return _digest(self.payload)

    def to_dict(self) -> dict[str, object]:
        """Serialize the projection."""
        return dict(self.payload)


@dataclass(frozen=True, slots=True)
class WorkspaceOperationsProjection:
    """Read-only operational view over one existing durable workspace."""

    payload: dict[str, object]

    @property
    def digest(self) -> str:
        """Return a deterministic digest for this display projection."""
        return _digest(self.payload)

    def to_dict(self) -> dict[str, object]:
        """Serialize the projection."""
        return dict(self.payload)


def build_release_trust_projection(
    bundle: ReleaseTrustBundle,
    *,
    content: ReleaseContentVerification | None,
    publication: PublicationAuthorizationState | None = None,
    registry_publication: RegistryPublicationReceipt | None = None,
    registry_lifecycle: tuple[RegistryPublicationLifecycleObservation, ...] = (),
) -> ReleaseTrustProjection:
    """Project one canonical release-trust bundle without inventing authenticity."""
    profile = evaluate_release_trust_bundle(bundle)
    content_payload: dict[str, object]
    if content is None:
        content_payload = {
            "status": "not_configured",
            "complete": None,
            "matched": [],
            "missing": [],
            "mismatched": [],
            "limitations": [
                "Local release bytes were not configured for independent digest verification."
            ],
        }
    else:
        content_payload = {
            "status": "verified" if content.content_complete else "failed",
            "complete": content.content_complete,
            "matched": list(content.matched),
            "missing": list(content.missing),
            "mismatched": list(content.mismatched),
            "limitations": list(content.limitations),
        }

    signature = bundle.signature
    payload: dict[str, object] = {
        "schema_version": _RELEASE_SCHEMA,
        "bundle_digest": bundle.digest,
        "source": bundle.source.to_dict(),
        "artifacts": [item.to_dict() for item in bundle.artifacts],
        "build": bundle.build.to_dict(),
        "tests": [item.to_dict() for item in bundle.tests],
        "external_evidence": {
            "sbom": bundle.sbom.to_dict() if bundle.sbom else None,
            "vulnerability_scan": (
                bundle.vulnerability_scan.to_dict()
                if bundle.vulnerability_scan
                else None
            ),
            "signature": signature.to_dict() if signature else None,
            "provenance": bundle.provenance.to_dict() if bundle.provenance else None,
        },
        "structural_profile": {
            "profile_id": profile.profile_id,
            "profile_version": profile.profile_version,
            "satisfied": profile.satisfied,
            "failed_requirements": list(profile.failed_requirements),
            "missing_evidence": list(profile.missing_evidence),
            "caveats": list(profile.caveats),
        },
        "content_verification": content_payload,
        "signature_authenticity": {
            "status": "not_verified",
            "authenticated": None,
            "reason": (
                "This read-only UI has no independently configured trusted signer; "
                "signature evidence presence is not signer authentication."
            ),
        },
        "human_decision": bundle.human_decision.to_dict(),
        "publication_authorized": (
            publication.publication_authorized if publication is not None else False
        ),
        "release_published": registry_publication is not None,
        "publication_authorization": (
            {
                "configured": False,
                "target_repository": None,
                "basis_digest": None,
                "expected_producer_id": None,
                "publication_authorized": False,
                "active_approval_receipt_ids": [],
                "items": [],
            }
            if publication is None
            else {
                "configured": True,
                "basis_digest": publication.basis_digest,
                "target_repository": publication.target_repository,
                "expected_producer_id": publication.expected_producer_id,
                "publication_authorized": publication.publication_authorized,
                "active_approval_receipt_ids": [
                    item.receipt.receipt_id for item in publication.active
                ],
                "items": [
                    {
                        "status": item.status,
                        "approval_receipt_id": item.approval.receipt.receipt_id,
                        "actor_identity_ref": item.approval.contract.actor_identity_ref,
                        "role": item.approval.contract.role,
                        "captured_at": item.approval.contract.captured_at.astimezone().isoformat(),
                        "superseded_by_receipt_id": item.superseded_by_receipt_id,
                        "revocation_receipt_id": (
                            None
                            if item.revocation is None
                            else item.revocation.receipt.receipt_id
                        ),
                    }
                    for item in publication.lifecycle
                ],
            }
        ),
        "registry_publication": (
            {
                "configured": False,
                "release_published": False,
                "registry_reconciled": False,
                "receipt_digest": None,
                "target_repository": None,
                "basis_digest": None,
                "permit_digest": None,
                "observed_at": None,
                "public_bytes_verified": False,
                "artifacts": [],
                "lifecycle": {
                    "configured": False,
                    "current_status": None,
                    "current_observed_at": None,
                    "observation_count": 0,
                    "registry_entry_present": None,
                    "default_install_eligible": None,
                    "public_bytes_verified": None,
                    "missing_artifacts": [],
                    "observations": [],
                },
            }
            if registry_publication is None
            else {
                "configured": True,
                "release_published": True,
                "registry_reconciled": True,
                "receipt_digest": registry_publication.digest,
                "target_repository": registry_publication.target_repository,
                "basis_digest": registry_publication.basis_digest,
                "permit_digest": registry_publication.permit_digest,
                "observed_at": registry_publication.observed_at.astimezone().isoformat(),
                "public_bytes_verified": True,
                "artifacts": [
                    item.to_dict() for item in registry_publication.artifacts
                ],
                "lifecycle": (
                    {
                        "configured": False,
                        "current_status": None,
                        "current_observed_at": None,
                        "observation_count": 0,
                        "registry_entry_present": None,
                        "default_install_eligible": None,
                        "public_bytes_verified": None,
                        "missing_artifacts": [],
                        "observations": [],
                    }
                    if not registry_lifecycle
                    else {
                        "configured": True,
                        "current_status": registry_lifecycle[-1].status,
                        "current_observed_at": registry_lifecycle[-1]
                        .observed_at.astimezone()
                        .isoformat(),
                        "observation_count": len(registry_lifecycle),
                        "registry_entry_present": registry_lifecycle[-1].status
                        != "unavailable",
                        "default_install_eligible": registry_lifecycle[-1].status
                        == "available",
                        "public_bytes_verified": registry_lifecycle[
                            -1
                        ].public_bytes_verified,
                        "missing_artifacts": list(
                            registry_lifecycle[-1].missing_artifacts
                        ),
                        "observations": [
                            {**item.to_dict(), "observation_digest": item.digest}
                            for item in registry_lifecycle
                        ],
                    }
                ),
            }
        ),
        "limitations": [
            *bundle.limitations,
            "Structural profile satisfaction is not publication authorization.",
            "Build provenance describes where/how artifacts were produced; it is not factual truth of the artifact.",
            "A signature evidence file is not authenticated unless a trusted signer is independently configured and verified.",
            "The read-only UI never publishes a release or issues a publication execution permit.",
            "Publication authorization is effective only for the exact canonical basis and can be revoked or superseded before external execution.",
            "Registry publication is reported only when a canonical post-publication receipt reconciles the exact public registry bytes to the execution permit.",
            "A registry receipt is immutable historical publication evidence; later lifecycle observations never rewrite it.",
            "Registry lifecycle monitoring distinguishes available, yanked, partially available, and observed-unavailable states without inferring who caused a yank, file deletion, or release disappearance.",
        ],
    }
    return ReleaseTrustProjection(payload)


def build_validation_study_projection(
    study: ComparativeValidationStudy,
) -> ValidationStudyProjection:
    """Project one frozen fixture study with denominators and limits kept visible."""
    metrics = []
    for metric in study.metrics:
        metrics.append(
            {
                **metric.to_dict(),
                "verification_coverage_denominator": metric.target_property_count,
                "fault_detection_denominator": metric.injected_fault_count,
                "false_positive_denominator": metric.valid_case_count,
            }
        )
    payload: dict[str, object] = {
        "schema_version": _STUDY_SCHEMA,
        "study_id": study.study_id,
        "study_digest": study.digest,
        "study_kind": "deterministic-fixture-study",
        "baselines": [item.to_dict() for item in study.baselines],
        "workloads": [item.to_dict() for item in study.workloads],
        "faults": [item.to_dict() for item in study.faults],
        "metrics": metrics,
        "case_count": len(study.cases),
        "cases": [item.to_dict() for item in study.cases],
        "limitations": [
            *study.limitations,
            "These measurements apply only to the recorded deterministic fixtures, workloads, and injected faults.",
            "This page does not run live benchmarks or generalize the results to untested systems.",
        ],
    }
    return ValidationStudyProjection(payload)


def _export_view(item: WorkspaceExport) -> dict[str, object]:
    """Return export metadata without leaking the server filesystem path or raw query."""
    return {
        "export_id": item.export_id,
        "format": item.format,
        "created_at": item.created_at,
        "disclosure_max_sensitivity": item.disclosure_max_sensitivity,
        "source_schema_version": item.source_schema_version,
        "output_digest": item.output_digest,
        "row_count": item.row_count,
    }


def build_workspace_operations_projection(
    workspace: StateWakeWorkspace,
    *,
    limit: int = 50,
    offset: int = 0,
) -> WorkspaceOperationsProjection:
    """Build a bounded workspace inspection view through the read-only handle."""
    if not workspace.read_only:
        raise ValueError("workspace operations projection requires read-only access")
    diagnostics = workspace.diagnostics()
    page = workspace.query(WorkspaceRecordQuery(limit=limit, offset=offset))
    exports = workspace.export_history(limit=100)
    snapshot = workspace.repository.integrity_snapshot()

    records: list[dict[str, object]] = []
    legal_hold_count = 0
    retention_count = 0
    for record in page.records:
        retention = workspace.repository.get_retention(record.record_id)
        if retention is not None:
            retention_count += 1
            legal_hold_count += int(retention.legal_hold)
        records.append(
            {
                "record_id": record.record_id,
                "receipt_id": record.receipt_id,
                "artifact_digest": record.artifact_digest,
                "artifact_size": record.artifact_size,
                "producer_id": record.producer_id,
                "producer_type": record.producer_type,
                "producer_version": record.producer_version,
                "source_event_id": record.source_event_id,
                "run_id": record.run_id,
                "captured_at": record.captured_at.isoformat(),
                "sensitivity": record.sensitivity,
                "verification_status": record.verification_status,
                "reliability_state": record.reliability_state,
                "retention": None
                if retention is None
                else {
                    "policy_id": retention.policy_id,
                    "sensitivity": retention.sensitivity,
                    "retain_until": retention.retain_until,
                    "legal_hold": retention.legal_hold,
                },
            }
        )

    verification = diagnostics.verification
    payload: dict[str, object] = {
        "schema_version": _WORKSPACE_SCHEMA,
        "workspace": {
            "workspace_id": workspace.identity.workspace_id,
            "schema_version": workspace.identity.schema_version,
            "public_api_contract_version": (
                workspace.identity.statewake_public_api_contract_version
            ),
            "mode": "read-only",
            "backend": "sqlite",
        },
        "health": {
            "status": verification.status,
            "healthy": verification.healthy,
            "has_errors": verification.has_errors,
            "checked_records": verification.checked_records,
            "checked_receipts": verification.checked_receipts,
            "checked_artifacts": verification.checked_artifacts,
            "checked_exports": verification.checked_exports,
            "issues": [
                {
                    "code": issue.code,
                    "severity": issue.severity,
                    "message": issue.message,
                    "object_id": issue.object_id,
                }
                for issue in verification.issues
            ],
            "orphan_counts": {
                "artifacts": len(verification.orphan_artifacts),
                "receipts": len(verification.orphan_receipts),
                "exports": len(verification.orphan_exports),
            },
        },
        "storage": {
            "total_bytes": diagnostics.storage.total_bytes,
            "artifact_bytes": diagnostics.storage.artifact_bytes,
            "receipt_bytes": diagnostics.storage.receipt_bytes,
            "database_bytes": diagnostics.storage.database_bytes,
            "export_bytes": diagnostics.storage.export_bytes,
            "manifest_bytes": diagnostics.storage.manifest_bytes,
            "lock_bytes": diagnostics.storage.lock_bytes,
        },
        "migration": {
            "current_schema_version": workspace.identity.schema_version,
            "status": "current",
        },
        "records": {
            "items": records,
            "total_count": page.total_count,
            "limit": page.limit,
            "offset": page.offset,
            "has_more": page.has_more,
            "next_offset": page.next_offset,
        },
        "lifecycle": {
            "retention_rows_in_snapshot": len(snapshot.retention_object_ids),
            "retention_rows_in_page": retention_count,
            "legal_holds_in_page": legal_hold_count,
            "deletion_tombstones": len(snapshot.deletion_records),
        },
        "exports": {
            "count": len(exports),
            "items": [_export_view(item) for item in exports],
            "supported_formats": ["csv", "json", "xlsx", "parquet", "portable-bundle"],
        },
        "backup": {
            "history_status": "not_recorded",
            "restore_eligibility": "not_evaluated",
            "note": "Workspace backup history is not a durable repository authority in the current schema.",
        },
        "operational_audit": {
            "status": "not_recorded",
            "note": "No canonical workspace-operations audit stream is present in the current workspace schema.",
        },
        "limitations": [
            "Absolute server paths, raw SQL/query definitions, and workspace credentials are intentionally omitted.",
            "Opening this projection does not create locks, migrate, restore, delete, export, or repair the workspace.",
            "Backup history and operational audit are reported unavailable rather than inferred from files.",
        ],
    }
    return WorkspaceOperationsProjection(payload)


__all__ = [
    "ReleaseTrustProjection",
    "ValidationStudyProjection",
    "WorkspaceOperationsProjection",
    "build_release_trust_projection",
    "build_validation_study_projection",
    "build_workspace_operations_projection",
]
