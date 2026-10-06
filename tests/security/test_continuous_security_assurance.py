"""Regression tests for Tier 5 continuous security assurance."""

from __future__ import annotations

import importlib.util
import shutil
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import ModuleType
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts/security/verify_continuous_security_assurance.py"


def load_module() -> ModuleType:
    """Load the Tier 5 verifier without requiring package installation."""
    spec = importlib.util.spec_from_file_location(
        "continuous_security_assurance_verifier", MODULE_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load Tier 5 verifier")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


ASSURANCE_VERIFIER = load_module()


class ContinuousSecurityAssuranceTests(unittest.TestCase):
    """Verify Tier 5 state, change-impact, and re-verification semantics."""

    def setUp(self) -> None:
        """Prepare a temporary copy and a promoted baseline snapshot."""
        self.temp_dir = TemporaryDirectory()
        self.root = Path(self.temp_dir.name) / "project"
        shutil.copytree(
            ROOT,
            self.root,
            ignore=shutil.ignore_patterns(
                ".git",
                ".mypy_cache",
                ".pytest_cache",
                ".ruff_cache",
                ".venv",
                "__pycache__",
                "build",
                "dist",
            ),
        )
        self.baseline_path = (
            self.root / "docs/security/security_assurance_baseline_manifest.txt"
        )
        baseline = ASSURANCE_VERIFIER.snapshot(
            self.root,
            exclude={"docs/security/security_assurance_baseline_manifest.txt"},
        )
        ASSURANCE_VERIFIER.write_snapshot_manifest(self.baseline_path, baseline)

    def tearDown(self) -> None:
        """Remove the temporary project copy."""
        self.temp_dir.cleanup()

    def test_assurance_is_verified_without_changes(self) -> None:
        """A candidate identical to its promoted baseline remains verified."""
        result = ASSURANCE_VERIFIER.assess(self.root, self.baseline_path)
        self.assertEqual(result.state, "VERIFIED")
        self.assertFalse(result.changed_files)
        self.assertFalse(result.impacted_invariants)

    def test_snapshot_can_exclude_baseline_by_file_identity(self) -> None:
        """Baseline exclusion does not depend on string-prefix path spelling."""
        snapshot = ASSURANCE_VERIFIER.snapshot(
            self.root, exclude_paths={self.baseline_path}
        )
        self.assertNotIn(
            "docs/security/security_assurance_baseline_manifest.txt", snapshot
        )

    def test_change_impact_classifies_signing_boundary(self) -> None:
        """A signing adapter change reopens cryptographic assurance."""
        change = ASSURANCE_VERIFIER.classify_change(
            "src/statewake/adapters/key_management.py"
        )
        self.assertIn("crypto-trust", change.families)
        self.assertIn("cryptographic-boundary", change.invariants)

    def test_publication_boundary_change_reopens_publication_assurance(self) -> None:
        """Publication authority/workflow changes reopen the publication invariant."""
        for path in (
            "src/statewake/release_trust/publication.py",
            "src/statewake/release_trust/registry.py",
            "scripts/release/verify_publication_execution.py",
            "scripts/release/reconcile_registry_publication.py",
            "scripts/release/reconcile_registry_publication_lifecycle.py",
            ".github/workflows/python-publish.yml",
        ):
            change = ASSURANCE_VERIFIER.classify_change(path)
            self.assertIn("release-publication", change.families)
            self.assertIn(
                "release-publication-authorization-integrity", change.invariants
            )
            self.assertIn(
                "registry-publication-reconciliation-integrity", change.invariants
            )
            self.assertIn("registry-publication-lifecycle-integrity", change.invariants)

    def test_security_evidence_change_invalidates_assurance(self) -> None:
        """A Tier 4 security-evidence edit cannot silently remain current."""
        change = ASSURANCE_VERIFIER.classify_change("docs/security/THREAT_MODEL.md")
        self.assertEqual(change.families, ("security-evidence",))
        self.assertEqual(change.invariants, ("tier4-security-assurance-evidence",))

    def test_stale_result_is_detected_before_reverification(self) -> None:
        """A relevant change reports stale status when re-verification is withheld."""
        target = self.root / "src/statewake/adapters/key_management.py"
        target.write_text(target.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        result = ASSURANCE_VERIFIER.assess(
            self.root, self.baseline_path, reverify=False
        )
        self.assertEqual(result.state, "STALE")
        self.assertFalse(result.reverified)
        self.assertIsNone(result.reverify_returncode)

    def test_reverification_restores_verified_state(self) -> None:
        """A relevant source change re-verifies Tier 4 before returning green."""
        target = self.root / "src/statewake/adapters/key_management.py"
        target.write_text(target.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        result = ASSURANCE_VERIFIER.assess(self.root, self.baseline_path, reverify=True)
        self.assertEqual(result.state, "VERIFIED")
        self.assertTrue(result.reverified)
        self.assertEqual(result.reverify_returncode, 0)
        self.assertIn("cryptographic-boundary", result.impacted_invariants)

    def test_failed_reverification_breaks_assurance(self) -> None:
        """A failing canonical verifier becomes ASSURANCE_BROKEN, not VERIFIED."""
        target = self.root / "src/statewake/adapters/key_management.py"
        target.write_text(target.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        broken = self.root / "scripts/security/verify_runtime_containment.py"
        original = broken.read_text(encoding="utf-8")
        broken.write_text("def invalid(:\n" + original, encoding="utf-8")
        result = ASSURANCE_VERIFIER.assess(self.root, self.baseline_path, reverify=True)
        self.assertEqual(result.state, "ASSURANCE_BROKEN")
        self.assertTrue(result.reverified is False)
        self.assertNotEqual(result.reverify_returncode, 0)

    def test_promote_on_success_reverifies_then_converges_to_zero_drift(self) -> None:
        """The SDLC promotion option cannot bless drift without Tier 4 re-verification."""
        target = self.root / "src/statewake/adapters/key_management.py"
        target.write_text(target.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        with patch.object(
            sys,
            "argv",
            [
                str(MODULE_PATH),
                "--root",
                str(self.root),
                "--baseline",
                str(self.baseline_path),
                "--promote-on-success",
            ],
        ):
            self.assertEqual(ASSURANCE_VERIFIER.main(), 0)
        converged = ASSURANCE_VERIFIER.assess(
            self.root, self.baseline_path, reverify=False
        )
        self.assertEqual(converged.state, "VERIFIED")
        self.assertFalse(converged.changed_files)

    def test_assurance_state_values_are_closed(self) -> None:
        """Only documented assurance states can be emitted."""
        allowed = {"VERIFIED", "STALE", "REVERIFYING", "ASSURANCE_BROKEN"}
        self.assertIn(
            ASSURANCE_VERIFIER.assess(self.root, self.baseline_path).state, allowed
        )

    def test_snapshot_manifest_uses_platform_independent_lf(self) -> None:
        """Generated assurance manifests use LF regardless of host platform."""
        target = self.root / "snapshot-manifest.txt"
        ASSURANCE_VERIFIER.write_snapshot_manifest(target, {"README.md": "a" * 64})
        expected = f"{'a' * 64}  README.md\n".encode("ascii")
        self.assertEqual(target.read_bytes(), expected)


if __name__ == "__main__":
    unittest.main()
