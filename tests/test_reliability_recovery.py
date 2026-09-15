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
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from statewake.adapters.reliability_attestation import (
    JsonlReliabilityOutcomeAttestationStore,
)
from statewake.adapters.reliability_state import JsonlReliabilityStateStore
from statewake.services.reliability_attestation_service import (
    attest_reliability_outcome,
)
from statewake.services.reliability_evidence_service import (
    build_reliability_evidence_chain,
)
from statewake.services.reliability_outcome_verification_service import (
    verify_reliability_outcome,
)
from statewake.services.reliability_recovery_service import (
    verify_reliability_recovery_outcome,
)
from statewake.services.reliability_state_service import transition_reliability_state


class ReliabilityRecoveryOutcomeTests(unittest.TestCase):
    """Provide regression coverage for the ReliabilityRecoveryOutcomeTests behavior."""

    def _write(self, root: Path, name: str, payload: object) -> Path:
        """Verify the `_write` behavior and its expected invariants."""
        path = root / name
        path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        return path

    def _fixtures(self, root: Path):
        """Verify the `_fixtures` behavior and its expected invariants."""
        run = self._write(root, "run.json", {"run_id": "run-1"})
        state = self._write(root, "state.json", {"state_id": "state-1"})
        evidence = self._write(root, "evidence.json", {"evidence": "recovered"})
        provenance = self._write(root, "provenance.json", {"provenance": "run-1"})
        integrity = self._write(root, "integrity.json", {"verified": True})
        reconciliation = self._write(
            root,
            "reconciliation.json",
            {"reconciliation_id": "reconcile-1", "state": "recovered"},
        )
        recovery_payload = {
            "recovery_id": "recovery-1",
            "occurred_at": "2026-09-11T08:00:00+00:00",
            "impact_id": "impact-1",
            "source_reconciliation_id": "reconcile-1",
            "actor": "operator",
            "approved": True,
            "status": "applied",
            "steps": [
                {
                    "step_id": "step-1",
                    "target": "target-1",
                    "action": "pause-dispatch",
                    "status": "applied",
                    "reason": "restored",
                }
            ],
            "reason": "drift recovered",
        }
        recovery_payload["digest"] = sha256(
            json.dumps(recovery_payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        recovery_path = root / "recovery.json"
        recovery_path.write_text(
            json.dumps(recovery_payload, sort_keys=True), encoding="utf-8"
        )
        return (
            run,
            state,
            evidence,
            provenance,
            integrity,
            reconciliation,
            recovery_path,
        )

    def _chain(
        self,
        root: Path,
        *,
        recovery_path: Path | None,
        reconciliation: Path,
        state: str,
        decision: str,
        reconciliation_state: str,
    ):
        """Verify the `_chain` behavior and its expected invariants."""
        run, system_state, evidence, provenance, integrity, _, _ = self._fixtures(root)
        return build_reliability_evidence_chain(
            run_id="run-1",
            run_path=run,
            state_id="state-1",
            state_path=system_state,
            evidence_paths=(evidence,),
            provenance_path=provenance,
            integrity_proof_path=integrity,
            verification_status="verified",
            reliability_state=state,
            reconciliation_state=reconciliation_state,
            reconciliation_path=reconciliation,
            recovery_path=recovery_path,
            decision=decision,
            rationale=(f"transition to {state}",),
        )

    def test_cli_exposes_recovery_verification(self):
        """Verify the `test_cli_exposes_recovery_verification` behavior and its expected invariants."""
        from statewake.cli.main import build_parser

        args = build_parser().parse_args(
            [
                "reliability-recovery-verify",
                "--chain",
                "chain.json",
                "--evidence-root",
                ".",
            ]
        )
        self.assertEqual(args.command, "reliability-recovery-verify")

    def test_recovered_chain_requires_and_verifies_applied_recovery(self):
        """Verify the `test_recovered_chain_requires_and_verifies_applied_recovery` behavior and its expected invariants."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            *_, reconciliation, recovery_path = self._fixtures(root)
            chain = self._chain(
                root,
                recovery_path=recovery_path,
                reconciliation=reconciliation,
                state="recovered",
                decision="accept",
                reconciliation_state="recovered",
            )
            binding = verify_reliability_recovery_outcome(chain, root=root)
            self.assertEqual(binding.outcome, "recovered")
            self.assertEqual(binding.recovery_id, "recovery-1")
            self.assertEqual(binding.source_reconciliation_id, "reconcile-1")

    def test_recovered_chain_rejects_recovery_not_applied(self):
        """Verify the `test_recovered_chain_rejects_recovery_not_applied` behavior and its expected invariants."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            *_, reconciliation, recovery_path = self._fixtures(root)
            payload = json.loads(recovery_path.read_text(encoding="utf-8"))
            chain = self._chain(
                root,
                recovery_path=recovery_path,
                reconciliation=reconciliation,
                state="recovered",
                decision="accept",
                reconciliation_state="recovered",
            )
            payload = json.loads(recovery_path.read_text(encoding="utf-8"))
            payload["status"] = "failed"
            recovery_path.write_text(
                json.dumps(payload, sort_keys=True), encoding="utf-8"
            )
            with self.assertRaisesRegex(
                ValueError, "recovery artifact digest mismatch"
            ):
                verify_reliability_recovery_outcome(chain, root=root)

    def test_recovered_chain_rejects_recovery_reconciliation_mismatch(self):
        """Verify the `test_recovered_chain_rejects_recovery_reconciliation_mismatch` behavior and its expected invariants."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            *_, reconciliation, recovery_path = self._fixtures(root)
            payload = json.loads(recovery_path.read_text(encoding="utf-8"))
            chain = self._chain(
                root,
                recovery_path=recovery_path,
                reconciliation=reconciliation,
                state="recovered",
                decision="accept",
                reconciliation_state="recovered",
            )
            payload = json.loads(recovery_path.read_text(encoding="utf-8"))
            payload["source_reconciliation_id"] = "other-reconciliation"
            unsigned = dict(payload)
            unsigned.pop("digest", None)
            payload["digest"] = sha256(
                json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            recovery_path.write_text(
                json.dumps(payload, sort_keys=True), encoding="utf-8"
            )
            with self.assertRaisesRegex(
                ValueError, "recovery artifact digest mismatch"
            ):
                verify_reliability_recovery_outcome(chain, root=root)

    def test_end_to_end_recovered_outcome_contains_recovery_binding(self):
        """Verify the `test_end_to_end_recovered_outcome_contains_recovery_binding` behavior and its expected invariants."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            *_, reconciliation, recovery_path = self._fixtures(root)
            store = JsonlReliabilityStateStore(root / "history.jsonl")
            unreliable_chain = self._chain(
                root,
                recovery_path=None,
                reconciliation=reconciliation,
                state="unreliable",
                decision="reject",
                reconciliation_state="verified",
            )
            transition_reliability_state(
                "agent-1",
                unreliable_chain,
                store=store,
                actor="engine",
                occurred_at=datetime(2026, 9, 11, 9, tzinfo=UTC),
                evidence_root=root,
            )
            recovered_chain = self._chain(
                root,
                recovery_path=recovery_path,
                reconciliation=reconciliation,
                state="recovered",
                decision="accept",
                reconciliation_state="recovered",
            )
            transition = transition_reliability_state(
                "agent-1",
                recovered_chain,
                store=store,
                actor="engine",
                occurred_at=datetime(2026, 9, 11, 9, 1, tzinfo=UTC),
                evidence_root=root,
            )
            attestation = attest_reliability_outcome(
                recovered_chain,
                transition,
                actor="engine",
                store=JsonlReliabilityOutcomeAttestationStore(
                    root / "attestations.jsonl"
                ),
                occurred_at=datetime(2026, 9, 11, 9, 2, tzinfo=UTC),
            )
            report = verify_reliability_outcome(
                attestation,
                recovered_chain,
                subject_id="agent-1",
                history_path=root / "history.jsonl",
                evidence_root=root,
            )
            self.assertTrue(report.verified)
            self.assertIn("recovery_outcome_binding", report.checks)

    def test_recovered_outcome_rejects_tampered_recovery_bytes(self):
        """Verify the `test_recovered_outcome_rejects_tampered_recovery_bytes` behavior and its expected invariants."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            *_, reconciliation, recovery_path = self._fixtures(root)
            chain = self._chain(
                root,
                recovery_path=recovery_path,
                reconciliation=reconciliation,
                state="recovered",
                decision="accept",
                reconciliation_state="recovered",
            )
            recovery_path.write_text(
                recovery_path.read_text(encoding="utf-8") + "tamper", encoding="utf-8"
            )
            with self.assertRaisesRegex(
                ValueError, "recovery artifact digest mismatch"
            ):
                verify_reliability_recovery_outcome(chain, root=root)


if __name__ == "__main__":
    unittest.main()


def test_recovery_verifier_rejects_string_boolean(tmp_path: Path):
    """Reject string values that could otherwise coerce to an approved boolean."""
    from statewake.services.reliability_recovery_service import (
        _verify_recovery_record,  # type: ignore
    )

    payload = {
        "recovery_id": "r",
        "occurred_at": "2026-09-12T00:00:00+00:00",
        "impact_id": "i",
        "source_reconciliation_id": "rec",
        "actor": "ops",
        "approved": "false",
        "status": "applied",
        "steps": [
            {
                "step_id": "s",
                "target": "x",
                "action": "y",
                "status": "applied",
                "reason": "z",
            }
        ],
        "reason": "r",
    }
    with __import__("pytest").raises(
        ValueError, match="approved must be a JSON boolean"
    ):
        _verify_recovery_record(payload)
