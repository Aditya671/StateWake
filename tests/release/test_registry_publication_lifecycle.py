"""Release-script regressions for append-only registry publication lifecycle."""

from __future__ import annotations

import json
import sys
import time
from datetime import timedelta
from pathlib import Path

import pytest

from scripts.release import reconcile_registry_publication_lifecycle as lifecycle_script
from statewake.release_trust import (
    RegistryPublicationLifecycleStore,
    load_publication_execution_permit,
    load_release_publication_basis,
    reconcile_registry_publication_lifecycle,
    write_registry_publication_receipt,
)
from tests.release.test_registry_publication_reconciliation import _evidence


def test_lifecycle_script_appends_verified_observation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    basis_path, permit_path, receipt = _evidence(tmp_path)
    receipt_path = tmp_path / "registry-receipt.json"
    history_path = tmp_path / "registry-lifecycle.jsonl"
    write_registry_publication_receipt(receipt, receipt_path)
    basis = load_release_publication_basis(basis_path)
    permit = load_publication_execution_permit(permit_path)
    observation = reconcile_registry_publication_lifecycle(
        receipt,
        basis,
        permit,
        None,
        {},
        unavailable_reason="release-specific registry API returned HTTP 404",
        observed_at=receipt.observed_at + timedelta(minutes=1),
    )
    monkeypatch.setattr(
        lifecycle_script,
        "fetch_registry_publication_lifecycle",
        lambda receipt, basis, permit, previous, timeout: observation,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "reconcile_registry_publication_lifecycle.py",
            "--basis",
            str(basis_path),
            "--permit",
            str(permit_path),
            "--receipt",
            str(receipt_path),
            "--history",
            str(history_path),
            "--target",
            "pypi",
            "--attempts",
            "1",
        ],
    )
    assert lifecycle_script.main() == 0
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "unavailable"
    assert output["created"] is True
    assert output["history_count"] == 1
    stored = RegistryPublicationLifecycleStore(history_path).read(
        receipt, basis, permit
    )
    assert stored == (observation,)


def test_lifecycle_script_rejects_target_rebinding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    basis_path, permit_path, receipt = _evidence(tmp_path)
    receipt_path = tmp_path / "registry-receipt.json"
    write_registry_publication_receipt(receipt, receipt_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "reconcile_registry_publication_lifecycle.py",
            "--basis",
            str(basis_path),
            "--permit",
            str(permit_path),
            "--receipt",
            str(receipt_path),
            "--history",
            str(tmp_path / "history.jsonl"),
            "--target",
            "testpypi",
        ],
    )
    with pytest.raises(PermissionError, match="target does not match"):
        lifecycle_script.main()


def test_lifecycle_script_retries_only_transport_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    basis_path, permit_path, receipt = _evidence(tmp_path)
    receipt_path = tmp_path / "registry-receipt.json"
    history_path = tmp_path / "registry-lifecycle.jsonl"
    write_registry_publication_receipt(receipt, receipt_path)
    basis = load_release_publication_basis(basis_path)
    permit = load_publication_execution_permit(permit_path)
    observation = reconcile_registry_publication_lifecycle(
        receipt,
        basis,
        permit,
        None,
        {},
        observed_at=receipt.observed_at + timedelta(minutes=1),
    )
    calls = 0

    def fetch(receipt, basis, permit, previous, timeout):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ConnectionError("synthetic registry transport failure")
        return observation

    monkeypatch.setattr(lifecycle_script, "fetch_registry_publication_lifecycle", fetch)
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "reconcile_registry_publication_lifecycle.py",
            "--basis",
            str(basis_path),
            "--permit",
            str(permit_path),
            "--receipt",
            str(receipt_path),
            "--history",
            str(history_path),
            "--target",
            "pypi",
            "--attempts",
            "2",
            "--retry-seconds",
            "0",
        ],
    )
    assert lifecycle_script.main() == 0
    output = json.loads(capsys.readouterr().out)
    assert output["attempt"] == 2
    assert calls == 2
