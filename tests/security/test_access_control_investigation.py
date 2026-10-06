"""Regression coverage for read-side identity-bound authorization reconstruction."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from statewake.services.access_control_investigation_service import (
    load_authorization_context,
)


def _payload(*, recorded: bool = True) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": "authorization-context.v1",
        "principal": {
            "principal_id": "alice@example.test",
            "roles": ["reader"],
            "resource_scopes": {"team-a": ["evidence-1"]},
            "status": "ACTIVE",
            "expires_at": "2026-10-01T00:00:00+00:00",
        },
        "policy": {
            "grants": [
                {"role": "reader", "operation": "READ", "allowed_states": ["verified"]},
                {
                    "role": "recovery-operator",
                    "operation": "RECOVER",
                    "allowed_states": ["degraded"],
                },
            ]
        },
        "request": {
            "operation": "READ",
            "resource_domain": "team-a",
            "resource_id": "evidence-1",
            "resource_state": "verified",
            "requested_at": "2026-09-30T00:00:00+00:00",
        },
    }
    if recorded:
        payload["recorded_decision"] = {
            "allowed": True,
            "principal_id": "alice@example.test",
            "operation": "READ",
            "resource_domain": "team-a",
            "resource_id": "evidence-1",
            "resource_state": "verified",
            "reason": "authorized",
            "matched_role": "reader",
        }
    return payload


def _write(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")


def test_authorization_context_replays_recorded_decision(tmp_path: Path) -> None:
    path = tmp_path / "authorization.json"
    _write(path, _payload())
    context = load_authorization_context(path, max_bytes=64_000)
    assert context.recorded_decision_present is True
    assert context.decision.allowed is True
    assert context.decision.matched_role == "reader"


def test_authorization_context_without_recorded_decision_is_still_replayable(
    tmp_path: Path,
) -> None:
    path = tmp_path / "authorization.json"
    _write(path, _payload(recorded=False))
    context = load_authorization_context(path, max_bytes=64_000)
    assert context.recorded_decision_present is False
    assert context.decision.allowed is True


def test_authorization_context_rejects_recorded_decision_mismatch(
    tmp_path: Path,
) -> None:
    payload = _payload()
    recorded = payload["recorded_decision"]
    assert isinstance(recorded, dict)
    recorded["allowed"] = False
    path = tmp_path / "authorization.json"
    _write(path, payload)
    with pytest.raises(ValueError, match="does not match policy replay"):
        load_authorization_context(path, max_bytes=64_000)


def test_authorization_context_replays_scope_denial(tmp_path: Path) -> None:
    payload = _payload(recorded=False)
    request = payload["request"]
    assert isinstance(request, dict)
    request["resource_id"] = "evidence-2"
    path = tmp_path / "authorization.json"
    _write(path, payload)
    context = load_authorization_context(path, max_bytes=64_000)
    assert context.decision.allowed is False
    assert context.decision.reason == "resource_scope_denied"


def test_authorization_context_replays_revoked_principal(tmp_path: Path) -> None:
    payload = _payload(recorded=False)
    principal = payload["principal"]
    assert isinstance(principal, dict)
    principal["status"] = "REVOKED"
    path = tmp_path / "authorization.json"
    _write(path, payload)
    context = load_authorization_context(path, max_bytes=64_000)
    assert context.decision.allowed is False
    assert context.decision.reason == "principal_revoked"


def test_authorization_context_rejects_scalar_coercion_and_extra_fields(
    tmp_path: Path,
) -> None:
    payload = _payload(recorded=False)
    principal = payload["principal"]
    assert isinstance(principal, dict)
    principal["principal_id"] = 123
    path = tmp_path / "authorization.json"
    _write(path, payload)
    with pytest.raises(ValueError, match="principal_id"):
        load_authorization_context(path, max_bytes=64_000)

    payload = _payload(recorded=False)
    payload["unexpected"] = True
    _write(path, payload)
    with pytest.raises(ValueError, match="unsupported fields"):
        load_authorization_context(path, max_bytes=64_000)


def test_authorization_context_rejects_symlink_and_oversize(tmp_path: Path) -> None:
    target = tmp_path / "authorization.json"
    _write(target, _payload())
    link = tmp_path / "authorization-link.json"
    link.symlink_to(target)
    with pytest.raises(ValueError, match="symlink"):
        load_authorization_context(link, max_bytes=64_000)
    with pytest.raises(OverflowError, match="byte limit"):
        load_authorization_context(target, max_bytes=1)
