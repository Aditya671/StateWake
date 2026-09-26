"""Workspace regression tests for AI evidence contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from statewake.ai_contracts import PromptEvidenceContract, contract_to_json_bytes
from statewake.workspace.workspace import StateWakeWorkspace

NOW = datetime(2026, 9, 21, 0, 0, tzinfo=UTC)


def test_workspace_records_prompt_contract(tmp_path: Path) -> None:
    """Prove AI contracts can persist through an explicit StateWake workspace."""
    workspace = StateWakeWorkspace.open(tmp_path / "statewake")
    contract = PromptEvidenceContract(
        contract_version="1",
        producer_id="prompt-producer",
        run_id="run-1",
        source="prompt-builder",
        rendered_prompt_digest="rendered",
        captured_at=NOW,
    )

    record = workspace.ingest(
        contract_to_json_bytes(contract.to_dict()),
        producer_type="ai_contract",
        producer_id=contract.producer_id,
        source_ref="statewake.ai_contracts.prompt",
        source_event_id="prompt/run-1",
        run_id=contract.run_id,
        captured_at=contract.captured_at,
        metadata={"contract_type": "prompt"},
    )

    assert record.producer_type == "ai_contract"
    assert record.producer_id == "prompt-producer"
    assert record.run_id == "run-1"
    assert record.metadata["contract_type"] == "prompt"
    workspace.verify(record)
