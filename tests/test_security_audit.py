"""Regression tests for the independently stored security audit boundary."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from statewake.adapters.deployment_security import SecurityEvent
from statewake.adapters.security_audit import JsonlSecurityAuditStore


def _event(reason: str = "test") -> SecurityEvent:
    """Build one non-sensitive deployment security event."""
    return SecurityEvent(
        event="request_rejected",
        operation="verify:evidence",
        method="POST",
        path="/v1/evidence/verify",
        reason=reason,
    )


def test_append_and_read_preserves_audit_chain(tmp_path: Path) -> None:
    """Persisted events remain ordered and hash-linked."""
    store = JsonlSecurityAuditStore(tmp_path / "security.jsonl")
    first = store.append(_event("first"))
    second = store.append(_event("second"))

    records = store.read()

    assert [record.sequence for record in records] == [0, 1]
    assert second.previous_digest == first.digest
    assert records == [first, second]


def test_duplicate_append_is_allowed_but_not_overwrite(tmp_path: Path) -> None:
    """Repeated legitimate events append rather than replacing history."""
    store = JsonlSecurityAuditStore(tmp_path / "security.jsonl")
    store.append(_event("same"))
    store.append(_event("same"))

    assert len(store.read()) == 2


def test_tampered_record_digest_is_rejected(tmp_path: Path) -> None:
    """Reject audit history whose stored content no longer matches its digest."""
    path = tmp_path / "security.jsonl"
    store = JsonlSecurityAuditStore(path)
    store.append(_event("original"))
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["reason"] = "tampered"
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="digest mismatch"):
        store.read()


def test_tampered_chain_link_is_rejected(tmp_path: Path) -> None:
    """Reject a second record whose previous digest no longer matches history."""
    path = tmp_path / "security.jsonl"
    store = JsonlSecurityAuditStore(path)
    store.append(_event("first"))
    store.append(_event("second"))
    lines = path.read_text(encoding="utf-8").splitlines()
    second = json.loads(lines[1])
    second["previous_digest"] = "0" * 64
    path.write_text(lines[0] + "\n" + json.dumps(second) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="discontinuous"):
        store.read()


def test_security_event_payload_is_not_persisted(tmp_path: Path) -> None:
    """Persist only safe event context, never request secrets or payload bodies."""
    store = JsonlSecurityAuditStore(tmp_path / "security.jsonl")
    event = SecurityEvent(
        event="authentication_failed",
        operation="verify:evidence",
        method="POST",
        path="/v1/evidence/verify",
        reason="authentication_failed",
    )
    store.append(event)
    raw = (tmp_path / "security.jsonl").read_text(encoding="utf-8")

    assert "Authorization" not in raw
    assert "secret-token" not in raw
    assert "request-body" not in raw
