import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# pyright: reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false
# pyright: reportUnknownParameterType=false
# pyright: reportMissingParameterType=false
from statewake.domain.reliability_evidence import (
    EvidenceReference,
    ReliabilityEvidenceChain,
)
from statewake.domain.reliability_outcome_verification import (
    ReliabilityOutcomeVerificationReport,
)
from statewake.domain.reliability_verification_report import (
    ReliabilityVerificationReport,
)
from statewake.services.release_proof_service import (
    build_release_proof,
    render_verification_report,
)

D = "a" * 64


def ref(kind, identity):
    return EvidenceReference(kind, identity, D, f"{identity}.json")


def chain():
    return ReliabilityEvidenceChain(
        chain_id="c",
        run=ref("run", "r"),
        state=ref("state", "s"),
        evidence=(ref("evidence", "e"),),
        provenance=ref("provenance", "p"),
        integrity=ref("integrity", "i"),
        verification_status="verified",
        reliability_state="reliable",
        reconciliation_state="verified",
        decision="accept",
        decision_rationale=("bounded release",),
    )


class FakeBundle:
    bundle_id = "bundle-1"
    manifest_id = "manifest-1"


class TestReleaseProof(unittest.TestCase):
    def test_report_renders_portable_inspection_artifact(self):
        report = ReliabilityVerificationReport(
            "1",
            "Release evidence complete",
            "accept",
            "release-evidence-complete",
            "1",
            True,
            ("run", "state", "evidence"),
            (),
            ("chain_verified",),
            (),
            ("r", "s"),
            ("bounded",),
            ("Verification does not establish external correctness."),  # type: ignore
            "verified",
            "statewake-0.6.1",
            "2026-01-01T00:00:00+00:00",
        )
        text = render_verification_report(report)
        self.assertIn("# Reliability Verification Report", text)
        self.assertIn("VERIFIED", text)
        self.assertIn(report.digest, text)

    def test_workflow_verifies_profile_before_emitting_bundle(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            chain_path = root / "chain.json"
            chain_path.write_text("{}")
            with (
                patch(
                    "statewake.services.release_proof_service.load_reliability_evidence_chain",
                    return_value=chain(),
                ),
                patch(
                    "statewake.services.release_proof_service.verify_reliability_evidence_chain"
                ),
                patch(
                    "statewake.services.release_proof_service.build_reliability_proof_bundle",
                    return_value=(
                        FakeBundle(),
                        ReliabilityOutcomeVerificationReport(
                            "a", "subject", True, ("attestation_integrity",)
                        ),
                    ),
                ),
            ):
                bundle, report, evaluation = build_release_proof(
                    attestation_path=root / "att.json",
                    evidence_chain_path=chain_path,
                    history_path=root / "history",
                    evidence_root=root,
                    output=root / "proof.zip",
                )
            self.assertEqual(bundle.bundle_id, "bundle-1")  # type: ignore
            self.assertTrue(evaluation.satisfied)
            self.assertTrue(report.verified)


if __name__ == "__main__":
    unittest.main()
