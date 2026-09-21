"""Public package API for StateWake's stabilized reliability lifecycle."""

__version__ = "0.4.0"
__public_api_contract_version__ = "1"

from statewake.adapters.first_party_evidence import (
    AgentRunLogAdapter,
    CICDArtifactAdapter,
    EvaluationOutputAdapter,
    EvidenceAdapterContext,
    FileEvidenceAdapter,
    IncidentRecoveryRecordAdapter,
    OpenTelemetryTraceAdapter,
)
from statewake.adapters.trust_anchor import JsonTrustAnchorStore
from statewake.domain.evidence_admission import ExternalEvidenceAdmission
from statewake.domain.evidence_receipt import ExternalEvidenceReceipt
from statewake.domain.key_management import (
    KeyLifecycleProvider,
    SigningKeyReference,
    SigningProvider,
    public_key_digest,
)
from statewake.domain.operational_hooks import (
    NullReliabilityFailureHook,
    ReliabilityFailureEvent,
    ReliabilityFailureHook,
)
from statewake.domain.operations import OperationalBundle
from statewake.domain.reliability_attestation import ReliabilityOutcomeAttestation
from statewake.domain.reliability_claim_profile import ReliabilityClaimProfile
from statewake.domain.reliability_decision_basis import ReliabilityDecisionBasis
from statewake.domain.reliability_evidence import ReliabilityEvidenceChain
from statewake.domain.reliability_outcome_verification import (
    ReliabilityOutcomeVerificationReport,
)
from statewake.domain.reliability_state import (
    ReliabilityStateSnapshot,
    ReliabilityStateTransition,
)
from statewake.domain.reliability_verification_report import (
    ReliabilityVerificationReport,
)
from statewake.domain.retention import (
    EvidenceRetentionAdapter,
    EvidenceRetentionRequirement,
)
from statewake.domain.security_incident import (
    AffectedTrustState,
    IncidentEvidenceReference,
    KeyCompromiseImpact,
    PostRecoveryVerification,
    RecoveryEvidence,
    SecurityIncidentEvidence,
)
from statewake.domain.trust_anchor import (
    AnchorDiscrepancyError,
    Ed25519TrustCheckpointVerifier,
    TrustAnchor,
    TrustAnchorError,
    TrustCheckpoint,
    compare_local_tip,
    create_trust_checkpoint,
    ensure_checkpoint_sequence,
)
from statewake.public_api import (
    admit_evidence,
    build_evidence_chain,
    derive_security_incident_id,
    load_evidence_chain,
    load_outcome_attestation,
    read_reliability_state,
    verify_evidence_chain,
    verify_outcome,
    verify_security_incident,
    write_evidence_chain,
    write_outcome_attestation,
)
from statewake.sdk import (
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
from statewake.services.release_proof_service import (
    build_release_proof,
    render_verification_report,
    write_verification_report,
)
from statewake.services.reliability_claim_profile_service import (
    ClaimProfileEvaluation,
    evaluate_claim_profile,
    get_builtin_claim_profile,
    list_builtin_claim_profiles,
    load_claim_profile,
    write_claim_profile,
)
from statewake.services.reliability_decision_basis_service import (
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
    "list_builtin_claim_profiles",
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
    "AffectedTrustState",
    "IncidentEvidenceReference",
    "KeyCompromiseImpact",
    "PostRecoveryVerification",
    "RecoveryEvidence",
    "SecurityIncidentEvidence",
    "derive_security_incident_id",
    "verify_security_incident",
    "__version__",
    "__public_api_contract_version__",
]
