"""Tests for the optional local read-only StateWake application API."""

from __future__ import annotations

import io
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from statewake.adapters.deployment_security import SecurityEvent
from statewake.adapters.incident_evidence import JsonlIncidentEvidenceStore
from statewake.adapters.security_audit import JsonlSecurityAuditStore
from statewake.domain.reliability_verification_report import (
    ReliabilityVerificationReport,
)
from statewake.domain.runtime_containment import RuntimeContainmentLimits
from statewake.domain.security_incident import (
    AffectedTrustState,
    IncidentEvidenceReference,
    PostRecoveryVerification,
    RecoveryEvidence,
    SecurityIncidentEvidence,
    derive_incident_id,
)
from statewake.read_api import ReadApiConfig, create_read_application
from statewake.reports.json_report import render_json_report
from statewake.services.runtime_containment_snapshot_service import (
    RuntimeContainmentConfigSnapshot,
    write_runtime_containment_snapshot,
)
from statewake.workspace.workspace import StateWakeWorkspace


def _report(**changes: object) -> ReliabilityVerificationReport:
    values: dict[str, object] = {
        "format_version": "1",
        "claim": "RAG answer verified",
        "decision": "accept",
        "profile_id": "rag_answer_verified.v1",
        "profile_version": "1",
        "verified": True,
        "evidence_included": ("run", "retrieval"),
        "evidence_omitted": (),
        "evidence_missing": (),
        "checks_passed": ("chain_verified", "reconciliation_verified"),
        "checks_failed": (),
        "checks_unrun": (),
        "checks_unknown": (),
        "source_identities": ("run-1", "retrieval-1"),
        "artifact_digests": ("a" * 64,),
        "rationale": ("Recorded requirements were satisfied.",),
        "caveats": ("Does not approve production use.",),
        "residual_risks": ("External correctness remains outside the report.",),
        "human_decisions_required": ("Review release readiness",),
        "allowed_use": ("Human inspection",),
        "prohibited_use": ("Automatic approval",),
        "machine_readable_appendix": ("claim_profile_evaluation",),
        "recovery_status": "verified",
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


def _workspace_report(
    tmp_path: Path,
) -> tuple[Path, str, ReliabilityVerificationReport]:
    root = tmp_path / "workspace"
    workspace = StateWakeWorkspace.open(root)
    report = _report()
    record = workspace.ingest(
        render_json_report(report).encode("utf-8"),
        producer_type="statewake-verification-report",
        producer_id="statewake.test",
        source_ref="report.json",
        source_event_id="report-1",
        run_id="run-1",
        captured_at=datetime(2026, 9, 27, tzinfo=UTC),
        metadata={"candidate_identity": report.candidate_identity},
    )
    workspace.verify(record)
    workspace.close()
    return root, record.record_id, report


def _request(
    application: Any,
    path: str,
    method: str = "GET",
    *,
    if_none_match: str | None = None,
    query_string: str = "",
) -> tuple[str, dict[str, str], bytes]:
    environ: dict[str, object] = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": query_string,
        "CONTENT_LENGTH": "0",
        "wsgi.input": io.BytesIO(b""),
        "wsgi.url_scheme": "http",
    }
    if if_none_match is not None:
        environ["HTTP_IF_NONE_MATCH"] = if_none_match
    captured: dict[str, object] = {}

    def start_response(status: str, headers: list[tuple[str, str]]) -> None:
        captured["status"] = status
        captured["headers"] = headers

    raw = b"".join(application(environ, start_response))
    captured_headers = captured.get("headers")
    assert isinstance(captured_headers, list)
    headers = dict(captured_headers)
    return str(captured["status"]), headers, raw


def test_capabilities_report_current_read_only_surface(tmp_path: Path) -> None:
    root, _, _ = _workspace_report(tmp_path)
    application = create_read_application(ReadApiConfig(root))
    status, _, raw = _request(application, "/api/v1/capabilities")
    payload = json.loads(raw)
    assert status == "200 OK"
    assert payload["mode"] == "local-read-only"
    assert payload["features"] == {
        "approval_write": False,
        "attestation_trust_read": False,
        "canonical_json": True,
        "canonical_markdown": True,
        "capture_health_read": False,
        "security_assurance_read": False,
        "assurance_decision_read": False,
        "authorization_policy_read": False,
        "claim_detail": True,
        "claim_list": True,
        "claim_summary": True,
        "comparison_read": True,
        "decision_lineage_read": False,
        "data_governance_read": False,
        "evidence_trace": True,
        "history_read": False,
        "incident_investigation_read": False,
        "overview_aggregates": True,
        "publication_authorization_read": False,
        "release_trust_read": False,
        "reliability_proof_read": False,
        "validation_study_read": False,
        "workspace_operations_read": True,
        "review_read": False,
        "review_write": False,
    }


def test_claim_detail_and_summary_are_backed_by_same_report_digest(
    tmp_path: Path,
) -> None:
    root, record_id, report = _workspace_report(tmp_path)
    application = create_read_application(ReadApiConfig(root))

    status, headers, raw = _request(application, f"/api/v1/claims/{record_id}")
    detail = json.loads(raw)
    assert status == "200 OK"
    assert headers["ETag"] == f'"{report.digest}"'
    assert detail["summary"]["report_digest"] == report.digest
    assert detail["summary"]["candidate"] == {
        "id": report.candidate_identity,
        "digest": report.candidate_digest,
    }
    assert detail["summary"]["decision"] == "accept"
    assert detail["summary"]["human_decision"]["approval_status"] == (
        "requires-human-approval"
    )

    status, _, raw = _request(application, f"/api/v1/claims/{record_id}/summary")
    summary = json.loads(raw)
    assert status == "200 OK"
    assert summary == detail["summary"]


def test_canonical_json_and_markdown_use_the_same_authoritative_report(
    tmp_path: Path,
) -> None:
    root, record_id, report = _workspace_report(tmp_path)
    application = create_read_application(ReadApiConfig(root))

    status, _, raw = _request(application, f"/api/v1/reports/{record_id}")
    assert status == "200 OK"
    assert json.loads(raw) == report.to_dict()

    status, headers, raw = _request(
        application, f"/api/v1/reports/{record_id}/markdown"
    )
    assert status == "200 OK"
    assert headers["Content-Type"] == "text/markdown; charset=utf-8"
    text = raw.decode("utf-8")
    assert report.candidate_identity in text
    assert f"Report digest: `{report.digest}`" in text


def test_read_api_honors_digest_conditional_request(tmp_path: Path) -> None:
    root, record_id, report = _workspace_report(tmp_path)
    application = create_read_application(ReadApiConfig(root))
    status, headers, raw = _request(
        application,
        f"/api/v1/claims/{record_id}",
        if_none_match=f'"{report.digest}"',
    )
    assert status == "304 Not Modified"
    assert headers["ETag"] == f'"{report.digest}"'
    assert raw == b""


def test_read_api_rejects_write_methods(tmp_path: Path) -> None:
    root, record_id, _ = _workspace_report(tmp_path)
    application = create_read_application(ReadApiConfig(root))
    status, _, raw = _request(application, f"/api/v1/claims/{record_id}", method="POST")
    assert status == "405 Method Not Allowed"
    assert json.loads(raw)["error"]["code"] == "READ_ONLY"


def test_read_api_rejects_tampered_content_addressed_report(tmp_path: Path) -> None:
    root, record_id, _ = _workspace_report(tmp_path)
    receipt = json.loads((root / "receipts" / f"{record_id}.json").read_text())
    digest = str(receipt["artifact_digest"])
    artifact = root / "artifacts" / digest[:2] / digest[2:]
    artifact.write_text("{}", encoding="utf-8")

    application = create_read_application(ReadApiConfig(root))
    status, _, raw = _request(application, f"/api/v1/claims/{record_id}")
    assert status == "422 Unprocessable Entity"
    assert json.loads(raw)["error"]["code"] == "INVALID_REPORT"


def test_read_api_rejects_report_digest_tampering_even_if_artifact_receipt_matches(
    tmp_path: Path,
) -> None:
    root, _, report = _workspace_report(tmp_path)
    tampered = report.to_dict()
    tampered["claim"] = "Tampered but re-ingested report"
    workspace = StateWakeWorkspace.open(root)
    record = workspace.ingest(
        (json.dumps(tampered, sort_keys=True) + "\n").encode("utf-8"),
        producer_type="statewake-verification-report",
        producer_id="statewake.test",
        source_ref="tampered-report.json",
        source_event_id="report-tampered",
        captured_at=datetime(2026, 9, 27, 1, tzinfo=UTC),
    )
    workspace.close()

    application = create_read_application(ReadApiConfig(root))
    status, _, raw = _request(application, f"/api/v1/claims/{record.record_id}")
    assert status == "422 Unprocessable Entity"
    assert json.loads(raw)["error"]["code"] == "INVALID_REPORT"


def test_read_api_is_side_effect_free_for_existing_workspace(tmp_path: Path) -> None:
    """Read requests must not mutate or repair the existing workspace."""
    root, record_id, _ = _workspace_report(tmp_path)

    def snapshot() -> dict[str, tuple[int, int, bytes]]:
        return {
            path.relative_to(root).as_posix(): (
                path.stat().st_size,
                path.stat().st_mtime_ns,
                path.read_bytes(),
            )
            for path in root.rglob("*")
            if path.is_file()
        }

    before = snapshot()
    application = create_read_application(ReadApiConfig(root))
    status, _, _ = _request(application, f"/api/v1/claims/{record_id}")
    assert status == "200 OK"
    assert snapshot() == before


def test_read_api_enforces_report_size_limit(tmp_path: Path) -> None:
    """Oversized report artifacts must fail closed before presentation."""
    root, record_id, _ = _workspace_report(tmp_path)
    application = create_read_application(ReadApiConfig(root, max_report_bytes=1))
    status, _, raw = _request(application, f"/api/v1/claims/{record_id}")
    assert status == "413 Request Entity Too Large"
    assert json.loads(raw)["error"]["code"] == "REPORT_TOO_LARGE"


def test_read_api_rejects_malformed_record_identity(tmp_path: Path) -> None:
    """Only canonical lowercase SHA-256 receipt identities are addressable."""
    root, _, _ = _workspace_report(tmp_path)
    application = create_read_application(ReadApiConfig(root))
    status, _, raw = _request(application, "/api/v1/claims/not-a-record-id")
    assert status == "422 Unprocessable Entity"
    assert json.loads(raw)["error"]["code"] == "INVALID_REPORT"


def test_read_api_classifies_invalid_workspace_manifest_as_unavailable(
    tmp_path: Path,
) -> None:
    """Workspace corruption must not be mislabeled as an invalid report."""
    root, record_id, _ = _workspace_report(tmp_path)
    (root / "manifest.json").write_text("{}", encoding="utf-8")

    application = create_read_application(ReadApiConfig(root))
    status, _, raw = _request(application, f"/api/v1/claims/{record_id}")
    assert status == "503 Service Unavailable"
    assert json.loads(raw)["error"]["code"] == "WORKSPACE_UNAVAILABLE"


def test_read_api_classifies_missing_required_report_field_as_invalid_report(
    tmp_path: Path,
) -> None:
    """Malformed canonical report content must fail as an invalid record."""
    root, _, report = _workspace_report(tmp_path)
    malformed = report.to_dict()
    del malformed["claim"]
    workspace = StateWakeWorkspace.open(root)
    record = workspace.ingest(
        (json.dumps(malformed, sort_keys=True) + "\n").encode("utf-8"),
        producer_type="statewake-verification-report",
        producer_id="statewake.test",
        source_ref="missing-field-report.json",
        source_event_id="report-missing-field",
        captured_at=datetime(2026, 9, 27, 2, tzinfo=UTC),
    )
    workspace.close()

    application = create_read_application(ReadApiConfig(root))
    status, _, raw = _request(application, f"/api/v1/claims/{record.record_id}")
    assert status == "422 Unprocessable Entity"
    assert json.loads(raw)["error"]["code"] == "INVALID_REPORT"


def _write_history(path: Path, report: ReliabilityVerificationReport) -> None:
    """Write one canonical state transition bound to a report candidate."""
    from statewake.domain.reliability_state import ReliabilityStateTransition

    transition = ReliabilityStateTransition(
        transition_id="transition-1",
        subject_id="agent-1",
        from_state="unknown",
        to_state="reliable",
        occurred_at=datetime(2026, 9, 27, 0, 30, tzinfo=UTC),
        actor="engine",
        evidence_chain_id=report.candidate_identity,
        evidence_chain_digest=report.candidate_digest,
        decision="accept",
        rationale=("recorded state transition",),
    )
    path.write_text(
        json.dumps(transition.to_dict(), sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def test_capabilities_expose_comparison_and_optional_history(tmp_path: Path) -> None:
    root, _, _ = _workspace_report(tmp_path)
    without_history = create_read_application(ReadApiConfig(root))
    _, _, raw = _request(without_history, "/api/v1/capabilities")
    features = json.loads(raw)["features"]
    assert features["comparison_read"] is True
    assert features["history_read"] is False

    history_path = tmp_path / "history.jsonl"
    with_history = create_read_application(
        ReadApiConfig(root, history_path=history_path)
    )
    _, _, raw = _request(with_history, "/api/v1/capabilities")
    assert json.loads(raw)["features"]["history_read"] is True


def test_history_reads_exact_candidate_binding_without_mutating_store(
    tmp_path: Path,
) -> None:
    root, record_id, report = _workspace_report(tmp_path)
    history_path = tmp_path / "history.jsonl"
    _write_history(history_path, report)
    before = history_path.read_bytes()
    application = create_read_application(
        ReadApiConfig(root, history_path=history_path)
    )

    status, headers, raw = _request(application, f"/api/v1/claims/{record_id}/history")
    payload = json.loads(raw)
    assert status == "200 OK"
    assert headers["ETag"].startswith('"')
    assert b"SYNTHETIC_SECRET_MUST_NOT_REACH_CATALOG" not in raw
    assert payload["recorded_count"] == 1
    assert payload["items"][0]["evidence_chain_id"] == report.candidate_identity
    assert payload["items"][0]["evidence_chain_digest"] == report.candidate_digest
    assert history_path.read_bytes() == before
    assert not history_path.with_name(f".{history_path.name}.lock").exists()


def test_history_is_explicitly_unavailable_when_not_configured(tmp_path: Path) -> None:
    root, record_id, _ = _workspace_report(tmp_path)
    application = create_read_application(ReadApiConfig(root))
    status, _, raw = _request(application, f"/api/v1/claims/{record_id}/history")
    assert status == "404 Not Found"
    assert json.loads(raw)["error"]["code"] == "HISTORY_NOT_CONFIGURED"


def test_history_rejects_candidate_identity_digest_collision(tmp_path: Path) -> None:
    root, record_id, report = _workspace_report(tmp_path)
    history_path = tmp_path / "history.jsonl"
    from statewake.domain.reliability_state import ReliabilityStateTransition

    transition = ReliabilityStateTransition(
        transition_id="transition-1",
        subject_id="agent-1",
        from_state="unknown",
        to_state="reliable",
        occurred_at=datetime(2026, 9, 27, 0, 30, tzinfo=UTC),
        actor="engine",
        evidence_chain_id=report.candidate_identity,
        evidence_chain_digest="f" * 64,
        decision="accept",
    )
    history_path.write_text(
        json.dumps(transition.to_dict(), sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    application = create_read_application(
        ReadApiConfig(root, history_path=history_path)
    )
    status, _, raw = _request(application, f"/api/v1/claims/{record_id}/history")
    assert status == "422 Unprocessable Entity"
    assert json.loads(raw)["error"]["code"] == "INVALID_HISTORY"


def test_history_limit_fails_closed_with_specific_error(tmp_path: Path) -> None:
    root, record_id, report = _workspace_report(tmp_path)
    history_path = tmp_path / "history.jsonl"
    _write_history(history_path, report)
    application = create_read_application(
        ReadApiConfig(root, history_path=history_path, max_history_bytes=1)
    )
    status, _, raw = _request(application, f"/api/v1/claims/{record_id}/history")
    assert status == "413 Request Entity Too Large"
    assert json.loads(raw)["error"]["code"] == "HISTORY_TOO_LARGE"


def test_direct_comparison_reports_recorded_changes_and_scope(tmp_path: Path) -> None:
    root, left_id, left = _workspace_report(tmp_path)
    right = _report(
        decision="review",
        verified=False,
        evidence_included=("run",),
        checks_failed=("retrieval",),
        evidence_missing=("retrieval",),
        candidate_digest="e" * 64,
    )
    workspace = StateWakeWorkspace.open(root)
    right_record = workspace.ingest(
        render_json_report(right).encode("utf-8"),
        producer_type="statewake-verification-report",
        producer_id="statewake.test",
        source_ref="report-right.json",
        source_event_id="report-right",
        run_id="run-2",
        captured_at=datetime(2026, 9, 27, 1, tzinfo=UTC),
        metadata={"candidate_identity": right.candidate_identity},
    )
    workspace.close()
    application = create_read_application(ReadApiConfig(root))
    status, _, raw = _request(
        application,
        f"/api/v1/claims/{left_id}/compare/{right_record.record_id}",
    )
    payload = json.loads(raw)
    assert status == "200 OK"
    assert payload["semantic_scope_same"] is True
    assert payload["changes"]["candidate_digest_changed"] is True
    assert payload["changes"]["decision"] == {
        "before": left.decision,
        "after": right.decision,
        "changed": True,
    }
    assert payload["limitations"]


def test_overview_cards_are_report_scoped_and_hand_countable(tmp_path: Path) -> None:
    """Aggregate only canonical verification-report records with explicit semantics."""
    root = tmp_path / "workspace"
    workspace = StateWakeWorkspace.open(root)
    reports = (
        _report(
            claim="Verified claim",
            decision="accept",
            verified=True,
            approval_status="approved",
            human_decisions_required=("Release owner approved",),
        ),
        _report(
            claim="Needs human decision",
            decision="review",
            verified=False,
            checks_unrun=("human-review",),
            evidence_missing=(),
            approval_status="requires-human-approval",
        ),
        _report(
            claim="Missing retrieval",
            decision="review",
            verified=False,
            evidence_included=("run",),
            evidence_missing=("retrieval",),
            checks_unrun=(),
            approval_status="requires-human-approval",
        ),
    )
    ids: list[str] = []
    for index, report in enumerate(reports):
        record = workspace.ingest(
            render_json_report(report).encode("utf-8"),
            producer_type="statewake-verification-report",
            producer_id="statewake.test",
            source_ref=f"report-{index}.json",
            source_event_id=f"report-{index}",
            run_id=f"run-{index}",
            captured_at=datetime(2026, 9, 27, index, tzinfo=UTC),
            metadata={"candidate_identity": report.candidate_identity},
        )
        workspace.verify(record)
        ids.append(record.record_id)
    workspace.ingest(
        b'{"not":"a report"}',
        producer_type="statewake-human-approval",
        producer_id="statewake.test",
        source_ref="approval.json",
        source_event_id="approval-1",
        run_id="approval-run-1",
        captured_at=datetime(2026, 9, 27, 4, tzinfo=UTC),
        metadata={"contract_type": "human_approval"},
    )
    workspace.close()

    application = create_read_application(ReadApiConfig(root))
    status, headers, raw = _request(application, "/api/v1/overview")
    payload = json.loads(raw)

    assert status == "200 OK"
    assert payload["scope"] == {
        "resource": "verification-report-records",
        "denominator": 3,
        "deduplication_key": "workspace receipt id",
    }
    assert payload["metrics"] == {
        "reports_evaluated": 3,
        "verified_reports": 1,
        "reports_missing_evidence": 1,
        "human_decisions_pending": 2,
    }
    assert payload["decisions"] == {
        "accept": 1,
        "review": 2,
        "reject": 0,
        "other": 0,
    }
    assert [item["record_id"] for item in payload["recent_reports"]] == list(
        reversed(ids)
    )
    assert headers["ETag"].startswith('"')


def test_overview_is_empty_not_fabricated_when_no_reports_exist(tmp_path: Path) -> None:
    """Return explicit zero denominators instead of illustrative dashboard values."""
    root = tmp_path / "workspace"
    workspace = StateWakeWorkspace.open(root)
    workspace.close()
    application = create_read_application(ReadApiConfig(root))

    status, _, raw = _request(application, "/api/v1/overview")
    payload = json.loads(raw)
    assert status == "200 OK"
    assert payload["scope"]["denominator"] == 0
    assert payload["metrics"] == {
        "reports_evaluated": 0,
        "verified_reports": 0,
        "reports_missing_evidence": 0,
        "human_decisions_pending": 0,
    }
    assert payload["recent_reports"] == []
    assert payload["as_of"] is None


def test_overview_fails_closed_when_report_receipt_is_tampered(tmp_path: Path) -> None:
    """Never silently omit a broken report receipt to make dashboard counts look clean."""
    root, record_id, _ = _workspace_report(tmp_path)
    receipt_path = root / "receipts" / f"{record_id}.json"
    receipt_path.write_text("{}", encoding="utf-8")
    application = create_read_application(ReadApiConfig(root))

    status, _, raw = _request(application, "/api/v1/overview")
    payload = json.loads(raw)
    assert status == "503 Service Unavailable"
    assert payload["error"]["code"] == "WORKSPACE_UNAVAILABLE"


def _workspace_report_with_evidence(
    tmp_path: Path,
) -> tuple[Path, str, ReliabilityVerificationReport, str, str]:
    """Create a report whose recorded identities resolve to real workspace evidence."""
    root = tmp_path / "workspace-evidence"
    workspace = StateWakeWorkspace.open(root)
    evidence = workspace.ingest(
        b'{"retrieval":"alpha-policy-v1"}',
        producer_type="retrieval",
        producer_id="statewake.test.retriever",
        source_ref="retrieval.json",
        source_event_id="retrieval-1",
        run_id="run-1",
        captured_at=datetime(2026, 9, 27, 0, 5, tzinfo=UTC),
        metadata={"authorization": "Bearer SYNTHETIC_SECRET_NEVER_EXPOSE"},
    )
    report = _report(
        source_identities=(evidence.record_id, "retrieval-1", "not-resolved"),
        artifact_digests=(evidence.artifact_digest, "f" * 64),
        evidence_missing=("policy-approval",),
        verified=False,
        decision="review",
    )
    report_record = workspace.ingest(
        render_json_report(report).encode("utf-8"),
        producer_type="statewake-verification-report",
        producer_id="statewake.test",
        source_ref="report.json",
        source_event_id="report-evidence",
        run_id="report-run-1",
        captured_at=datetime(2026, 9, 27, 0, 10, tzinfo=UTC),
        metadata={"candidate_identity": report.candidate_identity},
    )
    workspace.verify(evidence)
    workspace.verify(report_record)
    workspace.close()
    return (
        root,
        report_record.record_id,
        report,
        evidence.record_id,
        evidence.artifact_digest,
    )


def test_evidence_trace_resolves_recorded_workspace_relationships(
    tmp_path: Path,
) -> None:
    root, report_id, report, evidence_id, evidence_digest = (
        _workspace_report_with_evidence(tmp_path)
    )
    application = create_read_application(ReadApiConfig(root))

    status, headers, raw = _request(application, f"/api/v1/claims/{report_id}/evidence")
    payload = json.loads(raw)

    assert status == "200 OK"
    assert headers["ETag"].startswith('"')
    assert payload["schema_version"] == "evidence-trace.v2"
    assert payload["report_record_id"] == report_id
    assert payload["report_digest"] == report.digest
    assert payload["workspace_scan"]["complete"] is True

    workspace_node = next(
        node
        for node in payload["nodes"]
        if node["kind"] == "workspace-record" and node["record_id"] == evidence_id
    )
    assert workspace_node["digest"] == evidence_digest
    assert workspace_node["integrity_status"] == "verified"
    assert workspace_node["receipt_integrity_status"] == "verified"
    assert workspace_node["artifact_integrity_status"] == "verified"
    assert workspace_node["admission_status"] == "verified"
    assert len(workspace_node["receipt_digest"]) == 64
    assert len(workspace_node["admission_digest"]) == 64
    assert workspace_node["producer_authentication_status"] == "not-recorded"
    assert payload["assurance_summary"] == {
        "receipts_resolved": 1,
        "receipt_integrity_verified": 1,
        "artifact_integrity_verified": 1,
        "admission_verified": 1,
    }
    assert payload["producer_authentication"]["status"] == "not-recorded"
    assert payload["producer_authentication"]["authenticated"] is None
    assert any(
        edge["relationship_type"] == "resolves-to-workspace-record"
        for edge in payload["edges"]
    )
    assert any(
        edge["relationship_type"] == "verified-by-evidence-admission"
        for edge in payload["edges"]
    )
    assert any(item["identity"] == "not-resolved" for item in payload["unresolved"])
    assert any(
        item["identity"] == "policy-approval" and item["kind"] == "missing-evidence"
        for item in payload["unresolved"]
    )
    assert b"SYNTHETIC_SECRET_NEVER_EXPOSE" not in raw

    cached_status, cached_headers, cached_raw = _request(
        application,
        f"/api/v1/claims/{report_id}/evidence",
        if_none_match=headers["ETag"],
    )
    assert cached_status == "304 Not Modified"
    assert cached_headers["ETag"] == headers["ETag"]
    assert cached_raw == b""


def test_evidence_trace_reports_tampered_related_artifact_as_invalid(
    tmp_path: Path,
) -> None:
    root, report_id, _, evidence_id, evidence_digest = _workspace_report_with_evidence(
        tmp_path
    )
    artifact = root / "artifacts" / evidence_digest[:2] / evidence_digest[2:]
    artifact.write_bytes(b"tampered")
    application = create_read_application(ReadApiConfig(root))

    status, _, raw = _request(application, f"/api/v1/claims/{report_id}/evidence")
    payload = json.loads(raw)

    assert status == "200 OK"
    node = next(
        item
        for item in payload["nodes"]
        if item["kind"] == "workspace-record" and item["record_id"] == evidence_id
    )
    assert node["integrity_status"] == "invalid"
    assert node["artifact_integrity_status"] == "invalid"
    assert node["admission_status"] == "invalid"
    assert node["admission_digest"] is None
    assert payload["assurance_summary"]["receipt_integrity_verified"] == 1
    assert payload["assurance_summary"]["artifact_integrity_verified"] == 0
    assert payload["assurance_summary"]["admission_verified"] == 0


def test_evidence_trace_reports_missing_related_artifact_as_unavailable(
    tmp_path: Path,
) -> None:
    root, report_id, _, evidence_id, evidence_digest = _workspace_report_with_evidence(
        tmp_path
    )
    artifact = root / "artifacts" / evidence_digest[:2] / evidence_digest[2:]
    artifact.unlink()
    application = create_read_application(ReadApiConfig(root))

    status, _, raw = _request(application, f"/api/v1/claims/{report_id}/evidence")
    payload = json.loads(raw)

    assert status == "200 OK"
    node = next(
        item
        for item in payload["nodes"]
        if item["kind"] == "workspace-record" and item["record_id"] == evidence_id
    )
    assert node["integrity_status"] == "unavailable"
    assert node["artifact_integrity_status"] == "unavailable"
    assert node["admission_status"] == "unavailable"
    assert node["availability"] == "missing"
    assert payload["assurance_summary"]["artifact_integrity_verified"] == 0
    assert payload["assurance_summary"]["admission_verified"] == 0


def test_evidence_trace_marks_bounded_workspace_resolution_as_partial(
    tmp_path: Path,
) -> None:
    root, report_id, _, _, _ = _workspace_report_with_evidence(tmp_path)
    application = create_read_application(ReadApiConfig(root, max_evidence_receipts=1))

    status, _, raw = _request(application, f"/api/v1/claims/{report_id}/evidence")
    payload = json.loads(raw)

    assert status == "200 OK"
    assert payload["workspace_scan"]["complete"] is False
    assert any(
        item["reason"] == "not resolved within the bounded workspace receipt scan"
        for item in payload["unresolved"]
    )
    assert any("partial" in item for item in payload["limitations"])


def test_evidence_trace_fails_closed_when_node_bound_is_exceeded(
    tmp_path: Path,
) -> None:
    root, report_id, _, _, _ = _workspace_report_with_evidence(tmp_path)
    application = create_read_application(ReadApiConfig(root, max_evidence_nodes=2))

    status, _, raw = _request(application, f"/api/v1/claims/{report_id}/evidence")

    assert status == "413 Request Entity Too Large"
    assert json.loads(raw)["error"]["code"] == "EVIDENCE_TRACE_TOO_LARGE"


def _catalog_workspace(tmp_path: Path) -> tuple[Path, list[str]]:
    """Create canonical reports with distinct discovery fields and one non-report."""
    root = tmp_path / "catalog-workspace"
    workspace = StateWakeWorkspace.open(root)
    reports = (
        _report(
            claim="RAG answer verified for alpha policy",
            decision="accept",
            verified=True,
            approval_status="approved",
            profile_id="rag_answer_verified.v1",
            candidate_identity="candidate-alpha",
        ),
        _report(
            claim="Tool action requires approval",
            decision="review",
            verified=False,
            checks_unrun=("human-review",),
            approval_status="requires-human-approval",
            profile_id="tool_action_authorized.v1",
            candidate_identity="candidate-tool",
        ),
        _report(
            claim="Release evidence rejected",
            decision="reject",
            verified=False,
            checks_failed=("release-signature",),
            evidence_missing=("signature",),
            approval_status="not-approval",
            profile_id="release_evidence_complete.v1",
            candidate_identity="candidate-release",
        ),
    )
    record_ids: list[str] = []
    for index, report in enumerate(reports):
        record = workspace.ingest(
            render_json_report(report).encode("utf-8"),
            producer_type="statewake-verification-report",
            producer_id="statewake.test",
            source_ref=f"report-{index}.json",
            source_event_id=f"report-{index}",
            run_id=f"run-{index}",
            captured_at=datetime(2026, 9, 28, index, tzinfo=UTC),
            metadata={
                "candidate_identity": report.candidate_identity,
                "api_key": "SYNTHETIC_SECRET_MUST_NOT_REACH_CATALOG",
            },
        )
        workspace.verify(record)
        record_ids.append(record.record_id)
    workspace.ingest(
        b'{"ordinary":"evidence"}',
        producer_type="retrieval",
        producer_id="statewake.test",
        source_ref="retrieval.json",
        source_event_id="retrieval-1",
        captured_at=datetime(2026, 9, 28, 4, tzinfo=UTC),
    )
    workspace.close()
    return root, record_ids


def test_claim_catalog_lists_only_canonical_reports_with_exact_scope(
    tmp_path: Path,
) -> None:
    root, record_ids = _catalog_workspace(tmp_path)
    application = create_read_application(ReadApiConfig(root))

    status, headers, raw = _request(application, "/api/v1/claims")
    payload = json.loads(raw)

    assert status == "200 OK"
    assert payload["schema_version"] == "claim-catalog.v1"
    assert payload["scope"] == {
        "resource": "verification-report-records",
        "deduplication_key": "workspace receipt id",
        "sort": "captured_at_desc_record_id_asc",
        "scanned_receipts": 4,
        "total_reports": 3,
        "matched_reports": 3,
    }
    assert [item["record_id"] for item in payload["items"]] == list(
        reversed(record_ids)
    )
    assert payload["page"] == {
        "limit": 50,
        "offset": 0,
        "returned": 3,
        "has_more": False,
        "next_offset": None,
    }
    assert headers["ETag"].startswith('"')


def test_claim_catalog_filters_and_paginates_without_raw_workspace_query(
    tmp_path: Path,
) -> None:
    root, record_ids = _catalog_workspace(tmp_path)
    application = create_read_application(ReadApiConfig(root))

    status, _, raw = _request(
        application,
        "/api/v1/claims",
        query_string="decision=review&verified=false&limit=1&offset=0",
    )
    payload = json.loads(raw)
    assert status == "200 OK"
    assert payload["scope"]["matched_reports"] == 1
    assert payload["items"][0]["record_id"] == record_ids[1]
    assert payload["query"]["decision"] == "review"
    assert payload["query"]["verified"] is False

    status, _, raw = _request(
        application,
        "/api/v1/claims",
        query_string="q=release&profile_id=release_evidence_complete.v1",
    )
    payload = json.loads(raw)
    assert status == "200 OK"
    assert [item["record_id"] for item in payload["items"]] == [record_ids[2]]


def test_claim_catalog_candidate_and_approval_filters_are_exact(tmp_path: Path) -> None:
    root, record_ids = _catalog_workspace(tmp_path)
    application = create_read_application(ReadApiConfig(root))
    query = "candidate_id=candidate-tool&approval_status=requires-human-approval"
    status, _, raw = _request(application, "/api/v1/claims", query_string=query)
    payload = json.loads(raw)
    assert status == "200 OK"
    assert [item["record_id"] for item in payload["items"]] == [record_ids[1]]


def test_claim_catalog_returns_empty_page_without_fabricating_matches(
    tmp_path: Path,
) -> None:
    root, _ = _catalog_workspace(tmp_path)
    application = create_read_application(ReadApiConfig(root))
    status, _, raw = _request(
        application, "/api/v1/claims", query_string="q=does-not-exist"
    )
    payload = json.loads(raw)
    assert status == "200 OK"
    assert payload["scope"]["matched_reports"] == 0
    assert payload["items"] == []
    assert payload["page"]["returned"] == 0


def test_claim_catalog_rejects_arbitrary_duplicate_and_unbounded_query(
    tmp_path: Path,
) -> None:
    root, _ = _catalog_workspace(tmp_path)
    application = create_read_application(ReadApiConfig(root))
    for query in (
        "sql=select",
        "limit=201",
        "limit=10&limit=20",
        "verified=yes",
        "q=",
        f"q={'x' * 201}",
    ):
        status, _, raw = _request(application, "/api/v1/claims", query_string=query)
        payload = json.loads(raw)
        assert status == "400 Bad Request"
        assert payload["error"]["code"] == "INVALID_CLAIM_QUERY"


def test_claim_catalog_supports_conditional_read(tmp_path: Path) -> None:
    root, _ = _catalog_workspace(tmp_path)
    application = create_read_application(ReadApiConfig(root))
    status, headers, _ = _request(application, "/api/v1/claims")
    assert status == "200 OK"

    status, _, raw = _request(
        application,
        "/api/v1/claims",
        if_none_match=headers["ETag"],
    )
    assert status == "304 Not Modified"
    assert raw == b""


def test_claim_catalog_fails_closed_for_tampered_report_artifact(
    tmp_path: Path,
) -> None:
    root, record_ids = _catalog_workspace(tmp_path)
    receipt = json.loads((root / "receipts" / f"{record_ids[0]}.json").read_text())
    artifact = (
        root
        / "artifacts"
        / receipt["artifact_digest"][:2]
        / receipt["artifact_digest"][2:]
    )
    artifact.write_bytes(b'{"tampered":true}')
    application = create_read_application(ReadApiConfig(root))

    status, _, raw = _request(application, "/api/v1/claims")
    payload = json.loads(raw)
    assert status == "422 Unprocessable Entity"
    assert payload["error"]["code"] == "INVALID_REPORT"


def test_claim_catalog_scan_limit_is_explicit_not_partial(tmp_path: Path) -> None:
    root, _ = _catalog_workspace(tmp_path)
    application = create_read_application(
        ReadApiConfig(root, max_claim_catalog_receipts=3)
    )
    status, _, raw = _request(application, "/api/v1/claims")
    payload = json.loads(raw)
    assert status == "413 Request Entity Too Large"
    assert payload["error"]["code"] == "CLAIM_CATALOG_TOO_LARGE"


def _incident_source(tmp_path: Path) -> tuple[Path, str]:
    """Create a two-observation canonical incident chain for read-API tests."""
    path = tmp_path / "incidents.jsonl"
    store = JsonlIncidentEvidenceStore(path)
    detected_at = datetime(2026, 9, 29, 9, tzinfo=UTC)
    incident_id = derive_incident_id(
        event_id="incident-event-1",
        detected_at=detected_at,
        actor="detector",
        category="storage-compromise",
    )
    evidence = IncidentEvidenceReference("evidence", "evidence-1", "1" * 64)
    preserved = SecurityIncidentEvidence(
        incident_id=incident_id,
        event_id="incident-event-1",
        detected_at=detected_at,
        actor="detector",
        category="storage-compromise",
        status="preserved",
        evidence_refs=(evidence,),
        affected_states=(AffectedTrustState("state-1", "2" * 64, "trust-v1"),),
        security_event_digests=("3" * 64,),
        uncertainty=("host compromise remains outside this evidence",),
    )
    store.append(preserved)
    recovery_ref = IncidentEvidenceReference("recovery", "recovery-1", "4" * 64)
    reverified = SecurityIncidentEvidence(
        incident_id=incident_id,
        event_id="incident-event-1",
        detected_at=detected_at,
        actor="detector",
        category="storage-compromise",
        status="reverified",
        evidence_refs=(evidence, recovery_ref),
        affected_states=(AffectedTrustState("state-1", "2" * 64, "trust-v1"),),
        security_event_digests=("3" * 64,),
        uncertainty=("host compromise remains outside this evidence",),
        recovery=RecoveryEvidence(
            "recovery-1", recovery_ref, "operator", incident_id, "applied"
        ),
        post_recovery=PostRecoveryVerification(
            "verify-1",
            (evidence,),
            "verifier",
            "verified",
            datetime(2026, 9, 29, 10, tzinfo=UTC),
        ),
    )
    store.append(reverified)
    store.lock_path.unlink(missing_ok=True)
    return path, incident_id


def test_incident_investigation_capability_is_configured_explicitly(
    tmp_path: Path,
) -> None:
    root, _, _ = _workspace_report(tmp_path)
    incidents, _ = _incident_source(tmp_path)
    application = create_read_application(
        ReadApiConfig(root, incident_evidence_path=incidents)
    )
    status, _, raw = _request(application, "/api/v1/capabilities")
    assert status == "200 OK"
    assert json.loads(raw)["features"]["incident_investigation_read"] is True


def test_incident_portfolio_and_detail_are_backed_by_verified_store(
    tmp_path: Path,
) -> None:
    root, _, _ = _workspace_report(tmp_path)
    incidents, incident_id = _incident_source(tmp_path)
    before = incidents.read_bytes()
    application = create_read_application(
        ReadApiConfig(root, incident_evidence_path=incidents)
    )

    status, headers, raw = _request(application, "/api/v1/incidents")
    payload = json.loads(raw)
    assert status == "200 OK"
    assert headers["ETag"].startswith('"')
    assert payload["scope"] == {
        "resource": "security-incident-evidence",
        "sort": "latest_recorded_at_desc_incident_id_asc",
        "store_records": 2,
        "total_incidents": 1,
        "matched_incidents": 1,
    }
    assert payload["items"][0]["incident_id"] == incident_id
    assert payload["items"][0]["status"] == "reverified"
    assert payload["items"][0]["forensic_continuity_verified"] is True

    status, detail_headers, raw = _request(
        application, f"/api/v1/incidents/{incident_id}"
    )
    detail = json.loads(raw)
    assert status == "200 OK"
    assert detail_headers["ETag"].startswith('"')
    assert [item["status"] for item in detail["lifecycle"]] == [
        "preserved",
        "reverified",
    ]
    assert detail["recovery"]["status"] == "applied"
    assert detail["post_recovery"]["status"] == "verified"
    assert detail["forensic_continuity"]["causality_established"] is False
    assert incidents.read_bytes() == before
    assert not incidents.with_name(f".{incidents.name}.lock").exists()


def test_incident_portfolio_filters_paginates_and_supports_conditional_reads(
    tmp_path: Path,
) -> None:
    root, _, _ = _workspace_report(tmp_path)
    incidents, _ = _incident_source(tmp_path)
    application = create_read_application(
        ReadApiConfig(root, incident_evidence_path=incidents)
    )
    status, headers, raw = _request(
        application,
        "/api/v1/incidents",
        query_string="status=reverified&category=storage-compromise&q=DETECTOR&limit=1&offset=0",
    )
    payload = json.loads(raw)
    assert status == "200 OK"
    assert payload["scope"]["matched_incidents"] == 1
    assert payload["query"]["status"] == "reverified"

    status, _, raw = _request(
        application,
        "/api/v1/incidents",
        query_string="status=reverified&category=storage-compromise&q=DETECTOR&limit=1&offset=0",
        if_none_match=headers["ETag"],
    )
    assert status == "304 Not Modified"
    assert raw == b""


def test_incident_portfolio_rejects_arbitrary_duplicate_and_unbounded_query(
    tmp_path: Path,
) -> None:
    root, _, _ = _workspace_report(tmp_path)
    incidents, _ = _incident_source(tmp_path)
    application = create_read_application(
        ReadApiConfig(root, incident_evidence_path=incidents)
    )
    for query in (
        "sql=select",
        "status=closed",
        "status=reverified&status=recovered",
        "limit=201",
        "q=",
        f"q={'x' * 201}",
    ):
        status, _, raw = _request(application, "/api/v1/incidents", query_string=query)
        assert status == "400 Bad Request"
        assert json.loads(raw)["error"]["code"] == "INVALID_INCIDENT_QUERY"


def test_incident_investigation_reports_unconfigured_invalid_and_oversized_sources(
    tmp_path: Path,
) -> None:
    root, _, _ = _workspace_report(tmp_path)
    application = create_read_application(ReadApiConfig(root))
    status, _, raw = _request(application, "/api/v1/incidents")
    assert status == "404 Not Found"
    assert json.loads(raw)["error"]["code"] == "INCIDENT_SOURCE_NOT_CONFIGURED"

    invalid = tmp_path / "invalid-incidents.jsonl"
    invalid.write_text('{"not":"a canonical chain"}\n', encoding="utf-8")
    application = create_read_application(
        ReadApiConfig(root, incident_evidence_path=invalid)
    )
    status, _, raw = _request(application, "/api/v1/incidents")
    assert status == "422 Unprocessable Entity"
    assert json.loads(raw)["error"]["code"] == "INVALID_INCIDENT_SOURCE"

    incidents, _ = _incident_source(tmp_path)
    application = create_read_application(
        ReadApiConfig(
            root,
            incident_evidence_path=incidents,
            max_incident_evidence_bytes=1,
        )
    )
    status, _, raw = _request(application, "/api/v1/incidents")
    assert status == "413 Request Entity Too Large"
    assert json.loads(raw)["error"]["code"] == "INCIDENT_SOURCE_TOO_LARGE"


def test_incident_detail_malformed_identity_is_not_misclassified_as_report_error(
    tmp_path: Path,
) -> None:
    root, _, _ = _workspace_report(tmp_path)
    incidents, _ = _incident_source(tmp_path)
    application = create_read_application(
        ReadApiConfig(root, incident_evidence_path=incidents)
    )
    status, _, raw = _request(application, "/api/v1/incidents/not-a-digest")
    assert status == "404 Not Found"
    assert json.loads(raw)["error"]["code"] == "NOT_FOUND"


def _capture_failure_journal(tmp_path: Path) -> Path:
    path = tmp_path / "capture-failures.jsonl"
    path.write_text(
        '{"stage":"native_capture.persist","error_type":"OSError"}\n'
        '{"stage":"langchain.retriever_start","error_type":"AttributeError"}\n'
        '{"stage":"native_capture.persist","error_type":"OSError"}\n',
        encoding="utf-8",
    )
    return path


def test_capture_health_capability_is_configured_explicitly(tmp_path: Path) -> None:
    root, _, _ = _workspace_report(tmp_path)
    journal = _capture_failure_journal(tmp_path)
    application = create_read_application(
        ReadApiConfig(root, capture_failure_journal_path=journal)
    )
    status, _, raw = _request(application, "/api/v1/capabilities")
    assert status == "200 OK"
    assert json.loads(raw)["features"]["capture_health_read"] is True


def test_capture_health_reads_redacted_journal_without_mutation(tmp_path: Path) -> None:
    root, _, _ = _workspace_report(tmp_path)
    journal = _capture_failure_journal(tmp_path)
    before = journal.read_bytes()
    application = create_read_application(
        ReadApiConfig(
            root,
            capture_failure_journal_path=journal,
            capture_failure_journal_capacity_bytes=4096,
        )
    )
    status, headers, raw = _request(application, "/api/v1/capture-health")
    payload = json.loads(raw)
    assert status == "200 OK"
    assert headers["ETag"].startswith('"')
    assert payload["observations"]["recorded_failure_count"] == 3
    assert payload["observations"]["capture_success_inferred"] is False
    assert payload["source"]["declared_capacity_bytes"] == 4096
    assert payload["items"][0] == {
        "sequence": 0,
        "stage": "native_capture.persist",
        "error_type": "OSError",
    }
    assert str(journal) not in raw.decode("utf-8")
    assert journal.read_bytes() == before

    etag = headers["ETag"]
    status, headers, raw = _request(
        application, "/api/v1/capture-health", if_none_match=etag
    )
    assert status == "304 Not Modified"
    assert headers["ETag"] == etag
    assert raw == b""


def test_capture_health_filters_paginates_and_rejects_unbounded_query(
    tmp_path: Path,
) -> None:
    root, _, _ = _workspace_report(tmp_path)
    journal = _capture_failure_journal(tmp_path)
    application = create_read_application(
        ReadApiConfig(root, capture_failure_journal_path=journal)
    )
    status, _, raw = _request(
        application,
        "/api/v1/capture-health",
        query_string="stage=native_capture.persist&limit=1&offset=1",
    )
    payload = json.loads(raw)
    assert status == "200 OK"
    assert payload["page"]["matched"] == 2
    assert payload["items"][0]["sequence"] == 2

    for query in (
        "unknown=x",
        "stage=a&stage=b",
        "limit=201",
        "offset=-1",
        "error_type=",
    ):
        status, _, raw = _request(
            application, "/api/v1/capture-health", query_string=query
        )
        assert status == "400 Bad Request"
        assert json.loads(raw)["error"]["code"] == "INVALID_CAPTURE_FAILURE_QUERY"


def test_capture_health_reports_unconfigured_invalid_and_oversized_sources(
    tmp_path: Path,
) -> None:
    root, _, _ = _workspace_report(tmp_path)
    application = create_read_application(ReadApiConfig(root))
    status, _, raw = _request(application, "/api/v1/capture-health")
    assert status == "404 Not Found"
    assert json.loads(raw)["error"]["code"] == "CAPTURE_FAILURE_SOURCE_NOT_CONFIGURED"

    invalid = tmp_path / "invalid-capture-failures.jsonl"
    invalid.write_text(
        '{"stage":"native_capture.persist","error_type":"OSError","message":"raw secret"}\n',
        encoding="utf-8",
    )
    application = create_read_application(
        ReadApiConfig(root, capture_failure_journal_path=invalid)
    )
    status, _, raw = _request(application, "/api/v1/capture-health")
    assert status == "422 Unprocessable Entity"
    assert json.loads(raw)["error"]["code"] == "INVALID_CAPTURE_FAILURE_SOURCE"

    journal = _capture_failure_journal(tmp_path)
    application = create_read_application(
        ReadApiConfig(
            root,
            capture_failure_journal_path=journal,
            max_capture_failure_journal_bytes=1,
        )
    )
    status, _, raw = _request(application, "/api/v1/capture-health")
    assert status == "413 Request Entity Too Large"
    assert json.loads(raw)["error"]["code"] == "CAPTURE_FAILURE_SOURCE_TOO_LARGE"


def test_capture_health_enforces_record_scan_limit(tmp_path: Path) -> None:
    root, _, _ = _workspace_report(tmp_path)
    journal = _capture_failure_journal(tmp_path)
    application = create_read_application(
        ReadApiConfig(
            root,
            capture_failure_journal_path=journal,
            max_capture_failure_records=2,
        )
    )
    status, _, raw = _request(application, "/api/v1/capture-health")
    assert status == "413 Request Entity Too Large"
    assert json.loads(raw)["error"]["code"] == "CAPTURE_FAILURE_SOURCE_TOO_LARGE"


def _reliability_proof_bundle(tmp_path: Path) -> Path:
    """Build one canonical portable reliability proof for read-API tests."""
    from statewake.services.reliability_proof_bundle_service import (
        build_reliability_proof_bundle,
    )
    from tests.support.reliability_proof import prepare_reliability_proof_fixture

    root = tmp_path / "proof-fixture"
    root.mkdir()
    attestation, chain, history = prepare_reliability_proof_fixture(root)
    output = root / "proof.zip"
    build_reliability_proof_bundle(
        attestation_path=attestation,
        evidence_chain_path=chain,
        history_path=history,
        evidence_root=root,
        output=output,
    )
    return output


def test_reliability_proof_read_api_verifies_configured_bundle(tmp_path: Path) -> None:
    workspace_root, _, _ = _workspace_report(tmp_path)
    proof = _reliability_proof_bundle(tmp_path)
    application = create_read_application(
        ReadApiConfig(workspace_root, reliability_proof_path=proof)
    )

    status, headers, raw = _request(application, "/api/v1/proof-bundle")
    payload = json.loads(raw)
    assert status == "200 OK"
    assert payload["schema_version"] == "proof-bundle-investigation.v1"
    assert payload["verification"]["verified"] is True
    assert payload["verification"]["offline_reverification_succeeded"] is True
    assert payload["proof"]["format_version"] == "3"
    assert payload["completeness"]["status"] == "verified"
    assert payload["authorization"]["publication_authorized"] is False
    assert headers["ETag"]

    status, _, raw = _request(
        application,
        "/api/v1/proof-bundle",
        if_none_match=headers["ETag"],
    )
    assert status == "304 Not Modified"
    assert raw == b""


def test_reliability_proof_read_api_reports_unconfigured_source(tmp_path: Path) -> None:
    workspace_root, _, _ = _workspace_report(tmp_path)
    application = create_read_application(ReadApiConfig(workspace_root))
    status, _, raw = _request(application, "/api/v1/proof-bundle")
    assert status == "404 Not Found"
    assert json.loads(raw)["error"]["code"] == (
        "RELIABILITY_PROOF_SOURCE_NOT_CONFIGURED"
    )


def test_reliability_proof_read_api_rejects_tampered_bundle(tmp_path: Path) -> None:
    from zipfile import ZipFile

    workspace_root, _, _ = _workspace_report(tmp_path)
    proof = _reliability_proof_bundle(tmp_path)
    tampered = proof.with_name("tampered-proof.zip")
    with ZipFile(proof) as source, ZipFile(tampered, "w") as target:
        for info in source.infolist():
            content = source.read(info.filename)
            if info.filename.endswith("proof/verification-report.json"):
                content += b"\n"
            target.writestr(info, content)
    application = create_read_application(
        ReadApiConfig(workspace_root, reliability_proof_path=tampered)
    )
    status, _, raw = _request(application, "/api/v1/proof-bundle")
    assert status == "422 Unprocessable Entity"
    assert json.loads(raw)["error"]["code"] == "INVALID_RELIABILITY_PROOF_SOURCE"


def test_reliability_proof_read_api_enforces_configured_size_limit(
    tmp_path: Path,
) -> None:
    workspace_root, _, _ = _workspace_report(tmp_path)
    proof = _reliability_proof_bundle(tmp_path)
    application = create_read_application(
        ReadApiConfig(
            workspace_root,
            reliability_proof_path=proof,
            max_reliability_proof_bytes=1,
        )
    )
    status, _, raw = _request(application, "/api/v1/proof-bundle")
    assert status == "413 Request Entity Too Large"
    assert json.loads(raw)["error"]["code"] == "RELIABILITY_PROOF_SOURCE_TOO_LARGE"


def test_reliability_proof_config_rejects_symlink_source(tmp_path: Path) -> None:
    workspace_root, _, _ = _workspace_report(tmp_path)
    proof = _reliability_proof_bundle(tmp_path)
    link = tmp_path / "proof-link.zip"
    try:
        link.symlink_to(proof)
    except OSError:
        return
    try:
        ReadApiConfig(workspace_root, reliability_proof_path=link)
    except ValueError as exc:
        assert "symlink" in str(exc)
    else:
        raise AssertionError("symlink reliability proof source was accepted")


def test_reliability_proof_capability_is_advertised_only_when_configured(
    tmp_path: Path,
) -> None:
    workspace_root, _, _ = _workspace_report(tmp_path)
    proof = _reliability_proof_bundle(tmp_path)
    application = create_read_application(
        ReadApiConfig(workspace_root, reliability_proof_path=proof)
    )
    status, _, raw = _request(application, "/api/v1/capabilities")
    assert status == "200 OK"
    assert json.loads(raw)["features"]["reliability_proof_read"] is True


def test_workspace_portable_dataset_is_not_accepted_as_reliability_proof(
    tmp_path: Path,
) -> None:
    from statewake.workspace.models import WorkspaceRecordQuery
    from statewake.workspace.portable_bundle import write_portable_bundle

    workspace_root, _, _ = _workspace_report(tmp_path)
    dataset_root = tmp_path / "dataset-workspace"
    workspace = StateWakeWorkspace.open(dataset_root)
    record = workspace.ingest(
        b"dataset-row",
        producer_type="test",
        producer_id="producer",
        source_ref="source",
        captured_at=datetime(2026, 9, 29, tzinfo=UTC),
    )
    projection = workspace.project(WorkspaceRecordQuery(limit=10))
    result = write_portable_bundle(
        projection,
        (record,),
        tmp_path / "portable-dataset.zip",
        workspace_id=workspace.identity.workspace_id,
        schema_version=workspace.identity.schema_version,
        disclosure_max_sensitivity="internal",
        query_definition={"limit": 10},
        created_at=datetime(2026, 9, 29, 1, tzinfo=UTC),
    )
    workspace.close()

    application = create_read_application(
        ReadApiConfig(workspace_root, reliability_proof_path=result.output_path)
    )
    status, _, raw = _request(application, "/api/v1/proof-bundle")
    assert status == "422 Unprocessable Entity"
    assert json.loads(raw)["error"]["code"] == "INVALID_RELIABILITY_PROOF_SOURCE"


def _security_audit_path(tmp_path: Path) -> Path:
    """Create one canonical deployment-security audit chain for read API tests."""
    path = tmp_path / "security-audit.jsonl"
    store = JsonlSecurityAuditStore(path)
    store.append(
        SecurityEvent(
            event="authentication_failed",
            operation="verify:evidence",
            method="POST",
            path="/v1/evidence/verify",
            reason="authentication_failed",
        )
    )
    store.append(
        SecurityEvent(
            event="request_admitted",
            operation="verify:proof",
            method="POST",
            path="/v1/proof/verify",
            reason="authorized",
        )
    )
    return path


def test_security_assurance_read_api_is_bounded_private_and_etag_capable(
    tmp_path: Path,
) -> None:
    """Expose verified audit records without leaking raw paths or request context."""
    root, _, _ = _workspace_report(tmp_path)
    audit_path = _security_audit_path(tmp_path)
    application = create_read_application(
        ReadApiConfig(root, security_audit_path=audit_path)
    )

    status, headers, raw = _request(application, "/api/v1/security-assurance")
    payload = json.loads(raw)
    assert status == "200 OK"
    assert payload["schema_version"] == "security-assurance-investigation.v2"
    assert payload["source"]["chain_integrity"] == "verified"
    assert payload["observations"]["recorded_event_count"] == 2
    assert payload["observations"]["deployment_secure_inferred"] is False
    assert all(item["path_exposed"] is False for item in payload["items"])
    assert "/v1/evidence/verify" not in raw.decode("utf-8")
    etag = headers["ETag"]

    status, headers, raw = _request(
        application,
        "/api/v1/security-assurance",
        if_none_match=etag,
    )
    assert status == "304 Not Modified"
    assert headers["ETag"] == etag
    assert raw == b""


def test_security_assurance_query_filters_and_rejects_arbitrary_input(
    tmp_path: Path,
) -> None:
    """Allow only exact event/operation/reason/method filters and bounded pagination."""
    root, _, _ = _workspace_report(tmp_path)
    application = create_read_application(
        ReadApiConfig(root, security_audit_path=_security_audit_path(tmp_path))
    )

    status, _, raw = _request(
        application,
        "/api/v1/security-assurance",
        query_string="operation=verify%3Aproof&reason=authorized&method=POST&limit=1",
    )
    payload = json.loads(raw)
    assert status == "200 OK"
    assert payload["page"]["matched"] == 1
    assert payload["items"][0]["event"] == "request_admitted"

    for query in (
        "path=%2Fetc%2Fpasswd",
        "event=request_admitted&event=request_rejected",
        "reason=unknown-secret",
        "limit=9999",
        "method=POST%20SECRET",
    ):
        status, _, raw = _request(
            application,
            "/api/v1/security-assurance",
            query_string=query,
        )
        assert status == "400 Bad Request"
        assert json.loads(raw)["error"]["code"] == "INVALID_SECURITY_AUDIT_QUERY"


def test_security_assurance_rejects_tampered_and_oversized_sources(
    tmp_path: Path,
) -> None:
    """Fail closed on audit-chain corruption and configured read-limit overflow."""
    root, _, _ = _workspace_report(tmp_path)
    path = _security_audit_path(tmp_path)
    lines = path.read_text(encoding="utf-8").splitlines()
    tampered = json.loads(lines[0])
    tampered["reason"] = "tampered"
    lines[0] = json.dumps(tampered)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    application = create_read_application(ReadApiConfig(root, security_audit_path=path))
    status, _, raw = _request(application, "/api/v1/security-assurance")
    assert status == "422 Unprocessable Entity"
    assert json.loads(raw)["error"]["code"] == "INVALID_SECURITY_AUDIT_SOURCE"

    clean = _security_audit_path(tmp_path / "large")
    application = create_read_application(
        ReadApiConfig(
            root,
            security_audit_path=clean,
            max_security_audit_bytes=1,
        )
    )
    status, _, raw = _request(application, "/api/v1/security-assurance")
    assert status == "413 Request Entity Too Large"
    assert json.loads(raw)["error"]["code"] == "SECURITY_AUDIT_SOURCE_TOO_LARGE"


def test_security_assurance_unconfigured_and_capability_state(tmp_path: Path) -> None:
    """Advertise the feature only when an audit source is explicitly configured."""
    root, _, _ = _workspace_report(tmp_path)
    without = create_read_application(ReadApiConfig(root))
    status, _, raw = _request(without, "/api/v1/security-assurance")
    assert status == "404 Not Found"
    assert json.loads(raw)["error"]["code"] == "SECURITY_AUDIT_SOURCE_NOT_CONFIGURED"

    audit_path = _security_audit_path(tmp_path)
    with_source = create_read_application(
        ReadApiConfig(root, security_audit_path=audit_path)
    )
    _, _, raw = _request(with_source, "/api/v1/capabilities")
    assert json.loads(raw)["features"]["security_assurance_read"] is True


def _runtime_containment_snapshot_path(tmp_path: Path) -> Path:
    """Write one verified effective verification-service configuration snapshot."""
    path = tmp_path / "runtime-containment.json"
    write_runtime_containment_snapshot(
        path,
        RuntimeContainmentConfigSnapshot.capture(
            max_request_bytes=2048,
            read_only=True,
            require_https=True,
            allow_insecure_http=False,
            artifact_root_count=1,
            runtime_limits=RuntimeContainmentLimits(
                max_input_bytes=4096,
                max_json_depth=12,
                max_concurrency=3,
            ),
        ),
    )
    return path


def test_security_assurance_integrates_verified_runtime_configuration(
    tmp_path: Path,
) -> None:
    """Expose effective containment config without promoting policy-only limits to enforcement."""
    root, _, _ = _workspace_report(tmp_path)
    runtime_path = _runtime_containment_snapshot_path(tmp_path)
    application = create_read_application(
        ReadApiConfig(root, runtime_containment_snapshot_path=runtime_path)
    )

    status, _, raw = _request(application, "/api/v1/security-assurance")
    payload = json.loads(raw)
    assert status == "200 OK"
    assert payload["source"]["configured"] is False
    assert payload["observations"]["runtime_configuration_snapshot_observed"] is True
    runtime = payload["runtime_containment"]
    assert runtime["snapshot_observed"] is True
    assert runtime["verification_service"]["max_request_bytes"] == 2048
    assert runtime["verification_service"]["artifact_roots_exposed"] is False
    assert runtime["limits"]["max_json_depth"] == 12
    assert runtime["enforcement"]["json_depth"] == "verification-service-enforced"
    assert (
        runtime["enforcement"]["concurrency"]
        == "configured-limit-not-enforced-by-verification-service"
    )
    assert runtime["host_controls_evaluated"] is False

    _, _, raw = _request(application, "/api/v1/capabilities")
    assert json.loads(raw)["features"]["security_assurance_read"] is True


def test_security_assurance_rejects_invalid_runtime_snapshot(tmp_path: Path) -> None:
    """Fail closed when explicitly configured runtime configuration evidence is tampered."""
    root, _, _ = _workspace_report(tmp_path)
    runtime_path = _runtime_containment_snapshot_path(tmp_path)
    payload = json.loads(runtime_path.read_text(encoding="utf-8"))
    payload["verification_service"]["max_request_bytes"] = 9999
    runtime_path.write_text(json.dumps(payload), encoding="utf-8")
    application = create_read_application(
        ReadApiConfig(root, runtime_containment_snapshot_path=runtime_path)
    )
    status, _, raw = _request(application, "/api/v1/security-assurance")
    assert status == "422 Unprocessable Entity"
    assert json.loads(raw)["error"]["code"] == "INVALID_RUNTIME_CONTAINMENT_SNAPSHOT"


def _authorization_context_payload(*, mismatch: bool = False) -> dict[str, object]:
    """Return one explicit authorization context for read-API tests."""
    recorded: dict[str, object] = {
        "allowed": True,
        "principal_id": "TOP_SECRET_PRINCIPAL",
        "operation": "READ",
        "resource_domain": "TOP_SECRET_DOMAIN",
        "resource_id": "TOP_SECRET_RESOURCE",
        "resource_state": "verified",
        "reason": "authorized",
        "matched_role": "reader",
    }
    if mismatch:
        recorded["allowed"] = False
    return {
        "schema_version": "authorization-context.v1",
        "principal": {
            "principal_id": "TOP_SECRET_PRINCIPAL",
            "roles": ["reader"],
            "resource_scopes": {"TOP_SECRET_DOMAIN": ["TOP_SECRET_RESOURCE"]},
            "status": "ACTIVE",
            "expires_at": None,
        },
        "policy": {
            "grants": [
                {
                    "role": "reader",
                    "operation": "READ",
                    "allowed_states": ["verified"],
                }
            ]
        },
        "request": {
            "operation": "READ",
            "resource_domain": "TOP_SECRET_DOMAIN",
            "resource_id": "TOP_SECRET_RESOURCE",
            "resource_state": "verified",
            "requested_at": "2026-09-30T00:00:00+00:00",
        },
        "recorded_decision": recorded,
    }


def test_authorization_policy_read_api_replays_and_hides_identities(
    tmp_path: Path,
) -> None:
    root, _, _ = _workspace_report(tmp_path)
    source = tmp_path / "authorization.json"
    source.write_text(json.dumps(_authorization_context_payload()), encoding="utf-8")
    before = source.read_bytes()
    application = create_read_application(
        ReadApiConfig(root, authorization_context_path=source)
    )
    status, headers, raw = _request(application, "/api/v1/authorization-policy")
    payload = json.loads(raw)
    assert status == "200 OK"
    assert headers["ETag"].startswith('"')
    assert payload["decision"]["allowed"] is True
    assert payload["evaluation"]["policy_replay_verified"] is True
    assert payload["evaluation"]["recorded_decision_verified"] is True
    assert b"TOP_SECRET_PRINCIPAL" not in raw
    assert b"TOP_SECRET_DOMAIN" not in raw
    assert b"TOP_SECRET_RESOURCE" not in raw
    assert source.read_bytes() == before

    status, _, conditional = _request(
        application,
        "/api/v1/authorization-policy",
        if_none_match=headers["ETag"],
    )
    assert status == "304 Not Modified"
    assert conditional == b""


def test_authorization_policy_read_api_rejects_mismatch_and_oversize(
    tmp_path: Path,
) -> None:
    root, _, _ = _workspace_report(tmp_path)
    source = tmp_path / "authorization.json"
    source.write_text(
        json.dumps(_authorization_context_payload(mismatch=True)),
        encoding="utf-8",
    )
    application = create_read_application(
        ReadApiConfig(root, authorization_context_path=source)
    )
    status, _, raw = _request(application, "/api/v1/authorization-policy")
    assert status == "422 Unprocessable Entity"
    assert json.loads(raw)["error"]["code"] == "INVALID_AUTHORIZATION_CONTEXT_SOURCE"

    application = create_read_application(
        ReadApiConfig(
            root,
            authorization_context_path=source,
            max_authorization_context_bytes=1,
        )
    )
    status, _, raw = _request(application, "/api/v1/authorization-policy")
    assert status == "413 Request Entity Too Large"
    assert json.loads(raw)["error"]["code"] == "AUTHORIZATION_CONTEXT_SOURCE_TOO_LARGE"


def test_authorization_policy_capability_is_configuration_bound(tmp_path: Path) -> None:
    root, _, _ = _workspace_report(tmp_path)
    source = tmp_path / "authorization.json"
    source.write_text(json.dumps(_authorization_context_payload()), encoding="utf-8")
    application = create_read_application(
        ReadApiConfig(root, authorization_context_path=source)
    )
    status, _, raw = _request(application, "/api/v1/capabilities")
    assert status == "200 OK"
    assert json.loads(raw)["features"]["authorization_policy_read"] is True


def test_authorization_policy_is_explicitly_unconfigured(tmp_path: Path) -> None:
    root, _, _ = _workspace_report(tmp_path)
    application = create_read_application(ReadApiConfig(root))
    status, _, raw = _request(application, "/api/v1/authorization-policy")
    assert status == "404 Not Found"
    assert (
        json.loads(raw)["error"]["code"]
        == "AUTHORIZATION_CONTEXT_SOURCE_NOT_CONFIGURED"
    )


def _assurance_decision_files(tmp_path: Path) -> tuple[Path, Path]:
    """Write one exact-bound persisted assurance decision/exception pair."""
    from datetime import timedelta

    from statewake.domain.assurance_operations import (
        AssuranceDecisionInput,
        create_assurance_exception,
        evaluate_assurance_decision,
    )

    now = datetime(2026, 9, 30, tzinfo=UTC)
    decision = evaluate_assurance_decision(
        AssuranceDecisionInput(
            subject_id="SECRET_SUBJECT",
            reliability_state="degraded",
            verification_status="verified",
            trust_status="trusted",
            evidence_references=("SECRET_EVIDENCE",),
            verification_results=("verified",),
        ),
        generated_at=now,
    )
    exception = create_assurance_exception(
        decision,
        exception_id="SECRET_EXCEPTION",
        reason_operation_continues="bounded continuation",
        authorized_by="SECRET_AUTHORIZER",
        expires_at=now + timedelta(days=2),
        compensating_control="manual verification",
        reverification_required="before expiry",
        created_at=now,
    )
    decision_path = tmp_path / "decision.json"
    exception_path = tmp_path / "exception.json"
    decision_path.write_text(
        json.dumps(decision.to_dict(), sort_keys=True), encoding="utf-8"
    )
    exception_path.write_text(
        json.dumps(exception.to_dict(), sort_keys=True), encoding="utf-8"
    )
    return decision_path, exception_path


def test_assurance_decision_read_api_restored_with_exact_binding(
    tmp_path: Path,
) -> None:
    root, _, _ = _workspace_report(tmp_path)
    decision_path, exception_path = _assurance_decision_files(tmp_path)
    application = create_read_application(
        ReadApiConfig(
            root,
            assurance_decision_path=decision_path,
            assurance_exception_path=exception_path,
        )
    )
    status, headers, raw = _request(application, "/api/v1/assurance-decision")
    payload = json.loads(raw)
    assert status == "200 OK"
    assert payload["decision"]["semantic_replay_verified"] is True
    assert payload["exception"]["binding"] == "exact-decision-digest"
    assert payload["exception"]["system_state_preserved"] is True
    assert b"SECRET_SUBJECT" not in raw
    assert b"SECRET_AUTHORIZER" not in raw
    assert b"SECRET_EVIDENCE" not in raw

    status, _, conditional = _request(
        application,
        "/api/v1/assurance-decision",
        if_none_match=headers["ETag"],
    )
    assert status == "304 Not Modified"
    assert conditional == b""


def test_assurance_decision_capability_is_configuration_bound(tmp_path: Path) -> None:
    root, _, _ = _workspace_report(tmp_path)
    decision_path, _ = _assurance_decision_files(tmp_path)
    application = create_read_application(
        ReadApiConfig(root, assurance_decision_path=decision_path)
    )
    _, _, raw = _request(application, "/api/v1/capabilities")
    assert json.loads(raw)["features"]["assurance_decision_read"] is True
