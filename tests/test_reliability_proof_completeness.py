"""Regression tests for StateWake.

The active test suite protects the public package behavior and integration boundaries.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from config.project_paths import PROJECT_ROOT, SRC_PATH
from statewake.domain.reliability_proof_completeness import ReliabilityProofCompleteness
from statewake.services.reliability_proof_bundle_service import (
    build_reliability_proof_bundle,
    verify_reliability_proof_bundle,
)
from statewake.services.reliability_proof_completeness_service import (
    build_reliability_proof_completeness,
    verify_reliability_proof_completeness,
)
from tests.support.reliability_proof import prepare_reliability_proof_fixture


class TestReliabilityProofCompleteness(unittest.TestCase):
    """Provide regression coverage for the TestReliabilityProofCompleteness behavior."""

    def test_complete_v3_bundle_has_deterministic_completeness_witness(self):
        """Verify the `test_complete_v3_bundle_has_deterministic_completeness_witness` behavior and its expected invariants."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            att, chain, history = prepare_reliability_proof_fixture(root)
            output = root / "proof.zip"
            bundle, _ = build_reliability_proof_bundle(
                attestation_path=att,
                evidence_chain_path=chain,
                history_path=history,
                evidence_root=root,
                output=output,
            )
            _, descriptor = verify_reliability_proof_bundle(output)
            self.assertEqual(descriptor.format_version, "3")
            self.assertIsNotNone(descriptor.completeness_artifact_id)
            self.assertEqual("proof-completeness", descriptor.completeness_artifact_id)
            self.assertIsNotNone(descriptor.completeness_digest)
            artifact_ids = tuple(item.artifact_id for item in bundle.artifacts)
            witness = build_reliability_proof_completeness(
                descriptor, artifact_ids=artifact_ids
            )
            self.assertEqual(witness.digest, descriptor.completeness_digest)
            self.assertEqual(
                witness,
                verify_reliability_proof_completeness(
                    descriptor, witness, artifact_ids=artifact_ids
                ),
            )

    def test_missing_required_source_reference_is_rejected(self):
        """Verify the `test_missing_required_source_reference_is_rejected` behavior and its expected invariants."""
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
            _, descriptor = verify_reliability_proof_bundle(output)
            truncated = replace(
                descriptor,
                sources=tuple(
                    item for item in descriptor.sources if item.reference_key != "state"
                ),
            )
            with self.assertRaisesRegex(
                ValueError,
                "source references differ from canonical chain|expected artifacts are absent",
            ):
                build_reliability_proof_completeness(
                    truncated,
                    expected_source_reference_keys=(
                        "run",
                        "state",
                        "evidence:0",
                        "provenance",
                        "integrity",
                    ),
                    artifact_ids=(
                        "proof-attestation",
                        "proof-evidence-chain",
                        "proof-state-history",
                        "proof-verification-report",
                        "proof-descriptor",
                        "proof-lineage-closure",
                        "proof-completeness",
                        *(item.artifact_id for item in truncated.sources),
                    ),
                )

    def test_extra_unclassified_artifact_is_rejected(self):
        """Verify the `test_extra_unclassified_artifact_is_rejected` behavior and its expected invariants."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            att, chain, history = prepare_reliability_proof_fixture(root)
            output = root / "proof.zip"
            bundle, _ = build_reliability_proof_bundle(
                attestation_path=att,
                evidence_chain_path=chain,
                history_path=history,
                evidence_root=root,
                output=output,
            )
            _, descriptor = verify_reliability_proof_bundle(output)
            with self.assertRaisesRegex(ValueError, "extra artifacts"):
                build_reliability_proof_completeness(
                    descriptor,
                    artifact_ids=tuple(item.artifact_id for item in bundle.artifacts)
                    + ("unexpected",),
                )

    def test_cli_completeness_verification(self):
        """Verify the `test_cli_completeness_verification` behavior and its expected invariants."""
        import os
        import subprocess

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            att, chain, history = prepare_reliability_proof_fixture(root)
            output = root / "cli-proof.zip"
            build_reliability_proof_bundle(
                attestation_path=att,
                evidence_chain_path=chain,
                history_path=history,
                evidence_root=root,
                output=output,
            )
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
                    "reliability-proof-completeness-verify",
                    str(output),
                ],
                cwd=PROJECT_ROOT,
                env=environment,
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn('"completeness_verified": true', proc.stdout)

    def test_witness_round_trip_rejects_digest_tampering(self):
        """Verify the `test_witness_round_trip_rejects_digest_tampering` behavior and its expected invariants."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            att, chain, history = prepare_reliability_proof_fixture(root)
            output = root / "proof.zip"
            bundle, _ = build_reliability_proof_bundle(
                attestation_path=att,
                evidence_chain_path=chain,
                history_path=history,
                evidence_root=root,
                output=output,
            )
            _, descriptor = verify_reliability_proof_bundle(output)
            witness = build_reliability_proof_completeness(
                descriptor,
                artifact_ids=tuple(item.artifact_id for item in bundle.artifacts),
            )
            payload = witness.to_dict()
            payload["covered_artifact_ids"] = sorted(
                payload["covered_artifact_ids"] + ["unexpected"]
            )
            with self.assertRaises(ValueError):
                ReliabilityProofCompleteness.from_dict(payload)


if __name__ == "__main__":
    unittest.main()
