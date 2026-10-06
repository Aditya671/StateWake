"""End-to-end regressions for canonical signed reliability-attestation persistence."""

from __future__ import annotations

import base64
import io
import json
import sys
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import cast

import pytest

from statewake.adapters.key_management import ExternalSigningAdapter
from statewake.adapters.reliability_attestation import (
    JsonlReliabilityOutcomeAttestationStore,
    SignedReliabilityOutcomeBinding,
    read_reliability_attestation_snapshot,
)
from statewake.adapters.reliability_state import JsonlReliabilityStateStore
from statewake.domain.attestation_trust import (
    AttestationTrustAnchor,
    SignedAttestationTrustState,
)
from statewake.domain.key_management import SigningKeyReference
from statewake.domain.reliability_attestation import ReliabilityOutcomeAttestation
from statewake.domain.reliability_evidence import (
    EvidenceReference,
    ReliabilityEvidenceChain,
)
from statewake.domain.reliability_state import ReliabilityStateTransition
from statewake.read_api import ReadApiConfig, create_read_application
from statewake.services.reliability_attestation_service import (
    build_reliability_attestation_trust_context,
    create_signed_reliability_outcome_envelope,
    record_signed_reliability_outcome,
    sign_and_record_reliability_outcome,
)
from statewake.services.reliability_evidence_service import (
    write_reliability_evidence_chain,
)


def _attestation(
    *, previous_digest: str = "", key_id: str = "key-1"
) -> ReliabilityOutcomeAttestation:
    return ReliabilityOutcomeAttestation(
        attestation_id="att-1",
        subject_id="subject-1",
        occurred_at="2026-10-01T00:00:00+00:00",
        actor="operator",
        evidence_chain_id="chain-1",
        evidence_chain_digest="a" * 64,
        transition_id="transition-1",
        transition_digest="b" * 64,
        reliability_state="reliable",
        decision="accept",
        verification_status="verified",
        reconciliation_state="verified",
        signing_key_id=key_id,
        previous_digest=previous_digest,
    )


def _trust_state(
    *,
    status: str = "active",
    version: int = 1,
    issued_at: str = "2026-10-01T00:00:00+00:00",
    previous_digest: str | None = None,
) -> SignedAttestationTrustState:
    return SignedAttestationTrustState(
        authority_key_id="authority-1",
        version=version,
        issued_at=issued_at,
        anchors=(AttestationTrustAnchor("key-1", b"K" * 32, status=status),),
        signature="authority-signature",
        previous_digest=previous_digest,
    )


def _binding(monkeypatch: pytest.MonkeyPatch) -> SignedReliabilityOutcomeBinding:
    monkeypatch.setattr(
        "statewake.services.reliability_attestation_service.Ed25519AttestationTrustStateVerifier.verify",
        lambda self, state: state,
    )
    monkeypatch.setattr(
        "statewake.services.reliability_attestation_service.verify_ed25519_signature",
        lambda public_key, message, signature: None,
    )
    attestation = _attestation()
    envelope = create_signed_reliability_outcome_envelope(
        attestation, key_id="key-1", signature=b"signature"
    )
    context = build_reliability_attestation_trust_context(
        envelope,
        trust_state=_trust_state(),
        authority_store={"authority-1": b"A" * 32},
    )
    return SignedReliabilityOutcomeBinding(envelope, context)


def _request(app: object, path: str) -> tuple[str, dict[str, object]]:
    environ = {
        "REQUEST_METHOD": "GET",
        "PATH_INFO": path,
        "QUERY_STRING": "",
        "CONTENT_LENGTH": "0",
        "wsgi.input": io.BytesIO(b""),
        "wsgi.url_scheme": "http",
    }
    captured: dict[str, object] = {}

    def start_response(status: str, headers: list[tuple[str, str]]) -> None:
        captured["status"] = status
        captured["headers"] = headers

    raw = b"".join(app(environ, start_response))  # type: ignore[operator]
    return str(captured["status"]), cast(dict[str, object], json.loads(raw))


def test_signed_binding_round_trip_preserves_legacy_attestation_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = JsonlReliabilityOutcomeAttestationStore(tmp_path / "attestations.jsonl")
    binding = _binding(monkeypatch)
    persisted = store.append_signed(binding)
    assert persisted == binding
    assert store.read() == [binding.attestation]
    assert store.read_signed_bindings() == (binding,)

    snapshot = read_reliability_attestation_snapshot(
        store.path, max_bytes=1_000_000, max_records=10
    )
    assert snapshot.records == (binding.attestation,)
    assert snapshot.signed_bindings == (binding,)
    assert snapshot.binding_for("att-1") == binding


def test_existing_legacy_attestation_can_gain_one_signed_binding_without_rewrite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = JsonlReliabilityOutcomeAttestationStore(tmp_path / "attestations.jsonl")
    binding = _binding(monkeypatch)
    store.append(binding.attestation)
    before = store.path.read_text(encoding="utf-8")
    store.append_signed(binding)
    after = store.path.read_text(encoding="utf-8")
    assert after.startswith(before)
    assert len(store.read()) == 1
    assert store.read_signed_bindings() == (binding,)
    assert store.append_signed(binding) == binding
    assert store.path.read_text(encoding="utf-8") == after


def test_conflicting_signed_binding_for_same_attestation_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = JsonlReliabilityOutcomeAttestationStore(tmp_path / "attestations.jsonl")
    first = _binding(monkeypatch)
    store.append_signed(first)
    second_envelope = create_signed_reliability_outcome_envelope(
        first.attestation, key_id="key-1", signature=b"different-signature"
    )
    second_context = build_reliability_attestation_trust_context(
        second_envelope,
        trust_state=_trust_state(),
        authority_store={"authority-1": b"A" * 32},
    )
    with pytest.raises(ValueError, match="binding collision"):
        store.append_signed(
            SignedReliabilityOutcomeBinding(second_envelope, second_context)
        )


def test_tampered_signed_binding_record_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = JsonlReliabilityOutcomeAttestationStore(tmp_path / "attestations.jsonl")
    binding = _binding(monkeypatch)
    store.append_signed(binding)
    lines = store.path.read_text(encoding="utf-8").splitlines()
    payload = json.loads(lines[1])
    payload["envelope"]["signature"] = "tampered-signature"
    lines[1] = json.dumps(payload)
    store.path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="trust context envelope digest|trust-state"):
        read_reliability_attestation_snapshot(
            store.path, max_bytes=1_000_000, max_records=10
        )


def test_record_signed_outcome_binds_exact_authenticated_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "statewake.services.reliability_attestation_service.Ed25519AttestationTrustStateVerifier.verify",
        lambda self, state: state,
    )
    monkeypatch.setattr(
        "statewake.services.reliability_attestation_service.verify_ed25519_signature",
        lambda public_key, message, signature: None,
    )
    store = JsonlReliabilityOutcomeAttestationStore(tmp_path / "attestations.jsonl")
    attestation = _attestation()
    envelope = create_signed_reliability_outcome_envelope(
        attestation, key_id="key-1", signature=b"signature"
    )
    binding = record_signed_reliability_outcome(
        envelope,
        trust_state=_trust_state(),
        authority_store={"authority-1": b"A" * 32},
        store=store,
    )
    assert binding.trust_context.trust_state_version == 1
    assert binding.trust_context.trust_state_digest == _trust_state().digest()
    assert binding.trust_context.signing_key_digest == sha256(b"K" * 32).hexdigest()
    assert binding.trust_context.authority_key_digest == sha256(b"A" * 32).hexdigest()


def test_revoked_key_cannot_be_recorded_as_signing_context(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "statewake.services.reliability_attestation_service.Ed25519AttestationTrustStateVerifier.verify",
        lambda self, state: state,
    )
    monkeypatch.setattr(
        "statewake.services.reliability_attestation_service.verify_ed25519_signature",
        lambda public_key, message, signature: None,
    )
    envelope = create_signed_reliability_outcome_envelope(
        _attestation(), key_id="key-1", signature=b"signature"
    )
    with pytest.raises(ValueError, match="revoked"):
        record_signed_reliability_outcome(
            envelope,
            trust_state=_trust_state(status="revoked"),
            authority_store={"authority-1": b"A" * 32},
            store=JsonlReliabilityOutcomeAttestationStore(tmp_path / "a.jsonl"),
        )


def test_external_signer_persists_verified_binding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "statewake.services.reliability_attestation_service.Ed25519AttestationTrustStateVerifier.verify",
        lambda self, state: state,
    )
    monkeypatch.setattr(
        "statewake.services.reliability_attestation_service.verify_ed25519_signature",
        lambda public_key, message, signature: None,
    )

    class Provider:
        def sign(self, key: SigningKeyReference, payload: bytes) -> bytes:
            assert key.key_id == "key-1"
            assert payload
            return b"external-signature"

    binding = sign_and_record_reliability_outcome(
        _attestation(),
        signing_adapter=ExternalSigningAdapter(Provider()),
        signing_key=SigningKeyReference(
            "key-1",
            "kms",
            public_key_digest=sha256(b"K" * 32).hexdigest(),
        ),
        trust_state=_trust_state(),
        authority_store={"authority-1": b"A" * 32},
        store=JsonlReliabilityOutcomeAttestationStore(tmp_path / "a.jsonl"),
    )
    assert binding.envelope.signature


def test_read_api_projects_verified_signed_binding_without_raw_crypto_material(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    binding = _binding(monkeypatch)
    store = JsonlReliabilityOutcomeAttestationStore(tmp_path / "attestations.jsonl")
    store.append_signed(binding)
    state = _trust_state()
    state_path = tmp_path / "trust-state.json"
    state_path.write_text(json.dumps(state.to_dict()), encoding="utf-8")
    history_path = tmp_path / "trust-history.jsonl"
    history_path.write_text(json.dumps(state.to_dict()) + "\n", encoding="utf-8")
    authority_path = tmp_path / "authorities.json"
    authority_path.write_text(
        json.dumps(
            {
                "keys": {
                    "authority-1": base64.urlsafe_b64encode(b"A" * 32)
                    .rstrip(b"=")
                    .decode("ascii")
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "statewake.read_api.Ed25519AttestationTrustStateVerifier.verify",
        lambda self, candidate: candidate,
    )
    monkeypatch.setattr(
        "statewake.read_api.verify_reliability_attestation_trust_context",
        lambda candidate, trust_state, authority_store: candidate.attestation,
    )
    app = create_read_application(
        ReadApiConfig(
            tmp_path / "workspace",
            attestation_store_path=store.path,
            attestation_trust_state_path=state_path,
            attestation_trust_history_path=history_path,
            attestation_authority_store_path=authority_path,
        )
    )
    status, payload = _request(app, "/api/v1/attestation-trust")
    assert status == "200 OK"
    assert payload["schema_version"] == "attestation-trust-investigation.v3"
    item = cast(list[dict[str, object]], payload["items"])[0]
    assert item["signature_envelope_recorded"] is True
    signing_context = cast(dict[str, object], item["signing_trust_context"])
    assert signing_context["recorded"] is True
    authentication = cast(dict[str, object], signing_context["authentication"])
    assert authentication["status"] == "verified"
    assert authentication["authenticated"] is True
    serialized = json.dumps(payload)
    assert "external-signature" not in serialized
    assert base64.urlsafe_b64encode(b"K" * 32).decode("ascii") not in serialized


def test_read_api_distinguishes_verified_signing_context_from_current_revocation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first_state = _trust_state()
    monkeypatch.setattr(
        "statewake.services.reliability_attestation_service.Ed25519AttestationTrustStateVerifier.verify",
        lambda self, state: state,
    )
    monkeypatch.setattr(
        "statewake.services.reliability_attestation_service.verify_ed25519_signature",
        lambda public_key, message, signature: None,
    )
    attestation = _attestation()
    envelope = create_signed_reliability_outcome_envelope(
        attestation, key_id="key-1", signature=b"signature"
    )
    context = build_reliability_attestation_trust_context(
        envelope,
        trust_state=first_state,
        authority_store={"authority-1": b"A" * 32},
    )
    binding = SignedReliabilityOutcomeBinding(envelope, context)
    store = JsonlReliabilityOutcomeAttestationStore(tmp_path / "attestations.jsonl")
    store.append_signed(binding)

    current_state = _trust_state(
        status="revoked",
        version=2,
        issued_at="2026-10-01T01:00:00+00:00",
        previous_digest=first_state.digest(),
    )
    state_path = tmp_path / "trust-state.json"
    state_path.write_text(json.dumps(current_state.to_dict()), encoding="utf-8")
    history_path = tmp_path / "trust-history.jsonl"
    history_path.write_text(
        json.dumps(first_state.to_dict())
        + "\n"
        + json.dumps(current_state.to_dict())
        + "\n",
        encoding="utf-8",
    )
    authority_path = tmp_path / "authorities.json"
    authority_path.write_text(
        json.dumps(
            {
                "keys": {
                    "authority-1": base64.urlsafe_b64encode(b"A" * 32)
                    .rstrip(b"=")
                    .decode("ascii")
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "statewake.read_api.Ed25519AttestationTrustStateVerifier.verify",
        lambda self, candidate: candidate,
    )
    monkeypatch.setattr(
        "statewake.read_api.verify_reliability_attestation_trust_context",
        lambda candidate, trust_state, authority_store: candidate.attestation,
    )
    app = create_read_application(
        ReadApiConfig(
            tmp_path / "workspace",
            attestation_store_path=store.path,
            attestation_trust_state_path=state_path,
            attestation_trust_history_path=history_path,
            attestation_authority_store_path=authority_path,
        )
    )
    status, payload = _request(app, "/api/v1/attestation-trust")
    assert status == "200 OK"
    item = cast(list[dict[str, object]], payload["items"])[0]
    key_context = cast(dict[str, object], item["key_context"])
    signing_context = cast(dict[str, object], item["signing_trust_context"])
    assert key_context["effective_current_status"] == "revoked"
    assert signing_context["signing_time_key_status"] == "active"
    assert (
        cast(dict[str, object], signing_context["authentication"])["authenticated"]
        is True
    )
    assert signing_context["trust_state_version"] == 1


def test_recorded_binding_without_authority_does_not_claim_authentication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    binding = _binding(monkeypatch)
    store = JsonlReliabilityOutcomeAttestationStore(tmp_path / "attestations.jsonl")
    store.append_signed(binding)
    state = _trust_state()
    state_path = tmp_path / "trust-state.json"
    state_path.write_text(json.dumps(state.to_dict()), encoding="utf-8")
    app = create_read_application(
        ReadApiConfig(
            tmp_path / "workspace",
            attestation_store_path=store.path,
            attestation_trust_state_path=state_path,
        )
    )
    status, payload = _request(app, "/api/v1/attestation-trust")
    assert status == "200 OK"
    item = cast(list[dict[str, object]], payload["items"])[0]
    signing_context = cast(dict[str, object], item["signing_trust_context"])
    authentication = cast(dict[str, object], signing_context["authentication"])
    assert item["signature_envelope_recorded"] is True
    assert authentication["status"] == "authority-not-configured"
    assert authentication["authenticated"] is None
    assert signing_context["signing_time_key_status"] is None


def test_external_signer_is_not_invoked_before_trust_state_authentication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fail closed before asking an external signer to act on unauthenticated policy."""

    class Provider:
        def __init__(self) -> None:
            self.calls = 0

        def sign(self, key: SigningKeyReference, payload: bytes) -> bytes:
            self.calls += 1
            return b"S" * 64

    provider = Provider()

    def reject_unauthenticated_state(self: object, state: object) -> object:
        raise ValueError("unauthenticated trust state")

    monkeypatch.setattr(
        "statewake.services.reliability_attestation_service.Ed25519AttestationTrustStateVerifier.verify",
        reject_unauthenticated_state,
    )
    store = JsonlReliabilityOutcomeAttestationStore(tmp_path / "attestations.jsonl")
    with pytest.raises(ValueError, match="unauthenticated trust state"):
        sign_and_record_reliability_outcome(
            _attestation(),
            signing_adapter=ExternalSigningAdapter(provider),
            signing_key=SigningKeyReference("key-1", "test-kms"),
            trust_state=_trust_state(),
            authority_store={"authority-1": b"A" * 32},
            store=store,
        )
    assert provider.calls == 0
    assert not store.path.exists()


def test_cli_signed_attestation_executes_external_provider_and_persists_binding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Exercise the production CLI -> external signer -> canonical binding path."""
    from statewake.cli.main import _run_attestation, build_parser

    chain = ReliabilityEvidenceChain(
        chain_id="chain-cli-signed",
        run=EvidenceReference("run", "run-1", "a" * 64),
        state=EvidenceReference("state", "state-1", "b" * 64),
        evidence=(EvidenceReference("evidence", "evidence-1", "c" * 64),),
        provenance=EvidenceReference("provenance", "provenance-1", "d" * 64),
        integrity=EvidenceReference("integrity", "integrity-1", "e" * 64),
        verification_status="verified",
        reliability_state="reliable",
        reconciliation_state="verified",
        decision="accept",
        decision_rationale=("verified",),
    )
    chain_path = tmp_path / "chain.json"
    write_reliability_evidence_chain(chain, chain_path)
    transition = ReliabilityStateTransition(
        transition_id="transition-cli-signed",
        subject_id="subject-cli-signed",
        from_state="unknown",
        to_state="reliable",
        occurred_at=datetime(2026, 10, 2, 1, 0, tzinfo=UTC),
        actor="state-engine",
        evidence_chain_id=chain.chain_id,
        evidence_chain_digest=chain.digest(),
        decision="accept",
        rationale=("verified",),
    )
    history_path = tmp_path / "state-history.jsonl"
    JsonlReliabilityStateStore(history_path).append(transition)

    trust_state = _trust_state()
    trust_state_path = tmp_path / "trust-state.json"
    trust_state_path.write_text(json.dumps(trust_state.to_dict()), encoding="utf-8")
    authority_path = tmp_path / "authority-store.json"
    authority_path.write_text(
        json.dumps(
            {
                "keys": {
                    "authority-1": base64.urlsafe_b64encode(b"A" * 32)
                    .rstrip(b"=")
                    .decode("ascii")
                }
            }
        ),
        encoding="utf-8",
    )

    request_path = tmp_path / "signer-request.json"
    signer_path = tmp_path / "signer.py"
    signer_path.write_text(
        """
import base64
import json
import pathlib
import sys

request = json.loads(sys.stdin.read())
pathlib.Path(sys.argv[1]).write_text(json.dumps(request), encoding="utf-8")
print(json.dumps({
    "protocol": "statewake-external-signing.v1",
    "algorithm": request["key"]["algorithm"],
    "key_id": request["key"]["key_id"],
    "signature_base64": base64.urlsafe_b64encode(b"S" * 64).rstrip(b"=").decode("ascii"),
}))
""".strip()
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "statewake.services.reliability_attestation_service.Ed25519AttestationTrustStateVerifier.verify",
        lambda self, state: state,
    )
    monkeypatch.setattr(
        "statewake.services.reliability_attestation_service.verify_ed25519_signature",
        lambda public_key, message, signature: None,
    )

    attestation_store_path = tmp_path / "attestations.jsonl"
    output_path = tmp_path / "attestation.json"
    args = build_parser().parse_args(
        [
            "reliability-attest",
            "subject-cli-signed",
            "--chain",
            str(chain_path),
            "--history",
            str(history_path),
            "--attestation-store",
            str(attestation_store_path),
            "--actor",
            "operator",
            "--occurred-at",
            "2026-10-02T02:00:00+00:00",
            "--output",
            str(output_path),
            "--signer-command",
            sys.executable,
            "--signer-arg",
            str(signer_path),
            "--signer-arg",
            str(request_path),
            "--signing-key-id",
            "key-1",
            "--signing-key-provider",
            "test-kms",
            "--signing-key-public-digest",
            sha256(b"K" * 32).hexdigest(),
            "--attestation-trust-state",
            str(trust_state_path),
            "--attestation-authority-store",
            str(authority_path),
        ]
    )
    _run_attestation(args)

    store = JsonlReliabilityOutcomeAttestationStore(attestation_store_path)
    records = store.read()
    bindings = store.read_signed_bindings()
    assert len(records) == 1
    assert len(bindings) == 1
    assert records[0].signing_key_id == "key-1"
    assert bindings[0].trust_context.trust_state_version == 1
    assert output_path.exists()
    output = json.loads(output_path.read_text(encoding="utf-8"))
    assert output["signing_key_id"] == "key-1"

    provider_request = json.loads(request_path.read_text(encoding="utf-8"))
    assert provider_request["protocol"] == "statewake-external-signing.v1"
    assert provider_request["key"]["key_id"] == "key-1"
    assert provider_request["key"]["provider"] == "test-kms"
    assert "private" not in json.dumps(provider_request).lower()

    cli_payload = json.loads(capsys.readouterr().out)
    assert cli_payload["signed_binding"]["persisted"] is True
    assert cli_payload["signed_binding"]["signature_envelope_recorded"] is True
    assert cli_payload["signed_binding"]["attestation_time_binding_recorded"] is False
    assert cli_payload["signed_binding"]["trust_state_version"] == 1
    assert cli_payload["attestation"]["signing_key_id"] == "key-1"
    assert "signature_base64" not in json.dumps(cli_payload)


def test_cli_signed_attestation_options_are_all_or_nothing(tmp_path: Path) -> None:
    """Reject partial signed mode before reading any candidate source files."""
    from statewake.cli.main import _run_attestation, build_parser

    args = build_parser().parse_args(
        [
            "reliability-attest",
            "subject-1",
            "--chain",
            str(tmp_path / "missing-chain.json"),
            "--history",
            str(tmp_path / "missing-history.jsonl"),
            "--attestation-store",
            str(tmp_path / "attestations.jsonl"),
            "--actor",
            "operator",
            "--signer-command",
            sys.executable,
        ]
    )
    with pytest.raises(
        ValueError, match="signed reliability attestation requires"
    ) as caught:
        _run_attestation(args)
    message = str(caught.value)
    assert "--signing-key-id" in message
    assert "--signing-key-provider" in message
    assert "--attestation-trust-state" in message
    assert "--attestation-authority-store" in message
    assert "missing-chain.json" not in message


def test_cli_signed_attestation_verify_resolves_exact_historical_trust_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify a persisted signed binding against its historical signing state."""
    from statewake.cli.main import _run_attestation_verify, build_parser
    from statewake.services.reliability_attestation_service import (
        attest_signed_reliability_outcome,
        write_reliability_outcome_attestation,
    )

    monkeypatch.setattr(
        "statewake.services.trust_service.Ed25519AttestationTrustStateVerifier.verify",
        lambda self, state: state,
    )
    monkeypatch.setattr(
        "statewake.services.reliability_attestation_service.Ed25519AttestationTrustStateVerifier.verify",
        lambda self, state: state,
    )
    monkeypatch.setattr(
        "statewake.services.reliability_attestation_service.verify_ed25519_signature",
        lambda public_key, message, signature: None,
    )

    chain = ReliabilityEvidenceChain(
        chain_id="chain-cli-verify-signed",
        run=EvidenceReference("run", "run-verify", "a" * 64),
        state=EvidenceReference("state", "state-verify", "b" * 64),
        evidence=(EvidenceReference("evidence", "evidence-verify", "c" * 64),),
        provenance=EvidenceReference("provenance", "provenance-verify", "d" * 64),
        integrity=EvidenceReference("integrity", "integrity-verify", "e" * 64),
        verification_status="verified",
        reliability_state="reliable",
        reconciliation_state="verified",
        decision="accept",
        decision_rationale=("verified",),
    )
    chain_path = tmp_path / "chain.json"
    write_reliability_evidence_chain(chain, chain_path)
    transition = ReliabilityStateTransition(
        transition_id="transition-cli-verify-signed",
        subject_id="subject-cli-verify-signed",
        from_state="unknown",
        to_state="reliable",
        occurred_at=datetime(2026, 10, 2, 3, 0, tzinfo=UTC),
        actor="state-engine",
        evidence_chain_id=chain.chain_id,
        evidence_chain_digest=chain.digest(),
        decision="accept",
        rationale=("verified",),
    )
    history_path = tmp_path / "state-history.jsonl"
    JsonlReliabilityStateStore(history_path).append(transition)

    signing_state = _trust_state()
    current_state = _trust_state(
        status="revoked",
        version=2,
        issued_at="2026-10-02T04:00:00+00:00",
        previous_digest=signing_state.digest(),
    )
    trust_history_path = tmp_path / "trust-history.jsonl"
    trust_history_path.write_text(
        json.dumps(signing_state.to_dict())
        + "\n"
        + json.dumps(current_state.to_dict())
        + "\n",
        encoding="utf-8",
    )
    current_state_path = tmp_path / "current-trust-state.json"
    current_state_path.write_text(json.dumps(current_state.to_dict()), encoding="utf-8")
    authority_path = tmp_path / "authority-store.json"
    authority_path.write_text(
        json.dumps(
            {
                "keys": {
                    "authority-1": base64.urlsafe_b64encode(b"A" * 32)
                    .rstrip(b"=")
                    .decode("ascii")
                }
            }
        ),
        encoding="utf-8",
    )

    class Provider:
        def sign(self, key: SigningKeyReference, payload: bytes) -> bytes:
            assert key.key_id == "key-1"
            assert payload
            return b"S" * 64

    store_path = tmp_path / "attestations.jsonl"
    binding = attest_signed_reliability_outcome(
        chain,
        transition,
        actor="operator",
        store=JsonlReliabilityOutcomeAttestationStore(store_path),
        signing_adapter=ExternalSigningAdapter(Provider()),
        signing_key=SigningKeyReference("key-1", "test-kms"),
        trust_state=signing_state,
        authority_store={"authority-1": b"A" * 32},
        occurred_at=datetime(2026, 10, 2, 3, 30, tzinfo=UTC),
    )
    attestation_path = tmp_path / "attestation.json"
    write_reliability_outcome_attestation(binding.attestation, attestation_path)

    args = build_parser().parse_args(
        [
            "reliability-attest-verify",
            "--attestation",
            str(attestation_path),
            "--chain",
            str(chain_path),
            "--history",
            str(history_path),
            "--subject-id",
            "subject-cli-verify-signed",
            "--attestation-store",
            str(store_path),
            "--attestation-trust-state",
            str(current_state_path),
            "--attestation-trust-history",
            str(trust_history_path),
            "--attestation-authority-store",
            str(authority_path),
        ]
    )
    _run_attestation_verify(args)

    payload = json.loads(capsys.readouterr().out)
    assert payload["verified"] is True
    assert payload["attestation_id"] == binding.attestation.attestation_id
    signed = payload["signed_binding"]
    assert signed["verified"] is True
    assert signed["record_type"] == "signed-reliability-outcome-binding.v1"
    assert signed["trust_state_version"] == 1
    assert signed["trust_state_digest"] == signing_state.digest()
    assert signed["signing_key_id"] == "key-1"
    assert signed["authority_key_id"] == "authority-1"
    assert signed["attestation_time_binding_recorded"] is False
    serialized = json.dumps(payload)
    assert binding.envelope.signature not in serialized
    assert base64.urlsafe_b64encode(b"K" * 32).decode("ascii") not in serialized


def test_cli_signed_attestation_verify_requires_complete_trust_configuration(
    tmp_path: Path,
) -> None:
    """Reject partial signed verification before reading candidate source files."""
    from statewake.cli.main import _run_attestation_verify, build_parser

    args = build_parser().parse_args(
        [
            "reliability-attest-verify",
            "--attestation",
            str(tmp_path / "missing-attestation.json"),
            "--chain",
            str(tmp_path / "missing-chain.json"),
            "--history",
            str(tmp_path / "missing-history.jsonl"),
            "--subject-id",
            "subject-1",
            "--attestation-store",
            str(tmp_path / "attestations.jsonl"),
        ]
    )
    with pytest.raises(
        ValueError, match="signed reliability attestation verification requires"
    ) as caught:
        _run_attestation_verify(args)
    message = str(caught.value)
    assert "--attestation-authority-store" in message
    assert "--attestation-trust-state/--attestation-trust-history" in message
    assert "missing-attestation.json" not in message


def test_signed_attestation_verify_rejects_missing_exact_trust_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fail closed when the canonical binding's exact trust state is unavailable."""
    from statewake.services.reliability_attestation_service import (
        verify_persisted_signed_reliability_outcome,
    )

    binding = _binding(monkeypatch)
    store = JsonlReliabilityOutcomeAttestationStore(tmp_path / "attestations.jsonl")
    store.append_signed(binding)
    other_state = _trust_state(
        status="revoked",
        version=2,
        issued_at="2026-10-02T04:00:00+00:00",
        previous_digest=_trust_state().digest(),
    )
    with pytest.raises(ValueError, match="trust state is unavailable"):
        verify_persisted_signed_reliability_outcome(
            binding.attestation,
            store=store,
            trust_states=(other_state,),
            authority_store={"authority-1": b"A" * 32},
        )


def test_legacy_attestation_verify_output_remains_unchanged(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Preserve the established unsigned reliability-attest-verify contract."""
    from statewake.cli.main import _run_attestation_verify, build_parser
    from statewake.services.reliability_attestation_service import (
        attest_reliability_outcome,
        write_reliability_outcome_attestation,
    )

    chain = ReliabilityEvidenceChain(
        chain_id="chain-cli-verify-legacy",
        run=EvidenceReference("run", "run-legacy", "a" * 64),
        state=EvidenceReference("state", "state-legacy", "b" * 64),
        evidence=(EvidenceReference("evidence", "evidence-legacy", "c" * 64),),
        provenance=EvidenceReference("provenance", "provenance-legacy", "d" * 64),
        integrity=EvidenceReference("integrity", "integrity-legacy", "e" * 64),
        verification_status="verified",
        reliability_state="reliable",
        reconciliation_state="verified",
        decision="accept",
        decision_rationale=("verified",),
    )
    chain_path = tmp_path / "chain.json"
    write_reliability_evidence_chain(chain, chain_path)
    transition = ReliabilityStateTransition(
        transition_id="transition-cli-verify-legacy",
        subject_id="subject-cli-verify-legacy",
        from_state="unknown",
        to_state="reliable",
        occurred_at=datetime(2026, 10, 2, 5, 0, tzinfo=UTC),
        actor="state-engine",
        evidence_chain_id=chain.chain_id,
        evidence_chain_digest=chain.digest(),
        decision="accept",
        rationale=("verified",),
    )
    history_path = tmp_path / "state-history.jsonl"
    JsonlReliabilityStateStore(history_path).append(transition)
    attestation = attest_reliability_outcome(
        chain,
        transition,
        actor="operator",
        store=JsonlReliabilityOutcomeAttestationStore(tmp_path / "attestations.jsonl"),
        occurred_at=datetime(2026, 10, 2, 5, 30, tzinfo=UTC),
    )
    attestation_path = tmp_path / "attestation.json"
    write_reliability_outcome_attestation(attestation, attestation_path)

    args = build_parser().parse_args(
        [
            "reliability-attest-verify",
            "--attestation",
            str(attestation_path),
            "--chain",
            str(chain_path),
            "--history",
            str(history_path),
            "--subject-id",
            "subject-cli-verify-legacy",
        ]
    )
    _run_attestation_verify(args)
    assert json.loads(capsys.readouterr().out) == {
        "attestation_id": attestation.attestation_id,
        "verified": True,
    }


def test_signed_attestation_verify_requires_canonical_signed_sidecar(
    tmp_path: Path,
) -> None:
    """Do not infer signed verification from signing_key_id without a sidecar."""
    from statewake.services.reliability_attestation_service import (
        verify_persisted_signed_reliability_outcome,
    )

    attestation = _attestation()
    store = JsonlReliabilityOutcomeAttestationStore(tmp_path / "attestations.jsonl")
    store.append(attestation)
    with pytest.raises(
        ValueError, match="canonical signed attestation binding not found"
    ):
        verify_persisted_signed_reliability_outcome(
            attestation,
            store=store,
            trust_states=(_trust_state(),),
            authority_store={"authority-1": b"A" * 32},
        )


def test_canonical_signed_proof_bundle_resolves_historical_signing_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Build a portable proof from the canonical sidecar and exact historical trust state."""
    from zipfile import ZipFile

    from statewake.domain.attestation_trust import AttestationTrustAnchor
    from statewake.services.reliability_attestation_service import (
        load_reliability_outcome_attestation,
    )
    from statewake.services.reliability_proof_bundle_service import (
        build_reliability_proof_bundle,
        verify_reliability_proof_bundle,
    )
    from tests.support.reliability_proof import prepare_reliability_proof_fixture

    monkeypatch.setattr(
        "statewake.services.trust_service.Ed25519AttestationTrustStateVerifier.verify",
        lambda self, state: state,
    )
    monkeypatch.setattr(
        "statewake.services.reliability_attestation_service.Ed25519AttestationTrustStateVerifier.verify",
        lambda self, state: state,
    )
    monkeypatch.setattr(
        "statewake.services.reliability_attestation_service.verify_ed25519_signature",
        lambda public_key, message, signature: None,
    )

    attestation_path, chain_path, state_history_path = (
        prepare_reliability_proof_fixture(tmp_path)
    )
    attestation = load_reliability_outcome_attestation(attestation_path)
    signing_state = SignedAttestationTrustState(
        authority_key_id="authority-1",
        version=1,
        issued_at="2026-10-01T00:00:00+00:00",
        anchors=(AttestationTrustAnchor("rel-key", b"K" * 32, status="active"),),
        signature="authority-signature-v1",
    )
    current_state = SignedAttestationTrustState(
        authority_key_id="authority-1",
        version=2,
        issued_at="2026-10-02T00:00:00+00:00",
        anchors=(AttestationTrustAnchor("rel-key", b"K" * 32, status="revoked"),),
        signature="authority-signature-v2",
        previous_digest=signing_state.digest(),
    )
    trust_history_path = tmp_path / "attestation-trust-history.jsonl"
    trust_history_path.write_text(
        json.dumps(signing_state.to_dict())
        + "\n"
        + json.dumps(current_state.to_dict())
        + "\n",
        encoding="utf-8",
    )
    current_state_path = tmp_path / "attestation-trust-state.json"
    current_state_path.write_text(json.dumps(current_state.to_dict()), encoding="utf-8")
    authority_path = tmp_path / "attestation-authority.json"
    authority_path.write_text(
        json.dumps(
            {
                "keys": {
                    "authority-1": base64.urlsafe_b64encode(b"A" * 32)
                    .rstrip(b"=")
                    .decode("ascii")
                }
            }
        ),
        encoding="utf-8",
    )

    envelope = create_signed_reliability_outcome_envelope(
        attestation,
        key_id="rel-key",
        signature=b"S" * 64,
    )
    context = build_reliability_attestation_trust_context(
        envelope,
        trust_state=signing_state,
        authority_store={"authority-1": b"A" * 32},
    )
    store_path = tmp_path / "attestations.jsonl"
    JsonlReliabilityOutcomeAttestationStore(store_path).append_signed(
        SignedReliabilityOutcomeBinding(envelope, context)
    )

    output = tmp_path / "canonical-signed-proof.zip"
    _, report = build_reliability_proof_bundle(
        attestation_path=attestation_path,
        evidence_chain_path=chain_path,
        history_path=state_history_path,
        evidence_root=tmp_path,
        output=output,
        attestation_store_path=store_path,
        attestation_trust_state_path=current_state_path,
        attestation_trust_history_path=trust_history_path,
        attestation_authority_store_path=authority_path,
    )
    assert report.verified is True

    offline_report, descriptor = verify_reliability_proof_bundle(output)
    assert offline_report.verified is True
    assert descriptor.attestation_trust_context is not None
    assert descriptor.attestation_trust_context.trust_state_version == 1
    assert (
        descriptor.attestation_trust_context.trust_state_digest
        == signing_state.digest()
    )
    assert descriptor.attestation_trust_context.envelope_artifact_id == (
        "proof-attestation-envelope"
    )

    with ZipFile(output) as archive:
        packaged_state = json.loads(
            next(
                archive.read(name).decode("utf-8")
                for name in archive.namelist()
                if name.endswith("/proof/attestation-trust-state.json")
            )
        )
        packaged_envelope = json.loads(
            next(
                archive.read(name).decode("utf-8")
                for name in archive.namelist()
                if name.endswith("/proof/attestation-envelope.json")
            )
        )
    assert packaged_state["version"] == 1
    assert packaged_envelope == envelope.to_dict()


def test_canonical_signed_proof_cli_configuration_is_all_or_nothing(
    tmp_path: Path,
) -> None:
    """Reject partial canonical proof input before reading missing proof sources."""
    from statewake.cli.main import _run_proof_bundle, build_parser

    args = build_parser().parse_args(
        [
            "reliability-proof-bundle",
            "--attestation",
            str(tmp_path / "missing-attestation.json"),
            "--chain",
            str(tmp_path / "missing-chain.json"),
            "--history",
            str(tmp_path / "missing-state-history.jsonl"),
            "--evidence-root",
            str(tmp_path),
            "--output",
            str(tmp_path / "proof.zip"),
            "--attestation-store",
            str(tmp_path / "attestations.jsonl"),
        ]
    )
    with pytest.raises(
        ValueError, match="canonical signed reliability proof requires"
    ) as exc:
        _run_proof_bundle(args)
    message = str(exc.value)
    assert "--attestation-authority-store" in message
    assert "--attestation-trust-state/--attestation-trust-history" in message
    assert "missing-attestation.json" not in message


def test_canonical_signed_proof_rejects_manual_and_store_modes_together(
    tmp_path: Path,
) -> None:
    """Do not accept two competing signed-proof authorities in one invocation."""
    from statewake.cli.main import _run_proof_bundle, build_parser

    args = build_parser().parse_args(
        [
            "reliability-proof-bundle",
            "--attestation",
            str(tmp_path / "missing-attestation.json"),
            "--chain",
            str(tmp_path / "missing-chain.json"),
            "--history",
            str(tmp_path / "missing-state-history.jsonl"),
            "--evidence-root",
            str(tmp_path),
            "--output",
            str(tmp_path / "proof.zip"),
            "--signed-attestation",
            str(tmp_path / "manual-envelope.json"),
            "--attestation-store",
            str(tmp_path / "attestations.jsonl"),
        ]
    )
    with pytest.raises(ValueError, match="cannot be combined"):
        _run_proof_bundle(args)
