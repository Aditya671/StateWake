"""Regression tests for the first StateWake human-inspection projection."""

from __future__ import annotations

from statewake.domain.reliability_verification_report import (
    ReliabilityVerificationReport,
)
from statewake.presentation import (
    ReportSourceContext,
    build_claim_detail,
    build_claim_summary,
)


def report(**changes: object) -> ReliabilityVerificationReport:
    """Create a bounded report fixture using only canonical report fields."""
    values: dict[str, object] = {
        "format_version": "1",
        "claim": "RAG answer verified",
        "decision": "review",
        "profile_id": "rag_answer_verified.v1",
        "profile_version": "1",
        "verified": False,
        "evidence_included": ("prompt", "model_invocation"),
        "evidence_omitted": ("raw_prompt",),
        "evidence_missing": ("retrieval_evidence",),
        "checks_passed": ("chain_verified",),
        "checks_failed": ("ai-contract:retrieval_evidence",),
        "checks_unrun": ("environment-check",),
        "checks_unknown": ("external-policy",),
        "source_identities": ("run-1", "prompt-1"),
        "artifact_digests": ("a" * 64,),
        "rationale": ("Recorded evidence is incomplete.",),
        "caveats": ("External correctness is outside this report.",),
        "residual_risks": ("Retrieval evidence is unavailable.",),
        "human_decisions_required": ("Reviewer decision",),
        "allowed_use": ("Engineering inspection",),
        "prohibited_use": ("Automatic approval",),
        "machine_readable_appendix": ("claim_profile_evaluation",),
        "recovery_status": "pending",
        "verifier_version": "statewake-test",
        "generated_at": "2026-09-27T00:00:00+00:00",
        "candidate_identity": "candidate-1",
        "candidate_digest": "b" * 64,
        "report_type": "engineering",
        "profile_evaluation_digest": "c" * 64,
        "approval_status": "requires-human-approval",
    }
    values.update(changes)
    return ReliabilityVerificationReport(**values)  # type: ignore[arg-type]


def test_report_from_dict_round_trip_and_digest_guard() -> None:
    """Canonical JSON deserialization must verify the supplied report digest."""
    original = report()
    restored = ReliabilityVerificationReport.from_dict(original.to_dict())
    assert restored == original

    tampered = original.to_dict()
    tampered["claim"] = "tampered claim"
    try:
        ReliabilityVerificationReport.from_dict(tampered)
    except ValueError as exc:
        assert "digest mismatch" in str(exc)
    else:
        raise AssertionError("tampered report digest was accepted")

    wrong_type = original.to_dict()
    wrong_type["profile_version"] = 1
    try:
        ReliabilityVerificationReport.from_dict(wrong_type)
    except ValueError as exc:
        assert "profile_version must be a JSON string" in str(exc)
    else:
        raise AssertionError("non-string report field was silently coerced")


def test_summary_keeps_verification_evidence_decision_and_approval_separate() -> None:
    """The read model must never collapse StateWake's four semantic axes."""
    payload = build_claim_summary(report()).to_dict()
    assert payload["decision"] == "review"
    assert payload["verification"] == {
        "verified": False,
        "passed": 1,
        "failed": 1,
        "unrun": 1,
        "unknown": 1,
    }
    assert payload["evidence"] == {"included": 2, "omitted": 1, "missing": 1}
    assert payload["human_decision"] == {
        "required": True,
        "approval_status": "requires-human-approval",
        "required_actions": ["Reviewer decision"],
    }
    assert payload["as_of"] is None


def test_summary_preserves_every_canonical_claim_decision_literal() -> None:
    """Presentation must not rewrite accept/review/reject machine decisions."""
    for decision in ("accept", "review", "reject"):
        payload = build_claim_summary(report(decision=decision)).to_dict()
        assert payload["decision"] == decision


def test_summary_reasons_are_only_recorded_source_values() -> None:
    """Summary blockers are deterministic source references, not generated prose."""
    reasons = build_claim_summary(report()).to_dict()["reasons"]
    assert reasons == [
        {
            "kind": "failed-check",
            "source_ref": "ai-contract:retrieval_evidence",
            "text": "ai-contract:retrieval_evidence",
        },
        {
            "kind": "missing-evidence",
            "source_ref": "retrieval_evidence",
            "text": "retrieval_evidence",
        },
        {
            "kind": "unrun-check",
            "source_ref": "environment-check",
            "text": "environment-check",
        },
        {
            "kind": "unknown-check",
            "source_ref": "external-policy",
            "text": "external-policy",
        },
        {
            "kind": "omitted-evidence",
            "source_ref": "raw_prompt",
            "text": "raw_prompt",
        },
    ]


def test_accepted_machine_decision_does_not_become_human_approval() -> None:
    """An accepted claim may still require a distinct human decision."""
    accepted = report(decision="accept")
    payload = build_claim_summary(accepted).to_dict()
    assert payload["decision"] == "accept"
    assert payload["human_decision"] == {
        "required": True,
        "approval_status": "requires-human-approval",
        "required_actions": ["Reviewer decision"],
    }


def test_detail_preserves_canonical_links_and_full_blocker_sets() -> None:
    """The detail model must expose every canonical set used by the UI tabs."""
    source = ReportSourceContext(
        record_id="d" * 64,
        artifact_digest="e" * 64,
        producer_id="statewake.test",
        producer_type="statewake-verification-report",
        captured_at="2026-09-27T00:00:00+00:00",
    )
    payload = build_claim_detail(report(), source).to_dict()
    assert payload["checks"] == {
        "passed": ["chain_verified"],
        "failed": ["ai-contract:retrieval_evidence"],
        "unrun": ["environment-check"],
        "unknown": ["external-policy"],
    }
    assert payload["evidence"] == {
        "included": ["prompt", "model_invocation"],
        "omitted": ["raw_prompt"],
        "missing": ["retrieval_evidence"],
        "source_identities": ["run-1", "prompt-1"],
        "artifact_digests": ["a" * 64],
    }
    assert payload["links"] == {
        "canonical_json": f"/api/v1/reports/{'d' * 64}",
        "canonical_markdown": f"/api/v1/reports/{'d' * 64}/markdown",
    }
