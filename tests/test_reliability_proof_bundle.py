"""Regression tests for StateWake.

The active test suite protects the public package behavior and integration boundaries.
"""

import json
import sys
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from config.project_paths import PROJECT_ROOT, SRC_PATH
from statewake.adapters.reliability_attestation import (
    JsonlReliabilityOutcomeAttestationStore,
)
from statewake.adapters.reliability_state import JsonlReliabilityStateStore
from statewake.domain.attestation_trust import (
    AttestationTrustAnchor,
    SignedAttestationTrustState,
    create_signed_attestation_trust_state,
)
from statewake.domain.evidence_receipt import ExternalEvidenceReceipt
from statewake.domain.provenance import ProvenanceGraph, ProvenanceNode
from statewake.domain.reliability_evidence import (
    EvidenceReference,
    ReliabilityEvidenceChain,
)
from statewake.services.reliability_attestation_service import (
    attest_reliability_outcome,
    create_signed_reliability_outcome_envelope,
    write_reliability_outcome_attestation,
)
from statewake.services.reliability_evidence_service import (
    write_reliability_evidence_chain,
)
from statewake.services.reliability_proof_bundle_service import (
    build_reliability_proof_bundle,
    verify_reliability_proof_bundle,
)
from statewake.services.reliability_state_service import transition_reliability_state
from tests.support.reliability_proof import prepare_reliability_proof_fixture

NOW = datetime(2026, 9, 11, 0, 0, tzinfo=UTC)


def _refresh_lineage_graph(
    root: Path, chain: ReliabilityEvidenceChain
) -> ReliabilityEvidenceChain:
    """Verify the `_refresh_lineage_graph` behavior and its expected invariants."""
    refs = [("run", chain.run), ("state", chain.state)]
    for index, item in enumerate(chain.evidence):
        refs.append((f"evidence:{index}", item))
    if chain.decision_basis_ref is not None:
        refs.append(("decision_basis", chain.decision_basis_ref))
    if chain.reconciliation_ref is not None:
        refs.append(("reconciliation", chain.reconciliation_ref))
    if chain.recovery_ref is not None:
        refs.append(("recovery", chain.recovery_ref))
    nodes = []
    role_node = {}
    for role, ref in refs:
        node_id = role.replace(":", "-")
        role_node[role] = node_id
        parents: tuple[str, ...] = () if role == "run" else ("run",)
        nodes.append(
            ProvenanceNode(
                node_id=node_id,
                kind=ref.kind,
                digest=ref.digest,
                identity=ref.identity,
                derived_from=parents,
            )
        )
    # A decision basis derives from each exact declared input available in the chain.
    if chain.decision_basis_ref is not None:
        basis_path = root / chain.decision_basis_ref.source  # type: ignore
        import json as _json

        payload = _json.loads(basis_path.read_text(encoding="utf-8"))
        input_digests = tuple(str(x) for x in payload.get("input_digests", []))
        digest_nodes = {n.digest: n.node_id for n in nodes}
        parents = tuple(
            digest_nodes[x] for x in input_digests if x in digest_nodes
        ) or ("run",)
        basis_id = role_node["decision_basis"]
        nodes = [
            n
            if n.node_id != basis_id
            else ProvenanceNode(n.node_id, n.kind, n.digest, n.identity, parents)
            for n in nodes
        ]
    graph = ProvenanceGraph(
        tuple(nodes),
        tuple((node.node_id, parent) for node in nodes for parent in node.derived_from),
    )
    provenance_path = root / (chain.provenance.source or "provenance.json")
    provenance_path.write_text(
        json.dumps(graph.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return replace(
        chain,
        provenance=EvidenceReference(
            "provenance",
            chain.provenance.identity,
            sha256(provenance_path.read_bytes()).hexdigest(),
            provenance_path.name,
        ),
    )


def _prepare_signed_trust(root: Path, attestation_path: Path):
    """Verify the `_prepare_signed_trust` behavior and its expected invariants."""
    from nacl.signing import SigningKey

    authority_private = SigningKey.generate()
    authority_public = authority_private.verify_key.encode()
    signing_private = SigningKey.generate()
    signing_public = signing_private.verify_key.encode()
    attestation = json.loads(attestation_path.read_text(encoding="utf-8"))
    from statewake.domain.reliability_attestation import ReliabilityOutcomeAttestation

    canonical_attestation = ReliabilityOutcomeAttestation.from_dict(attestation)
    placeholder = create_signed_reliability_outcome_envelope(
        canonical_attestation, key_id="rel-key", signature=b"0" * 64
    )
    envelope = create_signed_reliability_outcome_envelope(
        canonical_attestation,
        key_id="rel-key",
        signature=signing_private.sign(placeholder.payload_bytes()).signature,
    )
    envelope_path = root / "signed-attestation.json"
    envelope_path.write_text(
        json.dumps(envelope.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    unsigned_state = SignedAttestationTrustState(
        authority_key_id="authority",
        version=1,
        issued_at="2026-09-11T00:00:00+00:00",
        anchors=(AttestationTrustAnchor("rel-key", signing_public),),
        signature="placeholder",
    )
    trust_state = create_signed_attestation_trust_state(
        unsigned_state,
        signature=authority_private.sign(unsigned_state.payload_bytes()).signature,
    )
    trust_state_path = root / "trust-state.json"
    trust_state_path.write_text(
        json.dumps(trust_state.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    import base64

    authority_path = root / "authority.json"
    authority_path.write_text(
        json.dumps(
            {
                "keys": {
                    "authority": base64.urlsafe_b64encode(authority_public)
                    .rstrip(b"=")
                    .decode("ascii")
                }
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return envelope_path, trust_state_path, authority_path


class TestReliabilityProofBundle(unittest.TestCase):
    """Provide regression coverage for the TestReliabilityProofBundle behavior."""

    def test_build_and_verify_portable_bundle(self):
        """Verify the `test_build_and_verify_portable_bundle` behavior and its expected invariants."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            att, chain, history = prepare_reliability_proof_fixture(root)
            output = root / "proof.zip"
            bundle, report = build_reliability_proof_bundle(
                attestation_path=att,
                evidence_chain_path=chain,
                history_path=history,
                evidence_root=root,
                output=output,
            )
            self.assertTrue(report.verified)
            self.assertEqual(bundle.agent_name, "agent-1")
            verified, descriptor = verify_reliability_proof_bundle(output)
            self.assertTrue(verified.verified)
            self.assertEqual(descriptor.bundle_type, "reliability-proof")
            self.assertEqual(descriptor.attestation_id, report.attestation_id)

    def test_export_is_byte_deterministic(self):
        """Verify the `test_export_is_byte_deterministic` behavior and its expected invariants."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            att, chain, history = prepare_reliability_proof_fixture(root)
            first = root / "first.zip"
            second = root / "second.zip"
            build_reliability_proof_bundle(
                attestation_path=att,
                evidence_chain_path=chain,
                history_path=history,
                evidence_root=root,
                output=first,
            )
            build_reliability_proof_bundle(
                attestation_path=att,
                evidence_chain_path=chain,
                history_path=history,
                evidence_root=root,
                output=second,
            )
            self.assertEqual(first.read_bytes(), second.read_bytes())

    def test_bundle_verifies_after_original_inputs_are_removed(self):
        """Verify the `test_bundle_verifies_after_original_inputs_are_removed` behavior and its expected invariants."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            att, chain, history = prepare_reliability_proof_fixture(root)
            output = root / "proof.zip"
            build_reliability_proof_bundle(
                attestation_path=att,
                evidence_chain_path=chain,
                history_path=history,
                evidence_root=root,
                output=output,
            )
            for path in root.glob("*.json"):
                path.unlink()
            history.unlink()
            verified, descriptor = verify_reliability_proof_bundle(output)
            self.assertTrue(verified.verified)
            self.assertEqual(descriptor.bundle_type, "reliability-proof")

    def test_portable_bundle_carries_and_verifies_external_receipt_binding(self):
        """Verify the `test_portable_bundle_carries_and_verifies_external_receipt_binding` behavior and its expected invariants."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            att, chain_path, history = prepare_reliability_proof_fixture(root)
            evidence = root / "evidence.json"
            provenance = root / "provenance.json"
            receipt = ExternalEvidenceReceipt(
                producer_type="evaluation",
                producer_id="runner",
                artifact_digest=sha256(evidence.read_bytes()).hexdigest(),
                artifact_size=evidence.stat().st_size,
                captured_at=datetime(2026, 9, 11, 12, tzinfo=UTC),
                source_ref="eval://runner/1",
                source_event_id="event-1",
                run_id="run-1",
                provenance_ref=EvidenceReference(
                    "provenance",
                    "p1",
                    sha256(provenance.read_bytes()).hexdigest(),
                    provenance.name,
                ),
            )
            receipt_path = root / "receipt.json"
            receipt_path.write_text(
                json.dumps(receipt.to_dict(), indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            from statewake.services.reliability_evidence_service import (
                load_reliability_evidence_chain,
                write_reliability_evidence_chain,
            )

            chain = load_reliability_evidence_chain(chain_path)
            evidence_ref = EvidenceReference(
                "evidence",
                receipt.receipt_id,
                receipt.artifact_digest,
                evidence.name,
                receipt.receipt_reference(source=receipt_path.name),
            )
            chain = replace(chain, evidence=(evidence_ref,))
            chain = _refresh_lineage_graph(root, chain)
            # The receipt semantically references the provenance file digest; update that reference
            # after the graph file is finalized, then bind the receipt's new deterministic digest.
            receipt = ExternalEvidenceReceipt.from_dict(
                json.loads(receipt_path.read_text(encoding="utf-8"))
            )
            updated_receipt = ExternalEvidenceReceipt(
                producer_type=receipt.producer_type,
                producer_id=receipt.producer_id,
                artifact_digest=receipt.artifact_digest,
                artifact_size=receipt.artifact_size,
                captured_at=receipt.captured_at,
                source_ref=receipt.source_ref,
                source_event_id=receipt.source_event_id,
                producer_version=receipt.producer_version,
                run_id=receipt.run_id,
                provenance_ref=EvidenceReference(
                    "provenance",
                    chain.provenance.identity,
                    chain.provenance.digest,
                    chain.provenance.source,
                ),
                metadata=receipt.metadata,
            )
            receipt_path.write_text(
                json.dumps(updated_receipt.to_dict(), indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            evidence_ref = EvidenceReference(
                "evidence",
                updated_receipt.receipt_id,
                updated_receipt.artifact_digest,
                evidence.name,
                updated_receipt.receipt_reference(source=receipt_path.name),
            )
            chain = replace(chain, evidence=(evidence_ref,))
            write_reliability_evidence_chain(chain, chain_path)
            # Recreate the authoritative transition and attestation for the receipt-bound chain.
            history.unlink()
            att.unlink()
            transition = transition_reliability_state(
                "agent-1",
                chain,
                store=JsonlReliabilityStateStore(history),
                actor="engine",
                occurred_at=NOW,
                evidence_root=root,
            )
            attestation = attest_reliability_outcome(
                chain,
                transition,
                actor="engine",
                store=JsonlReliabilityOutcomeAttestationStore(
                    root / "attestations.jsonl"
                ),
                occurred_at=NOW,
            )
            write_reliability_outcome_attestation(attestation, att)
            output = root / "proof.zip"
            build_reliability_proof_bundle(
                attestation_path=att,
                evidence_chain_path=chain_path,
                history_path=history,
                evidence_root=root,
                output=output,
            )
            for path in root.glob("*.json"):
                if path.name != "proof.zip":
                    path.unlink()
            history.unlink()
            verified, descriptor = verify_reliability_proof_bundle(output)
            self.assertTrue(verified.verified)
            self.assertTrue(
                any(
                    item.reference_key.endswith(":receipt")
                    for item in descriptor.sources
                )
            )

    def test_signed_attestation_trust_context_round_trip_is_portable(self):
        """Verify the `test_signed_attestation_trust_context_round_trip_is_portable` behavior and its expected invariants."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            att, chain, history = prepare_reliability_proof_fixture(root)
            envelope, trust_state, authority = _prepare_signed_trust(root, att)
            output = root / "proof-signed.zip"
            bundle, report = build_reliability_proof_bundle(  # type: ignore
                attestation_path=att,
                evidence_chain_path=chain,
                history_path=history,
                evidence_root=root,
                output=output,
                signed_attestation_path=envelope,
                attestation_trust_state_path=trust_state,
                attestation_authority_store_path=authority,
            )
            self.assertTrue(report.verified)
            descriptor = None
            _, descriptor = verify_reliability_proof_bundle(output)
            self.assertIsNotNone(descriptor.attestation_trust_context)
            assert descriptor.attestation_trust_context is not None
            self.assertEqual(
                descriptor.attestation_trust_context.signing_key_id, "rel-key"
            )
            for path in root.glob("*.json"):
                path.unlink()
            history.unlink()
            verified, descriptor = verify_reliability_proof_bundle(output)
            self.assertTrue(verified.verified)
            assert descriptor.attestation_trust_context is not None
            self.assertEqual(
                descriptor.attestation_trust_context.authority_key_id, "authority"
            )

    def test_portable_bundle_carries_and_verifies_decision_basis(self):
        """Verify the `test_portable_bundle_carries_and_verifies_decision_basis` behavior and its expected invariants."""
        from dataclasses import replace

        from statewake.domain.reliability_decision_basis import ReliabilityDecisionBasis
        from statewake.services.reliability_decision_basis_service import (
            write_reliability_decision_basis,
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            att, chain_path, history = prepare_reliability_proof_fixture(root)
            chain = __import__(
                "statewake.services.reliability_evidence_service",
                fromlist=["load_reliability_evidence_chain"],
            ).load_reliability_evidence_chain(chain_path)
            basis = ReliabilityDecisionBasis(
                "1",
                "policy",
                "refund-policy",
                "2026.1",
                "accept",
                "reliable",
                chain.decision_rationale,
                (chain.evidence[0].digest,),
            )
            basis_path = root / "decision-basis.json"
            write_reliability_decision_basis(basis, basis_path)
            chain = replace(
                chain,
                decision_basis_ref=EvidenceReference(
                    "policy",
                    "refund-policy",
                    sha256(basis_path.read_bytes()).hexdigest(),
                    basis_path.name,
                ),
            )
            chain = _refresh_lineage_graph(root, chain)
            write_reliability_evidence_chain(chain, chain_path)
            history.unlink()
            att.unlink()
            transition = transition_reliability_state(
                "agent-1",
                chain,
                store=JsonlReliabilityStateStore(history),
                actor="engine",
                occurred_at=NOW,
                evidence_root=root,
            )
            attestation = attest_reliability_outcome(
                chain,
                transition,
                actor="engine",
                store=JsonlReliabilityOutcomeAttestationStore(
                    root / "attestations.jsonl"
                ),
                occurred_at=NOW,
            )
            write_reliability_outcome_attestation(attestation, att)
            output = root / "proof.zip"
            build_reliability_proof_bundle(
                attestation_path=att,
                evidence_chain_path=chain_path,
                history_path=history,
                evidence_root=root,
                output=output,
            )
            for path in root.glob("*.json"):
                path.unlink()
            history.unlink()
            verified, descriptor = verify_reliability_proof_bundle(output)
            self.assertTrue(verified.verified)
            self.assertTrue(
                any(
                    item.reference_key == "decision_basis"
                    for item in descriptor.sources
                )
            )

    def test_tampered_attestation_trust_state_cannot_be_packaged(self):
        """Verify the `test_tampered_attestation_trust_state_cannot_be_packaged` behavior and its expected invariants."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            att, chain, history = prepare_reliability_proof_fixture(root)
            envelope, trust_state, authority = _prepare_signed_trust(root, att)
            payload = json.loads(trust_state.read_text(encoding="utf-8"))
            payload["anchors"][0]["status"] = "revoked"
            trust_state.write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            with self.assertRaises(ValueError):
                build_reliability_proof_bundle(
                    attestation_path=att,
                    evidence_chain_path=chain,
                    history_path=history,
                    evidence_root=root,
                    output=root / "proof.zip",
                    signed_attestation_path=envelope,
                    attestation_trust_state_path=trust_state,
                    attestation_authority_store_path=authority,
                )

    def test_tampered_signed_envelope_fails_offline(self):
        """Verify the `test_tampered_signed_envelope_fails_offline` behavior and its expected invariants."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            att, chain, history = prepare_reliability_proof_fixture(root)
            envelope, trust_state, authority = _prepare_signed_trust(root, att)
            output = root / "proof.zip"
            build_reliability_proof_bundle(
                attestation_path=att,
                evidence_chain_path=chain,
                history_path=history,
                evidence_root=root,
                output=output,
                signed_attestation_path=envelope,
                attestation_trust_state_path=trust_state,
                attestation_authority_store_path=authority,
            )
            tampered = root / "tampered.zip"
            with (
                ZipFile(output) as source,
                ZipFile(tampered, "w", compression=ZIP_DEFLATED) as target,
            ):
                for name in source.namelist():
                    info = ZipInfo(name)
                    info.date_time = (1980, 1, 1, 0, 0, 0)
                    info.compress_type = ZIP_DEFLATED
                    info.external_attr = 0o100644 << 16
                    data = source.read(name)
                    if name.endswith("/proof/attestation-envelope.json"):
                        payload = json.loads(data.decode("utf-8"))
                        payload["signature"] = payload["signature"][::-1]
                        data = (
                            json.dumps(payload, indent=2, sort_keys=True) + "\n"
                        ).encode()
                    target.writestr(info, data)
            with self.assertRaises(ValueError):
                verify_reliability_proof_bundle(tampered)

    def test_cli_build_and_verify_signed_proof(self):
        """Verify the `test_cli_build_and_verify_signed_proof` behavior and its expected invariants."""
        import os
        import subprocess

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            att, chain, history = prepare_reliability_proof_fixture(root)
            envelope, trust_state, authority = _prepare_signed_trust(root, att)
            output = root / "cli-proof.zip"
            environment = {**os.environ}
            source_root = str(SRC_PATH)
            environment["PYTHONPATH"] = os.pathsep.join(
                filter(None, (source_root, environment.get("PYTHONPATH")))
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "statewake.cli.main",
                    "reliability-proof-bundle",
                    "--attestation",
                    str(att),
                    "--chain",
                    str(chain),
                    "--history",
                    str(history),
                    "--evidence-root",
                    str(root),
                    "--output",
                    str(output),
                    "--signed-attestation",
                    str(envelope),
                    "--attestation-trust-state",
                    str(trust_state),
                    "--attestation-authority-store",
                    str(authority),
                ],
                cwd=PROJECT_ROOT,
                env=environment,
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "statewake.cli.main",
                    "reliability-proof-verify",
                    str(output),
                ],
                cwd=PROJECT_ROOT,
                env=environment,
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn('"verified": true', proc.stdout)
            self.assertIn('"attestation_id"', proc.stdout)

    def test_proof_descriptor_versions_preserve_legacy_shape(self):
        """Verify the `test_proof_descriptor_versions_preserve_legacy_shape` behavior and its expected invariants."""
        from statewake.domain.reliability_proof_bundle import (
            ReliabilityProofBundleDescriptor,
        )

        common = {
            "bundle_type": "reliability-proof",
            "subject_id": "agent-1",
            "attestation_artifact_id": "a",
            "evidence_chain_artifact_id": "b",
            "state_history_artifact_id": "c",
            "verification_report_artifact_id": "d",
            "attestation_id": "att",
            "attestation_digest": "a" * 64,
            "evidence_chain_id": "chain",
            "evidence_chain_digest": "b" * 64,
            "transition_id": "tr",
            "transition_digest": "c" * 64,
            "reliability_state": "reliable",
            "decision": "accept",
            "verification_report_digest": "d" * 64,
            "sources": (),
        }
        legacy = ReliabilityProofBundleDescriptor(format_version="1", **common)  # type: ignore
        self.assertEqual(
            ReliabilityProofBundleDescriptor.from_dict(legacy.to_dict()), legacy
        )
        with self.assertRaises(ValueError):
            ReliabilityProofBundleDescriptor(
                format_version="1",
                lineage_closure=object(),  # type: ignore
                **common,  # type: ignore
            )

    def test_trust_context_digest_is_self_consistent(self):
        """Verify the `test_trust_context_digest_is_self_consistent` behavior and its expected invariants."""
        from statewake.domain.reliability_attestation_trust_context import (
            ReliabilityAttestationTrustContext,
        )

        context = ReliabilityAttestationTrustContext(
            format_version="1",
            envelope_artifact_id="e",
            envelope_digest="a" * 64,
            attestation_id="att",
            attestation_digest="b" * 64,
            signing_key_id="signer",
            signing_key_digest="c" * 64,
            trust_state_artifact_id="s",
            trust_state_digest="d" * 64,
            trust_state_version=2,
            authority_store_artifact_id="a",
            authority_key_id="authority",
            authority_key_digest="e" * 64,
        )
        payload = context.to_dict()
        self.assertEqual(ReliabilityAttestationTrustContext.from_dict(payload), context)
        payload["signing_key_id"] = "attacker"
        with self.assertRaises(ValueError):
            ReliabilityAttestationTrustContext.from_dict(payload)

    def test_tampered_source_fails_closed(self):
        """Verify the `test_tampered_source_fails_closed` behavior and its expected invariants."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            att, chain, history = prepare_reliability_proof_fixture(root)
            output = root / "proof.zip"
            build_reliability_proof_bundle(
                attestation_path=att,
                evidence_chain_path=chain,
                history_path=history,
                evidence_root=root,
                output=output,
            )
            tampered = root / "tampered.zip"
            with (
                ZipFile(output) as source,
                ZipFile(tampered, "w", compression=ZIP_DEFLATED) as target,
            ):
                for name in source.namelist():
                    info = ZipInfo(name)
                    info.date_time = (1980, 1, 1, 0, 0, 0)
                    info.compress_type = ZIP_DEFLATED
                    info.external_attr = 0o100644 << 16
                    target.writestr(
                        info,
                        b"tampered"
                        if "/source-" in name and name.endswith("/run.json")
                        else source.read(name),
                    )
            with self.assertRaises(ValueError):
                verify_reliability_proof_bundle(tampered)

    def test_tampered_descriptor_fails_closed(self):
        """Verify the `test_tampered_descriptor_fails_closed` behavior and its expected invariants."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            att, chain, history = prepare_reliability_proof_fixture(root)
            output = root / "proof.zip"
            build_reliability_proof_bundle(
                attestation_path=att,
                evidence_chain_path=chain,
                history_path=history,
                evidence_root=root,
                output=output,
            )
            tampered = root / "tampered.zip"
            with (
                ZipFile(output) as source,
                ZipFile(tampered, "w", compression=ZIP_DEFLATED) as target,
            ):
                for name in source.namelist():
                    info = ZipInfo(name)
                    info.date_time = (1980, 1, 1, 0, 0, 0)
                    info.compress_type = ZIP_DEFLATED
                    info.external_attr = 0o100644 << 16
                    data = source.read(name)
                    if name.endswith("/proof/descriptor.json"):
                        payload = json.loads(data.decode("utf-8"))
                        payload["decision"] = "reject"
                        data = (
                            json.dumps(payload, indent=2, sort_keys=True) + "\n"
                        ).encode("utf-8")
                    target.writestr(info, data)
            with self.assertRaises(ValueError):
                verify_reliability_proof_bundle(tampered)

    def test_unverified_outcome_cannot_be_packaged(self):
        """Verify the `test_unverified_outcome_cannot_be_packaged` behavior and its expected invariants."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prepare_reliability_proof_fixture(root)
            chain = json.loads((root / "chain.json").read_text(encoding="utf-8"))
            chain["verification_status"] = "failed"
            chain["decision"] = "reject"
            chain["reliability_state"] = "unreliable"
            chain["reconciliation_state"] = "invalid"
            chain.pop("digest", None)
            chain["digest"] = sha256(
                json.dumps(
                    chain, sort_keys=True, separators=(",", ":"), ensure_ascii=False
                ).encode("utf-8")
            ).hexdigest()
            (root / "chain.json").write_text(
                json.dumps(chain, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            with self.assertRaises(ValueError):
                build_reliability_proof_bundle(
                    attestation_path=root / "attestation.json",
                    evidence_chain_path=root / "chain.json",
                    history_path=root / "history.jsonl",
                    evidence_root=root,
                    output=root / "proof.zip",
                )

    def test_conflicting_source_path_is_rejected(self):
        """Verify the `test_conflicting_source_path_is_rejected` behavior and its expected invariants."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            att, chain_path, history = prepare_reliability_proof_fixture(root)
            payload = json.loads(chain_path.read_text(encoding="utf-8"))
            # Force run and evidence to point at the same source path with different digests.
            payload["run"]["source"] = "evidence.json"
            payload.pop("digest", None)
            payload["digest"] = sha256(
                json.dumps(
                    payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
                ).encode("utf-8")
            ).hexdigest()
            chain_path.write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            with self.assertRaises(ValueError):
                build_reliability_proof_bundle(
                    attestation_path=att,
                    evidence_chain_path=chain_path,
                    history_path=history,
                    evidence_root=root,
                    output=root / "proof.zip",
                )

    def test_missing_local_source_is_rejected(self):
        """Verify the `test_missing_local_source_is_rejected` behavior and its expected invariants."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            att, chain_path, history = prepare_reliability_proof_fixture(root)
            chain = json.loads(chain_path.read_text(encoding="utf-8"))
            chain["run"]["source"] = None
            chain.pop("digest", None)
            chain["digest"] = sha256(
                json.dumps(
                    chain, sort_keys=True, separators=(",", ":"), ensure_ascii=False
                ).encode("utf-8")
            ).hexdigest()
            chain_path.write_text(
                json.dumps(chain, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            with self.assertRaises(ValueError):
                build_reliability_proof_bundle(
                    attestation_path=att,
                    evidence_chain_path=chain_path,
                    history_path=history,
                    evidence_root=root,
                    output=root / "proof.zip",
                )


if __name__ == "__main__":
    unittest.main()
