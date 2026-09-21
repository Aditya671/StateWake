from __future__ import annotations

from datetime import UTC, datetime

from statewake.domain.reliability_verification_report import (
    ReliabilityVerificationReport,
)
from statewake.reports.json_report import render_json_report
from statewake.workspace.models import WorkspaceRecordQuery
from statewake.workspace.workspace import StateWakeWorkspace


def test_report_round_trips_through_explicit_workspace(tmp_path):
    workspace = StateWakeWorkspace.open(tmp_path / "statewake")
    report = ReliabilityVerificationReport(
        format_version="1",
        claim="RAG answer verified",
        decision="accept",
        profile_id="rag_answer_verified.v1",
        profile_version="1",
        verified=True,
        evidence_included=("run",),
        evidence_omitted=(),
        checks_passed=("chain_verified",),
        checks_failed=(),
        source_identities=("run-1",),
        rationale=("because",),
        caveats=("bounded",),
        recovery_status="verified",
        verifier_version="statewake-test",
        generated_at="2026-09-21T00:00:00+00:00",
        candidate_identity="chain-1",
        candidate_digest="a" * 64,
        report_type="engineering",
        artifact_digests=("a" * 64,),
        human_decisions_required=("Review before release",),
        approval_status="requires-human-approval",
    )
    report_path = tmp_path / "report.json"
    report_path.write_text(render_json_report(report), encoding="utf-8")

    record = workspace.ingest_file(
        report_path,
        producer_type="statewake-verification-report",
        producer_id="statewake.phase3",
        captured_at=datetime(2026, 9, 21, 0, 0, 0, tzinfo=UTC),
        source_event_id="report-1",
        run_id="run-1",
        metadata={
            "candidate_identity": report.candidate_identity,
            "report_type": report.report_type,
        },
    )

    workspace.verify(record)
    page = workspace.query(WorkspaceRecordQuery(run_id="run-1", limit=10))
    assert len(page.records) == 1
    assert page.records[0].metadata["candidate_identity"] == "chain-1"
    assert page.records[0].metadata["report_type"] == "engineering"
