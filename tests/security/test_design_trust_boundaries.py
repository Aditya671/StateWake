"""Negative regressions for previously demonstrated whole-artifact design gaps."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from statewake.domain.reliability_evidence import EvidenceReference
from statewake.reports.redaction import redacted_payload_reference
from statewake.services.reliability_claim_profile_service import (
    evaluate_claim_profile,
    get_builtin_claim_profile,
)
from statewake.validation_study.chains import chain_for_workload
from statewake.validation_study.metrics import run_validation_case
from statewake.workspace import StateWakeWorkspace, WorkspaceRestoreError


def test_reference_source_cannot_supply_contract_identity() -> None:
    chain = chain_for_workload("rag_answer")
    spoofed = tuple(
        EvidenceReference(
            kind="evidence",
            identity=f"ordinary:{index}",
            digest=ref.digest,
            source=f"documentation/{ref.identity}",
        )
        for index, ref in enumerate(chain.evidence)
    )
    evaluation = evaluate_claim_profile(
        replace(chain, evidence=spoofed),
        get_builtin_claim_profile("rag_answer_verified.v1"),
    )
    assert evaluation.satisfied is False
    assert "ai-contract:retrieval_evidence" in evaluation.missing_evidence


def test_declared_fault_is_not_counted_without_observed_rejection() -> None:
    result = run_validation_case(
        "tool_action", "statewake_full", ("missing_tool_authorization",)
    )
    assert "missing_tool_authorization" not in result.detected_faults


def test_nested_sensitive_values_are_redacted() -> None:
    secret = "PRIVATE_SENTINEL"
    payload = {"context": {"api_key": secret}, "items": [{"token": secret}]}
    visible = redacted_payload_reference(payload)
    assert visible["visible"]["context"]["api_key"] == "<redacted>"
    assert visible["visible"]["items"][0]["token"] == "<redacted>"
    assert secret not in str(visible)


def test_restore_overwrite_removes_target_only_files(tmp_path: Path) -> None:
    source = StateWakeWorkspace.open(tmp_path / "source")
    source.ingest(
        b"payload",
        producer_type="fixture",
        producer_id="fixture",
        source_ref="fixture",
        captured_at=datetime(2026, 9, 21, tzinfo=UTC),
    )
    backup = source.backup(tmp_path / "backup.zip")
    source.close()
    target = tmp_path / "target"
    target.mkdir()
    (target / "stale.txt").write_text("stale", encoding="utf-8")
    StateWakeWorkspace.restore_backup(backup.output_path, target, overwrite=True)
    assert not (target / "stale.txt").exists()


def test_restore_rejects_target_symlink(tmp_path: Path) -> None:
    source = StateWakeWorkspace.open(tmp_path / "source")
    backup = source.backup(tmp_path / "backup.zip")
    target = tmp_path / "target"
    try:
        target.symlink_to(tmp_path / "source", target_is_directory=True)
    except OSError as exc:
        if getattr(exc, "winerror", None) == 1314:
            pytest.skip(
                "creating symlinks requires Windows developer mode or privilege"
            )
        raise
    with pytest.raises(WorkspaceRestoreError):
        StateWakeWorkspace.restore_backup(backup.output_path, target, overwrite=True)
