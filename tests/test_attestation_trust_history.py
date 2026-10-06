"""Regression coverage for durable attestation trust-state history."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from statewake.adapters.attestation_trust_history import (
    JsonlAttestationTrustHistoryStore,
    read_attestation_trust_history_snapshot,
)
from statewake.domain.attestation_trust import (
    AttestationTrustAnchor,
    SignedAttestationTrustState,
    validate_attestation_trust_transition,
)
from statewake.services.trust_service import append_attestation_trust_state


class _Verifier:
    def verify(self, state: SignedAttestationTrustState) -> SignedAttestationTrustState:
        if state.signature == "bad":
            raise ValueError("signature rejected")
        return state


def _state(
    version: int,
    *,
    previous_digest: str | None,
    anchors: tuple[AttestationTrustAnchor, ...],
    signature: str = "sig",
    authority: str = "authority-1",
) -> SignedAttestationTrustState:
    return SignedAttestationTrustState(
        authority_key_id=authority,
        version=version,
        issued_at=f"2026-10-01T00:00:0{version}+00:00",
        anchors=anchors,
        signature=signature,
        previous_digest=previous_digest,
    )


def test_history_store_persists_authenticated_chain_and_current_tip(
    tmp_path: Path,
) -> None:
    first = _state(
        1,
        previous_digest=None,
        anchors=(AttestationTrustAnchor("key-1", b"A" * 32),),
    )
    second = _state(
        2,
        previous_digest=first.digest(),
        anchors=(
            AttestationTrustAnchor("key-1", b"A" * 32, "superseded", "key-2"),
            AttestationTrustAnchor("key-2", b"B" * 32),
        ),
    )
    path = tmp_path / "trust-history.jsonl"
    current = tmp_path / "trust-current.json"
    store = JsonlAttestationTrustHistoryStore(path, _Verifier())

    append_attestation_trust_state(
        first, history_store=store, current_state_path=current
    )
    append_attestation_trust_state(
        second, history_store=store, current_state_path=current
    )

    assert store.read() == (first, second)
    assert json.loads(current.read_text(encoding="utf-8")) == second.to_dict()
    if os.name != "nt":
        assert path.stat().st_mode & 0o777 == 0o600


def test_history_exact_replay_is_idempotent_but_version_conflict_rejects(
    tmp_path: Path,
) -> None:
    first = _state(
        1,
        previous_digest=None,
        anchors=(AttestationTrustAnchor("key-1", b"A" * 32),),
    )
    store = JsonlAttestationTrustHistoryStore(tmp_path / "history.jsonl", _Verifier())
    assert store.append(first) == first
    assert store.append(first) == first
    conflicting = _state(
        1,
        previous_digest=None,
        anchors=(AttestationTrustAnchor("other", b"B" * 32),),
    )
    with pytest.raises(ValueError, match="version already exists"):
        store.append(conflicting)


def test_transition_rejects_gap_reactivation_and_key_material_change() -> None:
    first = _state(
        1,
        previous_digest=None,
        anchors=(AttestationTrustAnchor("key-1", b"A" * 32),),
    )
    with pytest.raises(ValueError, match="advance by exactly one"):
        validate_attestation_trust_transition(
            first,
            _state(
                3,
                previous_digest=first.digest(),
                anchors=(AttestationTrustAnchor("key-1", b"A" * 32),),
            ),
        )

    revoked = _state(
        2,
        previous_digest=first.digest(),
        anchors=(AttestationTrustAnchor("key-1", b"A" * 32, "revoked"),),
    )
    with pytest.raises(ValueError, match="cannot be reactivated"):
        validate_attestation_trust_transition(
            revoked,
            _state(
                3,
                previous_digest=revoked.digest(),
                anchors=(AttestationTrustAnchor("key-1", b"A" * 32),),
            ),
        )
    with pytest.raises(ValueError, match="key material changed"):
        validate_attestation_trust_transition(
            first,
            _state(
                2,
                previous_digest=first.digest(),
                anchors=(AttestationTrustAnchor("key-1", b"B" * 32),),
            ),
        )


def test_history_reader_rejects_bad_chain_oversize_and_symlink(tmp_path: Path) -> None:
    first = _state(
        1,
        previous_digest=None,
        anchors=(AttestationTrustAnchor("key-1", b"A" * 32),),
    )
    broken = _state(
        2,
        previous_digest="f" * 64,
        anchors=(AttestationTrustAnchor("key-1", b"A" * 32),),
    )
    path = tmp_path / "history.jsonl"
    path.write_text(
        json.dumps(first.to_dict()) + "\n" + json.dumps(broken.to_dict()) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="previous_digest"):
        read_attestation_trust_history_snapshot(path, max_bytes=100_000, max_records=10)
    with pytest.raises(OverflowError, match="read limit"):
        read_attestation_trust_history_snapshot(path, max_bytes=1, max_records=10)

    if hasattr(os, "symlink"):
        target = tmp_path / "target.jsonl"
        target.write_text(json.dumps(first.to_dict()) + "\n", encoding="utf-8")
        link = tmp_path / "link.jsonl"
        try:
            link.symlink_to(target)
        except OSError:
            pytest.skip("symlink creation unavailable")
        with pytest.raises(ValueError, match="symlink"):
            read_attestation_trust_history_snapshot(
                link, max_bytes=100_000, max_records=10
            )


def test_history_store_rejects_unauthenticated_state(tmp_path: Path) -> None:
    state = _state(
        1,
        previous_digest=None,
        anchors=(AttestationTrustAnchor("key-1", b"A" * 32),),
        signature="bad",
    )
    store = JsonlAttestationTrustHistoryStore(tmp_path / "history.jsonl", _Verifier())
    with pytest.raises(ValueError, match="signature rejected"):
        store.append(state)
    assert not (tmp_path / "history.jsonl").exists()


def test_history_rejects_key_reappearance_after_removal(tmp_path: Path) -> None:
    first = _state(
        1,
        previous_digest=None,
        anchors=(AttestationTrustAnchor("key-1", b"A" * 32),),
    )
    second = _state(2, previous_digest=first.digest(), anchors=())
    third = _state(
        3,
        previous_digest=second.digest(),
        anchors=(AttestationTrustAnchor("key-1", b"A" * 32),),
    )
    path = tmp_path / "history.jsonl"
    path.write_text(
        "".join(json.dumps(item.to_dict()) + "\n" for item in (first, second, third)),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="cannot reappear"):
        read_attestation_trust_history_snapshot(path, max_bytes=100_000, max_records=10)
