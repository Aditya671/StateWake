"""Workspace regression for Phase 7 study artifacts."""

from __future__ import annotations

from datetime import UTC, datetime

from statewake.validation_study.metrics import run_comparative_validation_study
from statewake.validation_study.report import write_study_reports
from statewake.workspace.models import WorkspaceRecordQuery
from statewake.workspace.workspace import StateWakeWorkspace


def test_comparative_study_report_persists_in_explicit_workspace(tmp_path) -> None:
    """Persist Phase 7 reports through an explicit StateWake workspace."""
    study = run_comparative_validation_study()
    json_path, markdown_path = write_study_reports(study, tmp_path / "reports")
    workspace = StateWakeWorkspace.open(tmp_path / "statewake")
    for path in (json_path, markdown_path):
        record = workspace.ingest_file(
            path,
            producer_type="statewake-comparative-validation-study",
            producer_id="statewake.phase7",
            captured_at=datetime(2026, 9, 21, 0, 0, 0, tzinfo=UTC),
            source_event_id=path.name,
            run_id=study.study_id,
            metadata={"study_id": study.study_id, "study_digest": study.digest},
        )
        workspace.verify(record)
    page = workspace.query(WorkspaceRecordQuery(run_id=study.study_id, limit=10))
    assert len(page.records) == 2
    assert {record.metadata["study_digest"] for record in page.records} == {
        study.digest
    }
