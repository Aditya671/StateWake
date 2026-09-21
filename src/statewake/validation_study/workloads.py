"""Representative workloads and comparison baselines for Phase 7."""

from __future__ import annotations

from statewake.validation_study.model import ValidationBaseline, WorkloadDefinition

BASELINES: tuple[ValidationBaseline, ...] = (
    ValidationBaseline(
        mode="final_output_only",
        captured_properties=("final_output",),
        limitation="Retains final response only; cannot verify evidence, provenance, or recovery.",
    ),
    ValidationBaseline(
        mode="conventional_logs",
        captured_properties=("final_output", "timestamp", "error_status"),
        limitation="Shows coarse execution history but not digest-bound claim evidence.",
    ),
    ValidationBaseline(
        mode="structured_traces",
        captured_properties=(
            "final_output",
            "timestamp",
            "error_status",
            "trace_identity",
        ),
        limitation="Shows spans and timing but not StateWake evidence contracts or claim profiles.",
    ),
    ValidationBaseline(
        mode="statewake_full",
        captured_properties=(
            "final_output",
            "timestamp",
            "error_status",
            "trace_identity",
            "evidence_contract",
            "profile_result",
            "workspace_history",
            "human_report",
            "release_trust",
            "recovery_history",
        ),
        limitation="Fixture-based study; does not claim statistical superiority beyond tested workloads.",
    ),
)

WORKLOADS: tuple[WorkloadDefinition, ...] = (
    WorkloadDefinition(
        workload="rag_answer",
        profile_id="rag_answer_verified.v1",
        target_properties=(
            "final_output",
            "trace_identity",
            "retrieval_corpus_identity",
            "retrieval_chunk_digest",
            "citation_boundary",
            "profile_result",
        ),
        required_ai_contracts=(
            "prompt_evidence",
            "model_invocation",
            "retrieval_evidence",
        ),
    ),
    WorkloadDefinition(
        workload="tool_action",
        profile_id="tool_action_authorized.v1",
        target_properties=(
            "tool_schema_version",
            "tool_input_digest",
            "tool_output_digest",
            "tool_authorization",
            "side_effect_classification",
            "profile_result",
        ),
        required_ai_contracts=("tool_call", "policy_evidence"),
    ),
    WorkloadDefinition(
        workload="incident_recovery",
        profile_id="incident_recovery_verified.v1",
        target_properties=(
            "failure_record",
            "recovery_action",
            "post_recovery_state",
            "recovery_history",
            "profile_result",
        ),
        required_ai_contracts=("runtime_trace",),
    ),
    WorkloadDefinition(
        workload="release_verification",
        profile_id="release_evidence_complete.v1",
        target_properties=(
            "package_digest",
            "lock_status",
            "test_result",
            "release_limitation",
            "release_trust",
            "human_release_decision",
        ),
        required_ai_contracts=("policy_evidence", "human_approval"),
    ),
    WorkloadDefinition(
        workload="human_approval_workflow",
        profile_id="human_approval_recorded.v1",
        target_properties=(
            "actor_identity_reference",
            "actor_role",
            "approval_scope",
            "approval_basis_digest",
            "approval_timestamp",
            "profile_result",
        ),
        required_ai_contracts=("human_approval",),
    ),
)
