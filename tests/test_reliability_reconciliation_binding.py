"""Regression tests for StateWake.

The active test suite protects the public package behavior and integration boundaries.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import UTC
from hashlib import sha256
from pathlib import Path
from typing import Any

from config.project_paths import PROJECT_ROOT, SRC_PATH
from statewake.domain.provenance import ProvenanceGraph, ProvenanceNode
from statewake.domain.reliability_evidence import EvidenceReference
from statewake.domain.reliability_reconciliation_binding import (
    ReliabilityReconciliationBinding,
)
from statewake.services.reliability_comparison_service import (
    build_reliability_behavioral_comparison,
)
from statewake.services.reliability_evidence_service import (
    build_reliability_evidence_chain,
    verify_reliability_evidence_chain,
)
from statewake.services.reliability_reconciliation_binding_service import (
    build_reliability_reconciliation_binding,
    verify_reliability_reconciliation_binding,
)


def _write(path: Path, payload: object) -> Path:
    """Verify the `_write` behavior and its expected invariants."""
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return path


def _state(state_id: str, model: str) -> dict[str, Any]:
    """Verify the `_state` behavior and its expected invariants."""
    return {
        "state_id": state_id,
        "captured_at": "2026-09-11T10:00:00+00:00",
        "agent_version": "agent@1",
        "model": model,
        "prompt_digest": "p",
        "tool_digests": {"crm": "t"},
        "retrieval_digest": "r",
        "memory_digest": None,
        "policy_digest": "policy",
    }


class ReliabilityReconciliationBindingTests(unittest.TestCase):
    """Provide regression coverage for the ReliabilityReconciliationBindingTests behavior."""

    def test_round_trip_and_exact_reconciliation_binding(self):
        """Verify the `test_round_trip_and_exact_reconciliation_binding` behavior and its expected invariants."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            before = _write(root / "before.json", _state("before", "model@1"))
            after = _write(root / "after.json", _state("after", "model@2"))
            comparison_path = root / "comparison.json"
            comparison = build_reliability_behavioral_comparison(
                before_state_path=before, after_state_path=after, output=comparison_path
            )
            reconciliation = _write(
                root / "reconciliation.json",
                {"reconciliation_id": "rec-1", "status": "verified"},
            )
            binding_path = root / "binding.json"
            binding = build_reliability_reconciliation_binding(
                comparison_path=comparison_path,
                reconciliation_path=reconciliation,
                output=binding_path,
            )
            loaded = ReliabilityReconciliationBinding.from_dict(
                json.loads(binding_path.read_text(encoding="utf-8"))
            )
            self.assertEqual(binding, loaded)
            verify_reliability_reconciliation_binding(
                loaded,
                comparison=comparison,
                reconciliation_path=reconciliation,
                root=root,
            )
            self.assertEqual(loaded.resolved_discrepancies, comparison.discrepancy)

    def test_tampered_reconciliation_fails_closed(self):
        """Verify the `test_tampered_reconciliation_fails_closed` behavior and its expected invariants."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            before = _write(root / "before.json", _state("before", "model@1"))
            after = _write(root / "after.json", _state("after", "model@2"))
            comparison_path = root / "comparison.json"
            comparison = build_reliability_behavioral_comparison(
                before_state_path=before, after_state_path=after, output=comparison_path
            )
            reconciliation = _write(
                root / "reconciliation.json",
                {"reconciliation_id": "rec-1", "status": "verified"},
            )
            binding = build_reliability_reconciliation_binding(
                comparison_path=comparison_path,
                reconciliation_path=reconciliation,
                output=root / "binding.json",
            )
            reconciliation.write_text(
                json.dumps({"reconciliation_id": "rec-1", "status": "recovered"}),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                verify_reliability_reconciliation_binding(
                    binding,
                    comparison=comparison,
                    reconciliation_path=reconciliation,
                    root=root,
                )

    def test_cli_build_and_verify(self):
        """Verify the `test_cli_build_and_verify` behavior and its expected invariants."""
        import os
        import subprocess

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            before = _write(root / "before.json", _state("before", "model@1"))
            after = _write(root / "after.json", _state("after", "model@2"))
            comparison = root / "comparison.json"
            build_reliability_behavioral_comparison(
                before_state_path=before, after_state_path=after, output=comparison
            )
            reconciliation = _write(
                root / "reconciliation.json",
                {"reconciliation_id": "rec-1", "status": "verified"},
            )
            binding = root / "binding.json"
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
                    "reliability-reconciliation-bind",
                    str(comparison),
                    str(reconciliation),
                    "--output",
                    str(binding),
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
                    "reliability-reconciliation-verify",
                    str(binding),
                    str(comparison),
                    str(reconciliation),
                ],
                cwd=PROJECT_ROOT,
                env=environment,
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn('"verified": true', proc.stdout)

    def test_chain_binds_exact_comparison_and_reconciliation(self):
        """Verify the `test_chain_binds_exact_comparison_and_reconciliation` behavior and its expected invariants."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run = _write(root / "run.json", {"run_id": "run-1"})
            state = _write(root / "state.json", _state("state-1", "model@2"))
            evidence = _write(root / "evidence.json", {"evidence": "e1"})
            integrity = _write(root / "integrity.json", {"verified": True})
            before = _write(root / "before.json", _state("before", "model@1"))
            after = _write(root / "after.json", _state("after", "model@2"))
            comparison_path = root / "comparison.json"
            comparison = build_reliability_behavioral_comparison(
                before_state_path=before, after_state_path=after, output=comparison_path
            )
            reconciliation_path = _write(
                root / "reconciliation.json",
                {"reconciliation_id": "rec-1", "status": "verified"},
            )
            binding_path = root / "binding.json"
            build_reliability_reconciliation_binding(
                comparison_path=comparison_path,
                reconciliation_path=reconciliation_path,
                output=binding_path,
            )

            refs = {
                "run": EvidenceReference(
                    "run", "run-1", sha256(run.read_bytes()).hexdigest(), run.name
                ),
                "state": EvidenceReference(
                    "state",
                    "state-1",
                    sha256(state.read_bytes()).hexdigest(),
                    state.name,
                ),
                "evidence": EvidenceReference(
                    "evidence",
                    "evidence.json",
                    sha256(evidence.read_bytes()).hexdigest(),
                    evidence.name,
                ),
                "comparison": EvidenceReference(
                    "comparison",
                    comparison.comparison_id,
                    sha256(comparison_path.read_bytes()).hexdigest(),
                    comparison_path.name,
                ),
                "before": EvidenceReference(
                    "state",
                    "before",
                    sha256(before.read_bytes()).hexdigest(),
                    before.name,
                ),
                "after": EvidenceReference(
                    "state", "after", sha256(after.read_bytes()).hexdigest(), after.name
                ),
                "reconciliation": EvidenceReference(
                    "reconciliation",
                    "rec-1",
                    sha256(reconciliation_path.read_bytes()).hexdigest(),
                    reconciliation_path.name,
                ),
            }
            nodes = tuple(
                ProvenanceNode(
                    name.replace(":", "-"),
                    ref.kind,
                    ref.digest,
                    ref.identity,
                    () if name == "run" else ("run",),
                )
                for name, ref in refs.items()
            )
            graph = ProvenanceGraph(
                nodes,
                tuple((node.node_id, "run") for node in nodes if node.node_id != "run"),
            )
            provenance = _write(root / "provenance.json", graph.to_dict())
            chain = build_reliability_evidence_chain(
                run_id="run-1",
                run_path=run,
                state_id="state-1",
                state_path=state,
                evidence_paths=(evidence,),
                provenance_path=provenance,
                integrity_proof_path=integrity,
                verification_status="verified",
                reliability_state="reliable",
                reconciliation_state="verified",
                reconciliation_path=reconciliation_path,
                decision="accept",
                rationale=("comparison verified",),
                comparison_path=comparison_path,
                reconciliation_binding_path=binding_path,
            )
            self.assertIsNotNone(chain.reconciliation_binding_ref)
            assert chain.reconciliation_binding_ref is not None
            self.assertEqual(len(chain.reconciliation_binding_ref.identity), 64)
            self.assertEqual(len(chain.reconciliation_binding_ref.digest), 64)
            verify_reliability_evidence_chain(chain, root=root)


if __name__ == "__main__":
    unittest.main()


class ReliabilityReconciliationBindingPortableProofTests(unittest.TestCase):
    """Provide regression coverage for the ReliabilityReconciliationBindingPortableProofTests behavior."""

    def test_binding_survives_portable_proof_and_offline_verification(self):
        """Verify the `test_binding_survives_portable_proof_and_offline_verification` behavior and its expected invariants."""
        from datetime import datetime

        from statewake.adapters.reliability_attestation import (
            JsonlReliabilityOutcomeAttestationStore,
        )
        from statewake.adapters.reliability_state import JsonlReliabilityStateStore
        from statewake.services.reliability_attestation_service import (
            attest_reliability_outcome,
            write_reliability_outcome_attestation,
        )
        from statewake.services.reliability_evidence_service import (
            write_reliability_evidence_chain,
        )
        from statewake.services.reliability_proof_bundle_service import (
            build_reliability_proof_bundle,
            verify_reliability_proof_bundle,
        )
        from statewake.services.reliability_state_service import (
            transition_reliability_state,
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run = _write(root / "run.json", {"run_id": "run-1"})
            state = _write(root / "state.json", _state("state-1", "model@2"))
            evidence = _write(root / "evidence.json", {"evidence": "e1"})
            integrity = _write(root / "integrity.json", {"verified": True})
            before = _write(root / "before.json", _state("before", "model@1"))
            after = _write(root / "after.json", _state("after", "model@2"))
            comparison_path = root / "comparison.json"
            comparison = build_reliability_behavioral_comparison(
                before_state_path=before, after_state_path=after, output=comparison_path
            )
            reconciliation_path = _write(
                root / "reconciliation.json",
                {"reconciliation_id": "rec-1", "status": "verified"},
            )
            binding_path = root / "binding.json"
            build_reliability_reconciliation_binding(
                comparison_path=comparison_path,
                reconciliation_path=reconciliation_path,
                output=binding_path,
            )

            refs = {
                "run": EvidenceReference(
                    "run", "run-1", sha256(run.read_bytes()).hexdigest(), run.name
                ),
                "state": EvidenceReference(
                    "state",
                    "state-1",
                    sha256(state.read_bytes()).hexdigest(),
                    state.name,
                ),
                "evidence": EvidenceReference(
                    "evidence",
                    "evidence.json",
                    sha256(evidence.read_bytes()).hexdigest(),
                    evidence.name,
                ),
                "comparison": EvidenceReference(
                    "comparison",
                    comparison.comparison_id,
                    sha256(comparison_path.read_bytes()).hexdigest(),
                    comparison_path.name,
                ),
                "before": EvidenceReference(
                    "state",
                    "before",
                    sha256(before.read_bytes()).hexdigest(),
                    before.name,
                ),
                "after": EvidenceReference(
                    "state", "after", sha256(after.read_bytes()).hexdigest(), after.name
                ),
                "reconciliation": EvidenceReference(
                    "reconciliation",
                    "rec-1",
                    sha256(reconciliation_path.read_bytes()).hexdigest(),
                    reconciliation_path.name,
                ),
            }
            nodes = tuple(
                ProvenanceNode(
                    name.replace(":", "-"),
                    ref.kind,
                    ref.digest,
                    ref.identity,
                    () if name == "run" else ("run",),
                )
                for name, ref in refs.items()
            )
            graph = ProvenanceGraph(
                nodes,
                tuple((node.node_id, "run") for node in nodes if node.node_id != "run"),
            )
            provenance = _write(root / "provenance.json", graph.to_dict())
            chain = build_reliability_evidence_chain(
                run_id="run-1",
                run_path=run,
                state_id="state-1",
                state_path=state,
                evidence_paths=(evidence,),
                provenance_path=provenance,
                integrity_proof_path=integrity,
                verification_status="verified",
                reliability_state="reliable",
                reconciliation_state="verified",
                reconciliation_path=reconciliation_path,
                decision="accept",
                rationale=("comparison verified",),
                comparison_path=comparison_path,
                reconciliation_binding_path=binding_path,
            )
            chain_path = root / "chain.json"
            write_reliability_evidence_chain(chain, chain_path)
            history = root / "history.jsonl"
            occurred = datetime(2026, 9, 11, 10, tzinfo=UTC)
            transition = transition_reliability_state(
                "agent-1",
                chain,
                store=JsonlReliabilityStateStore(history),
                actor="engine",
                occurred_at=occurred,
                evidence_root=root,
            )
            attestation = attest_reliability_outcome(
                chain,
                transition,
                actor="engine",
                store=JsonlReliabilityOutcomeAttestationStore(
                    root / "attestations.jsonl"
                ),
                occurred_at=occurred,
                signing_key_id="rel-key",
            )
            att = root / "attestation.json"
            write_reliability_outcome_attestation(attestation, att)
            proof = root / "proof.zip"
            build_reliability_proof_bundle(
                attestation_path=att,
                evidence_chain_path=chain_path,
                history_path=history,
                evidence_root=root,
                output=proof,
            )
            for path in (
                run,
                state,
                evidence,
                integrity,
                before,
                after,
                comparison_path,
                reconciliation_path,
                binding_path,
                provenance,
                chain_path,
                history,
                att,
            ):
                if path.exists():
                    path.unlink()
            report, descriptor = verify_reliability_proof_bundle(proof)
            self.assertTrue(report.verified)
            self.assertTrue(
                any(
                    item.reference_key == "reconciliation_binding"
                    for item in descriptor.sources
                )
            )
