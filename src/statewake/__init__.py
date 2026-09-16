"""Public package API for StateWake's stabilized reliability lifecycle."""

__version__ = "0.1.1"
__public_api_contract_version__ = "1"

from .adapters.first_party_evidence import (
    AgentRunLogAdapter,
    CICDArtifactAdapter,
    EvaluationOutputAdapter,
    EvidenceAdapterContext,
    FileEvidenceAdapter,
    IncidentRecoveryRecordAdapter,
    OpenTelemetryTraceAdapter,
)
from .adapters.trust_anchor import JsonTrustAnchorStore
from .domain.evidence_admission import ExternalEvidenceAdmission
from .domain.evidence_receipt import ExternalEvidenceReceipt
from .domain.key_management import (
    KeyLifecycleProvider,
    SigningKeyReference,
    SigningProvider,
    public_key_digest,
)
from .domain.operational_hooks import (
    NullReliabilityFailureHook,
    ReliabilityFailureEvent,
    ReliabilityFailureHook,
)
from .domain.operations import OperationalBundle
from .domain.reliability_attestation import ReliabilityOutcomeAttestation
from .domain.reliability_claim_profile import ReliabilityClaimProfile
from .domain.reliability_decision_basis import ReliabilityDecisionBasis
from .domain.reliability_evidence import ReliabilityEvidenceChain
from .domain.reliability_outcome_verification import (
    ReliabilityOutcomeVerificationReport,
)
from .domain.reliability_state import (
    ReliabilityStateSnapshot,
    ReliabilityStateTransition,
)
from .domain.reliability_verification_report import ReliabilityVerificationReport
from .domain.retention import EvidenceRetentionAdapter, EvidenceRetentionRequirement
from .domain.trust_anchor import (
    AnchorDiscrepancyError,
    Ed25519TrustCheckpointVerifier,
    TrustAnchor,
    TrustAnchorError,
    TrustCheckpoint,
    compare_local_tip,
    create_trust_checkpoint,
    ensure_checkpoint_sequence,
)
from .public_api import (
    admit_evidence,
    build_evidence_chain,
    load_evidence_chain,
    load_outcome_attestation,
    read_reliability_state,
    verify_evidence_chain,
    verify_outcome,
    write_evidence_chain,
    write_outcome_attestation,
)
from .sdk import (
    AgentEvidenceAdapter,
    AgentRunEvidence,
    BatchEvidenceAdapter,
    BatchRun,
    DatabaseChange,
    DatabaseEvidenceAdapter,
    IdentityConflictError,
    IntegrationContext,
    InvalidEvidenceError,
    PersistenceFailureError,
    QueueEvidenceAdapter,
    QueueMessage,
    StateWakeClient,
    StateWakeIntegrationError,
    WebhookEvent,
    WebhookEvidenceAdapter,
)
from .services.release_proof_service import (
    build_release_proof,
    render_verification_report,
    write_verification_report,
)
from .services.reliability_claim_profile_service import (
    ClaimProfileEvaluation,
    evaluate_claim_profile,
    get_builtin_claim_profile,
    load_claim_profile,
    write_claim_profile,
)
from .services.reliability_decision_basis_service import (
    build_reliability_decision_basis,
    prepare_reliability_decision_basis,
)

__all__ = [
    "AnchorDiscrepancyError",
    "Ed25519TrustCheckpointVerifier",
    "JsonTrustAnchorStore",
    "TrustAnchor",
    "TrustAnchorError",
    "TrustCheckpoint",
    "compare_local_tip",
    "create_trust_checkpoint",
    "ensure_checkpoint_sequence",
    "AgentRunLogAdapter",
    "CICDArtifactAdapter",
    "AgentEvidenceAdapter",
    "AgentRunEvidence",
    "BatchEvidenceAdapter",
    "BatchRun",
    "DatabaseChange",
    "DatabaseEvidenceAdapter",
    "IdentityConflictError",
    "IntegrationContext",
    "InvalidEvidenceError",
    "ClaimProfileEvaluation",
    "EvidenceAdapterContext",
    "EvidenceRetentionAdapter",
    "EvidenceRetentionRequirement",
    "EvaluationOutputAdapter",
    "ExternalEvidenceAdmission",
    "ExternalEvidenceReceipt",
    "ReliabilityEvidenceChain",
    "ReliabilityOutcomeAttestation",
    "ReliabilityOutcomeVerificationReport",
    "ReliabilityDecisionBasis",
    "OperationalBundle",
    "FileEvidenceAdapter",
    "IncidentRecoveryRecordAdapter",
    "KeyLifecycleProvider",
    "NullReliabilityFailureHook",
    "OpenTelemetryTraceAdapter",
    "PersistenceFailureError",
    "QueueEvidenceAdapter",
    "QueueMessage",
    "StateWakeClient",
    "StateWakeIntegrationError",
    "WebhookEvent",
    "WebhookEvidenceAdapter",
    "ReliabilityClaimProfile",
    "ReliabilityFailureEvent",
    "ReliabilityFailureHook",
    "ReliabilityStateSnapshot",
    "ReliabilityStateTransition",
    "ReliabilityVerificationReport",
    "SigningKeyReference",
    "SigningProvider",
    "admit_evidence",
    "build_evidence_chain",
    "build_release_proof",
    "build_reliability_decision_basis",
    "evaluate_claim_profile",
    "get_builtin_claim_profile",
    "load_claim_profile",
    "load_evidence_chain",
    "load_outcome_attestation",
    "prepare_reliability_decision_basis",
    "public_key_digest",
    "read_reliability_state",
    "render_verification_report",
    "verify_evidence_chain",
    "verify_outcome",
    "write_claim_profile",
    "write_evidence_chain",
    "write_outcome_attestation",
    "write_verification_report",
    "__version__",
    "__public_api_contract_version__",
]
