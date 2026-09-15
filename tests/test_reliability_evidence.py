"""Regression tests for StateWake.

The active test suite protects the public package behavior and integration boundaries.
"""

# pyright: reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false
# pyright: reportUnknownParameterType=false
# pyright: reportMissingParameterType=false
import json
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from statewake.domain.evidence_receipt import ExternalEvidenceReceipt
from statewake.domain.reliability_evidence import (
    EvidenceReference,
    ReliabilityEvidenceChain,
)
from statewake.services.reliability_evidence_service import (
    build_reliability_evidence_chain,
    load_reliability_evidence_chain,
    verify_external_evidence_receipts,
    verify_reliability_evidence_chain,
    write_reliability_evidence_chain,
)


class ReliabilityEvidenceChainTests(unittest.TestCase):
    """Provide regression coverage for the ReliabilityEvidenceChainTests behavior."""

    def _fixtures(self, root: Path):
        """Verify the `_fixtures` behavior and its expected invariants."""

        def write(name: str, payload: object) -> Path:
            """Verify the `write` behavior and its expected invariants."""
            path = root / name
            path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
            return path

        return (
            write("run.json", {"run_id": "run-1", "events": []}),
            write("state.json", {"state_id": "state-1"}),
            write("evidence.json", {"evidence_id": "ev-1"}),
            write("provenance.json", {"graph_digest": "x"}),
            write("integrity.json", {"verified": True}),
            write("reconciliation.json", {"state": "verified"}),
            write("attestation.json", {"digest": "a"}),
        )

    def _chain(
        self,
        root: Path,
        *,
        verification_status: str = "verified",
        reliability_state: str = "reliable",
        reconciliation_state: str = "verified",
        decision: str = "accept",
        evidence_receipt_paths: dict[str, Path] | None = None,
    ):
        """Build a typed test evidence chain from deterministic local fixtures."""
        run, state, evidence, provenance, integrity, reconciliation, attestation = (
            self._fixtures(root)
        )
        chain = build_reliability_evidence_chain(
            run_id="run-1",
            run_path=run,
            state_id="state-1",
            state_path=state,
            evidence_paths=(evidence,),
            provenance_path=provenance,
            integrity_proof_path=integrity,
            reconciliation_path=reconciliation,
            attestation_path=attestation,
            verification_status=verification_status,
            reliability_state=reliability_state,
            reconciliation_state=reconciliation_state,
            decision=decision,
            rationale=("all authoritative references are verified",),
            evidence_receipt_paths=evidence_receipt_paths,
        )
        return chain, (run, state, evidence, provenance, integrity)

    def test_roundtrip_and_digest(self):
        """Verify the `test_roundtrip_and_digest` behavior and its expected invariants."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            chain, _ = self._chain(root)
            out = root / "chain.json"
            write_reliability_evidence_chain(chain, out)
            loaded = load_reliability_evidence_chain(out)
            self.assertEqual(loaded, chain)
            self.assertEqual(len(loaded.digest()), 64)

    def test_accept_requires_verified_reconciled_reliable_state(self):
        """Verify the `test_accept_requires_verified_reconciled_reliable_state` behavior and its expected invariants."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(ValueError):
                self._chain(
                    root,
                    verification_status="unverified",
                    reconciliation_state="pending",
                )

    def test_failed_chain_rejects_acceptance(self):
        """Verify the `test_failed_chain_rejects_acceptance` behavior and its expected invariants."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(ValueError):
                self._chain(
                    root,
                    verification_status="failed",
                    reliability_state="unreliable",
                    decision="accept",
                )

    def test_source_verification_detects_tampering(self):
        """Verify the `test_source_verification_detects_tampering` behavior and its expected invariants."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            chain, (_, _, evidence, _, _) = self._chain(root)
            verify_reliability_evidence_chain(chain, root=root)
            evidence.write_text("tampered", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                verify_reliability_evidence_chain(chain, root=root)

    def test_roundtrip_rejects_tampered_chain_digest(self):
        """Verify the `test_roundtrip_rejects_tampered_chain_digest` behavior and its expected invariants."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            chain, _ = self._chain(root)
            payload = chain.to_dict()
            payload["run"]["digest"] = "0" * 64
            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                ReliabilityEvidenceChain.from_dict(payload)

    def test_external_receipt_binding_is_verified(self):
        """Verify the `test_external_receipt_binding_is_verified` behavior and its expected invariants."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run, state, evidence, provenance, integrity, _, _ = self._fixtures(root)  # type: ignore
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
                    provenance.name,
                    sha256(provenance.read_bytes()).hexdigest(),
                    provenance.name,
                ),
            )
            receipt_path = root / "receipt.json"
            receipt_path.write_text(
                json.dumps(receipt.to_dict(), indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            chain = self._chain(
                root, evidence_receipt_paths={evidence.name: receipt_path}
            )[0]
            self.assertIsNotNone(chain.evidence[0].receipt_ref)
            verify_external_evidence_receipts(chain, root=root)

    def test_external_receipt_binding_rejects_wrong_producer_occurrence(self):
        """Verify the `test_external_receipt_binding_rejects_wrong_producer_occurrence` behavior and its expected invariants."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run, state, evidence, provenance, integrity, _, _ = self._fixtures(root)  # type: ignore
            receipt = ExternalEvidenceReceipt(
                producer_type="evaluation",
                producer_id="runner",
                artifact_digest=sha256(evidence.read_bytes()).hexdigest(),
                artifact_size=evidence.stat().st_size,
                captured_at=datetime(2026, 9, 11, 12, tzinfo=UTC),
                source_ref="eval://runner/1",
                source_event_id="event-1",
                run_id="other-run",
            )
            receipt_path = root / "receipt.json"
            receipt_path.write_text(
                json.dumps(receipt.to_dict(), indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            chain = self._chain(root)[0]
            ref = EvidenceReference(
                "evidence",
                receipt.receipt_id,
                receipt.artifact_digest,
                evidence.name,
                receipt.receipt_reference(source=receipt_path.name),
            )
            chain = replace(chain, evidence=(ref,))
            with self.assertRaisesRegex(ValueError, "run_id"):
                verify_external_evidence_receipts(chain, root=root)

    def test_external_receipt_binding_rejects_tampered_receipt(self):
        """Verify the `test_external_receipt_binding_rejects_tampered_receipt` behavior and its expected invariants."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run, state, evidence, provenance, integrity, _, _ = self._fixtures(root)  # type: ignore
            receipt = ExternalEvidenceReceipt(
                producer_type="evaluation",
                producer_id="runner",
                artifact_digest=sha256(evidence.read_bytes()).hexdigest(),
                artifact_size=evidence.stat().st_size,
                captured_at=datetime(2026, 9, 11, 12, tzinfo=UTC),
                source_ref="eval://runner/1",
                source_event_id="event-1",
                run_id="run-1",
            )
            receipt_path = root / "receipt.json"
            payload = receipt.to_dict()
            payload["producer_id"] = "attacker"
            receipt_path.write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            # Construct a binding to the trusted receipt identity/digest so verification must inspect the receipt bytes.
            from statewake.domain.reliability_evidence import EvidenceReference

            chain = self._chain(root)[0]
            ref = EvidenceReference(
                "evidence",
                receipt.receipt_id,
                receipt.artifact_digest,
                evidence.name,
                receipt.receipt_reference(source=receipt_path.name),
            )
            chain = replace(chain, evidence=(ref,))
            with self.assertRaisesRegex(ValueError, "digest|receipt_id"):
                verify_external_evidence_receipts(chain, root=root)


if __name__ == "__main__":
    unittest.main()
