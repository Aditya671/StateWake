"""Read-only data governance, retention, disclosure, and deletion investigation."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from statewake.services.data_lifecycle_investigation_service import (
    ResolvedDataLifecycleContext,
)
from statewake.services.privacy_governance_runtime_service import (
    PrivacyGovernanceRuntimeConfig,
    runtime_config_digest,
)

DATA_GOVERNANCE_SCHEMA_VERSION = "data-governance-investigation.v2"


def _digest(value: str) -> str:
    """Return one stable privacy-safe identity digest."""
    return sha256(value.encode("utf-8")).hexdigest()


def _decision_payload(decision: object) -> dict[str, object]:
    """Serialize an already-verified lifecycle decision through its domain contract."""
    to_dict = getattr(decision, "to_dict", None)
    if not callable(to_dict):
        raise ValueError("lifecycle decision does not support canonical serialization")
    payload = to_dict()
    if not isinstance(payload, dict):
        raise ValueError("lifecycle decision serialization must be an object")
    payload = dict(payload)
    object_id = str(payload.pop("object_id"))
    payload["object_id_digest"] = _digest(object_id)
    payload["object_id_exposed"] = False
    return payload


@dataclass(frozen=True, slots=True)
class DataGovernanceProjection:
    """Privacy-safe projection over verified lifecycle and runtime governance state."""

    resolved: ResolvedDataLifecycleContext
    privacy_governance: PrivacyGovernanceRuntimeConfig | None = None

    def to_dict(self) -> dict[str, object]:
        """Render one complete bounded lifecycle investigation contract."""
        context = self.resolved.context
        policy = context.policy
        retention = self.resolved.retention
        deletion = self.resolved.deletion
        recorded = context.recorded_decision
        deletion_payload: dict[str, object]
        if deletion is None:
            deletion_payload = {
                "present": False,
                "payload_erasure_outside_statewake_evaluated": False,
            }
        else:
            deletion_payload = {
                "present": True,
                "digest": deletion.digest,
                "sensitivity": deletion.sensitivity,
                "deleted_at": deletion.deleted_at,
                "policy_id": deletion.policy_id,
                "reason": deletion.reason,
                "tombstone_cross_check_verified": True,
                "payload_content_retained_in_tombstone": False,
                "payload_erasure_outside_statewake_evaluated": False,
            }

        runtime = self.privacy_governance
        privacy_runtime: dict[str, object]
        if runtime is None:
            privacy_runtime = {
                "observed": False,
                "defaults_inferred": False,
                "source_path_exposed": False,
            }
        else:
            privacy_runtime = {
                "observed": True,
                "defaults_inferred": False,
                "source_path_exposed": False,
                "snapshot_digest": runtime_config_digest(runtime),
                "privacy_policy": {
                    "policy_id": runtime.privacy_policy.policy_id,
                    "redact_key_count": len(runtime.privacy_policy.redact_keys),
                    "regex_rule_count": len(runtime.privacy_policy.rules),
                    "patterns_exposed": False,
                    "metadata_redaction_before_receipt_identity": True,
                },
                "evidence_policy": {
                    "policy_id": runtime.evidence_policy.policy_id,
                    "storage_max_sensitivity": runtime.evidence_policy.storage_max_sensitivity,
                    "telemetry_max_sensitivity": runtime.evidence_policy.telemetry_max_sensitivity,
                    "require_digest_for": list(
                        runtime.evidence_policy.require_digest_for
                    ),
                    "storage_governance_before_artifact_write": True,
                    "workspace_sensitivity_indexing": True,
                    "telemetry_manifest_projection_supported": True,
                    "telemetry_runtime_binding_observed": False,
                },
                "opaque_content_secret_scanning": False,
            }

        return {
            "schema_version": DATA_GOVERNANCE_SCHEMA_VERSION,
            "source": {
                "resource": "explicit-lifecycle-context-plus-workspace-metadata",
                "configured": True,
                "source_path_exposed": False,
                "workspace_authority": True,
                "second_lifecycle_store_created": False,
                "privacy_governance_snapshot_configured": runtime is not None,
            },
            "privacy_governance_runtime": privacy_runtime,
            "object": {
                "kind": context.object_kind,
                "object_id_digest": _digest(context.object_id),
                "object_id_exposed": False,
                "sensitivity": context.sensitivity,
                "created_at": context.created_at.isoformat(),
                "original_digest": self.resolved.original_digest,
            },
            "policy": {
                "policy_id": policy.policy_id,
                "purpose": policy.purpose,
                "max_retention_days": policy.max_retention_days,
                "storage_max_sensitivity": policy.storage_max_sensitivity,
                "telemetry_max_sensitivity": policy.telemetry_max_sensitivity,
                "disclosure_max_sensitivity": policy.disclosure_max_sensitivity,
                "encryption_at_rest_required": policy.encryption_at_rest_required,
                "tls_required": policy.tls_required,
            },
            "durable_retention": {
                "present": True,
                "policy_id": retention.policy_id,
                "sensitivity": retention.sensitivity,
                "retain_until": retention.retain_until,
                "legal_hold": retention.legal_hold,
                "context_cross_check_verified": True,
            },
            "current_decision": {
                **_decision_payload(self.resolved.current_decision),
                "policy_replay_verified": True,
                "deletion_already_recorded": deletion is not None,
            },
            "recorded_decision": (
                {"present": False}
                if recorded is None
                else {
                    "present": True,
                    "evaluated_at": recorded.evaluated_at.isoformat(),
                    "decision": _decision_payload(recorded.decision),
                    "policy_replay_verified": True,
                }
            ),
            "deletion": deletion_payload,
            "confidentiality_requirements": {
                "encryption_at_rest_required": policy.encryption_at_rest_required,
                "tls_required": policy.tls_required,
                "host_requirement_satisfaction_evaluated": False,
            },
            "authorization": {
                "deletion_executed_by_this_view": False,
                "disclosure_executed_by_this_view": False,
                "business_authorization_inferred": False,
                "compliance_certified": False,
            },
            "limitations": [
                "The full DataLifecyclePolicy is supplied by one explicit investigation artifact because the workspace schema persists only lifecycle policy identity, sensitivity, retention deadline, and legal-hold state.",
                "Retention expiry is not deletion authority while a legal hold is active.",
                "A deletion tombstone proves the recorded StateWake deletion event and original digest binding; it does not prove erasure of copies outside StateWake's managed boundary.",
                "Encryption-at-rest and TLS flags are deployment requirements, not proof that the host currently satisfies them.",
                "This read-only investigation never deletes, exports, discloses, migrates, or repairs workspace state.",
                "Runtime privacy redaction applies only to configured metadata boundaries and does not inspect opaque artifact content for secrets.",
                "A telemetry projection capability does not prove that a live OpenTelemetry exporter is currently bound to the same policy snapshot.",
            ],
        }


__all__ = [
    "DATA_GOVERNANCE_SCHEMA_VERSION",
    "DataGovernanceProjection",
]
