from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from statewake.ai_contracts.prompt import PromptEvidenceContract
from statewake.domain.reliability_verification_report import (
    ReliabilityVerificationReport,
)
from statewake.reports.json_report import render_json_report
from statewake.reports.markdown import render_markdown_report
from statewake.reports.redaction import redacted_payload_reference
from statewake.services.reliability_claim_profile_service import (
    evaluate_claim_profile,
    get_builtin_claim_profile,
)
from tests.test_reliability_claim_profiles import chain


def _report(**changes: object) -> ReliabilityVerificationReport:
    values: dict[str, object] = {
        "format_version": "1",
        "claim": "RAG answer verified",
        "decision": "accept",
        "profile_id": "rag_answer_verified.v1",
        "profile_version": "1",
        "verified": True,
        "candidate_identity": "chain-1",
        "candidate_digest": "a" * 64,
        "report_type": "engineering",
        "evidence_included": ("run", "state", "provenance", "integrity"),
        "evidence_omitted": (),
        "evidence_missing": (),
        "checks_passed": ("chain_verified", "reconciliation_verified"),
        "checks_failed": (),
        "checks_unrun": (),
        "checks_unknown": (),
        "source_identities": ("run-1", "state-1"),
        "artifact_digests": ("a" * 64,),
        "rationale": ("profile requirements were satisfied",),
        "caveats": ("Does not approve production use.",),
        "residual_risks": ("External correctness remains outside the report.",),
        "human_decisions_required": ("Review release readiness",),
        "allowed_use": ("Human inspection",),
        "prohibited_use": ("Automatic approval",),
        "machine_readable_appendix": ("claim_profile_evaluation",),
        "recovery_status": "verified",
        "verifier_version": "statewake-test",
        "generated_at": "2026-09-21T00:00:00+00:00",
        "profile_evaluation_digest": "b" * 64,
        "approval_status": "requires-human-approval",
    }
    values.update(changes)
    return ReliabilityVerificationReport(**values)  # type: ignore[arg-type]


def test_report_includes_candidate_identity_and_digest() -> None:
    report = _report(candidate_identity="chain-a", candidate_digest="c" * 64)
    payload = report.to_dict()
    text = render_markdown_report(report)
    assert payload["candidate_identity"] == "chain-a"
    assert payload["candidate_digest"] == "c" * 64
    assert "Candidate identity" in text
    assert "chain-a" in text


def test_report_separates_pass_fail_unrun_unknown() -> None:
    report = _report(
        verified=False,
        checks_passed=("syntax",),
        checks_failed=("profile_missing_evidence",),
        checks_unrun=("mypy",),
        checks_unknown=("external_security_gate",),
        evidence_missing=("retrieval_evidence",),
    )
    text = render_markdown_report(report)
    assert "PASS" in text
    assert "FAIL" in text
    assert "UNRUN-ENV" in text
    assert "UNKNOWN" in text


def test_report_marks_missing_evidence_as_missing_not_passed() -> None:
    report = _report(
        verified=False,
        evidence_missing=("retrieval_evidence",),
        checks_passed=("chain_verified",),
        checks_failed=("ai-contract:retrieval_evidence",),
    )
    payload = report.to_dict()
    assert "retrieval_evidence" in payload["evidence_missing"]
    assert "retrieval_evidence" not in payload["checks_passed"]


def test_report_rejects_check_that_is_both_passed_and_failed() -> None:
    with pytest.raises(ValueError, match="both passed and blocked"):
        _report(
            verified=False,
            checks_passed=("chain_verified",),
            checks_failed=("chain_verified",),
        )


def test_report_redacts_sensitive_payload_but_preserves_digest() -> None:
    payload = {
        "raw_prompt": "customer secret",
        "rendered_prompt_digest": "d" * 64,
        "source": "fixture",
    }
    redacted = redacted_payload_reference(payload)
    assert redacted["visible"]["raw_prompt"] == "<redacted>"
    assert redacted["visible"]["rendered_prompt_digest"] == "d" * 64
    assert redacted["payload_digest"]


def test_report_links_profile_evaluation_to_evidence_ids() -> None:
    profile = get_builtin_claim_profile("rag_answer_verified.v1")
    result = evaluate_claim_profile(chain(), profile)
    report = _report(
        source_identities=tuple(sorted(result.missing_evidence)) + ("run-1",),
        profile_evaluation_digest="e" * 64,
    )
    assert report.profile_evaluation_digest == "e" * 64
    assert "run-1" in report.source_identities


def test_business_report_distinguishes_decision_from_approval() -> None:
    report = _report(
        report_type="business",
        decision="accept",
        approval_status="requires-human-approval",
        human_decisions_required=("Business owner release decision",),
    )
    text = render_markdown_report(report)
    assert "StateWake decision: `accept`" in text
    assert "Approval status: `requires-human-approval`" in text
    assert "Business owner release decision" in text


def test_incident_report_preserves_failed_attempt_and_recovery() -> None:
    report = _report(
        claim="Incident recovery verified",
        report_type="incident-recovery",
        decision="accept",
        recovery_status="recovered",
        source_identities=("failed-run-1", "recovery-run-1"),
        machine_readable_appendix=("failed_attempt", "post_recovery_state"),
    )
    text = render_markdown_report(report)
    assert "failed-run-1" in text
    assert "recovery-run-1" in text
    assert "post_recovery_state" in text


def test_markdown_report_is_deterministic_for_same_input() -> None:
    first = render_markdown_report(_report())
    second = render_markdown_report(_report())
    assert first == second


def test_json_report_is_deterministic_for_same_input() -> None:
    first = render_json_report(_report())
    second = render_json_report(_report())
    assert json.loads(first) == json.loads(second)


def test_phase1_contract_can_feed_phase2_profile_and_phase3_report() -> None:
    contract = PromptEvidenceContract(
        contract_version="1",
        producer_id="producer-1",
        run_id="run-1",
        prompt_template_id="template-1",
        prompt_template_version="1",
        rendered_prompt_digest="f" * 64,
        variables_digest="1" * 64,
        redaction_policy_id="digest-only",
        source="unit-test",
        captured_at=datetime(2026, 9, 21, 0, 0, 0, tzinfo=UTC),
    )
    evidence = contract.to_evidence_item()
    profile = get_builtin_claim_profile("rag_answer_verified.v1")
    evaluation = evaluate_claim_profile(chain(), profile)
    report = _report(
        source_identities=(evidence.evidence_id,),
        profile_evaluation_digest="2" * 64,
        checks_passed=evaluation.passed_conditions,
        caveats=evaluation.caveats or ("No additional profile caveats.",),
    )
    assert evidence.metadata["contract_type"] == "prompt"
    assert report.verified
