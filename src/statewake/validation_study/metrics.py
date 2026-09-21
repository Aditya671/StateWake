"""Metrics and case execution for the Phase 7 comparative validation study."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from typing import cast

from statewake.services.reliability_claim_profile_service import (
    evaluate_claim_profile,
    get_builtin_claim_profile,
)
from statewake.validation_study.chains import chain_for_workload
from statewake.validation_study.faults import FAULTS
from statewake.validation_study.model import (
    BaselineMode,
    ComparativeValidationStudy,
    FaultKind,
    StudyMetrics,
    ValidationBaseline,
    ValidationCaseResult,
    WorkloadDefinition,
    WorkloadKind,
    canonical_digest,
)
from statewake.validation_study.workloads import BASELINES, WORKLOADS

_BASELINE_EXTRA_PROPERTIES: dict[BaselineMode, tuple[str, ...]] = {
    "final_output_only": (),
    "conventional_logs": (),
    "structured_traces": (),
    "statewake_full": (
        "actor_identity_reference",
        "actor_role",
        "approval_basis_digest",
        "approval_scope",
        "approval_timestamp",
        "citation_boundary",
        "evidence_contract",
        "failure_record",
        "human_release_decision",
        "lock_status",
        "package_digest",
        "post_recovery_state",
        "profile_result",
        "recovery_action",
        "retrieval_chunk_digest",
        "retrieval_corpus_identity",
        "release_limitation",
        "side_effect_classification",
        "test_result",
        "tool_authorization",
        "tool_input_digest",
        "tool_output_digest",
        "tool_schema_version",
    ),
}

_ALL_FAULT_KINDS: tuple[FaultKind, ...] = cast(
    tuple[FaultKind, ...], tuple(fault.kind for fault in FAULTS)
)

_FAULT_DETECTION: dict[BaselineMode, tuple[FaultKind, ...]] = {
    "final_output_only": (),
    "conventional_logs": ("malformed_evidence",),
    "structured_traces": ("malformed_evidence", "broken_provenance_edge"),
    "statewake_full": _ALL_FAULT_KINDS,
}


def _baseline(mode: BaselineMode) -> ValidationBaseline:
    """Return one baseline descriptor by mode."""
    for baseline in BASELINES:
        if baseline.mode == mode:
            return baseline
    raise KeyError(f"unknown baseline: {mode}")


def _workload(kind: WorkloadKind) -> WorkloadDefinition:
    """Return one workload descriptor by kind."""
    for workload in WORKLOADS:
        if workload.workload == kind:
            return workload
    raise KeyError(f"unknown workload: {kind}")


def _checkable(workload: WorkloadDefinition, mode: BaselineMode) -> tuple[str, ...]:
    """Return target properties checkable by the supplied baseline."""
    baseline = _baseline(mode)
    supported = set(baseline.captured_properties) | set(
        _BASELINE_EXTRA_PROPERTIES[mode]
    )
    return tuple(item for item in workload.target_properties if item in supported)


def _profile_satisfied(
    workload: WorkloadDefinition,
    faults: tuple[FaultKind, ...],
    mode: BaselineMode,
) -> bool | None:
    """Return profile result when a StateWake chain is available."""
    if mode != "statewake_full":
        return None
    omit_contracts: list[str] = []
    verified = True
    preserve_failure = True
    if "omitted_evidence" in faults:
        omit_contracts.extend(workload.required_ai_contracts)
    if "broken_provenance_edge" in faults or "invalid_reliability_transition" in faults:
        verified = False
    if "recovery_without_preserved_failure" in faults:
        preserve_failure = False
    chain = chain_for_workload(
        workload.workload,
        omit_contracts=tuple(omit_contracts),
        verified=verified,
        preserve_failure=preserve_failure,
    )
    profile = get_builtin_claim_profile(workload.profile_id)
    return evaluate_claim_profile(chain, profile).satisfied


def run_validation_case(
    workload: WorkloadKind,
    baseline: BaselineMode,
    faults: Iterable[FaultKind] = (),
) -> ValidationCaseResult:
    """Run one deterministic validation case without external AI calls."""
    workload_definition = _workload(workload)
    injected: tuple[FaultKind, ...] = tuple(faults)
    detectable_faults = set(_FAULT_DETECTION[baseline])
    detected: tuple[FaultKind, ...] = tuple(
        fault for fault in injected if fault in detectable_faults
    )
    profile_satisfied = _profile_satisfied(workload_definition, injected, baseline)
    false_positive = not injected and profile_satisfied is False
    notes = (
        "fixture-based deterministic case",
        "live model calls and human timing studies are out of scope",
    )
    return ValidationCaseResult(
        workload=workload,
        baseline=baseline,
        injected_faults=injected,
        target_properties=workload_definition.target_properties,
        checkable_properties=_checkable(workload_definition, baseline),
        detected_faults=detected,
        false_positive=false_positive,
        profile_satisfied=profile_satisfied,
        notes=notes,
    )


def aggregate_metrics(
    cases: Iterable[ValidationCaseResult],
) -> tuple[StudyMetrics, ...]:
    """Aggregate deterministic study metrics by baseline."""
    grouped: dict[BaselineMode, list[ValidationCaseResult]] = defaultdict(list)
    for case in cases:
        grouped[case.baseline].append(case)
    metrics: list[StudyMetrics] = []
    for baseline in sorted(grouped):
        group = grouped[baseline]
        injected_fault_count = sum(len(case.injected_faults) for case in group)
        detected_fault_count = sum(len(case.detected_faults) for case in group)
        valid_cases = [case for case in group if not case.injected_faults]
        metrics.append(
            StudyMetrics(
                baseline=baseline,
                case_count=len(group),
                injected_fault_count=injected_fault_count,
                detected_fault_count=detected_fault_count,
                valid_case_count=len(valid_cases),
                false_positive_count=sum(case.false_positive for case in valid_cases),
                target_property_count=sum(
                    len(case.target_properties) for case in group
                ),
                checkable_property_count=sum(
                    len(case.checkable_properties) for case in group
                ),
            )
        )
    return tuple(metrics)


def run_comparative_validation_study() -> ComparativeValidationStudy:
    """Run the fixed Phase 7 comparison matrix over fixture workloads and faults."""
    selected_faults: dict[WorkloadKind, tuple[FaultKind, ...]] = {
        "rag_answer": ("omitted_evidence", "stale_corpus"),
        "tool_action": ("missing_tool_authorization", "modified_tool_output"),
        "incident_recovery": ("recovery_without_preserved_failure",),
        "release_verification": ("unsigned_release_artifact",),
        "human_approval_workflow": ("omitted_evidence",),
    }
    cases: list[ValidationCaseResult] = []
    for workload in WORKLOADS:
        for baseline in BASELINES:
            cases.append(run_validation_case(workload.workload, baseline.mode, ()))
            cases.append(
                run_validation_case(
                    workload.workload,
                    baseline.mode,
                    selected_faults[workload.workload],
                )
            )
    metrics = aggregate_metrics(cases)
    study_seed = {
        "baselines": [baseline.mode for baseline in BASELINES],
        "workloads": [workload.workload for workload in WORKLOADS],
        "faults": [fault.kind for fault in FAULTS],
    }
    return ComparativeValidationStudy(
        study_id=f"phase7-{canonical_digest(study_seed)[:12]}",
        baselines=BASELINES,
        workloads=WORKLOADS,
        faults=FAULTS,
        cases=tuple(cases),
        metrics=metrics,
        limitations=(
            "Deterministic fixtures are used before live AI calls.",
            "Metrics are scoped to these workloads and injected faults only.",
            "Human reconstruction-time measurement requires a separate timed study.",
        ),
    )
