"""Workspace tests for Phase 5 integration outputs."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from statewake.integrations import capture_llamaindex_retrieval_event
from statewake.workspace import StateWakeWorkspace
from statewake.workspace.models import WorkspaceRecordQuery


def test_adapter_output_persists_in_explicit_workspace(tmp_path: Path) -> None:
    workspace = StateWakeWorkspace.open(tmp_path / "statewake")
    try:
        result = capture_llamaindex_retrieval_event(
            {
                "run_id": "run-workspace",
                "corpus_identity": "kb-v1",
                "corpus_snapshot_id": "snap-1",
                "query": {"text": "question"},
                "retrieved_item_ids": ["doc-1"],
                "chunk_digests": ["0" * 64],
                "captured_at": datetime(2026, 9, 21, 0, 0, 0, tzinfo=UTC),
            }
        )
        record = result.persist(workspace)
        assert record.producer_type == "statewake-integration"
        assert record.metadata["contract_type"] == "retrieval"
        page = workspace.query(WorkspaceRecordQuery(run_id="run-workspace"))
        assert page.total_count == 1
        assert page.records[0].artifact_digest == result.digest
    finally:
        workspace.close()
