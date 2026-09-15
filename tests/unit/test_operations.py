"""Regression tests for the deterministic operational bundle boundary."""

import json
import tempfile
import unittest
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from statewake.domain.operations import (
    OperationalArtifact,
    OperationalBundle,
    RetentionPolicy,
    assess_retention,
)
from statewake.services.operations_service import (
    build_bundle,
    export_bundle,
    inspect_bundle,
)


class OperationsTests(unittest.TestCase):
    """Exercise deterministic bundle construction, verification, and retention."""

    @staticmethod
    def _fixture(root: Path) -> Path:
        """Create a minimal V1 operational-bundle specification."""
        artifacts = {
            "run": ("run.json", "run", b'{"run_id":"run-1"}'),
            "state": ("state.json", "state", b'{"state_id":"state-1"}'),
            "policy": ("policy.json", "policy", b'{"policy_id":"policy-1"}'),
            "events": ("events.json", "events", b'{"events":["run-1"]}'),
        }
        entries = []
        for artifact_id, (filename, kind, content) in artifacts.items():
            path = root / filename
            path.write_bytes(content)
            entries.append(  # type: ignore
                {
                    "artifact_id": artifact_id,
                    "path": filename,
                    "kind": kind,
                    "sha256": sha256(content).hexdigest(),
                    "sensitivity": "internal",
                    "derived_from": {
                        "policy": [],
                        "state": ["policy"],
                        "run": [],
                        "events": ["state"],
                    }[artifact_id],
                }
            )
        spec = {  # type: ignore
            "bundle_id": "pending",
            "manifest_id": "pending",
            "agent_name": "v1-fixture",
            "created_at": "2026-09-09T10:00:00+00:00",
            "artifacts": entries,
        }
        path = root / "operational-bundle.json"
        path.write_text(json.dumps(spec, indent=2), encoding="utf-8")
        return path

    def test_build_bundle_derives_stable_ids(self) -> None:
        """Verify that bundle and manifest identifiers are deterministic."""
        with tempfile.TemporaryDirectory() as directory:
            bundle, files = build_bundle(self._fixture(Path(directory)))
        self.assertEqual(bundle.bundle_id, bundle.computed_bundle_id())
        self.assertEqual(bundle.manifest_id, bundle.computed_manifest_id())
        self.assertIn("manifest.json", files)
        self.assertEqual(len(bundle.artifacts), 4)

    def test_bundle_round_trip_and_provenance_are_verified(self) -> None:
        """Verify that an exported bundle passes full integrity verification."""
        with tempfile.TemporaryDirectory() as directory:
            bundle, files = build_bundle(self._fixture(Path(directory)))
            path = Path(directory) / "bundle.zip"
            export_bundle(bundle, files, path)
            verified = inspect_bundle(path)
        self.assertEqual(verified.bundle_id, bundle.bundle_id)
        self.assertEqual(verified.artifacts[1].derived_from, ("policy",))
        self.assertEqual(verified.artifacts[3].derived_from, ("state",))

    def test_equivalent_bundle_exports_are_byte_deterministic(self) -> None:
        """Verify that equivalent exports have identical ZIP bytes."""
        with tempfile.TemporaryDirectory() as directory:
            bundle, files = build_bundle(self._fixture(Path(directory)))
            first = Path(directory) / "one.zip"
            second = Path(directory) / "two.zip"
            export_bundle(bundle, files, first)
            export_bundle(bundle, files, second)
            self.assertEqual(first.read_bytes(), second.read_bytes())

    def test_tampered_artifact_is_rejected(self) -> None:
        """Verify that changing a bundled artifact invalidates the bundle."""
        with tempfile.TemporaryDirectory() as directory:
            bundle, files = build_bundle(self._fixture(Path(directory)))
            path = Path(directory) / "bundle.zip"
            export_bundle(bundle, files, path)
            tampered = Path(directory) / "tampered.zip"
            with (
                ZipFile(path, "r") as source,
                ZipFile(tampered, "w", compression=ZIP_DEFLATED) as target,
            ):
                for name in source.namelist():
                    info = ZipInfo(name)
                    info.date_time = (1980, 1, 1, 0, 0, 0)
                    info.compress_type = ZIP_DEFLATED
                    info.external_attr = 0o100644 << 16
                    content = (
                        b"tampered"
                        if name.endswith("state.json")
                        else source.read(name)
                    )
                    target.writestr(info, content)
            with self.assertRaises(ValueError):
                inspect_bundle(tampered)

    def test_unknown_provenance_is_rejected(self) -> None:
        """Verify that an artifact cannot reference an unknown provenance node."""
        artifact = OperationalArtifact(
            "child", "child.json", "state", "0" * 64, 1, derived_from=("missing",)
        )
        with self.assertRaises(ValueError):
            OperationalBundle(
                "bundle",
                "manifest",
                "agent",
                "0.2.0",
                datetime(2026, 9, 9, tzinfo=UTC),
                (artifact,),
            )

    def test_retention_expires_deterministically(self) -> None:
        """Verify deterministic retention expiry."""
        with tempfile.TemporaryDirectory() as directory:
            bundle, _ = build_bundle(self._fixture(Path(directory)))
        policy = RetentionPolicy("p", max_age_days=30, max_sensitivity="internal")
        decision = assess_retention(
            bundle,
            policy,
            as_of=datetime(2026, 10, 10, tzinfo=UTC),
        )
        self.assertEqual(decision.state, "expired")
        self.assertIn("30 days", decision.reason)

    def test_retention_quarantines_above_ceiling(self) -> None:
        """Verify retention quarantine when sensitivity exceeds policy."""
        with tempfile.TemporaryDirectory() as directory:
            bundle, _ = build_bundle(self._fixture(Path(directory)))
        policy = RetentionPolicy("p", max_age_days=30, max_sensitivity="public")
        decision = assess_retention(
            bundle,
            policy,
            as_of=datetime(2026, 9, 9, tzinfo=UTC),
        )
        self.assertEqual(decision.state, "quarantine")


if __name__ == "__main__":
    unittest.main()


class OperationalArtifactPathTests(unittest.TestCase):
    """Verify artifact identifiers cannot become ZIP path traversal components."""

    def test_artifact_id_rejects_path_separators(self) -> None:
        """Reject traversal and nested path syntax in artifact identifiers."""
        for artifact_id in ("../evil", "..\\evil", "foo/bar", "foo\\bar", ".."):
            with self.subTest(artifact_id=artifact_id):
                with self.assertRaisesRegex(ValueError, "artifact_id"):
                    OperationalArtifact(artifact_id, "payload.txt", "data", "0" * 64, 1)

    def test_artifact_path_rejects_windows_style_traversal(self) -> None:
        """Reject backslash traversal in artifact paths at the domain boundary."""
        with self.assertRaisesRegex(ValueError, "artifact path"):
            OperationalArtifact("artifact", r"..\evil.txt", "data", "0" * 64, 1)

    def test_manifest_rejects_traversal_artifact_id(self) -> None:
        """Reject a traversal-crafted artifact identifier during bundle parsing."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spec = OperationsTests._fixture(root)
            payload = json.loads(spec.read_text(encoding="utf-8"))
            payload["artifacts"][0]["artifact_id"] = "../../tmp/evil"
            spec.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "artifact_id"):
                build_bundle(spec)
