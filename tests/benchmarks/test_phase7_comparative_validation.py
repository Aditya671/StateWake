"""Regression tests for Phase 7 comparative validation study."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from statewake.services.reliability_claim_profile_service import (
    evaluate_claim_profile,
    get_builtin_claim_profile,
)
from statewake.validation_study.chains import chain_for_workload
from statewake.validation_study.metrics import (
    run_comparative_validation_study,
    run_validation_case,
)
from statewake.validation_study.report import (
    render_study_json,
    render_study_markdown,
    report_timestamp,
)


def test_fault_injection_omitted_evidence_detected_by_statewake() -> None:
    """Prove omitted required evidence is detected by the StateWake baseline."""
    result = run_validation_case(
        "rag_answer",
        "statewake_full",
        ("omitted_evidence",),
    )
    assert result.detected_faults == ("omitted_evidence",)
    assert result.profile_satisfied is False
    assert "profile_result" in result.checkable_properties


def test_fault_injection_modified_payload_detected_by_digest() -> None:
    """Prove digest-sensitive tool-output tampering is detected in StateWake mode."""
    result = run_validation_case(
        "tool_action",
        "statewake_full",
        ("modified_tool_output",),
    )
    assert result.detected_faults == ("modified_tool_output",)
    assert "tool_output_digest" in result.checkable_properties


def test_baseline_final_output_cannot_verify_retrieval_corpus() -> None:
    """Keep the final-output-only baseline honest for RAG corpus claims."""
    result = run_validation_case("rag_answer", "final_output_only")
    assert "retrieval_corpus_identity" in result.missing_properties
    assert "retrieval_chunk_digest" in result.missing_properties
    assert result.profile_satisfied is None


def test_structured_trace_without_contract_cannot_satisfy_claim_profile() -> None:
    """Show that traces alone cannot satisfy a StateWake claim profile."""
    chain = chain_for_workload("rag_answer", omit_contracts=("retrieval_evidence",))
    profile = get_builtin_claim_profile("rag_answer_verified.v1")
    evaluation = evaluate_claim_profile(chain, profile)
    assert evaluation.satisfied is False
    assert "ai-contract:retrieval_evidence" in evaluation.missing_evidence


def test_recovery_workload_preserves_failed_attempt() -> None:
    """Prove recovery inspectability depends on preserving failed-attempt evidence."""
    ok = run_validation_case("incident_recovery", "statewake_full")
    faulty = run_validation_case(
        "incident_recovery",
        "statewake_full",
        ("recovery_without_preserved_failure",),
    )
    assert ok.profile_satisfied is True
    assert faulty.profile_satisfied is False
    assert faulty.detected_faults == ("recovery_without_preserved_failure",)


def test_benchmark_metrics_are_deterministic_for_fixed_fixture() -> None:
    """Prevent flaky research evidence from nondeterministic study output."""
    first = run_comparative_validation_study()
    second = run_comparative_validation_study()
    assert first.digest == second.digest
    assert first.to_dict() == second.to_dict()
    assert len(first.workloads) == 5
    assert len(first.faults) >= 10


def test_ablation_evidence_only_fails_profile_requiring_recovery() -> None:
    """Prove recovery profiles need recovery evidence, not just generic evidence."""
    chain = chain_for_workload("incident_recovery", preserve_failure=False)
    profile = get_builtin_claim_profile("incident_recovery_verified.v1")
    evaluation = evaluate_claim_profile(chain, profile)
    assert evaluation.satisfied is False
    assert "recovery_present" in evaluation.failed_requirements


def test_study_json_and_markdown_are_deterministic() -> None:
    """Ensure study reports are stable and machine-readable."""
    study = run_comparative_validation_study()
    json_report = render_study_json(study)
    markdown_report = render_study_markdown(study)
    parsed = json.loads(json_report)
    assert parsed["digest"] == study.digest
    assert "StateWake Comparative Validation Study" in markdown_report
    assert study.study_id in markdown_report


def test_report_timestamp_rejects_naive_datetime() -> None:
    """Preserve timezone-aware report metadata."""
    assert report_timestamp(datetime(2026, 9, 21, tzinfo=UTC)).endswith("+00:00")
    try:
        report_timestamp(datetime(2026, 9, 21, tzinfo=UTC).replace(tzinfo=None))
    except ValueError as exc:
        assert "timezone-aware" in str(exc)
    else:
        raise AssertionError("naive timestamp should be rejected")
