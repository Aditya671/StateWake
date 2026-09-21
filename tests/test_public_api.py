"""Regression tests for StateWake.

The active test suite protects the public package behavior and integration boundaries.
"""

from pathlib import Path

from statewake import __version__, read_reliability_state


def test_public_version_and_state_api(tmp_path: Path) -> None:
    """
    Verify the `test_public_version_and_state_api` behavior
    and its expected invariants.
    """
    assert __version__ == "0.4.0"
    snapshot = read_reliability_state(
        "subject-1", history_path=tmp_path / "state.jsonl"
    )
    assert snapshot.subject_id == "subject-1"
    assert snapshot.state == "unknown"


def test_stable_evidence_chain_loader_is_top_level():
    import statewake

    assert callable(statewake.load_evidence_chain)


def test_public_evidence_facade_build_verify_and_reject_tampering(
    tmp_path: Path,
) -> None:
    """Exercise the documented public evidence facade through a full lifecycle."""
    import json
    from datetime import UTC, datetime
    from hashlib import sha256

    from statewake import (
        ExternalEvidenceReceipt,
        admit_evidence,
        build_evidence_chain,
        load_evidence_chain,
        verify_evidence_chain,
        write_evidence_chain,
    )

    artifact = tmp_path / "evidence.json"
    artifact.write_bytes(b'{"decision":"accept","run":"public-api"}')
    receipt = ExternalEvidenceReceipt(
        producer_type="ci",
        producer_id="public-api-test",
        artifact_digest=sha256(artifact.read_bytes()).hexdigest(),
        artifact_size=artifact.stat().st_size,
        captured_at=datetime(2026, 9, 13, tzinfo=UTC),
        source_ref="ci://public-api",
        source_event_id="public-api-event",
        run_id="public-api-run",
    )
    receipt_path = tmp_path / "receipt.json"
    receipt_path.write_text(
        json.dumps(receipt.to_dict(), sort_keys=True), encoding="utf-8"
    )
    for name, payload in (
        ("run.json", {"run_id": "public-api-run"}),
        ("state.json", {"state_id": "public-api-state"}),
        ("provenance.json", {"provenance": "public-api"}),
        ("integrity.json", {"integrity": "public-api"}),
    ):
        (tmp_path / name).write_text(
            json.dumps(payload, sort_keys=True), encoding="utf-8"
        )

    admission = admit_evidence(
        receipt,
        artifact_path=artifact,
        receipt_path=receipt_path,
        expected_run_id="public-api-run",
        expected_producer_type="ci",
        expected_producer_id="public-api-test",
    )
    assert admission.receipt_id == receipt.receipt_id

    chain = build_evidence_chain(
        run_id="public-api-run",
        run_path=tmp_path / "run.json",
        state_id="public-api-state",
        state_path=tmp_path / "state.json",
        evidence_paths=(artifact,),
        provenance_path=tmp_path / "provenance.json",
        integrity_proof_path=tmp_path / "integrity.json",
        evidence_receipt_paths={artifact.name: receipt_path},
    )
    chain_path = tmp_path / "chain.json"
    write_evidence_chain(chain, chain_path)
    loaded = load_evidence_chain(chain_path)
    verify_evidence_chain(loaded, root=tmp_path)

    artifact.write_bytes(b'{"decision":"reject","run":"public-api"}')
    try:
        verify_evidence_chain(loaded, root=tmp_path)
    except (ValueError, FileNotFoundError):
        pass
    else:
        raise AssertionError("public evidence facade accepted tampered evidence")
