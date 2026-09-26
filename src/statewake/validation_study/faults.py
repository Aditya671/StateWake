"""Deterministic fault catalog for the Phase 7 comparative study."""

from __future__ import annotations

from statewake.validation_study.model import FaultInjection

FAULTS: tuple[FaultInjection, ...] = (
    FaultInjection(
        kind="omitted_evidence",
        description="Required evidence reference is absent from the claim support set.",
        affected_property="evidence_contract",
    ),
    FaultInjection(
        kind="malformed_evidence",
        description="Evidence payload cannot satisfy the expected contract shape.",
        affected_property="evidence_contract",
    ),
    FaultInjection(
        kind="stale_corpus",
        description="RAG corpus identity no longer matches the verified snapshot.",
        affected_property="retrieval_corpus_identity",
    ),
    FaultInjection(
        kind="wrong_model_version",
        description="Model version differs from the model invocation evidence.",
        affected_property="model_identity",
    ),
    FaultInjection(
        kind="changed_prompt_template",
        description="Prompt template digest differs from the verified prompt evidence.",
        affected_property="prompt_template_digest",
    ),
    FaultInjection(
        kind="missing_tool_authorization",
        description="Side-effecting tool call lacks authorization evidence.",
        affected_property="tool_authorization",
    ),
    FaultInjection(
        kind="modified_tool_output",
        description="Tool output digest does not match the recorded evidence.",
        affected_property="tool_output_digest",
    ),
    FaultInjection(
        kind="broken_provenance_edge",
        description="Evidence chain cannot connect output, provenance, and integrity records.",
        affected_property="trace_identity",
    ),
    FaultInjection(
        kind="invalid_reliability_transition",
        description="Claim state transition is not allowed by the profile.",
        affected_property="profile_result",
    ),
    FaultInjection(
        kind="partial_workspace_write",
        description="Workspace contains an incomplete record after interrupted persistence.",
        affected_property="workspace_history",
    ),
    FaultInjection(
        kind="recovery_without_preserved_failure",
        description="Recovery exists but the original failed attempt was erased.",
        affected_property="recovery_history",
    ),
    FaultInjection(
        kind="unsigned_release_artifact",
        description="Release artifact lacks signature evidence or explicit signing limitation.",
        affected_property="release_trust",
    ),
)
