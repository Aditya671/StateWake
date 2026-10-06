"""Optional dependency-free read API for the StateWake human-inspection UI.

This module deliberately does not extend :mod:`statewake.server`.  The existing
verification adapter keeps its bounded verification-only contract, while this
adapter exposes source-bound read projections for the current human-inspection
and operational trust surface.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs
from wsgiref.simple_server import make_server
from wsgiref.types import StartResponse, WSGIApplication, WSGIEnvironment

from statewake import __version__
from statewake.adapters.attestation_trust_history import (
    AttestationTrustHistorySnapshot,
    read_attestation_trust_history_snapshot,
)
from statewake.adapters.content_store import ContentAddressedArtifactStore
from statewake.adapters.evidence_ingestion import JsonEvidenceReceiptStore
from statewake.adapters.human_approval import WorkspaceHumanApprovalStore
from statewake.adapters.incident_evidence import (
    StoredIncidentRecord,
    read_incident_evidence_snapshot,
)
from statewake.adapters.reliability_attestation import (
    ReliabilityAttestationSnapshot,
    read_reliability_attestation_snapshot,
)
from statewake.adapters.reliability_state import parse_reliability_state_history
from statewake.adapters.security_audit import (
    SecurityAuditSnapshot,
    read_security_audit_snapshot,
)
from statewake.domain.attestation_trust import (
    Ed25519AttestationTrustStateVerifier,
    SignedAttestationTrustState,
)
from statewake.domain.evidence_receipt import ExternalEvidenceReceipt
from statewake.domain.reliability_evidence import (
    EvidenceReference,
    ReliabilityEvidenceChain,
)
from statewake.domain.reliability_verification_report import (
    ReliabilityVerificationReport,
)
from statewake.integrations.native_capture import (
    NativeCaptureCapacityError,
    read_native_capture_failure_journal_snapshot,
)
from statewake.presentation import (
    ATTESTATION_KEY_STATUSES,
    INCIDENT_STATUSES,
    MAX_ATTESTATION_TRUST_FILTER_CHARS,
    MAX_ATTESTATION_TRUST_PAGE_LIMIT,
    MAX_ATTESTATION_TRUST_TEXT_CHARS,
    MAX_CAPTURE_FAILURE_FILTER_CHARS,
    MAX_CAPTURE_FAILURE_PAGE_LIMIT,
    MAX_CLAIM_CATALOG_FILTER_CHARS,
    MAX_CLAIM_CATALOG_PAGE_LIMIT,
    MAX_CLAIM_CATALOG_TEXT_CHARS,
    MAX_INCIDENT_FILTER_CHARS,
    MAX_INCIDENT_PAGE_LIMIT,
    MAX_INCIDENT_TEXT_CHARS,
    MAX_SECURITY_AUDIT_FILTER_CHARS,
    MAX_SECURITY_AUDIT_PAGE_LIMIT,
    AccessAuthorizationProjection,
    AssuranceDecisionProjection,
    AttestationTrustAuthentication,
    AttestationTrustQuery,
    CaptureFailureQuery,
    ClaimCatalogQuery,
    ClaimCatalogRecord,
    DataGovernanceProjection,
    EvidenceTraceRecord,
    IncidentInvestigationQuery,
    OverviewReportRecord,
    ReportSourceContext,
    SecurityAuditQuery,
    SignedAttestationBindingAuthentication,
    build_attestation_trust_projection,
    build_capture_health,
    build_claim_catalog,
    build_claim_comparison,
    build_claim_detail,
    build_claim_history,
    build_claim_summary,
    build_decision_lineage_investigation,
    build_evidence_trace,
    build_incident_detail,
    build_incident_investigation,
    build_overview,
    build_release_trust_projection,
    build_reliability_proof_investigation,
    build_security_assurance_projection,
    build_validation_study_projection,
    build_workspace_operations_projection,
)
from statewake.release_trust.bundle import load_release_trust_bundle
from statewake.release_trust.content_verification import verify_release_trust_files
from statewake.release_trust.publication import (
    load_publication_execution_permit,
    load_release_publication_basis,
    resolve_publication_authorization,
)
from statewake.release_trust.registry import (
    RegistryPublicationLifecycleObservation,
    RegistryPublicationLifecycleStore,
    load_registry_publication_receipt,
    verify_registry_publication_receipt,
)
from statewake.reports.json_report import render_json_report
from statewake.reports.markdown import render_markdown_report
from statewake.services.access_control_investigation_service import (
    load_authorization_context,
)
from statewake.services.assurance_decision_service import (
    load_assurance_decision,
    load_assurance_exception,
)
from statewake.services.data_lifecycle_investigation_service import (
    load_data_lifecycle_context,
    resolve_data_lifecycle_context,
)
from statewake.services.evidence_admission_service import admit_external_evidence
from statewake.services.operations_service import verify_bundle
from statewake.services.privacy_governance_runtime_service import (
    load_privacy_governance_runtime_snapshot,
)
from statewake.services.provenance_service import load_provenance_graph
from statewake.services.reliability_attestation_service import (
    resolve_reliability_attestation_trust_state,
    verify_reliability_attestation_trust_context,
)
from statewake.services.reliability_comparison_service import (
    load_reliability_behavioral_comparison,
)
from statewake.services.reliability_decision_basis_service import (
    load_reliability_decision_basis,
)
from statewake.services.reliability_evidence_service import (
    verify_reliability_evidence_chain,
)
from statewake.services.reliability_lineage_service import (
    build_reliability_lineage_closure,
)
from statewake.services.reliability_proof_bundle_service import (
    verify_reliability_proof_bundle,
)
from statewake.services.reliability_reconciliation_binding_service import (
    load_reliability_reconciliation_binding,
)
from statewake.services.reliability_recovery_service import (
    verify_reliability_recovery_outcome,
)
from statewake.services.runtime_containment_snapshot_service import (
    load_runtime_containment_snapshot,
)
from statewake.services.trust_service import authority_store_from_dict
from statewake.utils.json_support import loads_object, require_string
from statewake.validation_study.report import load_study_report
from statewake.workspace import (
    StateWakeWorkspace,
    WorkspaceError,
    WorkspaceRepositoryError,
)

_DEFAULT_MAX_REPORT_BYTES = 1_048_576
_DEFAULT_MAX_HISTORY_BYTES = 8_388_608
_DEFAULT_MAX_HISTORY_ITEMS = 200
_DEFAULT_MAX_OVERVIEW_RECEIPTS = 2_000
_DEFAULT_MAX_CLAIM_CATALOG_RECEIPTS = 2_000
_DEFAULT_MAX_EVIDENCE_RECEIPTS = 2_000
_DEFAULT_MAX_EVIDENCE_NODES = 200
_DEFAULT_MAX_RELEASE_BUNDLE_BYTES = 2_097_152
_DEFAULT_MAX_RELIABILITY_PROOF_BYTES = 16 * 1024 * 1024
_DEFAULT_MAX_STUDY_BYTES = 8_388_608
_DEFAULT_MAX_INCIDENT_BYTES = 8_388_608
_DEFAULT_MAX_INCIDENT_RECORDS = 2_000
_DEFAULT_MAX_CAPTURE_FAILURE_JOURNAL_BYTES = 8 * 1024 * 1024
_DEFAULT_MAX_CAPTURE_FAILURE_RECORDS = 10_000
_DEFAULT_MAX_SECURITY_AUDIT_BYTES = 8 * 1024 * 1024
_DEFAULT_MAX_SECURITY_AUDIT_RECORDS = 10_000
_DEFAULT_MAX_ATTESTATION_STORE_BYTES = 8 * 1024 * 1024
_DEFAULT_MAX_ATTESTATION_RECORDS = 2_000
_DEFAULT_MAX_ATTESTATION_TRUST_STATE_BYTES = 1 * 1024 * 1024
_DEFAULT_MAX_ATTESTATION_TRUST_HISTORY_BYTES = 8 * 1024 * 1024
_DEFAULT_MAX_ATTESTATION_TRUST_HISTORY_RECORDS = 2_000
_DEFAULT_MAX_ATTESTATION_AUTHORITY_STORE_BYTES = 1 * 1024 * 1024
_DEFAULT_MAX_DECISION_CHAIN_BYTES = 2 * 1024 * 1024
_DEFAULT_MAX_DECISION_SOURCE_BYTES = 32 * 1024 * 1024
_DEFAULT_MAX_ASSURANCE_DECISION_BYTES = 1 * 1024 * 1024
_DEFAULT_MAX_ASSURANCE_EXCEPTION_BYTES = 1 * 1024 * 1024
_DEFAULT_MAX_AUTHORIZATION_CONTEXT_BYTES = 1 * 1024 * 1024
_DEFAULT_MAX_DATA_LIFECYCLE_CONTEXT_BYTES = 1 * 1024 * 1024
_DEFAULT_MAX_RUNTIME_CONTAINMENT_SNAPSHOT_BYTES = 256 * 1024
_DEFAULT_MAX_PRIVACY_GOVERNANCE_SNAPSHOT_BYTES = 256 * 1024
_DEFAULT_WORKSPACE_PAGE_LIMIT = 50
_MAX_WORKSPACE_PAGE_LIMIT = 200
_DEFAULT_CLAIM_PAGE_LIMIT = 50
_DEFAULT_INCIDENT_PAGE_LIMIT = 50
_DEFAULT_CAPTURE_FAILURE_PAGE_LIMIT = 50
_DEFAULT_SECURITY_AUDIT_PAGE_LIMIT = 50
_DEFAULT_ATTESTATION_TRUST_PAGE_LIMIT = 50
_CAPABILITIES_SCHEMA_VERSION = "ui-capabilities.v1"


class WorkspaceReadError(RuntimeError):
    """Raised when the configured workspace cannot be safely read."""


class InvalidReportError(ValueError):
    """Raised when a requested receipt does not contain a valid canonical report."""


class HistoryNotConfiguredError(RuntimeError):
    """Raised when optional reliability-state history is not configured."""


class InvalidHistoryError(ValueError):
    """Raised when configured reliability-state history cannot be trusted."""


class HistoryTooLargeError(OverflowError):
    """Raised when configured history exceeds a bounded read limit."""


class EvidenceTraceTooLargeError(OverflowError):
    """Raised when an evidence trace exceeds its explicit node bound."""


class OperationalSourceNotConfiguredError(RuntimeError):
    """Raised when an optional operational read source was not configured."""


class InvalidOperationalSourceError(ValueError):
    """Raised when an operational source cannot be trusted as valid input."""


class InvalidWorkspaceQueryError(ValueError):
    """Raised when workspace pagination exceeds the fixed read contract."""


class InvalidClaimCatalogQueryError(ValueError):
    """Raised when claim discovery exceeds its allowlisted query contract."""


class ClaimCatalogTooLargeError(OverflowError):
    """Raised when claim discovery exceeds its bounded receipt scan."""


class OperationalSourceTooLargeError(OverflowError):
    """Raised when a configured operational artifact exceeds its read limit."""


class IncidentSourceNotConfiguredError(RuntimeError):
    """Raised when the optional incident evidence source is not configured."""


class InvalidIncidentSourceError(ValueError):
    """Raised when configured incident evidence cannot be trusted."""


class IncidentSourceTooLargeError(OverflowError):
    """Raised when configured incident evidence exceeds bounded read limits."""


class InvalidIncidentQueryError(ValueError):
    """Raised when incident discovery exceeds the allowlisted query contract."""


class CaptureFailureSourceNotConfiguredError(RuntimeError):
    """Raised when the optional native capture failure journal is not configured."""


class InvalidCaptureFailureSourceError(ValueError):
    """Raised when configured native capture failure evidence cannot be trusted."""


class CaptureFailureSourceTooLargeError(OverflowError):
    """Raised when configured native capture failure evidence exceeds read limits."""


class InvalidCaptureFailureQueryError(ValueError):
    """Raised when capture failure investigation exceeds the allowlisted query contract."""


class SecurityAuditSourceNotConfiguredError(RuntimeError):
    """Raised when no deployment security audit source is configured."""


class InvalidSecurityAuditSourceError(ValueError):
    """Raised when configured deployment security audit evidence is invalid."""


class SecurityAuditSourceTooLargeError(OverflowError):
    """Raised when configured deployment security audit evidence is too large."""


class InvalidSecurityAuditQueryError(ValueError):
    """Raised when security audit investigation exceeds its query contract."""


class InvalidRuntimeContainmentSnapshotError(ValueError):
    """Raised when configured runtime-containment configuration evidence is invalid."""


class RuntimeContainmentSnapshotTooLargeError(OverflowError):
    """Raised when runtime-containment configuration evidence exceeds its read bound."""


class AttestationTrustSourceNotConfiguredError(RuntimeError):
    """Raised when no attestation trust source is configured."""


class InvalidAttestationTrustSourceError(ValueError):
    """Raised when configured attestation trust evidence cannot be trusted."""


class AttestationTrustSourceTooLargeError(OverflowError):
    """Raised when configured attestation trust evidence exceeds read bounds."""


class InvalidAttestationTrustQueryError(ValueError):
    """Raised when attestation trust investigation exceeds its query contract."""


class ReliabilityProofSourceNotConfiguredError(RuntimeError):
    """Raised when no reliability proof bundle is configured."""


class InvalidReliabilityProofSourceError(ValueError):
    """Raised when the configured reliability proof bundle cannot be verified."""


class ReliabilityProofSourceTooLargeError(OverflowError):
    """Raised when a configured reliability proof bundle exceeds the read limit."""


class DecisionLineageSourceNotConfiguredError(RuntimeError):
    """Raised when no reliability decision evidence chain is configured."""


class InvalidDecisionLineageSourceError(ValueError):
    """Raised when the configured decision/lineage source cannot be verified."""


class DecisionLineageSourceTooLargeError(OverflowError):
    """Raised when configured decision/lineage sources exceed bounded read limits."""


class AssuranceDecisionSourceNotConfiguredError(RuntimeError):
    """Raised when no assurance decision source is configured."""


class InvalidAssuranceDecisionSourceError(ValueError):
    """Raised when configured assurance decision evidence cannot be verified."""


class AssuranceDecisionSourceTooLargeError(OverflowError):
    """Raised when assurance decision/exception input exceeds its read bound."""


class AuthorizationContextSourceNotConfiguredError(RuntimeError):
    """Raised when no authorization investigation context is configured."""


class InvalidAuthorizationContextSourceError(ValueError):
    """Raised when configured authorization context cannot be replay-verified."""


class AuthorizationContextSourceTooLargeError(OverflowError):
    """Raised when configured authorization context exceeds its read bound."""


class DataGovernanceSourceNotConfiguredError(RuntimeError):
    """Raised when no data lifecycle investigation context is configured."""


class InvalidDataGovernanceSourceError(ValueError):
    """Raised when configured lifecycle context disagrees with workspace state."""


class DataGovernanceSourceTooLargeError(OverflowError):
    """Raised when configured lifecycle context exceeds its read bound."""


class InvalidDataGovernanceQueryError(ValueError):
    """Raised when data-governance investigation receives query parameters."""


@dataclass(frozen=True, slots=True)
class ReadApiConfig:
    """Configuration for the local, read-only human-inspection API."""

    workspace_root: Path
    max_report_bytes: int = _DEFAULT_MAX_REPORT_BYTES
    history_path: Path | None = None
    max_history_bytes: int = _DEFAULT_MAX_HISTORY_BYTES
    max_history_items: int = _DEFAULT_MAX_HISTORY_ITEMS
    max_overview_receipts: int = _DEFAULT_MAX_OVERVIEW_RECEIPTS
    max_claim_catalog_receipts: int = _DEFAULT_MAX_CLAIM_CATALOG_RECEIPTS
    max_evidence_receipts: int = _DEFAULT_MAX_EVIDENCE_RECEIPTS
    max_evidence_nodes: int = _DEFAULT_MAX_EVIDENCE_NODES
    release_bundle_path: Path | None = None
    release_root: Path | None = None
    max_release_bundle_bytes: int = _DEFAULT_MAX_RELEASE_BUNDLE_BYTES
    publication_basis_path: Path | None = None
    publication_approval_workspace: Path | None = None
    publication_expected_producer_id: str | None = None
    publication_permit_path: Path | None = None
    publication_registry_receipt_path: Path | None = None
    publication_registry_lifecycle_path: Path | None = None
    reliability_proof_path: Path | None = None
    max_reliability_proof_bytes: int = _DEFAULT_MAX_RELIABILITY_PROOF_BYTES
    validation_study_path: Path | None = None
    max_validation_study_bytes: int = _DEFAULT_MAX_STUDY_BYTES
    incident_evidence_path: Path | None = None
    max_incident_evidence_bytes: int = _DEFAULT_MAX_INCIDENT_BYTES
    max_incident_records: int = _DEFAULT_MAX_INCIDENT_RECORDS
    capture_failure_journal_path: Path | None = None
    max_capture_failure_journal_bytes: int = _DEFAULT_MAX_CAPTURE_FAILURE_JOURNAL_BYTES
    max_capture_failure_records: int = _DEFAULT_MAX_CAPTURE_FAILURE_RECORDS
    capture_failure_journal_capacity_bytes: int | None = None
    security_audit_path: Path | None = None
    max_security_audit_bytes: int = _DEFAULT_MAX_SECURITY_AUDIT_BYTES
    max_security_audit_records: int = _DEFAULT_MAX_SECURITY_AUDIT_RECORDS
    attestation_store_path: Path | None = None
    max_attestation_store_bytes: int = _DEFAULT_MAX_ATTESTATION_STORE_BYTES
    max_attestation_records: int = _DEFAULT_MAX_ATTESTATION_RECORDS
    attestation_trust_state_path: Path | None = None
    max_attestation_trust_state_bytes: int = _DEFAULT_MAX_ATTESTATION_TRUST_STATE_BYTES
    attestation_trust_history_path: Path | None = None
    max_attestation_trust_history_bytes: int = (
        _DEFAULT_MAX_ATTESTATION_TRUST_HISTORY_BYTES
    )
    max_attestation_trust_history_records: int = (
        _DEFAULT_MAX_ATTESTATION_TRUST_HISTORY_RECORDS
    )
    attestation_authority_store_path: Path | None = None
    max_attestation_authority_store_bytes: int = (
        _DEFAULT_MAX_ATTESTATION_AUTHORITY_STORE_BYTES
    )
    reliability_decision_chain_path: Path | None = None
    max_decision_chain_bytes: int = _DEFAULT_MAX_DECISION_CHAIN_BYTES
    max_decision_source_bytes: int = _DEFAULT_MAX_DECISION_SOURCE_BYTES
    assurance_decision_path: Path | None = None
    assurance_exception_path: Path | None = None
    max_assurance_decision_bytes: int = _DEFAULT_MAX_ASSURANCE_DECISION_BYTES
    max_assurance_exception_bytes: int = _DEFAULT_MAX_ASSURANCE_EXCEPTION_BYTES
    authorization_context_path: Path | None = None
    max_authorization_context_bytes: int = _DEFAULT_MAX_AUTHORIZATION_CONTEXT_BYTES
    data_lifecycle_context_path: Path | None = None
    max_data_lifecycle_context_bytes: int = _DEFAULT_MAX_DATA_LIFECYCLE_CONTEXT_BYTES
    runtime_containment_snapshot_path: Path | None = None
    max_runtime_containment_snapshot_bytes: int = (
        _DEFAULT_MAX_RUNTIME_CONTAINMENT_SNAPSHOT_BYTES
    )
    privacy_governance_snapshot_path: Path | None = None
    max_privacy_governance_snapshot_bytes: int = (
        _DEFAULT_MAX_PRIVACY_GOVERNANCE_SNAPSHOT_BYTES
    )

    def __post_init__(self) -> None:
        """Normalize paths and validate bounded response inputs."""
        root = self.workspace_root.expanduser().resolve()
        object.__setattr__(self, "workspace_root", root)
        if self.history_path is not None:
            object.__setattr__(
                self,
                "history_path",
                self.history_path.expanduser().resolve(),
            )
        capture_path = self.capture_failure_journal_path
        if capture_path is not None:
            capture_path = capture_path.expanduser()
            if capture_path.is_symlink() or any(
                part.is_symlink() for part in capture_path.parents
            ):
                raise ValueError(
                    "capture failure journal path cannot traverse a symlink"
                )
            object.__setattr__(
                self, "capture_failure_journal_path", capture_path.resolve()
            )
        for field_name in (
            "release_bundle_path",
            "release_root",
            "publication_basis_path",
            "publication_approval_workspace",
            "publication_permit_path",
            "publication_registry_receipt_path",
            "publication_registry_lifecycle_path",
            "validation_study_path",
            "incident_evidence_path",
        ):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, value.expanduser().resolve())
        proof_path = self.reliability_proof_path
        if proof_path is not None:
            proof_path = proof_path.expanduser()
            if proof_path.is_symlink() or any(
                parent.is_symlink() for parent in proof_path.parents
            ):
                raise ValueError("reliability proof path cannot traverse a symlink")
            object.__setattr__(self, "reliability_proof_path", proof_path.resolve())
        for field_name in (
            "security_audit_path",
            "attestation_store_path",
            "attestation_trust_state_path",
            "attestation_trust_history_path",
            "attestation_authority_store_path",
            "reliability_decision_chain_path",
            "assurance_decision_path",
            "assurance_exception_path",
            "authorization_context_path",
            "data_lifecycle_context_path",
            "runtime_containment_snapshot_path",
            "privacy_governance_snapshot_path",
        ):
            value = getattr(self, field_name)
            if value is not None:
                value = value.expanduser()
                if value.is_symlink() or any(
                    parent.is_symlink() for parent in value.parents
                ):
                    raise ValueError(f"{field_name} cannot traverse a symlink")
                object.__setattr__(self, field_name, value.resolve())
        if self.max_report_bytes <= 0:
            raise ValueError("max_report_bytes must be positive")
        if self.max_history_bytes <= 0:
            raise ValueError("max_history_bytes must be positive")
        if self.max_history_items <= 0:
            raise ValueError("max_history_items must be positive")
        if self.max_overview_receipts <= 0:
            raise ValueError("max_overview_receipts must be positive")
        if self.max_claim_catalog_receipts <= 0:
            raise ValueError("max_claim_catalog_receipts must be positive")
        if self.max_evidence_receipts <= 0:
            raise ValueError("max_evidence_receipts must be positive")
        if self.max_evidence_nodes <= 0:
            raise ValueError("max_evidence_nodes must be positive")
        if self.max_release_bundle_bytes <= 0:
            raise ValueError("max_release_bundle_bytes must be positive")
        publication_configured = (
            self.publication_basis_path is not None,
            self.publication_approval_workspace is not None,
            self.publication_expected_producer_id is not None,
        )
        if any(publication_configured) and not all(publication_configured):
            raise ValueError(
                "publication basis, approval workspace, and producer id must be configured together"
            )
        if (
            self.publication_expected_producer_id is not None
            and not self.publication_expected_producer_id.strip()
        ):
            raise ValueError("publication_expected_producer_id must not be blank")
        registry_projection_configured = (
            self.publication_permit_path is not None,
            self.publication_registry_receipt_path is not None,
        )
        if any(registry_projection_configured) and not all(
            registry_projection_configured
        ):
            raise ValueError(
                "publication permit and registry receipt must be configured together"
            )
        if any(registry_projection_configured) and not all(publication_configured):
            raise ValueError(
                "registry publication projection requires publication authority configuration"
            )
        if self.publication_registry_lifecycle_path is not None and not all(
            registry_projection_configured
        ):
            raise ValueError(
                "registry lifecycle projection requires publication permit and registry receipt"
            )
        if self.max_reliability_proof_bytes <= 0:
            raise ValueError("max_reliability_proof_bytes must be positive")
        if self.max_validation_study_bytes <= 0:
            raise ValueError("max_validation_study_bytes must be positive")
        if self.max_incident_evidence_bytes <= 0:
            raise ValueError("max_incident_evidence_bytes must be positive")
        if self.max_incident_records <= 0:
            raise ValueError("max_incident_records must be positive")
        if self.max_capture_failure_journal_bytes <= 0:
            raise ValueError("max_capture_failure_journal_bytes must be positive")
        if self.max_capture_failure_records <= 0:
            raise ValueError("max_capture_failure_records must be positive")
        if self.max_security_audit_bytes <= 0:
            raise ValueError("max_security_audit_bytes must be positive")
        if self.max_security_audit_records <= 0:
            raise ValueError("max_security_audit_records must be positive")
        if self.max_attestation_store_bytes <= 0:
            raise ValueError("max_attestation_store_bytes must be positive")
        if self.max_attestation_records <= 0:
            raise ValueError("max_attestation_records must be positive")
        if self.max_attestation_trust_state_bytes <= 0:
            raise ValueError("max_attestation_trust_state_bytes must be positive")
        if self.max_attestation_trust_history_bytes <= 0:
            raise ValueError("max_attestation_trust_history_bytes must be positive")
        if self.max_attestation_trust_history_records <= 0:
            raise ValueError("max_attestation_trust_history_records must be positive")
        if self.max_attestation_authority_store_bytes <= 0:
            raise ValueError("max_attestation_authority_store_bytes must be positive")
        if self.max_decision_chain_bytes <= 0:
            raise ValueError("max_decision_chain_bytes must be positive")
        if self.max_decision_source_bytes <= 0:
            raise ValueError("max_decision_source_bytes must be positive")
        if self.max_assurance_decision_bytes <= 0:
            raise ValueError("max_assurance_decision_bytes must be positive")
        if self.max_assurance_exception_bytes <= 0:
            raise ValueError("max_assurance_exception_bytes must be positive")
        if self.max_authorization_context_bytes <= 0:
            raise ValueError("max_authorization_context_bytes must be positive")
        if self.max_data_lifecycle_context_bytes <= 0:
            raise ValueError("max_data_lifecycle_context_bytes must be positive")
        if self.max_runtime_containment_snapshot_bytes <= 0:
            raise ValueError("max_runtime_containment_snapshot_bytes must be positive")
        if self.max_privacy_governance_snapshot_bytes <= 0:
            raise ValueError("max_privacy_governance_snapshot_bytes must be positive")
        if (
            self.capture_failure_journal_capacity_bytes is not None
            and self.capture_failure_journal_capacity_bytes <= 0
        ):
            raise ValueError("capture failure journal capacity must be positive")

    @classmethod
    def from_environment(cls) -> ReadApiConfig:
        """Build configuration from explicit local read-only environment values."""
        workspace = os.environ.get("STATEWAKE_UI_WORKSPACE_ROOT", "").strip()
        history = os.environ.get("STATEWAKE_UI_RELIABILITY_HISTORY", "").strip()
        release_bundle = os.environ.get("STATEWAKE_UI_RELEASE_TRUST_BUNDLE", "").strip()
        release_root = os.environ.get("STATEWAKE_UI_RELEASE_ROOT", "").strip()
        publication_basis = os.environ.get("STATEWAKE_UI_PUBLICATION_BASIS", "").strip()
        publication_workspace = os.environ.get(
            "STATEWAKE_UI_PUBLICATION_APPROVAL_WORKSPACE", ""
        ).strip()
        publication_producer = os.environ.get(
            "STATEWAKE_UI_PUBLICATION_PRODUCER_ID", ""
        ).strip()
        publication_permit = os.environ.get(
            "STATEWAKE_UI_PUBLICATION_PERMIT", ""
        ).strip()
        publication_registry_receipt = os.environ.get(
            "STATEWAKE_UI_PUBLICATION_REGISTRY_RECEIPT", ""
        ).strip()
        publication_registry_lifecycle = os.environ.get(
            "STATEWAKE_UI_PUBLICATION_REGISTRY_LIFECYCLE", ""
        ).strip()
        reliability_proof = os.environ.get(
            "STATEWAKE_UI_RELIABILITY_PROOF_BUNDLE", ""
        ).strip()
        study = os.environ.get("STATEWAKE_UI_VALIDATION_STUDY", "").strip()
        incidents = os.environ.get("STATEWAKE_UI_INCIDENT_EVIDENCE", "").strip()
        capture_failures = os.environ.get(
            "STATEWAKE_UI_CAPTURE_FAILURE_JOURNAL", ""
        ).strip()
        capture_capacity_text = os.environ.get(
            "STATEWAKE_UI_CAPTURE_FAILURE_JOURNAL_CAPACITY_BYTES", ""
        ).strip()
        security_audit = os.environ.get("STATEWAKE_UI_SECURITY_AUDIT", "").strip()
        attestations = os.environ.get("STATEWAKE_UI_ATTESTATION_STORE", "").strip()
        trust_state = os.environ.get("STATEWAKE_UI_ATTESTATION_TRUST_STATE", "").strip()
        trust_history = os.environ.get(
            "STATEWAKE_UI_ATTESTATION_TRUST_HISTORY", ""
        ).strip()
        authority_store = os.environ.get(
            "STATEWAKE_UI_ATTESTATION_AUTHORITY_STORE", ""
        ).strip()
        decision_chain = os.environ.get(
            "STATEWAKE_UI_RELIABILITY_DECISION_CHAIN", ""
        ).strip()
        assurance_decision = os.environ.get(
            "STATEWAKE_UI_ASSURANCE_DECISION", ""
        ).strip()
        assurance_exception = os.environ.get(
            "STATEWAKE_UI_ASSURANCE_EXCEPTION", ""
        ).strip()
        authorization_context = os.environ.get(
            "STATEWAKE_UI_AUTHORIZATION_CONTEXT", ""
        ).strip()
        data_lifecycle_context = os.environ.get(
            "STATEWAKE_UI_DATA_LIFECYCLE_CONTEXT", ""
        ).strip()
        runtime_containment_snapshot = os.environ.get(
            "STATEWAKE_UI_RUNTIME_CONTAINMENT_SNAPSHOT", ""
        ).strip()
        privacy_governance_snapshot = os.environ.get(
            "STATEWAKE_UI_PRIVACY_GOVERNANCE_SNAPSHOT", ""
        ).strip()
        capture_capacity = int(capture_capacity_text) if capture_capacity_text else None
        return cls(
            Path(workspace) if workspace else Path("data/statewake"),
            history_path=Path(history) if history else None,
            release_bundle_path=Path(release_bundle) if release_bundle else None,
            release_root=Path(release_root) if release_root else None,
            publication_basis_path=Path(publication_basis)
            if publication_basis
            else None,
            publication_approval_workspace=(
                Path(publication_workspace) if publication_workspace else None
            ),
            publication_expected_producer_id=publication_producer or None,
            publication_permit_path=(
                Path(publication_permit) if publication_permit else None
            ),
            publication_registry_receipt_path=(
                Path(publication_registry_receipt)
                if publication_registry_receipt
                else None
            ),
            publication_registry_lifecycle_path=(
                Path(publication_registry_lifecycle)
                if publication_registry_lifecycle
                else None
            ),
            reliability_proof_path=(
                Path(reliability_proof) if reliability_proof else None
            ),
            validation_study_path=Path(study) if study else None,
            incident_evidence_path=Path(incidents) if incidents else None,
            capture_failure_journal_path=(
                Path(capture_failures) if capture_failures else None
            ),
            capture_failure_journal_capacity_bytes=capture_capacity,
            security_audit_path=Path(security_audit) if security_audit else None,
            attestation_store_path=Path(attestations) if attestations else None,
            attestation_trust_state_path=Path(trust_state) if trust_state else None,
            attestation_trust_history_path=(
                Path(trust_history) if trust_history else None
            ),
            attestation_authority_store_path=(
                Path(authority_store) if authority_store else None
            ),
            reliability_decision_chain_path=(
                Path(decision_chain) if decision_chain else None
            ),
            assurance_decision_path=(
                Path(assurance_decision) if assurance_decision else None
            ),
            assurance_exception_path=(
                Path(assurance_exception) if assurance_exception else None
            ),
            authorization_context_path=(
                Path(authorization_context) if authorization_context else None
            ),
            data_lifecycle_context_path=(
                Path(data_lifecycle_context) if data_lifecycle_context else None
            ),
            runtime_containment_snapshot_path=(
                Path(runtime_containment_snapshot)
                if runtime_containment_snapshot
                else None
            ),
            privacy_governance_snapshot_path=(
                Path(privacy_governance_snapshot)
                if privacy_governance_snapshot
                else None
            ),
        )


def _json_response(
    start_response: StartResponse,
    status: str,
    payload: dict[str, object],
    *,
    etag: str | None = None,
) -> list[bytes]:
    """Return one bounded JSON response with conservative cache semantics."""
    body = (json.dumps(payload, sort_keys=True) + "\n").encode("utf-8")
    headers = [
        ("Content-Type", "application/json; charset=utf-8"),
        ("Content-Length", str(len(body))),
        ("Cache-Control", "no-store"),
    ]
    if etag is not None:
        headers.append(("ETag", f'"{etag}"'))
    start_response(status, headers)
    return [body]


def _text_response(
    start_response: StartResponse,
    status: str,
    text: str,
    *,
    content_type: str,
    etag: str,
) -> list[bytes]:
    """Return one canonical text representation."""
    body = text.encode("utf-8")
    start_response(
        status,
        [
            ("Content-Type", content_type),
            ("Content-Length", str(len(body))),
            ("Cache-Control", "no-store"),
            ("ETag", f'"{etag}"'),
        ],
    )
    return [body]


def _empty_response(
    start_response: StartResponse,
    status: str,
    *,
    etag: str,
) -> list[bytes]:
    """Return an empty conditional response."""
    start_response(status, [("ETag", f'"{etag}"'), ("Cache-Control", "no-store")])
    return []


def _error(
    start_response: StartResponse,
    status: str,
    code: str,
    message: str,
) -> list[bytes]:
    """Return a stable safe API error without exposing local paths."""
    return _json_response(
        start_response,
        status,
        {"error": {"code": code, "message": message}},
    )


def _record_id_from_path(path: str, prefix: str, suffix: str = "") -> str | None:
    """Extract a deterministic receipt identity from a route path."""
    if not path.startswith(prefix) or (suffix and not path.endswith(suffix)):
        return None
    end = len(path) - len(suffix) if suffix else len(path)
    value = path[len(prefix) : end]
    if "/" in value or not value:
        return None
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError("record id must be a lowercase SHA-256 identity")
    return value


def _incident_id_from_path(path: str) -> str | None:
    """Extract one incident identity without reclassifying malformed routes as reports."""
    prefix = "/api/v1/incidents/"
    if not path.startswith(prefix):
        return None
    value = path[len(prefix) :]
    if (
        "/" in value
        or len(value) != 64
        or any(char not in "0123456789abcdef" for char in value)
    ):
        return None
    return value


def _comparison_ids_from_path(path: str) -> tuple[str, str] | None:
    """Extract two canonical report IDs from a direct comparison route."""
    prefix = "/api/v1/claims/"
    marker = "/compare/"
    if not path.startswith(prefix) or marker not in path:
        return None
    left, right = path[len(prefix) :].split(marker, 1)
    for value in (left, right):
        if (
            "/" in value
            or len(value) != 64
            or any(char not in "0123456789abcdef" for char in value)
        ):
            raise ValueError("record id must be a lowercase SHA-256 identity")
    return left, right


def _workspace_identity(root: Path) -> dict[str, str]:
    """Read the existing workspace identity without creating or repairing state."""
    manifest = root / "manifest.json"
    try:
        payload = loads_object(manifest.read_bytes(), field="workspace manifest")
        schema_version = require_string(
            payload["schema_version"], field="schema_version"
        )
        if schema_version != "1":
            raise ValueError("unsupported workspace schema version")
        return {
            "workspace_id": require_string(
                payload["workspace_id"], field="workspace_id"
            ),
            "created_at": require_string(payload["created_at"], field="created_at"),
            "schema_version": schema_version,
            "public_api_contract_version": require_string(
                payload["public_api_contract_version"],
                field="public_api_contract_version",
            ),
        }
    except (OSError, KeyError, ValueError) as exc:
        raise WorkspaceReadError(
            "workspace manifest is unavailable or invalid"
        ) from exc


def _load_report(
    config: ReadApiConfig,
    record_id: str,
) -> tuple[ReliabilityVerificationReport, ReportSourceContext]:
    """Load and verify one durable report receipt without mutating its workspace."""
    _workspace_identity(config.workspace_root)
    receipt_store = JsonEvidenceReceiptStore(config.workspace_root / "receipts")
    receipt = receipt_store.get(record_id)
    if receipt.artifact_size > config.max_report_bytes:
        raise OverflowError("report artifact exceeds configured read limit")

    content = ContentAddressedArtifactStore(config.workspace_root / "artifacts").get(
        receipt.artifact_digest
    )
    if len(content) != receipt.artifact_size:
        raise ValueError("report artifact size does not match its receipt")
    try:
        payload = loads_object(content, field="verification report")
        report = ReliabilityVerificationReport.from_dict(payload)
    except (KeyError, ValueError) as exc:
        raise InvalidReportError("stored verification report is invalid") from exc

    metadata_candidate = receipt.metadata.get("candidate_identity")
    if (
        metadata_candidate is not None
        and metadata_candidate != report.candidate_identity
    ):
        raise InvalidReportError(
            "report candidate identity conflicts with its receipt metadata"
        )

    source = ReportSourceContext(
        record_id=receipt.receipt_id,
        artifact_digest=receipt.artifact_digest,
        producer_id=receipt.producer_id,
        producer_type=receipt.producer_type,
        captured_at=receipt.captured_at.isoformat(),
        run_id=receipt.run_id,
    )
    return report, source


def _load_history_projection(
    config: ReadApiConfig,
    record_id: str,
    report: ReliabilityVerificationReport,
) -> tuple[dict[str, object], str]:
    """Load configured state history as a bounded, non-mutating projection."""
    history_path = config.history_path
    if history_path is None:
        raise HistoryNotConfiguredError("reliability-state history is not configured")
    if history_path.exists() and history_path.stat().st_size > config.max_history_bytes:
        raise HistoryTooLargeError(
            "reliability-state history exceeds configured read limit"
        )
    try:
        raw = history_path.read_bytes() if history_path.exists() else b""
        transitions = tuple(parse_reliability_state_history(raw))
        projection = build_claim_history(
            record_id,
            report,
            transitions,
            max_items=config.max_history_items,
        )
    except OverflowError as exc:
        raise HistoryTooLargeError(
            "reliability-state history exceeds configured item limit"
        ) from exc
    except (OSError, ValueError) as exc:
        raise InvalidHistoryError(
            "configured reliability-state history is invalid"
        ) from exc
    return projection.to_dict(), projection.digest


def _load_canonical_report_records(
    config: ReadApiConfig,
    *,
    max_receipts: int,
) -> tuple[tuple[ClaimCatalogRecord, ...], int]:
    """Load canonical report records through the existing verified report boundary."""
    _workspace_identity(config.workspace_root)
    receipt_root = config.workspace_root / "receipts"
    if not receipt_root.exists():
        return (), 0
    paths = sorted(receipt_root.glob("*.json"))
    if len(paths) > max_receipts:
        raise ClaimCatalogTooLargeError("workspace receipt count exceeds scan limit")
    records: list[ClaimCatalogRecord] = []
    for path in paths:
        try:
            payload = loads_object(path.read_bytes(), field="evidence receipt")
            receipt = ExternalEvidenceReceipt.from_dict(payload)
        except (OSError, KeyError, TypeError, ValueError) as exc:
            raise WorkspaceReadError(
                "workspace receipt is unavailable or invalid"
            ) from exc
        if not (
            receipt.producer_type == "statewake-verification-report"
            or "report_type" in receipt.metadata
        ):
            continue
        report, source = _load_report(config, receipt.receipt_id)
        records.append(ClaimCatalogRecord(report=report, source=source))
    return tuple(records), len(paths)


def _single_query_value(
    query: dict[str, list[str]],
    key: str,
    *,
    max_chars: int,
) -> str | None:
    """Return one trimmed, bounded query value or reject duplicates and blanks."""
    values = query.get(key)
    if values is None:
        return None
    if len(values) != 1:
        raise InvalidClaimCatalogQueryError("duplicate claim query parameter")
    value = values[0].strip()
    if not value or len(value) > max_chars:
        raise InvalidClaimCatalogQueryError("claim query value is blank or too long")
    return value


def _claim_catalog_query(environ: WSGIEnvironment) -> ClaimCatalogQuery:
    """Parse the allowlisted, bounded canonical-report discovery query."""
    query = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
    allowed = {
        "decision",
        "verified",
        "approval_status",
        "profile_id",
        "candidate_id",
        "q",
        "limit",
        "offset",
    }
    if any(key not in allowed for key in query):
        raise InvalidClaimCatalogQueryError("unsupported claim query parameter")
    if any(len(values) != 1 for values in query.values()):
        raise InvalidClaimCatalogQueryError("duplicate claim query parameter")

    verified_raw = _single_query_value(
        query, "verified", max_chars=MAX_CLAIM_CATALOG_FILTER_CHARS
    )
    if verified_raw is None:
        verified = None
    elif verified_raw == "true":
        verified = True
    elif verified_raw == "false":
        verified = False
    else:
        raise InvalidClaimCatalogQueryError("verified must be true or false")

    limit_raw = query.get("limit", [str(_DEFAULT_CLAIM_PAGE_LIMIT)])[0]
    offset_raw = query.get("offset", ["0"])[0]
    if not limit_raw.isdigit() or not offset_raw.isdigit():
        raise InvalidClaimCatalogQueryError("claim pagination must be integers")
    limit = int(limit_raw)
    offset = int(offset_raw)
    if limit < 1 or limit > MAX_CLAIM_CATALOG_PAGE_LIMIT or offset < 0:
        raise InvalidClaimCatalogQueryError("claim pagination is out of bounds")

    return ClaimCatalogQuery(
        decision=_single_query_value(
            query, "decision", max_chars=MAX_CLAIM_CATALOG_FILTER_CHARS
        ),
        verified=verified,
        approval_status=_single_query_value(
            query, "approval_status", max_chars=MAX_CLAIM_CATALOG_FILTER_CHARS
        ),
        profile_id=_single_query_value(
            query, "profile_id", max_chars=MAX_CLAIM_CATALOG_FILTER_CHARS
        ),
        candidate_id=_single_query_value(
            query, "candidate_id", max_chars=MAX_CLAIM_CATALOG_FILTER_CHARS
        ),
        text=_single_query_value(query, "q", max_chars=MAX_CLAIM_CATALOG_TEXT_CHARS),
        limit=limit,
        offset=offset,
    )


def _load_claim_catalog_projection(
    config: ReadApiConfig,
    environ: WSGIEnvironment,
) -> tuple[dict[str, object], str]:
    """Build one deterministic page from verified canonical report artifacts."""
    query = _claim_catalog_query(environ)
    records, scanned = _load_canonical_report_records(
        config, max_receipts=config.max_claim_catalog_receipts
    )
    projection = build_claim_catalog(records, query, scanned_receipts=scanned)
    return projection.to_dict(), projection.digest


def _load_overview_projection(
    config: ReadApiConfig,
) -> tuple[dict[str, object], str]:
    """Build a bounded overview from canonical verification-report receipts."""
    try:
        catalog_records, _ = _load_canonical_report_records(
            config, max_receipts=config.max_overview_receipts
        )
    except ClaimCatalogTooLargeError as exc:
        raise OverflowError(
            "workspace receipt count exceeds overview scan limit"
        ) from exc
    records = tuple(
        OverviewReportRecord(report=item.report, source=item.source)
        for item in catalog_records
    )
    projection = build_overview(records)
    return projection.to_dict(), projection.digest


def _receipt_integrity(
    config: ReadApiConfig,
    receipt: ExternalEvidenceReceipt,
) -> str:
    """Verify one referenced workspace artifact without exposing its payload."""
    store = ContentAddressedArtifactStore(config.workspace_root / "artifacts")
    try:
        content = store.get(receipt.artifact_digest)
    except FileNotFoundError:
        return "unavailable"
    except ValueError:
        return "invalid"
    if len(content) != receipt.artifact_size:
        return "invalid"
    return "verified"


def _receipt_admission_assurance(
    config: ReadApiConfig,
    receipt_path: Path,
    receipt: ExternalEvidenceReceipt,
) -> tuple[str, str, str | None]:
    """Return artifact integrity, admission status, and admission digest."""
    artifact_status = _receipt_integrity(config, receipt)
    if artifact_status == "unavailable":
        return artifact_status, "unavailable", None
    if artifact_status != "verified":
        return artifact_status, "invalid", None

    artifact_path = (
        config.workspace_root
        / "artifacts"
        / receipt.artifact_digest[:2]
        / receipt.artifact_digest[2:]
    )
    try:
        admission = admit_external_evidence(
            receipt,
            artifact_path=artifact_path,
            receipt_path=receipt_path,
        )
    except FileNotFoundError:
        return "unavailable", "unavailable", None
    except (OSError, TypeError, ValueError):
        return "invalid", "invalid", None
    return "verified", "verified", admission.digest


def _load_evidence_trace_projection(
    config: ReadApiConfig,
    record_id: str,
    report: ReliabilityVerificationReport,
    source: ReportSourceContext,
) -> tuple[dict[str, object], str]:
    """Resolve a bounded evidence trace from canonical reports and receipts."""
    receipt_root = config.workspace_root / "receipts"
    try:
        paths = sorted(path for path in receipt_root.glob("*.json") if path.is_file())
    except OSError as exc:
        raise WorkspaceReadError("workspace receipts are unavailable") from exc

    source_identities = set(report.source_identities)
    artifact_digests = set(report.artifact_digests)
    selected_paths = list(paths[: config.max_evidence_receipts])
    selected_names = {path.name for path in selected_paths}
    for identity in source_identities:
        is_receipt_id = len(identity) == 64 and all(
            char in "0123456789abcdef" for char in identity
        )
        if not is_receipt_id:
            continue
        direct = receipt_root / f"{identity}.json"
        if direct.is_file() and direct.name not in selected_names:
            selected_paths.append(direct)
            selected_names.add(direct.name)

    records: list[EvidenceTraceRecord] = []
    store = JsonEvidenceReceiptStore(receipt_root)
    for path in selected_paths:
        try:
            receipt = store.get(path.stem)
        except (OSError, KeyError, TypeError, ValueError) as exc:
            raise WorkspaceReadError(
                "workspace receipt is unavailable or invalid"
            ) from exc
        if receipt.receipt_id == record_id:
            continue
        relevant = (
            receipt.receipt_id in source_identities
            or (
                receipt.source_event_id is not None
                and receipt.source_event_id in source_identities
            )
            or (receipt.run_id is not None and receipt.run_id in source_identities)
            or receipt.artifact_digest in artifact_digests
        )
        if not relevant:
            continue
        artifact_status, admission_status, admission_digest = (
            _receipt_admission_assurance(config, path, receipt)
        )
        records.append(
            EvidenceTraceRecord(
                record_id=receipt.receipt_id,
                artifact_digest=receipt.artifact_digest,
                artifact_size=receipt.artifact_size,
                producer_id=receipt.producer_id,
                producer_type=receipt.producer_type,
                captured_at=receipt.captured_at.isoformat(),
                source_ref=receipt.source_ref,
                source_event_id=receipt.source_event_id,
                run_id=receipt.run_id,
                receipt_digest=receipt.digest,
                receipt_integrity_status="verified",
                artifact_integrity_status=artifact_status,
                admission_status=admission_status,
                admission_digest=admission_digest,
                producer_authentication_status="not-recorded",
            )
        )

    try:
        projection = build_evidence_trace(
            report,
            source,
            tuple(records),
            records_scanned=len(selected_paths),
            records_available=len(paths),
            scan_complete=len(paths) <= config.max_evidence_receipts,
            max_nodes=config.max_evidence_nodes,
        )
    except OverflowError as exc:
        raise EvidenceTraceTooLargeError(str(exc)) from exc
    return projection.to_dict(), projection.digest


def _single_capture_failure_query_value(
    query: dict[str, list[str]],
    key: str,
) -> str | None:
    """Return one trimmed bounded capture-failure query value."""
    values = query.get(key)
    if values is None:
        return None
    if len(values) != 1:
        raise InvalidCaptureFailureQueryError(
            "duplicate capture failure query parameter"
        )
    value = values[0].strip()
    if not value or len(value) > MAX_CAPTURE_FAILURE_FILTER_CHARS:
        raise InvalidCaptureFailureQueryError(
            "capture failure query value is blank or too long"
        )
    return value


def _capture_failure_query(environ: WSGIEnvironment) -> CaptureFailureQuery:
    """Parse bounded failure-journal filters and pagination."""
    query = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
    if set(query) - {"stage", "error_type", "limit", "offset"}:
        raise InvalidCaptureFailureQueryError(
            "unsupported capture failure query parameter"
        )
    if any(len(values) != 1 for values in query.values()):
        raise InvalidCaptureFailureQueryError(
            "duplicate capture failure query parameter"
        )
    try:
        limit = int(query.get("limit", [str(_DEFAULT_CAPTURE_FAILURE_PAGE_LIMIT)])[0])
        offset = int(query.get("offset", ["0"])[0])
    except ValueError as exc:
        raise InvalidCaptureFailureQueryError(
            "capture failure pagination must be integers"
        ) from exc
    if limit < 1 or limit > MAX_CAPTURE_FAILURE_PAGE_LIMIT or offset < 0:
        raise InvalidCaptureFailureQueryError(
            "capture failure pagination is out of bounds"
        )
    return CaptureFailureQuery(
        stage=_single_capture_failure_query_value(query, "stage"),
        error_type=_single_capture_failure_query_value(query, "error_type"),
        limit=limit,
        offset=offset,
    )


def _load_capture_health_projection(
    config: ReadApiConfig, environ: WSGIEnvironment
) -> tuple[dict[str, object], str]:
    """Build a bounded read-only projection from the configured failure journal."""
    path = config.capture_failure_journal_path
    if path is None:
        raise CaptureFailureSourceNotConfiguredError(
            "native capture failure journal is not configured"
        )
    query = _capture_failure_query(environ)
    try:
        snapshot = read_native_capture_failure_journal_snapshot(
            path,
            max_bytes=config.max_capture_failure_journal_bytes,
            max_records=config.max_capture_failure_records,
        )
        projection = build_capture_health(
            snapshot,
            query,
            read_limit_bytes=config.max_capture_failure_journal_bytes,
            declared_journal_capacity_bytes=(
                config.capture_failure_journal_capacity_bytes
            ),
        )
    except NativeCaptureCapacityError as exc:
        raise CaptureFailureSourceTooLargeError(
            "native capture failure journal exceeds bounded read limits"
        ) from exc
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise InvalidCaptureFailureSourceError(
            "native capture failure journal is invalid"
        ) from exc
    return projection.to_dict(), projection.digest


def _single_security_audit_query_value(
    query: dict[str, list[str]],
    key: str,
) -> str | None:
    """Return one trimmed bounded security-audit query value."""
    values = query.get(key)
    if values is None:
        return None
    if len(values) != 1:
        raise InvalidSecurityAuditQueryError("duplicate security audit query parameter")
    value = values[0].strip()
    if not value or len(value) > MAX_SECURITY_AUDIT_FILTER_CHARS:
        raise InvalidSecurityAuditQueryError(
            "security audit query value is blank or too long"
        )
    return value


def _security_audit_query(environ: WSGIEnvironment) -> SecurityAuditQuery:
    """Parse bounded deployment-security audit filters and pagination."""
    query = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
    if set(query) - {"event", "operation", "reason", "method", "limit", "offset"}:
        raise InvalidSecurityAuditQueryError(
            "unsupported security audit query parameter"
        )
    if any(len(values) != 1 for values in query.values()):
        raise InvalidSecurityAuditQueryError("duplicate security audit query parameter")
    try:
        limit = int(query.get("limit", [str(_DEFAULT_SECURITY_AUDIT_PAGE_LIMIT)])[0])
        offset = int(query.get("offset", ["0"])[0])
    except ValueError as exc:
        raise InvalidSecurityAuditQueryError(
            "security audit pagination must be integers"
        ) from exc
    if limit < 1 or limit > MAX_SECURITY_AUDIT_PAGE_LIMIT or offset < 0:
        raise InvalidSecurityAuditQueryError(
            "security audit pagination is out of bounds"
        )
    try:
        return SecurityAuditQuery(
            event=_single_security_audit_query_value(query, "event"),
            operation=_single_security_audit_query_value(query, "operation"),
            reason=_single_security_audit_query_value(query, "reason"),
            method=_single_security_audit_query_value(query, "method"),
            limit=limit,
            offset=offset,
        )
    except ValueError as exc:
        raise InvalidSecurityAuditQueryError(str(exc)) from exc


def _load_security_assurance_projection(
    config: ReadApiConfig,
    environ: WSGIEnvironment,
) -> tuple[dict[str, object], str]:
    """Build one bounded deployment-security and runtime-containment projection."""
    audit_path = config.security_audit_path
    runtime_path = config.runtime_containment_snapshot_path
    if audit_path is None and runtime_path is None:
        raise SecurityAuditSourceNotConfiguredError(
            "security audit and runtime-containment sources are not configured"
        )
    query = _security_audit_query(environ)
    try:
        audit_snapshot = (
            read_security_audit_snapshot(
                audit_path,
                max_bytes=config.max_security_audit_bytes,
                max_records=config.max_security_audit_records,
            )
            if audit_path is not None
            else SecurityAuditSnapshot(records=(), exists=False, byte_size=0)
        )
    except OverflowError as exc:
        raise SecurityAuditSourceTooLargeError(
            "deployment security audit exceeds bounded read limits"
        ) from exc
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        raise InvalidSecurityAuditSourceError(
            "deployment security audit source is invalid"
        ) from exc

    runtime_snapshot = None
    if runtime_path is not None:
        try:
            runtime_snapshot = load_runtime_containment_snapshot(
                runtime_path,
                max_bytes=config.max_runtime_containment_snapshot_bytes,
            )
        except OverflowError as exc:
            raise RuntimeContainmentSnapshotTooLargeError(
                "runtime containment snapshot exceeds bounded read limits"
            ) from exc
        except (
            OSError,
            UnicodeError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise InvalidRuntimeContainmentSnapshotError(
                "runtime containment snapshot is invalid"
            ) from exc

    projection = build_security_assurance_projection(
        audit_snapshot,
        query,
        read_limit_bytes=config.max_security_audit_bytes,
        record_limit=config.max_security_audit_records,
        audit_configured=audit_path is not None,
        runtime_snapshot=runtime_snapshot,
    )
    return projection.to_dict(), projection.digest


def _single_attestation_trust_query_value(
    query: dict[str, list[str]],
    key: str,
    *,
    max_chars: int,
) -> str | None:
    """Return one trimmed bounded attestation-trust query value."""
    values = query.get(key)
    if values is None:
        return None
    if len(values) != 1:
        raise InvalidAttestationTrustQueryError(
            "duplicate attestation trust query parameter"
        )
    value = values[0].strip()
    if not value or len(value) > max_chars:
        raise InvalidAttestationTrustQueryError(
            "attestation trust query value is blank or too long"
        )
    return value


def _attestation_trust_query(environ: WSGIEnvironment) -> AttestationTrustQuery:
    """Parse the allowlisted bounded attestation trust filters and pagination."""
    query = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
    allowed = {"decision", "reliability_state", "key_status", "q", "limit", "offset"}
    if any(key not in allowed for key in query):
        raise InvalidAttestationTrustQueryError(
            "unsupported attestation trust query parameter"
        )
    if any(len(values) != 1 for values in query.values()):
        raise InvalidAttestationTrustQueryError(
            "duplicate attestation trust query parameter"
        )
    try:
        limit = int(query.get("limit", [str(_DEFAULT_ATTESTATION_TRUST_PAGE_LIMIT)])[0])
        offset = int(query.get("offset", ["0"])[0])
    except ValueError as exc:
        raise InvalidAttestationTrustQueryError(
            "attestation trust pagination must be integers"
        ) from exc
    if limit < 1 or limit > MAX_ATTESTATION_TRUST_PAGE_LIMIT or offset < 0:
        raise InvalidAttestationTrustQueryError(
            "attestation trust pagination is out of bounds"
        )
    key_status = _single_attestation_trust_query_value(
        query,
        "key_status",
        max_chars=MAX_ATTESTATION_TRUST_FILTER_CHARS,
    )
    if key_status is not None and key_status not in ATTESTATION_KEY_STATUSES:
        raise InvalidAttestationTrustQueryError(
            "unsupported attestation key-status filter"
        )
    try:
        return AttestationTrustQuery(
            decision=_single_attestation_trust_query_value(
                query,
                "decision",
                max_chars=MAX_ATTESTATION_TRUST_FILTER_CHARS,
            ),
            reliability_state=_single_attestation_trust_query_value(
                query,
                "reliability_state",
                max_chars=MAX_ATTESTATION_TRUST_FILTER_CHARS,
            ),
            key_status=key_status,
            text=_single_attestation_trust_query_value(
                query,
                "q",
                max_chars=MAX_ATTESTATION_TRUST_TEXT_CHARS,
            ),
            limit=limit,
            offset=offset,
        )
    except ValueError as exc:
        raise InvalidAttestationTrustQueryError(str(exc)) from exc


def _read_bounded_json_object(
    path: Path,
    *,
    max_bytes: int,
    field: str,
) -> dict[str, Any]:
    """Read one strict bounded JSON object without following symlink paths."""
    if max_bytes <= 0:
        raise ValueError("bounded JSON read limit must be positive")
    if path.is_symlink() or any(parent.is_symlink() for parent in path.parents):
        raise ValueError(f"{field} path cannot traverse a symlink")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    try:
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(fd, min(65_536, max_bytes + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > max_bytes:
                raise OverflowError(f"{field} exceeds configured read limit")
        raw = b"".join(chunks)
    finally:
        os.close(fd)
    return dict(loads_object(raw, field=field))


def _decision_source_path(root: Path, source: str) -> Path:
    """Resolve one decision/lineage source inside its configured evidence root."""
    normalized = source.replace("\\", "/")
    raw = root / normalized
    if raw.is_symlink() or any(parent.is_symlink() for parent in raw.parents):
        raise ValueError("decision/lineage source cannot traverse a symlink")
    candidate = raw.resolve()
    resolved_root = root.resolve()
    if candidate != resolved_root and resolved_root not in candidate.parents:
        raise ValueError("decision/lineage source escapes configured evidence root")
    if not candidate.is_file():
        raise FileNotFoundError(candidate)
    return candidate


def _preflight_decision_sources(
    chain: ReliabilityEvidenceChain,
    *,
    root: Path,
    max_total_bytes: int,
) -> None:
    """Bound every local source the decision/lineage verifiers may read."""
    seen: set[Path] = set()
    total = 0

    def check_source(source: str) -> Path:
        """Validate one unique source and account for its bounded byte size."""
        nonlocal total
        candidate = _decision_source_path(root, source)
        if candidate not in seen:
            seen.add(candidate)
            total += candidate.stat().st_size
            if total > max_total_bytes:
                raise OverflowError(
                    "decision/lineage sources exceed configured aggregate read limit"
                )
        return candidate

    def check_reference(reference: EvidenceReference | None) -> None:
        """Preflight one evidence reference and its optional receipt binding."""
        if reference is None:
            return
        if reference.source is not None:
            check_source(reference.source)
        if reference.receipt_ref is not None:
            check_reference(reference.receipt_ref)

    references = (
        chain.run,
        chain.state,
        *chain.evidence,
        chain.provenance,
        chain.integrity,
        chain.reconciliation_ref,
        chain.recovery_ref,
        chain.attestation_ref,
        chain.decision_basis_ref,
        chain.comparison_ref,
        chain.reconciliation_binding_ref,
    )
    for reference in references:
        check_reference(reference)

    if chain.comparison_ref is not None and chain.comparison_ref.source is not None:
        comparison = load_reliability_behavioral_comparison(
            check_source(chain.comparison_ref.source)
        )
        for item in (*comparison.before, *comparison.after):
            check_source(item.source)

    if chain.provenance.source is not None:
        graph = load_provenance_graph(check_source(chain.provenance.source))
        for node in graph.nodes:
            if node.path is not None:
                check_source(node.path)


def _load_decision_lineage_projection(
    config: ReadApiConfig,
) -> tuple[dict[str, object], str]:
    """Verify and project one configured decision/reconciliation/lineage chain."""
    path = config.reliability_decision_chain_path
    if path is None:
        raise DecisionLineageSourceNotConfiguredError(
            "reliability decision chain is not configured"
        )
    try:
        payload = _read_bounded_json_object(
            path,
            max_bytes=config.max_decision_chain_bytes,
            field="reliability decision chain",
        )
        chain = ReliabilityEvidenceChain.from_dict(payload)
        root = path.parent.resolve()
        _preflight_decision_sources(
            chain,
            root=root,
            max_total_bytes=config.max_decision_source_bytes,
        )
        verify_reliability_evidence_chain(chain, root=root)
        lineage = build_reliability_lineage_closure(chain, root=root)

        basis = None
        if chain.decision_basis_ref is not None:
            if chain.decision_basis_ref.source is None:
                raise ValueError("decision basis reference lacks a local source")
            basis = load_reliability_decision_basis(
                _decision_source_path(root, chain.decision_basis_ref.source)
            )

        comparison = None
        if chain.comparison_ref is not None:
            if chain.comparison_ref.source is None:
                raise ValueError("comparison reference lacks a local source")
            comparison = load_reliability_behavioral_comparison(
                _decision_source_path(root, chain.comparison_ref.source)
            )

        reconciliation_binding = None
        if chain.reconciliation_binding_ref is not None:
            if chain.reconciliation_binding_ref.source is None:
                raise ValueError("reconciliation binding lacks a local source")
            reconciliation_binding = load_reliability_reconciliation_binding(
                _decision_source_path(root, chain.reconciliation_binding_ref.source)
            )

        recovery = None
        if chain.reliability_state == "recovered":
            recovery = verify_reliability_recovery_outcome(chain, root=root)

        projection = build_decision_lineage_investigation(
            chain,
            lineage,
            basis=basis,
            comparison=comparison,
            reconciliation_binding=reconciliation_binding,
            recovery=recovery,
        )
    except FileNotFoundError:
        raise
    except OverflowError as exc:
        raise DecisionLineageSourceTooLargeError(str(exc)) from exc
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        raise InvalidDecisionLineageSourceError(
            "configured reliability decision/lineage evidence could not be verified"
        ) from exc
    return projection.to_dict(), projection.digest


def _attestation_trust_authentication(
    state: SignedAttestationTrustState | None,
    authority_store: dict[str, bytes] | None,
) -> AttestationTrustAuthentication:
    """Authenticate one current trust-state snapshot when an authority is available."""
    if state is None:
        return AttestationTrustAuthentication(
            "not-configured",
            None,
            "No attestation trust-state snapshot is configured.",
        )
    if authority_store is None:
        return AttestationTrustAuthentication(
            "not-configured",
            None,
            "The trust-state snapshot is structurally valid but no authority store is configured for independent authentication.",
        )
    authority_key = authority_store.get(state.authority_key_id)
    authority_digest = (
        None if authority_key is None else sha256(authority_key).hexdigest()
    )
    try:
        Ed25519AttestationTrustStateVerifier(authority_store).verify(state)
    except RuntimeError:
        return AttestationTrustAuthentication(
            "dependency-unavailable",
            None,
            "Ed25519 trust-state authentication is unavailable because the declared cryptographic dependency is not importable.",
            authority_digest,
        )
    except ValueError:
        return AttestationTrustAuthentication(
            "failed",
            False,
            "The configured attestation trust-state signature did not authenticate against the configured authority store.",
            authority_digest,
        )
    return AttestationTrustAuthentication(
        "verified",
        True,
        "The current attestation trust-state snapshot authenticated against the configured authority store.",
        authority_digest,
    )


def _signed_binding_authentication(
    snapshot: ReliabilityAttestationSnapshot | None,
    state: SignedAttestationTrustState | None,
    trust_history: AttestationTrustHistorySnapshot | None,
    authority_store: dict[str, bytes] | None,
) -> dict[str, SignedAttestationBindingAuthentication]:
    """Verify each recorded signed binding against its exact authenticated trust state."""
    if snapshot is None or not snapshot.signed_bindings:
        return {}
    states: list[SignedAttestationTrustState] = []
    if trust_history is not None:
        states.extend(trust_history.records)
    if state is not None:
        if all(
            existing.version != state.version or existing.digest() != state.digest()
            for existing in states
        ):
            states.append(state)

    results: dict[str, SignedAttestationBindingAuthentication] = {}
    for binding in snapshot.signed_bindings:
        attestation_id = binding.attestation.attestation_id
        try:
            exact_state = resolve_reliability_attestation_trust_state(
                binding,
                trust_states=states,
            )
        except ValueError as exc:
            if "trust state is unavailable" not in str(exc):
                raise
            results[attestation_id] = SignedAttestationBindingAuthentication(
                "trust-state-unavailable",
                None,
                "The canonical signed binding references a trust-state version/digest that is not available in the configured current state or history.",
            )
            continue
        if authority_store is None:
            results[attestation_id] = SignedAttestationBindingAuthentication(
                "authority-not-configured",
                None,
                "The canonical signed binding is recorded, but the independent authority store required to authenticate its trust state is not configured.",
            )
            continue
        try:
            verified = verify_reliability_attestation_trust_context(
                binding,
                trust_state=exact_state,
                authority_store=authority_store,
            )
        except RuntimeError:
            results[attestation_id] = SignedAttestationBindingAuthentication(
                "dependency-unavailable",
                None,
                "The canonical signed binding could not be cryptographically verified because the declared Ed25519 verification dependency is unavailable.",
            )
            continue
        if verified.attestation_id != attestation_id:
            raise ValueError("verified signed attestation identity mismatch")
        results[attestation_id] = SignedAttestationBindingAuthentication(
            "verified",
            True,
            "The signed envelope and exact bound trust-state snapshot authenticated against the configured authority store.",
        )
    return results


def _load_attestation_trust_projection(
    config: ReadApiConfig,
    environ: WSGIEnvironment,
) -> tuple[dict[str, object], str]:
    """Build one bounded attestation trust and key-lifecycle investigation page."""
    if (
        config.attestation_store_path is None
        and config.attestation_trust_state_path is None
        and config.attestation_trust_history_path is None
        and config.attestation_authority_store_path is None
    ):
        raise AttestationTrustSourceNotConfiguredError(
            "attestation trust sources are not configured"
        )
    query = _attestation_trust_query(environ)
    snapshot = None
    state = None
    trust_history = None
    trust_state_from_history = False
    history_authenticated: bool | None = None
    history_authentication_status: str | None = None
    authority_store = None
    try:
        if config.attestation_store_path is not None:
            snapshot = read_reliability_attestation_snapshot(
                config.attestation_store_path,
                max_bytes=config.max_attestation_store_bytes,
                max_records=config.max_attestation_records,
            )
        if config.attestation_trust_state_path is not None:
            trust_payload = _read_bounded_json_object(
                config.attestation_trust_state_path,
                max_bytes=config.max_attestation_trust_state_bytes,
                field="attestation trust state",
            )
            state = SignedAttestationTrustState.from_dict(trust_payload)
        if config.attestation_trust_history_path is not None:
            trust_history = read_attestation_trust_history_snapshot(
                config.attestation_trust_history_path,
                max_bytes=config.max_attestation_trust_history_bytes,
                max_records=config.max_attestation_trust_history_records,
            )
        if config.attestation_authority_store_path is not None:
            authority_payload = _read_bounded_json_object(
                config.attestation_authority_store_path,
                max_bytes=config.max_attestation_authority_store_bytes,
                field="attestation authority store",
            )
            authority_store = authority_store_from_dict(authority_payload)
        if trust_history is not None and trust_history.records:
            tip = trust_history.records[-1]
            if authority_store is not None:
                verifier = Ed25519AttestationTrustStateVerifier(authority_store)
                try:
                    for historical_state in trust_history.records:
                        verifier.verify(historical_state)
                except RuntimeError:
                    history_authentication_status = "dependency-unavailable"
                else:
                    history_authenticated = True
                    history_authentication_status = "verified"
            if state is None:
                state = tip
                trust_state_from_history = True
            elif state.digest() != tip.digest():
                raise ValueError(
                    "current attestation trust state does not match trust history tip"
                )
        authentication = _attestation_trust_authentication(state, authority_store)
        signed_binding_authentication = _signed_binding_authentication(
            snapshot, state, trust_history, authority_store
        )
        projection = build_attestation_trust_projection(
            snapshot,
            state,
            authentication,
            query,
            trust_history,
            history_authenticated,
            attestation_configured=config.attestation_store_path is not None,
            attestation_read_limit_bytes=config.max_attestation_store_bytes,
            attestation_record_limit=config.max_attestation_records,
            trust_state_configured=config.attestation_trust_state_path is not None,
            authority_store_configured=(
                config.attestation_authority_store_path is not None
            ),
            trust_history_configured=(
                config.attestation_trust_history_path is not None
            ),
            trust_history_read_limit_bytes=config.max_attestation_trust_history_bytes,
            trust_history_record_limit=config.max_attestation_trust_history_records,
            trust_state_from_history=trust_state_from_history,
            trust_history_authentication_status=history_authentication_status,
            signed_binding_authentication=signed_binding_authentication,
        )
    except OverflowError as exc:
        raise AttestationTrustSourceTooLargeError(
            "attestation trust source exceeds bounded read limits"
        ) from exc
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        raise InvalidAttestationTrustSourceError(
            "configured attestation trust evidence is invalid"
        ) from exc
    return projection.to_dict(), projection.digest


def _single_incident_query_value(
    query: dict[str, list[str]],
    key: str,
    *,
    max_chars: int,
) -> str | None:
    """Return one trimmed bounded incident query value."""
    values = query.get(key)
    if values is None:
        return None
    if len(values) != 1:
        raise InvalidIncidentQueryError("duplicate incident query parameter")
    value = values[0].strip()
    if not value or len(value) > max_chars:
        raise InvalidIncidentQueryError("incident query value is blank or too long")
    return value


def _incident_query(environ: WSGIEnvironment) -> IncidentInvestigationQuery:
    """Parse bounded incident portfolio filters and pagination."""
    query = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
    allowed = {"status", "category", "q", "limit", "offset"}
    if any(key not in allowed for key in query):
        raise InvalidIncidentQueryError("unsupported incident query parameter")
    if any(len(values) != 1 for values in query.values()):
        raise InvalidIncidentQueryError("duplicate incident query parameter")
    status = _single_incident_query_value(
        query, "status", max_chars=MAX_INCIDENT_FILTER_CHARS
    )
    if status is not None and status not in INCIDENT_STATUSES:
        raise InvalidIncidentQueryError("unsupported incident status")
    limit_raw = query.get("limit", [str(_DEFAULT_INCIDENT_PAGE_LIMIT)])[0]
    offset_raw = query.get("offset", ["0"])[0]
    if not limit_raw.isdigit() or not offset_raw.isdigit():
        raise InvalidIncidentQueryError("incident pagination must be integers")
    limit = int(limit_raw)
    offset = int(offset_raw)
    if limit < 1 or limit > MAX_INCIDENT_PAGE_LIMIT or offset < 0:
        raise InvalidIncidentQueryError("incident pagination is out of bounds")
    return IncidentInvestigationQuery(
        status=status,
        category=_single_incident_query_value(
            query, "category", max_chars=MAX_INCIDENT_FILTER_CHARS
        ),
        text=_single_incident_query_value(
            query, "q", max_chars=MAX_INCIDENT_TEXT_CHARS
        ),
        limit=limit,
        offset=offset,
    )


def _incident_records(
    config: ReadApiConfig,
) -> tuple[StoredIncidentRecord, ...]:
    """Read the configured incident evidence chain without mutating its store."""
    path = config.incident_evidence_path
    if path is None:
        raise IncidentSourceNotConfiguredError("incident evidence is not configured")
    try:
        return read_incident_evidence_snapshot(
            path,
            max_bytes=config.max_incident_evidence_bytes,
            max_records=config.max_incident_records,
        )
    except FileNotFoundError:
        raise
    except OverflowError as exc:
        raise IncidentSourceTooLargeError(str(exc)) from exc
    except (OSError, UnicodeError, KeyError, TypeError, ValueError) as exc:
        raise InvalidIncidentSourceError("incident evidence source is invalid") from exc


def _load_incident_investigation_projection(
    config: ReadApiConfig, environ: WSGIEnvironment
) -> tuple[dict[str, object], str]:
    """Build one incident portfolio page from the verified configured chain."""
    projection = build_incident_investigation(
        _incident_records(config), _incident_query(environ)
    )
    return projection.to_dict(), projection.digest


def _load_incident_detail_projection(
    config: ReadApiConfig, incident_id: str
) -> tuple[dict[str, object], str]:
    """Build one detailed incident reconstruction from the verified chain."""
    projection = build_incident_detail(_incident_records(config), incident_id)
    return projection.to_dict(), projection.digest


def _load_reliability_proof_projection(
    config: ReadApiConfig,
) -> tuple[dict[str, object], str]:
    """Verify and project one configured portable reliability proof bundle."""
    path = config.reliability_proof_path
    if path is None:
        raise ReliabilityProofSourceNotConfiguredError(
            "reliability proof bundle is not configured"
        )
    try:
        if path.is_symlink():
            raise InvalidReliabilityProofSourceError(
                "reliability proof source cannot be a symlink"
            )
        size = path.stat().st_size
        if size > config.max_reliability_proof_bytes:
            raise ReliabilityProofSourceTooLargeError(
                "reliability proof bundle exceeds configured read limit"
            )
        bundle = verify_bundle(path)
        report, descriptor = verify_reliability_proof_bundle(path)
        projection = build_reliability_proof_investigation(bundle, report, descriptor)
    except FileNotFoundError:
        raise
    except ReliabilityProofSourceTooLargeError:
        raise
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise InvalidReliabilityProofSourceError(
            "configured reliability proof bundle could not be verified"
        ) from exc
    return projection.to_dict(), projection.digest


def _load_release_trust_projection(
    config: ReadApiConfig,
) -> tuple[dict[str, object], str]:
    """Load one configured release-trust bundle and optional byte verification."""
    path = config.release_bundle_path
    if path is None:
        raise OperationalSourceNotConfiguredError("release trust is not configured")
    try:
        if path.stat().st_size > config.max_release_bundle_bytes:
            raise OperationalSourceTooLargeError(
                "release trust bundle exceeds configured read limit"
            )
        bundle = load_release_trust_bundle(path)
        content = (
            verify_release_trust_files(bundle, config.release_root)
            if config.release_root is not None
            else None
        )
        publication = None
        if (
            config.publication_basis_path is not None
            and config.publication_approval_workspace is not None
            and config.publication_expected_producer_id is not None
        ):
            basis = load_release_publication_basis(config.publication_basis_path)
            if (
                basis.distribution != bundle.source.distribution
                or basis.version != bundle.source.version
                or basis.source_revision != bundle.source.source_revision
                or basis.source_tree_sha256 != bundle.source.source_tree_sha256
            ):
                raise ValueError(
                    "publication authorization basis does not match release trust source identity"
                )
            if (
                basis.release_bundle_digest is not None
                and basis.release_bundle_digest != bundle.digest
            ):
                raise ValueError(
                    "publication authorization basis does not match release trust bundle"
                )
            publication = resolve_publication_authorization(
                WorkspaceHumanApprovalStore(config.publication_approval_workspace),
                basis,
                expected_producer_id=config.publication_expected_producer_id,
            )
        registry_publication = None
        registry_lifecycle: tuple[RegistryPublicationLifecycleObservation, ...] = ()
        if (
            config.publication_permit_path is not None
            and config.publication_registry_receipt_path is not None
        ):
            if publication is None:
                raise ValueError(
                    "registry publication receipt requires publication authority context"
                )
            permit = load_publication_execution_permit(config.publication_permit_path)
            receipt = load_registry_publication_receipt(
                config.publication_registry_receipt_path
            )
            verify_registry_publication_receipt(receipt, basis, permit)
            registry_publication = receipt
            if config.publication_registry_lifecycle_path is not None:
                registry_lifecycle = RegistryPublicationLifecycleStore(
                    config.publication_registry_lifecycle_path
                ).read(receipt, basis, permit)
        projection = build_release_trust_projection(
            bundle,
            content=content,
            publication=publication,
            registry_publication=registry_publication,
            registry_lifecycle=registry_lifecycle,
        )
    except FileNotFoundError:
        raise
    except OperationalSourceTooLargeError:
        raise
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise InvalidOperationalSourceError("release trust bundle is invalid") from exc
    return projection.to_dict(), projection.digest


def _load_validation_study_projection(
    config: ReadApiConfig,
) -> tuple[dict[str, object], str]:
    """Load one frozen comparative study without executing a benchmark."""
    path = config.validation_study_path
    if path is None:
        raise OperationalSourceNotConfiguredError("validation study is not configured")
    try:
        study = load_study_report(path, max_bytes=config.max_validation_study_bytes)
        projection = build_validation_study_projection(study)
    except FileNotFoundError:
        raise
    except OverflowError as exc:
        raise OperationalSourceTooLargeError(
            "validation study exceeds configured read limit"
        ) from exc
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise InvalidOperationalSourceError("validation study is invalid") from exc
    return projection.to_dict(), projection.digest


def _workspace_page(environ: WSGIEnvironment) -> tuple[int, int]:
    """Parse bounded workspace pagination without arbitrary query syntax."""
    query = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
    if any(key not in {"limit", "offset"} for key in query):
        raise InvalidWorkspaceQueryError("unsupported workspace query parameter")
    if any(len(values) != 1 for values in query.values()):
        raise InvalidWorkspaceQueryError("duplicate workspace query parameter")
    try:
        limit = int(query.get("limit", [str(_DEFAULT_WORKSPACE_PAGE_LIMIT)])[0])
        offset = int(query.get("offset", ["0"])[0])
    except (TypeError, ValueError) as exc:
        raise InvalidWorkspaceQueryError(
            "workspace pagination must be integers"
        ) from exc
    if limit < 1 or limit > _MAX_WORKSPACE_PAGE_LIMIT or offset < 0:
        raise InvalidWorkspaceQueryError("workspace pagination is out of bounds")
    return limit, offset


def _load_workspace_operations_projection(
    config: ReadApiConfig,
    environ: WSGIEnvironment,
) -> tuple[dict[str, object], str]:
    """Inspect an existing workspace through a read-only SQLite handle."""
    limit, offset = _workspace_page(environ)
    try:
        with StateWakeWorkspace.open_read_only(config.workspace_root) as workspace:
            projection = build_workspace_operations_projection(
                workspace, limit=limit, offset=offset
            )
    except (OSError, ValueError, WorkspaceError, WorkspaceRepositoryError) as exc:
        raise WorkspaceReadError("workspace operations could not be read") from exc
    return projection.to_dict(), projection.digest


def _etag_matches(environ: WSGIEnvironment, digest: str) -> bool:
    """Return whether the request explicitly names the current immutable digest."""
    supplied = str(environ.get("HTTP_IF_NONE_MATCH", "")).strip()
    return supplied in {digest, f'"{digest}"'}


def _projection_digest(payload: dict[str, object]) -> str:
    """Return a deterministic digest for one read-only JSON projection."""
    return sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _load_assurance_decision_projection(
    config: ReadApiConfig,
) -> tuple[dict[str, object], str]:
    """Load and replay-verify the configured assurance decision context."""
    if config.assurance_decision_path is None:
        raise AssuranceDecisionSourceNotConfiguredError
    try:
        decision = load_assurance_decision(
            config.assurance_decision_path,
            max_bytes=config.max_assurance_decision_bytes,
        )
        exception = (
            None
            if config.assurance_exception_path is None
            else load_assurance_exception(
                config.assurance_exception_path,
                max_bytes=config.max_assurance_exception_bytes,
            )
        )
        projection = AssuranceDecisionProjection(
            decision=decision,
            exception=exception,
            evaluated_at=datetime.now(UTC),
        )
        payload = projection.to_dict()
    except OverflowError as exc:
        raise AssuranceDecisionSourceTooLargeError from exc
    except (OSError, ValueError) as exc:
        raise InvalidAssuranceDecisionSourceError from exc
    return payload, _projection_digest(payload)


def _load_authorization_policy_projection(
    config: ReadApiConfig,
) -> tuple[dict[str, object], str]:
    """Load and replay one explicitly configured authorization context."""
    if config.authorization_context_path is None:
        raise AuthorizationContextSourceNotConfiguredError
    try:
        context = load_authorization_context(
            config.authorization_context_path,
            max_bytes=config.max_authorization_context_bytes,
        )
        payload = AccessAuthorizationProjection(context).to_dict()
    except OverflowError as exc:
        raise AuthorizationContextSourceTooLargeError from exc
    except (OSError, ValueError) as exc:
        raise InvalidAuthorizationContextSourceError from exc
    return payload, _projection_digest(payload)


def _load_data_governance_projection(
    config: ReadApiConfig,
    environ: WSGIEnvironment,
) -> tuple[dict[str, object], str]:
    """Load lifecycle policy context and cross-check durable workspace state."""
    if str(environ.get("QUERY_STRING", "")).strip():
        raise InvalidDataGovernanceQueryError
    if config.data_lifecycle_context_path is None:
        raise DataGovernanceSourceNotConfiguredError
    try:
        context = load_data_lifecycle_context(
            config.data_lifecycle_context_path,
            max_bytes=config.max_data_lifecycle_context_bytes,
        )
        evaluated_at = datetime.now(UTC)
        with StateWakeWorkspace.open_read_only(config.workspace_root) as workspace:
            resolved = resolve_data_lifecycle_context(
                context,
                workspace,
                evaluated_at=evaluated_at,
            )
        privacy_governance = None
        if config.privacy_governance_snapshot_path is not None:
            privacy_governance = load_privacy_governance_runtime_snapshot(
                config.privacy_governance_snapshot_path,
                max_bytes=config.max_privacy_governance_snapshot_bytes,
            )
        payload = DataGovernanceProjection(
            resolved, privacy_governance=privacy_governance
        ).to_dict()
    except OverflowError as exc:
        raise DataGovernanceSourceTooLargeError from exc
    except (OSError, ValueError, WorkspaceError, WorkspaceRepositoryError) as exc:
        raise InvalidDataGovernanceSourceError from exc
    return payload, _projection_digest(payload)


def create_read_application(config: ReadApiConfig | None = None) -> WSGIApplication:
    """Create the optional local read-only application API."""
    cfg = config or ReadApiConfig.from_environment()

    def application(
        environ: WSGIEnvironment,
        start_response: StartResponse,
    ) -> list[bytes]:
        """Handle one bounded read request."""
        method = str(environ.get("REQUEST_METHOD", "GET")).upper()
        path = str(environ.get("PATH_INFO", "/"))
        if method != "GET":
            return _error(
                start_response,
                "405 Method Not Allowed",
                "READ_ONLY",
                "this API surface is read-only",
            )

        try:
            if path == "/api/v1/capabilities":
                identity = _workspace_identity(cfg.workspace_root)
                return _json_response(
                    start_response,
                    "200 OK",
                    {
                        "schema_version": _CAPABILITIES_SCHEMA_VERSION,
                        "mode": "local-read-only",
                        "statewake_version": __version__,
                        "workspace": identity,
                        "features": {
                            "claim_detail": True,
                            "claim_summary": True,
                            "canonical_json": True,
                            "canonical_markdown": True,
                            "claim_list": True,
                            "overview_aggregates": True,
                            "history_read": cfg.history_path is not None,
                            "comparison_read": True,
                            "evidence_trace": True,
                            "review_read": False,
                            "review_write": False,
                            "approval_write": False,
                            "release_trust_read": cfg.release_bundle_path is not None,
                            "publication_authorization_read": (
                                cfg.publication_basis_path is not None
                            ),
                            "reliability_proof_read": (
                                cfg.reliability_proof_path is not None
                            ),
                            "decision_lineage_read": (
                                cfg.reliability_decision_chain_path is not None
                            ),
                            "validation_study_read": cfg.validation_study_path
                            is not None,
                            "workspace_operations_read": True,
                            "incident_investigation_read": cfg.incident_evidence_path
                            is not None,
                            "capture_health_read": cfg.capture_failure_journal_path
                            is not None,
                            "security_assurance_read": any(
                                value is not None
                                for value in (
                                    cfg.security_audit_path,
                                    cfg.runtime_containment_snapshot_path,
                                )
                            ),
                            "assurance_decision_read": cfg.assurance_decision_path
                            is not None,
                            "authorization_policy_read": cfg.authorization_context_path
                            is not None,
                            "data_governance_read": cfg.data_lifecycle_context_path
                            is not None,
                            "attestation_trust_read": any(
                                value is not None
                                for value in (
                                    cfg.attestation_store_path,
                                    cfg.attestation_trust_state_path,
                                    cfg.attestation_trust_history_path,
                                    cfg.attestation_authority_store_path,
                                )
                            ),
                        },
                    },
                )

            if path == "/api/v1/assurance-decision":
                payload, digest = _load_assurance_decision_projection(cfg)
                if _etag_matches(environ, digest):
                    return _empty_response(
                        start_response, "304 Not Modified", etag=digest
                    )
                return _json_response(start_response, "200 OK", payload, etag=digest)

            if path == "/api/v1/authorization-policy":
                payload, digest = _load_authorization_policy_projection(cfg)
                if _etag_matches(environ, digest):
                    return _empty_response(
                        start_response, "304 Not Modified", etag=digest
                    )
                return _json_response(start_response, "200 OK", payload, etag=digest)

            if path == "/api/v1/data-governance":
                payload, digest = _load_data_governance_projection(cfg, environ)
                if _etag_matches(environ, digest):
                    return _empty_response(
                        start_response, "304 Not Modified", etag=digest
                    )
                return _json_response(start_response, "200 OK", payload, etag=digest)

            if path == "/api/v1/security-assurance":
                payload, digest = _load_security_assurance_projection(cfg, environ)
                if _etag_matches(environ, digest):
                    return _empty_response(
                        start_response, "304 Not Modified", etag=digest
                    )
                return _json_response(start_response, "200 OK", payload, etag=digest)

            if path == "/api/v1/attestation-trust":
                payload, digest = _load_attestation_trust_projection(cfg, environ)
                if _etag_matches(environ, digest):
                    return _empty_response(
                        start_response, "304 Not Modified", etag=digest
                    )
                return _json_response(start_response, "200 OK", payload, etag=digest)

            if path == "/api/v1/capture-health":
                payload, digest = _load_capture_health_projection(cfg, environ)
                if _etag_matches(environ, digest):
                    return _empty_response(
                        start_response, "304 Not Modified", etag=digest
                    )
                return _json_response(start_response, "200 OK", payload, etag=digest)

            if path == "/api/v1/incidents":
                payload, digest = _load_incident_investigation_projection(cfg, environ)
                if _etag_matches(environ, digest):
                    return _empty_response(
                        start_response, "304 Not Modified", etag=digest
                    )
                return _json_response(start_response, "200 OK", payload, etag=digest)

            incident_id = _incident_id_from_path(path)
            if incident_id is not None:
                payload, digest = _load_incident_detail_projection(cfg, incident_id)
                if _etag_matches(environ, digest):
                    return _empty_response(
                        start_response, "304 Not Modified", etag=digest
                    )
                return _json_response(start_response, "200 OK", payload, etag=digest)

            if path == "/api/v1/claims":
                payload, digest = _load_claim_catalog_projection(cfg, environ)
                if _etag_matches(environ, digest):
                    return _empty_response(
                        start_response, "304 Not Modified", etag=digest
                    )
                return _json_response(start_response, "200 OK", payload, etag=digest)

            if path == "/api/v1/overview":
                overview, overview_digest = _load_overview_projection(cfg)
                if _etag_matches(environ, overview_digest):
                    return _empty_response(
                        start_response, "304 Not Modified", etag=overview_digest
                    )
                return _json_response(
                    start_response, "200 OK", overview, etag=overview_digest
                )

            if path == "/api/v1/proof-bundle":
                payload, digest = _load_reliability_proof_projection(cfg)
                if _etag_matches(environ, digest):
                    return _empty_response(
                        start_response, "304 Not Modified", etag=digest
                    )
                return _json_response(start_response, "200 OK", payload, etag=digest)

            if path == "/api/v1/decision-lineage":
                payload, digest = _load_decision_lineage_projection(cfg)
                if _etag_matches(environ, digest):
                    return _empty_response(
                        start_response, "304 Not Modified", etag=digest
                    )
                return _json_response(start_response, "200 OK", payload, etag=digest)

            if path == "/api/v1/release-trust":
                payload, digest = _load_release_trust_projection(cfg)
                if _etag_matches(environ, digest):
                    return _empty_response(
                        start_response, "304 Not Modified", etag=digest
                    )
                return _json_response(start_response, "200 OK", payload, etag=digest)

            if path == "/api/v1/validation-study":
                payload, digest = _load_validation_study_projection(cfg)
                if _etag_matches(environ, digest):
                    return _empty_response(
                        start_response, "304 Not Modified", etag=digest
                    )
                return _json_response(start_response, "200 OK", payload, etag=digest)

            if path == "/api/v1/workspace/operations":
                payload, digest = _load_workspace_operations_projection(cfg, environ)
                if _etag_matches(environ, digest):
                    return _empty_response(
                        start_response, "304 Not Modified", etag=digest
                    )
                return _json_response(start_response, "200 OK", payload, etag=digest)

            comparison_ids = _comparison_ids_from_path(path)
            if comparison_ids is not None:
                left_id, right_id = comparison_ids
                left_report, left_source = _load_report(cfg, left_id)
                right_report, right_source = _load_report(cfg, right_id)
                projection = build_claim_comparison(
                    left_report,
                    left_source,
                    right_report,
                    right_source,
                )
                if _etag_matches(environ, projection.digest):
                    return _empty_response(
                        start_response, "304 Not Modified", etag=projection.digest
                    )
                return _json_response(
                    start_response,
                    "200 OK",
                    projection.to_dict(),
                    etag=projection.digest,
                )

            evidence_id = _record_id_from_path(path, "/api/v1/claims/", "/evidence")
            if evidence_id is not None:
                report, source = _load_report(cfg, evidence_id)
                trace, trace_digest = _load_evidence_trace_projection(
                    cfg, evidence_id, report, source
                )
                if _etag_matches(environ, trace_digest):
                    return _empty_response(
                        start_response, "304 Not Modified", etag=trace_digest
                    )
                return _json_response(
                    start_response, "200 OK", trace, etag=trace_digest
                )

            history_id = _record_id_from_path(path, "/api/v1/claims/", "/history")
            if history_id is not None:
                report, _ = _load_report(cfg, history_id)
                history, history_digest = _load_history_projection(
                    cfg, history_id, report
                )
                if _etag_matches(environ, history_digest):
                    return _empty_response(
                        start_response, "304 Not Modified", etag=history_digest
                    )
                return _json_response(
                    start_response, "200 OK", history, etag=history_digest
                )

            markdown_id = _record_id_from_path(path, "/api/v1/reports/", "/markdown")
            if markdown_id is not None:
                report, _ = _load_report(cfg, markdown_id)
                if _etag_matches(environ, report.digest):
                    return _empty_response(
                        start_response, "304 Not Modified", etag=report.digest
                    )
                return _text_response(
                    start_response,
                    "200 OK",
                    render_markdown_report(report),
                    content_type="text/markdown; charset=utf-8",
                    etag=report.digest,
                )

            report_id = _record_id_from_path(path, "/api/v1/reports/")
            if report_id is not None:
                report, _ = _load_report(cfg, report_id)
                if _etag_matches(environ, report.digest):
                    return _empty_response(
                        start_response, "304 Not Modified", etag=report.digest
                    )
                text = render_json_report(report)
                return _text_response(
                    start_response,
                    "200 OK",
                    text,
                    content_type="application/json; charset=utf-8",
                    etag=report.digest,
                )

            summary_id = _record_id_from_path(path, "/api/v1/claims/", "/summary")
            if summary_id is not None:
                report, _ = _load_report(cfg, summary_id)
                if _etag_matches(environ, report.digest):
                    return _empty_response(
                        start_response, "304 Not Modified", etag=report.digest
                    )
                return _json_response(
                    start_response,
                    "200 OK",
                    build_claim_summary(report).to_dict(),
                    etag=report.digest,
                )

            claim_id = _record_id_from_path(path, "/api/v1/claims/")
            if claim_id is not None:
                report, source = _load_report(cfg, claim_id)
                if _etag_matches(environ, report.digest):
                    return _empty_response(
                        start_response, "304 Not Modified", etag=report.digest
                    )
                return _json_response(
                    start_response,
                    "200 OK",
                    build_claim_detail(report, source).to_dict(),
                    etag=report.digest,
                )

            return _error(start_response, "404 Not Found", "NOT_FOUND", "not found")
        except AssuranceDecisionSourceNotConfiguredError:
            return _error(
                start_response,
                "404 Not Found",
                "ASSURANCE_DECISION_SOURCE_NOT_CONFIGURED",
                "assurance decision evidence is not configured for this read API",
            )
        except InvalidAssuranceDecisionSourceError:
            return _error(
                start_response,
                "422 Unprocessable Entity",
                "INVALID_ASSURANCE_DECISION_SOURCE",
                "configured assurance decision evidence could not be verified",
            )
        except AssuranceDecisionSourceTooLargeError:
            return _error(
                start_response,
                "413 Request Entity Too Large",
                "ASSURANCE_DECISION_SOURCE_TOO_LARGE",
                "configured assurance decision evidence exceeds the read limit",
            )
        except AuthorizationContextSourceNotConfiguredError:
            return _error(
                start_response,
                "404 Not Found",
                "AUTHORIZATION_CONTEXT_SOURCE_NOT_CONFIGURED",
                "authorization policy context is not configured for this read API",
            )
        except InvalidAuthorizationContextSourceError:
            return _error(
                start_response,
                "422 Unprocessable Entity",
                "INVALID_AUTHORIZATION_CONTEXT_SOURCE",
                "configured authorization policy context could not be replay-verified",
            )
        except AuthorizationContextSourceTooLargeError:
            return _error(
                start_response,
                "413 Request Entity Too Large",
                "AUTHORIZATION_CONTEXT_SOURCE_TOO_LARGE",
                "configured authorization context exceeds the read limit",
            )
        except InvalidDataGovernanceQueryError:
            return _error(
                start_response,
                "400 Bad Request",
                "INVALID_DATA_GOVERNANCE_QUERY",
                "data governance investigation does not accept query parameters",
            )
        except DataGovernanceSourceNotConfiguredError:
            return _error(
                start_response,
                "404 Not Found",
                "DATA_GOVERNANCE_SOURCE_NOT_CONFIGURED",
                "data lifecycle context is not configured for this read API",
            )
        except InvalidDataGovernanceSourceError:
            return _error(
                start_response,
                "422 Unprocessable Entity",
                "INVALID_DATA_GOVERNANCE_SOURCE",
                "configured lifecycle policy context disagrees with durable workspace state",
            )
        except DataGovernanceSourceTooLargeError:
            return _error(
                start_response,
                "413 Request Entity Too Large",
                "DATA_GOVERNANCE_SOURCE_TOO_LARGE",
                "configured lifecycle context exceeds the read limit",
            )
        except InvalidSecurityAuditQueryError:
            return _error(
                start_response,
                "400 Bad Request",
                "INVALID_SECURITY_AUDIT_QUERY",
                "security audit query is invalid or unsupported",
            )
        except SecurityAuditSourceNotConfiguredError:
            return _error(
                start_response,
                "404 Not Found",
                "SECURITY_AUDIT_SOURCE_NOT_CONFIGURED",
                "deployment security audit is not configured for this read API",
            )
        except InvalidSecurityAuditSourceError:
            return _error(
                start_response,
                "422 Unprocessable Entity",
                "INVALID_SECURITY_AUDIT_SOURCE",
                "configured deployment security audit could not be verified",
            )
        except SecurityAuditSourceTooLargeError:
            return _error(
                start_response,
                "413 Request Entity Too Large",
                "SECURITY_AUDIT_SOURCE_TOO_LARGE",
                "configured deployment security audit exceeds the read limit",
            )
        except InvalidRuntimeContainmentSnapshotError:
            return _error(
                start_response,
                "422 Unprocessable Entity",
                "INVALID_RUNTIME_CONTAINMENT_SNAPSHOT",
                "configured runtime containment snapshot could not be verified",
            )
        except RuntimeContainmentSnapshotTooLargeError:
            return _error(
                start_response,
                "413 Request Entity Too Large",
                "RUNTIME_CONTAINMENT_SNAPSHOT_TOO_LARGE",
                "configured runtime containment snapshot exceeds the read limit",
            )
        except DecisionLineageSourceNotConfiguredError:
            return _error(
                start_response,
                "404 Not Found",
                "DECISION_LINEAGE_SOURCE_NOT_CONFIGURED",
                "reliability decision/lineage evidence is not configured for this read API",
            )
        except InvalidDecisionLineageSourceError:
            return _error(
                start_response,
                "422 Unprocessable Entity",
                "INVALID_DECISION_LINEAGE_SOURCE",
                "configured reliability decision/lineage evidence could not be verified",
            )
        except DecisionLineageSourceTooLargeError:
            return _error(
                start_response,
                "413 Request Entity Too Large",
                "DECISION_LINEAGE_SOURCE_TOO_LARGE",
                "configured reliability decision/lineage evidence exceeds the read limit",
            )
        except ReliabilityProofSourceNotConfiguredError:
            return _error(
                start_response,
                "404 Not Found",
                "RELIABILITY_PROOF_SOURCE_NOT_CONFIGURED",
                "reliability proof bundle is not configured for this read API",
            )
        except InvalidReliabilityProofSourceError:
            return _error(
                start_response,
                "422 Unprocessable Entity",
                "INVALID_RELIABILITY_PROOF_SOURCE",
                "configured reliability proof bundle could not be verified",
            )
        except ReliabilityProofSourceTooLargeError:
            return _error(
                start_response,
                "413 Request Entity Too Large",
                "RELIABILITY_PROOF_SOURCE_TOO_LARGE",
                "configured reliability proof bundle exceeds the read limit",
            )
        except InvalidAttestationTrustQueryError:
            return _error(
                start_response,
                "400 Bad Request",
                "INVALID_ATTESTATION_TRUST_QUERY",
                "attestation trust query is invalid or unsupported",
            )
        except AttestationTrustSourceNotConfiguredError:
            return _error(
                start_response,
                "404 Not Found",
                "ATTESTATION_TRUST_SOURCE_NOT_CONFIGURED",
                "attestation trust evidence is not configured for this read API",
            )
        except InvalidAttestationTrustSourceError:
            return _error(
                start_response,
                "422 Unprocessable Entity",
                "INVALID_ATTESTATION_TRUST_SOURCE",
                "configured attestation trust evidence could not be verified",
            )
        except AttestationTrustSourceTooLargeError:
            return _error(
                start_response,
                "413 Request Entity Too Large",
                "ATTESTATION_TRUST_SOURCE_TOO_LARGE",
                "configured attestation trust evidence exceeds the read limit",
            )
        except InvalidCaptureFailureQueryError:
            return _error(
                start_response,
                "400 Bad Request",
                "INVALID_CAPTURE_FAILURE_QUERY",
                "capture failure query is invalid or unsupported",
            )
        except CaptureFailureSourceNotConfiguredError:
            return _error(
                start_response,
                "404 Not Found",
                "CAPTURE_FAILURE_SOURCE_NOT_CONFIGURED",
                "native capture failure journal is not configured for this read API",
            )
        except InvalidCaptureFailureSourceError:
            return _error(
                start_response,
                "422 Unprocessable Entity",
                "INVALID_CAPTURE_FAILURE_SOURCE",
                "configured native capture failure journal could not be verified",
            )
        except CaptureFailureSourceTooLargeError:
            return _error(
                start_response,
                "413 Request Entity Too Large",
                "CAPTURE_FAILURE_SOURCE_TOO_LARGE",
                "configured native capture failure journal exceeds the read limit",
            )
        except InvalidIncidentQueryError:
            return _error(
                start_response,
                "400 Bad Request",
                "INVALID_INCIDENT_QUERY",
                "incident investigation query is invalid or unsupported",
            )
        except IncidentSourceNotConfiguredError:
            return _error(
                start_response,
                "404 Not Found",
                "INCIDENT_SOURCE_NOT_CONFIGURED",
                "incident evidence is not configured for this read API",
            )
        except InvalidIncidentSourceError:
            return _error(
                start_response,
                "422 Unprocessable Entity",
                "INVALID_INCIDENT_SOURCE",
                "configured incident evidence could not be verified",
            )
        except IncidentSourceTooLargeError:
            return _error(
                start_response,
                "413 Request Entity Too Large",
                "INCIDENT_SOURCE_TOO_LARGE",
                "configured incident evidence exceeds the read limit",
            )
        except HistoryNotConfiguredError:
            return _error(
                start_response,
                "404 Not Found",
                "HISTORY_NOT_CONFIGURED",
                "reliability-state history is not configured for this read API",
            )
        except InvalidHistoryError:
            return _error(
                start_response,
                "422 Unprocessable Entity",
                "INVALID_HISTORY",
                "configured reliability-state history could not be verified",
            )
        except EvidenceTraceTooLargeError:
            return _error(
                start_response,
                "413 Request Entity Too Large",
                "EVIDENCE_TRACE_TOO_LARGE",
                "the requested evidence trace exceeds the configured node limit",
            )
        except HistoryTooLargeError:
            return _error(
                start_response,
                "413 Request Entity Too Large",
                "HISTORY_TOO_LARGE",
                "configured reliability-state history exceeds the read limit",
            )
        except InvalidClaimCatalogQueryError:
            return _error(
                start_response,
                "400 Bad Request",
                "INVALID_CLAIM_QUERY",
                "claim discovery query is invalid or unsupported",
            )
        except ClaimCatalogTooLargeError:
            return _error(
                start_response,
                "413 Request Entity Too Large",
                "CLAIM_CATALOG_TOO_LARGE",
                "workspace receipts exceed the configured claim discovery scan limit",
            )
        except InvalidWorkspaceQueryError:
            return _error(
                start_response,
                "400 Bad Request",
                "INVALID_WORKSPACE_QUERY",
                "workspace pagination is invalid or unsupported",
            )
        except OperationalSourceNotConfiguredError:
            return _error(
                start_response,
                "404 Not Found",
                "NOT_CONFIGURED",
                "the requested operational source is not configured",
            )
        except InvalidOperationalSourceError:
            return _error(
                start_response,
                "422 Unprocessable Entity",
                "INVALID_OPERATIONAL_SOURCE",
                "the configured operational source could not be verified",
            )
        except OperationalSourceTooLargeError:
            return _error(
                start_response,
                "413 Request Entity Too Large",
                "OPERATIONAL_SOURCE_TOO_LARGE",
                "the configured operational source exceeds the read limit",
            )
        except (InvalidReportError, ValueError):
            return _error(
                start_response,
                "422 Unprocessable Entity",
                "INVALID_REPORT",
                "the requested record is not a valid StateWake verification report",
            )
        except OverflowError:
            return _error(
                start_response,
                "413 Request Entity Too Large",
                "REPORT_TOO_LARGE",
                "the requested report exceeds the configured read limit",
            )
        except FileNotFoundError:
            return _error(
                start_response,
                "404 Not Found",
                "NOT_FOUND",
                "the requested StateWake record was not found",
            )
        except (WorkspaceReadError, OSError, KeyError):
            return _error(
                start_response,
                "503 Service Unavailable",
                "WORKSPACE_UNAVAILABLE",
                "the configured StateWake workspace is unavailable",
            )

    return application


def serve_read_api(host: str = "127.0.0.1", port: int = 8788) -> None:
    """Run the optional local read-only UI API on loopback by default."""
    application = create_read_application()
    with make_server(host, port, application) as httpd:
        print(
            f"StateWake {__version__} read API listening on http://{host}:{port} "
            "(local read-only mode)"
        )
        httpd.serve_forever()


__all__ = ["ReadApiConfig", "create_read_application", "serve_read_api"]


if __name__ == "__main__":
    serve_read_api()
