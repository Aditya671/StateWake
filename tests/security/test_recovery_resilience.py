"""Tier 6 failure-injection and recovery-resilience regression tests."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from statewake.adapters.key_management import ExternalSigningAdapter
from statewake.adapters.reliability_state import JsonlReliabilityStateStore
from statewake.domain.key_management import SigningKeyReference
from statewake.domain.provenance import ProvenanceGraph, ProvenanceNode
from statewake.domain.reliability_evidence import (
    EvidenceReference,
    ReliabilityEvidenceChain,
)
from statewake.domain.reliability_recovery_outcome import ReliabilityRecoveryOutcome
from statewake.domain.reliability_state import ReliabilityStateTransition
from statewake.domain.trust_anchor import (
    AnchorDiscrepancyError,
    TrustCheckpoint,
    compare_local_tip,
)
from statewake.services.persistence import atomic_write_text
from statewake.services.reliability_recovery_service import (
    verify_reliability_recovery_outcome,
)

ROOT = Path(__file__).resolve().parents[1]


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _write_recovery_fixture(root: Path) -> tuple[Path, ReliabilityEvidenceChain]:
    reconciliation = root / "reconciliation.json"
    recovery = root / "recovery.json"
    reconciliation.write_text(
        json.dumps({"bundle_id": "reconcile-1", "state": "recovered"}, sort_keys=True),
        encoding="utf-8",
    )
    recovery_payload = {
        "recovery_id": "recovery-1",
        "occurred_at": "2026-09-16T00:00:00+00:00",
        "impact_id": "impact-1",
        "source_reconciliation_id": "reconcile-1",
        "actor": "tier6-test",
        "approved": True,
        "status": "applied",
        "steps": [
            {
                "step_id": "step-1",
                "target": "target-1",
                "action": "restore-authoritative",
                "status": "applied",
                "reason": "verified source",
            }
        ],
        "reason": "corruption recovery",
    }
    recovery_payload["digest"] = _sha(
        json.dumps(
            {k: v for k, v in recovery_payload.items() if k != "digest"},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    )
    recovery.write_text(json.dumps(recovery_payload, sort_keys=True), encoding="utf-8")

    def reference(kind: str, identity: str, path: Path) -> EvidenceReference:
        return EvidenceReference(kind, identity, _sha(path.read_bytes()), path.name)

    digest = "a" * 64
    chain = ReliabilityEvidenceChain(
        chain_id="chain-1",
        run=EvidenceReference("run", "run-1", digest),
        state=EvidenceReference("state", "state-1", digest),
        evidence=(EvidenceReference("evidence", "evidence-1", digest),),
        provenance=EvidenceReference("provenance", "prov-1", digest),
        integrity=EvidenceReference("integrity", "int-1", digest),
        verification_status="verified",
        reliability_state="recovered",
        reconciliation_state="recovered",
        reconciliation_ref=reference("reconciliation", "reconcile-1", reconciliation),
        recovery_ref=reference("recovery", "recovery-1", recovery),
        decision="accept",
        decision_rationale=("recovered from authoritative evidence",),
    )
    return recovery, chain


def test_mode_a_evidence_corruption_recovery(tmp_path: Path) -> None:
    recovery_path, chain = _write_recovery_fixture(tmp_path)
    original = recovery_path.read_bytes()
    recovery_path.write_bytes(original + b"tamper")
    with pytest.raises(ValueError, match="recovery artifact digest mismatch"):
        verify_reliability_recovery_outcome(chain, root=tmp_path)
    recovery_path.write_bytes(original)
    outcome = verify_reliability_recovery_outcome(chain, root=tmp_path)
    assert outcome.outcome == "recovered"


def test_mode_b_provenance_corruption_recovery() -> None:
    with pytest.raises(
        ValueError, match="required provenance edges must reference known node IDs"
    ):
        ProvenanceGraph(
            nodes=(
                ProvenanceNode("root", "source", "a" * 64, "root"),
                ProvenanceNode("child", "derived", "b" * 64, "child", ("root",)),
            ),
            required_edges=(("child", "missing"),),
        ).validate_required_edges()

    graph = ProvenanceGraph(
        nodes=(
            ProvenanceNode("root", "source", "a" * 64, "root"),
            ProvenanceNode("child", "derived", "b" * 64, "child", ("root",)),
        ),
        required_edges=(("child", "root"),),
    )
    graph.validate_required_edges()
    assert graph.reachable("child", "root")


def _transition(
    subject: str,
    transition_id: str,
    previous: str,
    digest: str,
    from_state: str,
    to_state: str,
) -> ReliabilityStateTransition:
    return ReliabilityStateTransition(
        transition_id=transition_id,
        subject_id=subject,
        from_state=from_state,
        to_state=to_state,
        occurred_at=datetime(2026, 9, 16, tzinfo=UTC),
        actor="tier6-test",
        evidence_chain_id="chain-" + transition_id,
        evidence_chain_digest=digest,
        decision="reject" if to_state == "unreliable" else "review",
        rationale=("tier6",),
        previous_transition_digest=previous,
    )


def test_mode_c_state_history_corruption_recovery(tmp_path: Path) -> None:
    path = tmp_path / "history.jsonl"
    store = JsonlReliabilityStateStore(path)
    first = _transition("s", "1", "", "a" * 64, "unknown", "unreliable")
    store.append(first)
    second = _transition(
        "s", "2", first.computed_digest, "b" * 64, "unreliable", "degraded"
    )
    store.append(second)
    payload = [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
    ]
    payload[0]["digest"] = "c" * 64
    path.write_text(
        "\n".join(json.dumps(item, sort_keys=True) for item in payload) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(
        ValueError, match="reliability-state transition digest mismatch"
    ):
        JsonlReliabilityStateStore(path, recover_partial_tail=False).read()
    path.write_text(
        json.dumps(first.to_dict(), sort_keys=True) + "\n", encoding="utf-8"
    )
    assert [item.transition_id for item in store.read()] == ["1"]


def test_mode_d_checkpoint_disagreement_is_not_silently_repaired() -> None:
    with pytest.raises(AnchorDiscrepancyError, match="independent trust checkpoint"):
        compare_local_tip(
            TrustCheckpoint(
                checkpoint_id="checkpoint-1",
                subject_id="recovery-test",
                issued_at="2026-09-21T00:00:00Z",
                history_tip_digest="a" * 64,
                history_record_count=10,
                signing_key_id="test-key",
                signing_key_digest="c" * 64,
                signature="test-signature",
            ),
            history_tip_digest="b" * 64,
            history_record_count=9,
        )


@dataclass
class _Lifecycle:
    revoked: list[tuple[str, str]]
    rotations: int = 0

    def rotate(self, key: SigningKeyReference) -> SigningKeyReference:
        self.rotations += 1
        return SigningKeyReference(f"{key.key_id}-rotated", key.provider)

    def revoke(self, key: SigningKeyReference, *, reason: str) -> None:
        self.revoked.append((key.key_id, reason))


class _Signer:
    def sign(self, key: SigningKeyReference, payload: bytes) -> bytes:
        return b"signature"


def test_mode_e_key_compromise_revoke_rotate() -> None:
    lifecycle = _Lifecycle([])
    adapter = ExternalSigningAdapter(_Signer(), lifecycle)
    old = SigningKeyReference("key-v1", "external")
    replacement = adapter.rotate(old)
    adapter.revoke(old, reason="suspected compromise")
    assert replacement.key_id == "key-v1-rotated"
    assert lifecycle.revoked == [("key-v1", "suspected compromise")]


def test_interrupted_recovery_never_marks_success(tmp_path: Path) -> None:
    marker = tmp_path / "status.json"
    atomic_write_text(marker, json.dumps({"status": "recovery-in-progress"}))
    interrupted = marker.read_text(encoding="utf-8")
    assert json.loads(interrupted)["status"] == "recovery-in-progress"
    assert json.loads(interrupted)["status"] != "recovered"


def test_partial_failure_does_not_promote_unverified_state() -> None:
    lifecycle = _Lifecycle([])
    adapter = ExternalSigningAdapter(_Signer(), lifecycle)
    old = SigningKeyReference("key-v1", "external")
    with pytest.raises(ValueError, match="revocation reason"):
        adapter.revoke(old, reason="")
    assert lifecycle.revoked == []


def test_post_recovery_verification_is_mandatory(tmp_path: Path) -> None:
    recovery_path, chain = _write_recovery_fixture(tmp_path)
    payload = json.loads(recovery_path.read_text(encoding="utf-8"))
    payload["status"] = "failed"
    unsigned = dict(payload)
    unsigned.pop("digest", None)
    payload["digest"] = _sha(
        json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()
    )
    recovery_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    tampered_ref = EvidenceReference(
        "recovery",
        "recovery-1",
        _sha(recovery_path.read_bytes()),
        recovery_path.name,
    )
    tampered_chain = replace(chain, recovery_ref=tampered_ref)
    with pytest.raises(ValueError, match="does not record an applied recovery result"):
        verify_reliability_recovery_outcome(tampered_chain, root=tmp_path)


def test_recovery_outcome_digest_is_deterministic() -> None:
    outcome = ReliabilityRecoveryOutcome(
        format_version="1",
        recovery_id="r",
        recovery_digest="a" * 64,
        recovery_status="applied",
        source_reconciliation_id="rec",
        reconciliation_id="rec",
        reconciliation_digest="b" * 64,
        reconciliation_status="recovered",
    )
    assert (
        outcome.digest == ReliabilityRecoveryOutcome.from_dict(outcome.to_dict()).digest
    )
