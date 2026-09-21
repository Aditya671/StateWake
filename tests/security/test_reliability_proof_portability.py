from __future__ import annotations

import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from config.project_paths import PROJECT_ROOT
from scripts.security.verify_reliability_proof_portability import verify_package
from statewake.services.reliability_proof_bundle_service import (
    build_reliability_proof_bundle,
)
from tests.support.reliability_proof import (
    prepare_reliability_proof_fixture,
)

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class TestReliabilityProofPortability(unittest.TestCase):
    """Cover Tier 9 portable evidence verification invariants."""

    def test_independent_verifier_accepts_portable_bundle_with_limitations(
        self,
    ) -> None:
        """Verify portable evidence without requiring the originating runtime."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            att, chain, history = prepare_reliability_proof_fixture(root)
            bundle = root / "proof.zip"
            build_reliability_proof_bundle(
                attestation_path=att,
                evidence_chain_path=chain,
                history_path=history,
                evidence_root=root,
                output=bundle,
            )
            status, _ = verify_package(bundle)
            self.assertEqual(status, "VERIFIED_WITH_LIMITATIONS")

    def test_independent_verifier_detects_artifact_tampering(self) -> None:
        """Verify changed portable bytes are rejected."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            att, chain, history = prepare_reliability_proof_fixture(root)
            bundle = root / "proof.zip"
            build_reliability_proof_bundle(
                attestation_path=att,
                evidence_chain_path=chain,
                history_path=history,
                evidence_root=root,
                output=bundle,
            )
            tampered = root / "tampered.zip"
            with (
                zipfile.ZipFile(bundle) as source,
                zipfile.ZipFile(tampered, "w") as target,
            ):
                for item in source.infolist():
                    data = source.read(item.filename)
                    if item.filename.endswith("/evidence.json"):
                        data = b'{"evidence":"tampered"}'
                    target.writestr(item, data)
            status, messages = verify_package(tampered)
            self.assertEqual(status, "TAMPERED")
            self.assertTrue(messages)

    def test_independent_verifier_requires_explicit_trust_root_for_full_status(
        self,
    ) -> None:
        """Verify absence of an external trust root cannot become a false VERIFIED."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            att, chain, history = prepare_reliability_proof_fixture(root)
            bundle = root / "proof.zip"
            build_reliability_proof_bundle(
                attestation_path=att,
                evidence_chain_path=chain,
                history_path=history,
                evidence_root=root,
                output=bundle,
            )
            status, messages = verify_package(bundle)
            self.assertEqual(status, "VERIFIED_WITH_LIMITATIONS")
            self.assertTrue(messages)

    def test_portability_assurance_is_development_only(self) -> None:
        """Verify the Tier 9 artifact cannot silently become a release."""
        pyproject = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('version = "0.3.0"', pyproject)
        text = (
            PROJECT_ROOT / "docs/security/evidence_portability_assurance.md"
        ).read_text(encoding="utf-8")
        self.assertIn("not a release approval", text)
