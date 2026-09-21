"""Tier 7 trust-domain and anchor assurance regression tests."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from statewake.adapters.trust_anchor import JsonTrustAnchorStore
from statewake.domain.attestation_trust import (
    AttestationTrustAnchor,
    SignedAttestationTrustState,
)
from statewake.domain.trust_anchor import (
    AnchorDiscrepancyError,
    TrustCheckpoint,
    compare_local_tip,
)

ROOT = Path(__file__).resolve().parents[1]


def _checkpoint(identifier: str, previous: str | None = None) -> TrustCheckpoint:
    return TrustCheckpoint(
        checkpoint_id=identifier,
        subject_id="subject-1",
        issued_at="2026-09-16T00:00:00Z",
        history_tip_digest="a" * 64,
        history_record_count=1,
        signing_key_id="checkpoint-key-1",
        signing_key_digest="b" * 64,
        signature="signature",
        previous_checkpoint_digest=previous,
    )


def test_checkpoint_store_rejects_conflicting_overwrite(tmp_path: Path) -> None:
    class Verifier:
        def verify(self, checkpoint: TrustCheckpoint) -> TrustCheckpoint:
            return checkpoint

    store = JsonTrustAnchorStore(tmp_path, Verifier())
    first = _checkpoint("cp-1")
    store.publish(first)
    conflicting = replace(first, signature="other-signature")
    with pytest.raises(AnchorDiscrepancyError):
        store.publish(conflicting)


def test_checkpoint_disagreement_is_security_discrepancy() -> None:
    checkpoint = _checkpoint("cp-1")
    with pytest.raises(AnchorDiscrepancyError, match="disagrees"):
        compare_local_tip(
            checkpoint,
            history_tip_digest="c" * 64,
            history_record_count=2,
        )


def test_key_purpose_separation_is_explicit() -> None:
    text = (ROOT / "docs/security/trust_domain_anchor_assurance.md").read_text(
        encoding="utf-8"
    )
    assert "artifact signing" in text
    assert "checkpoint signing" in text
    assert "release signing" in text
    assert "deployment credentials/secrets" in text
    assert "one key" in text


def test_attestation_trust_rotation_preserves_history() -> None:
    state = SignedAttestationTrustState(
        authority_key_id="authority-1",
        version=2,
        issued_at="2026-09-16T00:00:00Z",
        anchors=(
            AttestationTrustAnchor(
                "old", b"1" * 32, status="superseded", superseded_by="new"
            ),
            AttestationTrustAnchor("new", b"2" * 32, status="active"),
        ),
        signature="sig",
        previous_digest="a" * 64,
    )
    assert state.anchors[0].status == "superseded"
    assert state.anchors[0].superseded_by == "new"
    assert state.previous_digest == "a" * 64


def test_anchor_compromise_never_self_authenticates() -> None:
    text = (ROOT / "docs/security/trust_domain_anchor_assurance.md").read_text(
        encoding="utf-8"
    )
    assert "must not be treated as self-authenticating authority" in text
    assert "signature proves integrity/authenticity" in text
    assert "does not by itself prove administrative independence" in text


def test_trust_domain_assurance_is_not_a_release() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    document = (ROOT / "docs/security/trust_domain_anchor_assurance.md").read_text(
        encoding="utf-8"
    )
    assert 'version = "0.3.0"' in pyproject
    assert "not a release approval" in document.lower()
