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

from statewake.adapters.reliability_attestation import (
    JsonlReliabilityOutcomeAttestationStore,
)
from statewake.adapters.reliability_state import JsonlReliabilityStateStore
from statewake.domain.reliability_decision_basis import ReliabilityDecisionBasis
from statewake.domain.reliability_evidence import (
    EvidenceReference,
    ReliabilityEvidenceChain,
)
from statewake.services.reliability_attestation_service import (
    attest_reliability_outcome,
)
from statewake.services.reliability_decision_basis_service import (
    verify_reliability_decision_basis,
    write_reliability_decision_basis,
)
from statewake.services.reliability_evidence_service import (
    verify_reliability_evidence_chain,
    write_reliability_evidence_chain,
)
from statewake.services.reliability_state_service import transition_reliability_state

NOW = datetime(2026, 9, 11, 1, tzinfo=UTC)


def _chain(root: Path):
    """Verify the `_chain` behavior and its expected invariants."""
    for name, payload in (
        ("run.json", {"run": "r"}),
        ("state.json", {"state": "reliable"}),
        ("evidence.json", {"e": "v"}),
        ("prov.json", {"p": "v"}),
        ("integrity.json", {"i": "v"}),
    ):
        (root / name).write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")

    def ref(kind, identity, name):
        """Verify the `ref` behavior and its expected invariants."""
        path = root / name
        return EvidenceReference(
            kind, identity, sha256(path.read_bytes()).hexdigest(), name
        )

    return ReliabilityEvidenceChain(
        chain_id="chain-base",
        run=ref("run", "r", "run.json"),
        state=ref("state", "s", "state.json"),
        evidence=(ref("evidence", "e", "evidence.json"),),
        provenance=ref("provenance", "p", "prov.json"),
        integrity=ref("integrity", "i", "integrity.json"),
        verification_status="verified",
        reliability_state="reliable",
        reconciliation_state="verified",
        decision="accept",
        decision_rationale=("evidence verified",),
    )


class TestReliabilityDecisionBasis(unittest.TestCase):
    """Provide regression coverage for the TestReliabilityDecisionBasis behavior."""

    def test_round_trip_and_semantic_binding(self):
        """Verify the `test_round_trip_and_semantic_binding` behavior and its expected invariants."""
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            chain = _chain(root)
            basis = ReliabilityDecisionBasis(
                format_version="1",
                basis_type="policy",
                basis_id="refund-policy",
                version="2026.1",
                decision="accept",
                reliability_state="reliable",
                rationale=chain.decision_rationale,
                input_digests=(
                    chain.run.digest,
                    chain.evidence[0].digest,
                    chain.provenance.digest,
                ),
            )
            path = root / "decision-basis.json"
            write_reliability_decision_basis(basis, path)
            bound = replace(
                chain,
                decision_basis_ref=EvidenceReference(
                    "policy",
                    "refund-policy",
                    sha256(path.read_bytes()).hexdigest(),
                    path.name,
                ),
            )
            write_reliability_evidence_chain(bound, root / "chain.json")
            verify_reliability_decision_basis(bound, root=root)
            self.assertEqual(
                ReliabilityDecisionBasis.from_dict(json.loads(path.read_text())), basis
            )

    def test_decision_basis_tamper_is_rejected(self):
        """Verify the `test_decision_basis_tamper_is_rejected` behavior and its expected invariants."""
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            chain = _chain(root)
            path = root / "basis.json"
            basis = ReliabilityDecisionBasis(
                "1",
                "manual",
                "basis-1",
                "1",
                "accept",
                "reliable",
                chain.decision_rationale,
            )
            write_reliability_decision_basis(basis, path)
            bound = replace(
                chain,
                decision_basis_ref=EvidenceReference(
                    "decision-basis",
                    "basis-1",
                    sha256(path.read_bytes()).hexdigest(),
                    path.name,
                ),
            )
            path.write_text(
                path.read_text().replace("reliable", "degraded"), encoding="utf-8"
            )
            with self.assertRaises(ValueError):
                verify_reliability_decision_basis(bound, root=root)

    def test_decision_basis_cannot_change_outcome_semantics(self):
        """Verify the `test_decision_basis_cannot_change_outcome_semantics` behavior and its expected invariants."""
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            chain = _chain(root)
            basis = ReliabilityDecisionBasis(
                "1",
                "manual",
                "basis-1",
                "1",
                "reject",
                "unreliable",
                chain.decision_rationale,
            )
            path = root / "basis.json"
            write_reliability_decision_basis(basis, path)
            bad = replace(
                chain,
                decision_basis_ref=EvidenceReference(
                    "decision-basis",
                    "basis-1",
                    sha256(path.read_bytes()).hexdigest(),
                    path.name,
                ),
            )
            with self.assertRaises(ValueError):
                verify_reliability_decision_basis(bad, root=root)

    def test_decision_basis_input_must_belong_to_chain(self):
        """Verify the `test_decision_basis_input_must_belong_to_chain` behavior and its expected invariants."""
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            chain = _chain(root)
            basis = ReliabilityDecisionBasis(
                "1",
                "manual",
                "basis-1",
                "1",
                "accept",
                "reliable",
                chain.decision_rationale,
                ("f" * 64,),
            )
            path = root / "basis.json"
            write_reliability_decision_basis(basis, path)
            bad = replace(
                chain,
                decision_basis_ref=EvidenceReference(
                    "decision-basis",
                    "basis-1",
                    sha256(path.read_bytes()).hexdigest(),
                    path.name,
                ),
            )
            with self.assertRaises(ValueError):
                verify_reliability_decision_basis(bad, root=root)

    def test_full_state_and_attestation_chain_preserves_basis_binding(self):
        """Verify the `test_full_state_and_attestation_chain_preserves_basis_binding` behavior and its expected invariants."""
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            chain = _chain(root)
            basis = ReliabilityDecisionBasis(
                "1",
                "manual",
                "basis-1",
                "1",
                "accept",
                "reliable",
                chain.decision_rationale,
                (chain.evidence[0].digest,),
            )
            basis_path = root / "basis.json"
            write_reliability_decision_basis(basis, basis_path)
            chain = replace(
                chain,
                decision_basis_ref=EvidenceReference(
                    "decision-basis",
                    "basis-1",
                    sha256(basis_path.read_bytes()).hexdigest(),
                    basis_path.name,
                ),
            )
            verify_reliability_evidence_chain(chain, root=root)
            history = root / "history.jsonl"
            transition = transition_reliability_state(
                "agent",
                chain,
                store=JsonlReliabilityStateStore(history),
                actor="operator",
                occurred_at=NOW,
                evidence_root=root,
            )
            att = attest_reliability_outcome(
                chain,
                transition,
                actor="operator",
                store=JsonlReliabilityOutcomeAttestationStore(root / "a.jsonl"),
                occurred_at=NOW,
            )
            self.assertEqual(att.evidence_chain_digest, chain.digest())
            self.assertIn("decision_basis_ref", chain.to_dict())


if __name__ == "__main__":
    unittest.main()


def test_claim_profile_can_prepare_and_bind_decision_basis_before_state_attestation(
    tmp_path: Path,
):
    from statewake import (
        get_builtin_claim_profile,
        load_evidence_chain,
        prepare_reliability_decision_basis,
    )

    chain = _chain(tmp_path)
    profile = get_builtin_claim_profile("release-evidence-complete")
    basis_path = tmp_path / "decision-basis.json"
    chain_path = tmp_path / "prepared-chain.json"
    bound = prepare_reliability_decision_basis(
        chain,
        profile,
        basis_path=basis_path,
        output_chain_path=chain_path,
    )
    assert bound.decision_basis_ref is not None
    assert bound.decision_basis_ref.source == basis_path.name
    assert (
        load_evidence_chain(chain_path).decision_basis_ref == bound.decision_basis_ref
    )
    verify_reliability_evidence_chain(bound, root=tmp_path)
