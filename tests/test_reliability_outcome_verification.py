"""Regression tests for StateWake.

The active test suite protects the public package behavior and integration boundaries.
"""

import json
import tempfile
import unittest
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from statewake.adapters.reliability_attestation import (
    JsonlReliabilityOutcomeAttestationStore,
)
from statewake.adapters.reliability_state import JsonlReliabilityStateStore
from statewake.domain.reliability_attestation import ReliabilityOutcomeAttestation
from statewake.domain.reliability_evidence import (
    EvidenceReference,
    ReliabilityEvidenceChain,
)
from statewake.services.reliability_attestation_service import (
    attest_reliability_outcome,
)
from statewake.services.reliability_outcome_verification_service import (
    verify_reliability_outcome,
)
from statewake.services.reliability_state_service import transition_reliability_state

NOW = datetime(2026, 9, 11, 0, 0, tzinfo=UTC)
DIGESTS = [f"{i:x}" * 64 for i in range(1, 7)]


def write_fixture(root: Path, state="reliable") -> tuple[Path, Path, Path, Path, Path]:
    """Verify the `write_fixture` behavior and its expected invariants."""
    paths = []
    for name, payload in (
        ("run.json", {"run": "r1"}),
        ("state.json", {"state": state}),
        ("evidence.json", {"evidence": "e1"}),
        ("provenance.json", {"provenance": "p1"}),
        ("integrity.json", {"integrity": "verified"}),
    ):
        path = root / name
        path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        paths.append(path)
    return paths[0], paths[1], paths[2], paths[3], paths[4]


def chain(root: Path, state="reliable", decision="accept") -> ReliabilityEvidenceChain:
    """Verify the `chain` behavior and its expected invariants."""
    run, state_path, evidence, provenance, integrity = write_fixture(root, state)

    def ref(kind, identity, digest, source):
        """Verify the `ref` behavior and its expected invariants."""
        return EvidenceReference(kind, identity, digest, source)

    return ReliabilityEvidenceChain(
        chain_id="chain-1",
        run=ref("run", "run-1", sha256(run.read_bytes()).hexdigest(), run.name),
        state=ref(
            "state",
            "state-1",
            sha256(state_path.read_bytes()).hexdigest(),
            state_path.name,
        ),
        evidence=(
            ref(
                "evidence",
                "e1",
                sha256(evidence.read_bytes()).hexdigest(),
                evidence.name,
            ),
        ),
        provenance=ref(
            "provenance",
            "p1",
            sha256(provenance.read_bytes()).hexdigest(),
            provenance.name,
        ),
        integrity=ref(
            "integrity",
            "i1",
            sha256(integrity.read_bytes()).hexdigest(),
            integrity.name,
        ),
        verification_status="verified",
        reliability_state=state,
        reconciliation_state="verified",
        decision=decision,
        decision_rationale=("all required inputs verified",),
    )


class TestReliabilityOutcomeVerification(unittest.TestCase):
    """Provide regression coverage for the TestReliabilityOutcomeVerification behavior."""

    def _prepare(self, root: Path):
        """Verify the `_prepare` behavior and its expected invariants."""
        c = chain(root)
        state_store = JsonlReliabilityStateStore(root / "state-history.jsonl")
        transition = transition_reliability_state(
            "agent-1",
            c,
            store=state_store,
            actor="engine",
            occurred_at=NOW,
            evidence_root=root,
        )
        att_store = JsonlReliabilityOutcomeAttestationStore(root / "attestations.jsonl")
        attestation = attest_reliability_outcome(
            c, transition, actor="engine", store=att_store, occurred_at=NOW
        )
        return c, transition, attestation

    def test_complete_outcome_verifies(self):
        """Verify the `test_complete_outcome_verifies` behavior and its expected invariants."""
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            c, transition, attestation = self._prepare(root)  # type: ignore
            report = verify_reliability_outcome(
                attestation,
                c,
                subject_id="agent-1",
                history_path=root / "state-history.jsonl",
                evidence_root=root,
            )
            self.assertTrue(report.verified)
            self.assertEqual(report.failures, ())
            self.assertEqual(report.checks[-1], "attestation_binding")
            self.assertEqual(len(report.digest), 64)

    def test_report_digest_is_deterministic(self):
        """Verify the `test_report_digest_is_deterministic` behavior and its expected invariants."""
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            c, _, attestation = self._prepare(root)
            a = verify_reliability_outcome(
                attestation,
                c,
                subject_id="agent-1",
                history_path=root / "state-history.jsonl",
                evidence_root=root,
            )
            b = verify_reliability_outcome(
                attestation,
                c,
                subject_id="agent-1",
                history_path=root / "state-history.jsonl",
                evidence_root=root,
            )
            self.assertEqual(a.to_dict(), b.to_dict())
            self.assertEqual(a.digest, b.digest)

    def test_tampered_external_evidence_fails_closed(self):
        """Verify the `test_tampered_external_evidence_fails_closed` behavior and its expected invariants."""
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            c, _, attestation = self._prepare(root)
            (root / "evidence.json").write_text(
                '{"evidence":"tampered"}', encoding="utf-8"
            )
            report = verify_reliability_outcome(
                attestation,
                c,
                subject_id="agent-1",
                history_path=root / "state-history.jsonl",
                evidence_root=root,
            )
            self.assertFalse(report.verified)
            self.assertTrue(any("digest mismatch" in item for item in report.failures))

    def test_tampered_attestation_fails_closed(self):
        """Verify the `test_tampered_attestation_fails_closed` behavior and its expected invariants."""
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            c, _, attestation = self._prepare(root)  # type: ignore
            payload = attestation.to_dict()
            payload["decision_rationale"] = ["tampered"]
            with self.assertRaises(ValueError):
                ReliabilityOutcomeAttestation.from_dict(payload)

    def test_missing_transition_fails_closed(self):
        """Verify the `test_missing_transition_fails_closed` behavior and its expected invariants."""
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            c = chain(root)
            attestation = ReliabilityOutcomeAttestation(
                attestation_id="a1",
                subject_id="agent-1",
                occurred_at=NOW.isoformat(),
                actor="engine",
                evidence_chain_id=c.chain_id,
                evidence_chain_digest=c.digest(),
                transition_id="missing",
                transition_digest="a" * 64,
                reliability_state="reliable",
                decision="accept",
                verification_status="verified",
                reconciliation_state="verified",
                decision_rationale=("x",),
            )
            JsonlReliabilityStateStore(root / "state-history.jsonl").path.write_text(
                "", encoding="utf-8"
            )
            report = verify_reliability_outcome(
                attestation,
                c,
                subject_id="agent-1",
                history_path=root / "state-history.jsonl",
                evidence_root=root,
            )
            self.assertFalse(report.verified)
            self.assertTrue(
                any("transition not found" in item for item in report.failures)
            )

    def test_wrong_subject_fails_closed(self):
        """Verify the `test_wrong_subject_fails_closed` behavior and its expected invariants."""
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            c, _, attestation = self._prepare(root)
            report = verify_reliability_outcome(
                attestation,
                c,
                subject_id="other-agent",
                history_path=root / "state-history.jsonl",
                evidence_root=root,
            )
            self.assertFalse(report.verified)
            self.assertTrue(any("subject" in item for item in report.failures))

    def test_tampered_transition_history_is_detected(self):
        """Verify the `test_tampered_transition_history_is_detected` behavior and its expected invariants."""
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            c, _, attestation = self._prepare(root)
            path = root / "state-history.jsonl"
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["actor"] = "tampered"
            path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
            report = verify_reliability_outcome(
                attestation,
                c,
                subject_id="agent-1",
                history_path=path,
                evidence_root=root,
            )
            self.assertFalse(report.verified)
            self.assertTrue(any("digest mismatch" in item for item in report.failures))


if __name__ == "__main__":
    unittest.main()
