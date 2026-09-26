"""Regression tests for StateWake.

The active test suite protects the public package behavior and integration boundaries.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from config.project_paths import PROJECT_ROOT, SRC_PATH
from statewake.adapters.jsonl_store import JsonlEventStore
from statewake.domain.events import EventEnvelope
from statewake.domain.provenance import ProvenanceGraph, ProvenanceNode
from statewake.domain.reliability_comparison import ReliabilityBehavioralComparison
from statewake.domain.reliability_evidence import EvidenceReference
from statewake.services.reliability_comparison_service import (
    build_reliability_behavioral_comparison,
    verify_reliability_behavioral_comparison,
)
from statewake.services.reliability_evidence_service import (
    build_reliability_evidence_chain,
    verify_reliability_evidence_chain,
)


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
    }  # type: ignore


def _write(path: Path, payload: object) -> Path:
    """Verify the `_write` behavior and its expected invariants."""
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return path


class ReliabilityComparisonTests(unittest.TestCase):
    """Provide regression coverage for the ReliabilityComparisonTests behavior."""

    def _events(self, path: Path, run_id: str, tool: str) -> None:
        """Verify the `_events` behavior and its expected invariants."""
        store = JsonlEventStore(path)
        store.append(
            EventEnvelope(
                run_id,
                0,
                datetime(2026, 9, 11, 10, tzinfo=UTC),
                "run.started",
                "runtime",
            )
        )
        store.append(
            EventEnvelope(
                run_id,
                1,
                datetime(2026, 9, 11, 10, 0, 1, tzinfo=UTC),
                "tool.called",
                "agent",
                name=tool,
            )
        )
        store.append(
            EventEnvelope(
                run_id,
                2,
                datetime(2026, 9, 11, 10, 0, 2, tzinfo=UTC),
                "run.completed",
                "runtime",
                name="success",
            )
        )

    def test_build_round_trip_reproduces_existing_diff(self):
        """Verify the `test_build_round_trip_reproduces_existing_diff` behavior and its expected invariants."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            before = _write(root / "before.json", _state("before", "model@1"))
            after = _write(root / "after.json", _state("after", "model@2"))
            before_events = root / "before.jsonl"
            after_events = root / "after.jsonl"
            self._events(before_events, "run-before", "crm.read")
            self._events(after_events, "run-after", "crm.lookup")
            output = root / "comparison.json"
            item = build_reliability_behavioral_comparison(
                before_state_path=before,
                after_state_path=after,
                output=output,
                before_events_path=before_events,
                before_run_id="run-before",
                after_events_path=after_events,
                after_run_id="run-after",
            )
            loaded = ReliabilityBehavioralComparison.from_dict(
                json.loads(output.read_text())
            )
            self.assertEqual(item, loaded)
            verify_reliability_behavioral_comparison(loaded, root=root)
            self.assertEqual(loaded.significance, "medium")
            self.assertEqual(loaded.discrepancy, ("state_change", "action_change"))

    def test_tampered_comparison_semantics_fail_closed(self):
        """Verify the `test_tampered_comparison_semantics_fail_closed` behavior and its expected invariants."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            before = _write(root / "before.json", _state("before", "model@1"))
            after = _write(root / "after.json", _state("after", "model@2"))
            output = root / "comparison.json"
            build_reliability_behavioral_comparison(
                before_state_path=before, after_state_path=after, output=output
            )
            payload = json.loads(output.read_text())
            payload["significance"] = "none"
            with self.assertRaises(ValueError):
                ReliabilityBehavioralComparison.from_dict(payload)

    def test_source_tampering_fails_closed(self):
        """Verify the `test_source_tampering_fails_closed` behavior and its expected invariants."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            before = _write(root / "before.json", _state("before", "model@1"))
            after = _write(root / "after.json", _state("after", "model@2"))
            output = root / "comparison.json"
            build_reliability_behavioral_comparison(  # ruff: ignore[unused-variable]
                before_state_path=before, after_state_path=after, output=output
            )
            before.write_text("tampered", encoding="utf-8")
            from statewake.services.reliability_comparison_service import (
                load_reliability_behavioral_comparison,
            )

            with self.assertRaises(ValueError):
                tampered = load_reliability_behavioral_comparison(output)
                verify_reliability_behavioral_comparison(tampered, root=root)

    def test_cli_comparison_build_and_verify(self):
        """Verify the `test_cli_comparison_build_and_verify` behavior and its expected invariants."""
        import os
        import subprocess

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            before = _write(root / "before.json", _state("before", "model@1"))
            after = _write(root / "after.json", _state("after", "model@2"))
            output = root / "comparison.json"
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
                    "reliability-comparison",
                    str(before),
                    str(after),
                    "--output",
                    str(output),
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
                    "reliability-comparison-verify",
                    str(output),
                ],
                cwd=PROJECT_ROOT,
                env=environment,
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn('"verified": true', proc.stdout)


class ReliabilityComparisonChainBindingTests(unittest.TestCase):
    """Provide regression coverage for the ReliabilityComparisonChainBindingTests behavior."""

    def test_comparison_binds_to_chain_and_verifies_sources(self):
        """Verify the `test_comparison_binds_to_chain_and_verifies_sources` behavior and its expected invariants."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run = _write(root / "run.json", {"run_id": "run-1"})
            state = _write(root / "state.json", _state("state-1", "model@2"))
            evidence = _write(root / "evidence.json", {"e": "1"})
            provenance = _write(root / "provenance.json", {"placeholder": True})
            integrity = _write(root / "integrity.json", {"verified": True})
            before = _write(root / "before.json", _state("before", "model@1"))
            after = _write(root / "after.json", _state("after", "model@2"))
            comparison_path = root / "comparison.json"
            comparison = build_reliability_behavioral_comparison(
                before_state_path=before, after_state_path=after, output=comparison_path
            )
            # Build a minimal provenance graph that includes the comparison node and all chain material.
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
                "evidence:0": EvidenceReference(
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
            }
            nodes = tuple(
                ProvenanceNode(
                    role.replace(":", "-"),
                    ref.kind,
                    ref.digest,
                    ref.identity,
                    (() if role == "run" else ("run",)),
                )
                for role, ref in refs.items()
            )
            graph = ProvenanceGraph(
                nodes,
                tuple(
                    (role.replace(":", "-"), "run") for role in refs if role != "run"
                ),
            )
            provenance.write_text(
                json.dumps(graph.to_dict(), indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            refs["provenance"] = EvidenceReference(
                "provenance",
                provenance.name,
                sha256(provenance.read_bytes()).hexdigest(),
                provenance.name,
            )
            refs["integrity"] = EvidenceReference(
                "integrity",
                "integrity.json",
                sha256(integrity.read_bytes()).hexdigest(),
                integrity.name,
            )
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
                decision="accept",
                rationale=("ok",),
                comparison_path=comparison_path,
            )
            comparison_ref = chain.comparison_ref
            self.assertIsNotNone(comparison_ref)
            assert comparison_ref is not None
            self.assertEqual(comparison_ref.identity, comparison.comparison_id)
            verify_reliability_evidence_chain(chain, root=root)

    def test_chain_comparison_tampering_fails_closed(self):
        """Verify the `test_chain_comparison_tampering_fails_closed` behavior and its expected invariants."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            before = _write(root / "before.json", _state("before", "model@1"))
            after = _write(root / "after.json", _state("after", "model@2"))
            comparison_path = root / "comparison.json"
            build_reliability_behavioral_comparison(
                before_state_path=before, after_state_path=after, output=comparison_path
            )
            payload = json.loads(comparison_path.read_text())
            payload["diff"]["outcome_before"] = "tampered"
            comparison_path.write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            from statewake.services.reliability_comparison_service import (
                load_reliability_behavioral_comparison,
            )

            with self.assertRaises(ValueError):
                tampered = load_reliability_behavioral_comparison(comparison_path)
                verify_reliability_behavioral_comparison(tampered, root=root)


class ReliabilityComparisonPortableProofTests(unittest.TestCase):
    """Provide regression coverage for the ReliabilityComparisonPortableProofTests behavior."""

    def test_comparison_survives_portable_proof_and_offline_verification(self):
        """Verify the `test_comparison_survives_portable_proof_and_offline_verification` behavior and its expected invariants."""
        from statewake.adapters.reliability_attestation import (
            JsonlReliabilityOutcomeAttestationStore,
        )
        from statewake.adapters.reliability_state import JsonlReliabilityStateStore
        from statewake.domain.provenance import ProvenanceGraph, ProvenanceNode
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

            def ref(kind, identity, path) -> EvidenceReference:  # type: ignore
                """Verify the `ref` behavior and its expected invariants."""
                return EvidenceReference(
                    kind,
                    identity,
                    sha256(path.read_bytes()).hexdigest(),  # type: ignore
                    path.name,  # type: ignore
                )

            comparison_ref = ref(
                "comparison", comparison.comparison_id, comparison_path
            )
            refs = {
                "run": ref("run", "run-1", run),
                "state": ref("state", "state-1", state),
                "evidence": ref("evidence", "evidence.json", evidence),
                "comparison": comparison_ref,
                "before_state": ref("state", "before", before),
                "after_state": ref("state", "after", after),
            }
            nodes = tuple(
                ProvenanceNode(
                    role.replace(":", "-"),
                    item.kind,
                    item.digest,
                    item.identity,
                    () if role == "run" else ("run",),
                )
                for role, item in refs.items()
            )
            graph = ProvenanceGraph(
                nodes,
                tuple(
                    (node.node_id, parent)
                    for node in nodes
                    for parent in node.derived_from
                ),
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
                decision="accept",
                rationale=("comparison verified",),
                comparison_path=comparison_path,
            )
            chain_path = root / "chain.json"
            write_reliability_evidence_chain(chain, chain_path)
            history = root / "history.jsonl"
            transition = transition_reliability_state(
                "agent-1",
                chain,
                store=JsonlReliabilityStateStore(history),
                actor="engine",
                occurred_at=datetime(2026, 9, 11, 10, tzinfo=UTC),
                evidence_root=root,
            )
            attestation = attest_reliability_outcome(
                chain,
                transition,
                actor="engine",
                store=JsonlReliabilityOutcomeAttestationStore(
                    root / "attestations.jsonl"
                ),
                occurred_at=datetime(2026, 9, 11, 10, tzinfo=UTC),
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
                provenance,
                chain_path,
                history,
                att,
            ):
                if path.exists():
                    path.unlink()
            report, descriptor = verify_reliability_proof_bundle(proof)
            self.assertTrue(report.verified)
            self.assertIsNotNone(descriptor)
            self.assertIn(
                "comparison", [item.reference_key for item in descriptor.sources]
            )
            self.assertTrue(
                any(
                    item.reference_key.startswith("comparison-input:")
                    for item in descriptor.sources
                )
            )
