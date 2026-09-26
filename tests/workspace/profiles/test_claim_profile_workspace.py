from datetime import UTC, datetime

from statewake.services.reliability_claim_profile_service import (
    evaluate_claim_profile,
    get_builtin_claim_profile,
    write_claim_profile_evaluation,
)
from statewake.workspace.models import WorkspaceRecordQuery
from statewake.workspace.workspace import StateWakeWorkspace
from tests.test_reliability_claim_profiles import chain


def test_profile_result_round_trips_through_workspace(tmp_path):
    workspace = StateWakeWorkspace.open(tmp_path / "statewake")
    profile = get_builtin_claim_profile("rag_answer_verified.v1")
    result = evaluate_claim_profile(chain(), profile)
    result_path = tmp_path / "profile-result.json"
    write_claim_profile_evaluation(result, result_path)

    record = workspace.ingest_file(
        result_path,
        producer_type="statewake-profile-evaluation",
        producer_id="statewake.phase2",
        captured_at=datetime(2026, 9, 21, 0, 0, 0, tzinfo=UTC),
        source_event_id="profile-result-1",
        run_id="run-1",
        metadata={
            "profile_id": result.profile_id,
            "decision": result.decision,
        },
    )

    workspace.verify(record)
    page = workspace.query(WorkspaceRecordQuery(run_id="run-1", limit=10))
    assert len(page.records) == 1
    assert page.records[0].metadata["profile_id"] == "rag_answer_verified.v1"
    assert page.records[0].metadata["decision"] == "accepted"
