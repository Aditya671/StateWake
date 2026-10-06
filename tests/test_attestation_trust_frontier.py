"""End-to-end regressions for attestation trust and key lifecycle investigation."""

from __future__ import annotations

import base64
import io
import json
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

import pytest

from statewake.adapters.reliability_attestation import (
    JsonlReliabilityOutcomeAttestationStore,
    read_reliability_attestation_snapshot,
)
from statewake.domain.attestation_trust import (
    AttestationTrustAnchor,
    SignedAttestationTrustState,
)
from statewake.domain.reliability_attestation import ReliabilityOutcomeAttestation
from statewake.presentation.attestation_trust import (
    AttestationTrustAuthentication,
    AttestationTrustQuery,
    build_attestation_trust_projection,
)
from statewake.read_api import ReadApiConfig, create_read_application


def _attestation(
    *,
    attestation_id: str,
    subject_id: str,
    signing_key_id: str | None,
    previous_digest: str = "",
    state: str = "reliable",
    decision: str = "accept",
    reconciliation: str = "verified",
) -> ReliabilityOutcomeAttestation:
    return ReliabilityOutcomeAttestation(
        attestation_id=attestation_id,
        subject_id=subject_id,
        occurred_at="2026-09-29T10:00:00+00:00",
        actor="operator",
        evidence_chain_id=f"chain-{attestation_id}",
        evidence_chain_digest="a" * 64,
        transition_id=f"transition-{attestation_id}",
        transition_digest="b" * 64,
        reliability_state=state,
        decision=decision,
        verification_status="verified",
        reconciliation_state=reconciliation,
        decision_rationale=("sensitive rationale must not be exposed",),
        signing_key_id=signing_key_id,
        previous_digest=previous_digest,
    )


def _attestation_store(
    tmp_path: Path,
) -> tuple[Path, tuple[ReliabilityOutcomeAttestation, ...]]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    first = _attestation(
        attestation_id="att-1",
        subject_id="agent-1",
        signing_key_id="key-active",
    )
    second = _attestation(
        attestation_id="att-2",
        subject_id="agent-2",
        signing_key_id="key-revoked",
        previous_digest=first.digest,
        state="unreliable",
        decision="reject",
    )
    path = tmp_path / "attestations.jsonl"
    payload = (
        "\n".join(
            json.dumps(item.to_dict(), sort_keys=True) for item in (first, second)
        )
        + "\n"
    ).encode("utf-8")
    path.write_bytes(payload)
    return path, (first, second)


def _trust_state() -> SignedAttestationTrustState:
    return SignedAttestationTrustState(
        authority_key_id="authority-1",
        version=3,
        issued_at="2026-09-29T11:00:00+00:00",
        previous_digest="c" * 64,
        anchors=(
            AttestationTrustAnchor("key-active", b"A" * 32, "active"),
            AttestationTrustAnchor("key-revoked", b"B" * 32, "revoked"),
            AttestationTrustAnchor("key-old", b"C" * 32, "superseded", "key-active"),
        ),
        signature=base64.urlsafe_b64encode(b"signature").rstrip(b"=").decode("ascii"),
    )


def _write_trust_sources(
    tmp_path: Path,
) -> tuple[Path, Path, SignedAttestationTrustState]:
    state = _trust_state()
    state_path = tmp_path / "trust-state.json"
    state_path.write_text(json.dumps(state.to_dict()), encoding="utf-8")
    authority_path = tmp_path / "authorities.json"
    authority_path.write_text(
        json.dumps(
            {
                "keys": {
                    "authority-1": base64.urlsafe_b64encode(b"D" * 32)
                    .rstrip(b"=")
                    .decode("ascii")
                }
            }
        ),
        encoding="utf-8",
    )
    return state_path, authority_path, state


def _request(
    application: Any,
    path: str,
    *,
    query: str = "",
    if_none_match: str | None = None,
) -> tuple[str, dict[str, str], dict[str, object] | None, bytes]:
    environ: dict[str, object] = {
        "REQUEST_METHOD": "GET",
        "PATH_INFO": path,
        "QUERY_STRING": query,
        "CONTENT_LENGTH": "0",
        "wsgi.input": io.BytesIO(b""),
        "wsgi.url_scheme": "http",
    }
    if if_none_match is not None:
        environ["HTTP_IF_NONE_MATCH"] = if_none_match
    captured: dict[str, object] = {}

    def start_response(status: str, headers: list[tuple[str, str]]) -> None:
        captured["status"] = status
        captured["headers"] = headers

    raw = b"".join(application(environ, start_response))
    payload = json.loads(raw) if raw else None
    headers = dict(cast(list[tuple[str, str]], captured["headers"]))
    return str(captured["status"]), headers, payload, raw


def test_snapshot_is_bounded_verified_and_does_not_create_lock(tmp_path: Path) -> None:
    path, records = _attestation_store(tmp_path)
    lock_path = path.with_name(f".{path.name}.lock")
    persisted = path.read_bytes()
    snapshot = read_reliability_attestation_snapshot(
        path, max_bytes=1_000_000, max_records=10
    )
    assert snapshot.exists is True
    assert snapshot.records == records
    assert b"\r\n" not in persisted
    assert snapshot.byte_size == len(persisted) == path.stat().st_size
    assert not lock_path.exists()


def test_snapshot_counts_existing_crlf_store_by_physical_bytes(tmp_path: Path) -> None:
    path, records = _attestation_store(tmp_path)
    canonical = path.read_bytes()
    assert b"\r\n" not in canonical
    crlf = b"\r\n".join(canonical.rstrip(b"\n").split(b"\n")) + b"\r\n"
    path.write_bytes(crlf)

    snapshot = read_reliability_attestation_snapshot(
        path, max_bytes=1_000_000, max_records=10
    )

    assert snapshot.exists is True
    assert snapshot.records == records
    assert snapshot.byte_size == len(crlf) == path.stat().st_size


def test_attestation_store_writes_canonical_lf_and_counts_exact_bytes(
    tmp_path: Path,
) -> None:
    first = _attestation(
        attestation_id="att-1",
        subject_id="agent-1",
        signing_key_id="key-active",
    )
    second = _attestation(
        attestation_id="att-2",
        subject_id="agent-2",
        signing_key_id="key-revoked",
        previous_digest=first.digest,
        state="unreliable",
        decision="reject",
    )
    path = tmp_path / "store-attestations.jsonl"
    store = JsonlReliabilityOutcomeAttestationStore(path)
    store.append(first)
    store.append(second)

    persisted = path.read_bytes()
    snapshot = read_reliability_attestation_snapshot(
        path, max_bytes=1_000_000, max_records=10
    )

    assert b"\r\n" not in persisted
    assert snapshot.records == (first, second)
    assert snapshot.byte_size == len(persisted) == path.stat().st_size


def test_projection_applies_authenticated_current_key_status_without_claiming_signature() -> (
    None
):
    first = _attestation(
        attestation_id="att-1", subject_id="agent-1", signing_key_id="key-active"
    )
    second = _attestation(
        attestation_id="att-2",
        subject_id="agent-2",
        signing_key_id="key-revoked",
        previous_digest=first.digest,
        state="unreliable",
        decision="reject",
    )
    from statewake.adapters.reliability_attestation import (
        ReliabilityAttestationSnapshot,
    )

    projection = build_attestation_trust_projection(
        ReliabilityAttestationSnapshot((first, second), 100, True),
        _trust_state(),
        AttestationTrustAuthentication(
            "verified", True, "verified", sha256(b"D" * 32).hexdigest()
        ),
        AttestationTrustQuery(),
        attestation_configured=True,
        attestation_read_limit_bytes=1024,
        attestation_record_limit=100,
        trust_state_configured=True,
        authority_store_configured=True,
    ).to_dict()
    items = cast(list[dict[str, object]], projection["items"])
    first_context = cast(dict[str, object], items[0]["key_context"])
    second_context = cast(dict[str, object], items[1]["key_context"])
    assert first_context["effective_current_status"] == "active"
    assert first_context["currently_trusted_for_signing"] is True
    assert second_context["effective_current_status"] == "revoked"
    assert second_context["currently_trusted_for_signing"] is False
    assert items[0]["signature_envelope_recorded"] is False
    assert "decision_rationale" not in items[0]


def test_unauthenticated_trust_state_is_diagnostic_not_authority(
    tmp_path: Path,
) -> None:
    attestation_path, _ = _attestation_store(tmp_path)
    state_path, _, _ = _write_trust_sources(tmp_path)
    app = create_read_application(
        ReadApiConfig(
            tmp_path / "workspace",
            attestation_store_path=attestation_path,
            attestation_trust_state_path=state_path,
        )
    )
    status, _, payload, _ = _request(app, "/api/v1/attestation-trust")
    assert status == "200 OK"
    assert payload is not None
    source = cast(dict[str, object], payload["sources"])
    trust_state = cast(dict[str, object], source["trust_state"])
    authentication = cast(dict[str, object], trust_state["authentication"])
    assert authentication["authenticated"] is None
    items = cast(list[dict[str, object]], payload["items"])
    key_context = cast(dict[str, object], items[0]["key_context"])
    assert key_context["recorded_anchor_status"] == "active"
    assert key_context["effective_current_status"] == "trust-state-unauthenticated"
    assert key_context["currently_trusted_for_signing"] is None


def test_authenticated_trust_state_wires_existing_verifier_without_exposing_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    attestation_path, _ = _attestation_store(tmp_path)
    state_path, authority_path, state = _write_trust_sources(tmp_path)

    def verified(
        self: object, supplied: SignedAttestationTrustState
    ) -> SignedAttestationTrustState:
        assert supplied == state
        return supplied

    monkeypatch.setattr(
        "statewake.read_api.Ed25519AttestationTrustStateVerifier.verify", verified
    )
    app = create_read_application(
        ReadApiConfig(
            tmp_path / "workspace",
            attestation_store_path=attestation_path,
            attestation_trust_state_path=state_path,
            attestation_authority_store_path=authority_path,
        )
    )
    status, headers, payload, raw = _request(app, "/api/v1/attestation-trust")
    assert status == "200 OK"
    assert payload is not None
    source = cast(dict[str, object], payload["sources"])
    trust_state = cast(dict[str, object], source["trust_state"])
    authentication = cast(dict[str, object], trust_state["authentication"])
    assert authentication["authenticated"] is True
    assert authentication["authority_key_digest"] == sha256(b"D" * 32).hexdigest()
    text = raw.decode("utf-8")
    assert str(attestation_path) not in text
    assert str(state_path) not in text
    assert str(authority_path) not in text
    assert base64.urlsafe_b64encode(b"A" * 32).decode("ascii") not in text
    assert state.signature not in text
    assert "sensitive rationale" not in text

    etag = headers["ETag"]
    status, headers, payload, raw = _request(
        app, "/api/v1/attestation-trust", if_none_match=etag
    )
    assert status == "304 Not Modified"
    assert headers["ETag"] == etag
    assert payload is None
    assert raw == b""


def test_failed_trust_state_authentication_is_result_not_parse_failure(
    tmp_path: Path,
) -> None:
    attestation_path, _ = _attestation_store(tmp_path)
    state_path, _, _ = _write_trust_sources(tmp_path)
    wrong_authority = tmp_path / "wrong-authority.json"
    wrong_authority.write_text(
        json.dumps(
            {
                "keys": {
                    "different-authority": base64.urlsafe_b64encode(b"E" * 32)
                    .rstrip(b"=")
                    .decode("ascii")
                }
            }
        ),
        encoding="utf-8",
    )
    app = create_read_application(
        ReadApiConfig(
            tmp_path / "workspace",
            attestation_store_path=attestation_path,
            attestation_trust_state_path=state_path,
            attestation_authority_store_path=wrong_authority,
        )
    )
    status, _, payload, _ = _request(app, "/api/v1/attestation-trust")
    assert status == "200 OK"
    assert payload is not None
    source = cast(dict[str, object], payload["sources"])
    trust_state = cast(dict[str, object], source["trust_state"])
    authentication = cast(dict[str, object], trust_state["authentication"])
    assert authentication["status"] == "failed"
    assert authentication["authenticated"] is False
    items = cast(list[dict[str, object]], payload["items"])
    context = cast(dict[str, object], items[0]["key_context"])
    assert context["effective_current_status"] == "trust-state-unauthenticated"


def test_filters_pagination_and_capability_advertisement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    attestation_path, _ = _attestation_store(tmp_path)
    state_path, authority_path, _ = _write_trust_sources(tmp_path)
    monkeypatch.setattr(
        "statewake.read_api.Ed25519AttestationTrustStateVerifier.verify",
        lambda self, state: state,
    )
    app = create_read_application(
        ReadApiConfig(
            tmp_path / "workspace",
            attestation_store_path=attestation_path,
            attestation_trust_state_path=state_path,
            attestation_authority_store_path=authority_path,
        )
    )
    status, _, payload, _ = _request(
        app,
        "/api/v1/attestation-trust",
        query="key_status=revoked&limit=1&offset=0",
    )
    assert status == "200 OK"
    assert payload is not None
    assert cast(dict[str, object], payload["page"])["matched"] == 1
    item = cast(list[dict[str, object]], payload["items"])[0]
    assert item["attestation_id"] == "att-2"

    status, _, payload, _ = _request(
        app, "/api/v1/attestation-trust", query="q=AGENT-1"
    )
    assert status == "200 OK"
    assert payload is not None
    assert cast(dict[str, object], payload["page"])["matched"] == 1

    for query in (
        "unknown=x",
        "decision=accept&decision=reject",
        "decision=maybe",
        "key_status=historical",
        "limit=201",
        "offset=-1",
        "q=",
    ):
        status, _, payload, _ = _request(app, "/api/v1/attestation-trust", query=query)
        assert status == "400 Bad Request"
        assert payload is not None
        error = cast(dict[str, object], payload["error"])
        assert error["code"] == "INVALID_ATTESTATION_TRUST_QUERY"


def test_tamper_and_read_bounds_fail_closed(tmp_path: Path) -> None:
    attestation_path, records = _attestation_store(tmp_path)
    tampered = json.loads(attestation_path.read_text(encoding="utf-8").splitlines()[1])
    tampered["previous_digest"] = "f" * 64
    attestation_path.write_text(
        json.dumps(records[0].to_dict()) + "\n" + json.dumps(tampered) + "\n",
        encoding="utf-8",
    )
    app = create_read_application(
        ReadApiConfig(tmp_path / "workspace", attestation_store_path=attestation_path)
    )
    status, _, payload, _ = _request(app, "/api/v1/attestation-trust")
    assert status == "422 Unprocessable Entity"
    assert payload is not None
    assert cast(dict[str, object], payload["error"])["code"] == (
        "INVALID_ATTESTATION_TRUST_SOURCE"
    )

    clean_path, _ = _attestation_store(tmp_path / "clean")
    app = create_read_application(
        ReadApiConfig(
            tmp_path / "workspace",
            attestation_store_path=clean_path,
            max_attestation_store_bytes=1,
        )
    )
    status, _, payload, _ = _request(app, "/api/v1/attestation-trust")
    assert status == "413 Request Entity Too Large"
    assert payload is not None
    assert cast(dict[str, object], payload["error"])["code"] == (
        "ATTESTATION_TRUST_SOURCE_TOO_LARGE"
    )


def test_unconfigured_source_is_explicit(tmp_path: Path) -> None:
    app = create_read_application(ReadApiConfig(tmp_path / "workspace"))
    status, _, payload, _ = _request(app, "/api/v1/attestation-trust")
    assert status == "404 Not Found"
    assert payload is not None
    assert cast(dict[str, object], payload["error"])["code"] == (
        "ATTESTATION_TRUST_SOURCE_NOT_CONFIGURED"
    )


def _history_states() -> tuple[SignedAttestationTrustState, ...]:
    first = SignedAttestationTrustState(
        authority_key_id="authority-1",
        version=1,
        issued_at="2026-09-29T09:00:00+00:00",
        anchors=(
            AttestationTrustAnchor("key-old", b"C" * 32, "active"),
            AttestationTrustAnchor("key-revoked", b"B" * 32, "active"),
        ),
        signature="sig-1",
        previous_digest=None,
    )
    second = SignedAttestationTrustState(
        authority_key_id="authority-1",
        version=2,
        issued_at="2026-09-29T10:00:00+00:00",
        anchors=(
            AttestationTrustAnchor("key-old", b"C" * 32, "superseded", "key-active"),
            AttestationTrustAnchor("key-active", b"A" * 32, "active"),
            AttestationTrustAnchor("key-revoked", b"B" * 32, "active"),
        ),
        signature="sig-2",
        previous_digest=first.digest(),
    )
    third = SignedAttestationTrustState(
        authority_key_id="authority-1",
        version=3,
        issued_at="2026-09-29T11:00:00+00:00",
        anchors=(
            AttestationTrustAnchor("key-old", b"C" * 32, "superseded", "key-active"),
            AttestationTrustAnchor("key-active", b"A" * 32, "active"),
            AttestationTrustAnchor("key-revoked", b"B" * 32, "revoked"),
        ),
        signature="sig-3",
        previous_digest=second.digest(),
    )
    return first, second, third


def _write_history_sources(
    tmp_path: Path,
) -> tuple[Path, Path, Path, SignedAttestationTrustState]:
    states = _history_states()
    history_path = tmp_path / "trust-history.jsonl"
    history_path.write_text(
        "".join(json.dumps(state.to_dict(), sort_keys=True) + "\n" for state in states),
        encoding="utf-8",
    )
    state_path = tmp_path / "trust-state.json"
    state_path.write_text(json.dumps(states[-1].to_dict()), encoding="utf-8")
    authority_path = tmp_path / "authorities.json"
    authority_path.write_text(
        json.dumps(
            {
                "keys": {
                    "authority-1": base64.urlsafe_b64encode(b"D" * 32)
                    .rstrip(b"=")
                    .decode("ascii")
                }
            }
        ),
        encoding="utf-8",
    )
    return history_path, state_path, authority_path, states[-1]


def test_authenticated_history_projects_lifecycle_without_attestation_time_claim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    attestation_path, _ = _attestation_store(tmp_path)
    history_path, state_path, authority_path, _ = _write_history_sources(tmp_path)
    monkeypatch.setattr(
        "statewake.read_api.Ed25519AttestationTrustStateVerifier.verify",
        lambda self, state: state,
    )
    app = create_read_application(
        ReadApiConfig(
            tmp_path / "workspace",
            attestation_store_path=attestation_path,
            attestation_trust_state_path=state_path,
            attestation_trust_history_path=history_path,
            attestation_authority_store_path=authority_path,
        )
    )
    status, _, payload, _ = _request(app, "/api/v1/attestation-trust")
    assert status == "200 OK"
    assert payload is not None
    assert payload["schema_version"] == "attestation-trust-investigation.v3"
    sources = cast(dict[str, object], payload["sources"])
    history = cast(dict[str, object], sources["trust_history"])
    assert history["state_count"] == 3
    assert history["authentication_status"] == "verified"
    assert history["lifecycle_authoritative"] is True
    assert history["current_tip_alignment"] == "verified"
    transitions = cast(list[dict[str, object]], history["transitions"])
    assert transitions[0]["superseded_keys"] == [
        {"key_id": "key-old", "superseded_by": "key-active"}
    ]
    assert transitions[1]["revoked_key_ids"] == ["key-revoked"]

    items = cast(list[dict[str, object]], payload["items"])
    active_context = cast(dict[str, object], items[0]["key_context"])
    active_history = cast(dict[str, object], active_context["historical_context"])
    assert active_history["observed_in_authenticated_history"] is True
    assert active_history["ever_observed_active"] is True
    assert active_history["observed_statuses"] == ["active"]
    assert active_history["attestation_time_binding_recorded"] is False
    assert active_history["attestation_time_status"] is None

    revoked_context = cast(dict[str, object], items[1]["key_context"])
    revoked_history = cast(dict[str, object], revoked_context["historical_context"])
    assert revoked_history["observed_statuses"] == ["active", "revoked"]
    assert revoked_history["latest_observed_status"] == "revoked"


def test_history_tip_can_supply_current_diagnostic_state_when_snapshot_is_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    history_path, _, authority_path, tip = _write_history_sources(tmp_path)
    monkeypatch.setattr(
        "statewake.read_api.Ed25519AttestationTrustStateVerifier.verify",
        lambda self, state: state,
    )
    app = create_read_application(
        ReadApiConfig(
            tmp_path / "workspace",
            attestation_trust_history_path=history_path,
            attestation_authority_store_path=authority_path,
        )
    )
    status, _, payload, _ = _request(app, "/api/v1/attestation-trust")
    assert status == "200 OK"
    assert payload is not None
    sources = cast(dict[str, object], payload["sources"])
    trust_state = cast(dict[str, object], sources["trust_state"])
    assert trust_state["configured"] is False
    assert trust_state["derived_from_history"] is True
    assert trust_state["digest"] == tip.digest()
    assert (
        cast(dict[str, object], trust_state["authentication"])["authenticated"] is True
    )


def test_history_without_authority_is_structural_only(tmp_path: Path) -> None:
    history_path, _, _, _ = _write_history_sources(tmp_path)
    app = create_read_application(
        ReadApiConfig(
            tmp_path / "workspace",
            attestation_trust_history_path=history_path,
        )
    )
    status, _, payload, _ = _request(app, "/api/v1/attestation-trust")
    assert status == "200 OK"
    assert payload is not None
    sources = cast(dict[str, object], payload["sources"])
    history = cast(dict[str, object], sources["trust_history"])
    assert history["chain_integrity"] == "verified"
    assert history["authentication_status"] == "authority-not-configured"
    assert history["lifecycle_authoritative"] is False
    assert history["transitions"] == []


def test_current_snapshot_must_match_history_tip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    history_path, state_path, authority_path, tip = _write_history_sources(tmp_path)
    mismatch = SignedAttestationTrustState(
        authority_key_id=tip.authority_key_id,
        version=tip.version,
        issued_at=tip.issued_at,
        anchors=(AttestationTrustAnchor("different", b"Z" * 32),),
        signature=tip.signature,
        previous_digest=tip.previous_digest,
    )
    state_path.write_text(json.dumps(mismatch.to_dict()), encoding="utf-8")
    monkeypatch.setattr(
        "statewake.read_api.Ed25519AttestationTrustStateVerifier.verify",
        lambda self, state: state,
    )
    app = create_read_application(
        ReadApiConfig(
            tmp_path / "workspace",
            attestation_trust_state_path=state_path,
            attestation_trust_history_path=history_path,
            attestation_authority_store_path=authority_path,
        )
    )
    status, _, payload, _ = _request(app, "/api/v1/attestation-trust")
    assert status == "422 Unprocessable Entity"
    assert payload is not None
    assert cast(dict[str, object], payload["error"])["code"] == (
        "INVALID_ATTESTATION_TRUST_SOURCE"
    )
