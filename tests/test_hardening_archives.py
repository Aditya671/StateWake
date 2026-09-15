"""Adversarial tests for portable operational ZIP boundaries."""

from __future__ import annotations

import json
import warnings
from datetime import UTC
from hashlib import sha256
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

import pytest

from statewake.domain.operations import OperationalArtifact, OperationalBundle
from statewake.services.operations_service import export_bundle, verify_bundle


def _bundle(tmp_path: Path) -> tuple[OperationalBundle, dict[str, bytes], Path]:
    """Build a minimal valid bundle fixture."""
    content = b"safe artifact\n"
    artifact = OperationalArtifact(
        artifact_id="artifact-1",
        path="payload.txt",
        kind="text",
        sha256=sha256(content).hexdigest(),
        size_bytes=len(content),
    )
    pending = OperationalBundle(
        bundle_id="pending",
        manifest_id="pending",
        agent_name="test-agent",
        engine_version="v0.1.0",
        created_at=__import__("datetime").datetime(2026, 9, 12, tzinfo=UTC),
        artifacts=(artifact,),
    )
    manifest_id = pending.computed_manifest_id()
    bundle = OperationalBundle(
        bundle_id="pending",
        manifest_id=manifest_id,
        agent_name=pending.agent_name,
        engine_version=pending.engine_version,
        created_at=pending.created_at,
        artifacts=pending.artifacts,
    )
    bundle = OperationalBundle(
        bundle_id=bundle.computed_bundle_id(),
        manifest_id=bundle.manifest_id,
        agent_name=bundle.agent_name,
        engine_version=bundle.engine_version,
        created_at=bundle.created_at,
        artifacts=bundle.artifacts,
    )
    files = {
        "manifest.json": (json.dumps(bundle.to_dict(), sort_keys=True) + "\n").encode(),
        "artifacts/artifact-1/payload.txt": content,
    }
    output = tmp_path / "bundle.zip"
    export_bundle(bundle, files, output)
    return bundle, files, output


def test_archive_rejects_unexpected_member_before_reading_it(tmp_path: Path) -> None:
    """Reject extra archive members before decompressing attacker-controlled content."""
    bundle, files, _ = _bundle(tmp_path)  # type: ignore
    malicious = tmp_path / "extra.zip"
    with ZipFile(malicious, "w", compression=ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
        bomb = ZipInfo("artifacts/evil/payload.bin")
        bomb.compress_type = ZIP_DEFLATED
        archive.writestr(bomb, b"x" * (8 * 1024 * 1024))

    with pytest.raises(ValueError, match="contents do not match manifest"):
        verify_bundle(malicious)


def test_archive_rejects_duplicate_member_names(tmp_path: Path) -> None:
    """Reject ZIP duplicate-name ambiguity before trusting any duplicate member."""
    bundle, files, _ = _bundle(tmp_path)  # type: ignore
    duplicate = tmp_path / "duplicate.zip"
    with ZipFile(duplicate, "w", compression=ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            archive.writestr("artifacts/artifact-1/payload.txt", b"tampered")

    with pytest.raises(ValueError, match="duplicate ZIP member"):
        verify_bundle(duplicate)


def test_archive_rejects_manifest_size_disagreement(tmp_path: Path) -> None:
    """Reject an archive whose declared member size differs from the manifest."""
    bundle, files, _ = _bundle(tmp_path)
    mismatch = tmp_path / "mismatch.zip"
    with ZipFile(mismatch, "w", compression=ZIP_DEFLATED) as archive:
        manifest = dict(bundle.to_dict())
        manifest["artifacts"] = [
            dict(files and bundle.artifacts[0].to_dict(), size_bytes=999)
        ]
        archive.writestr("manifest.json", json.dumps(manifest, sort_keys=True).encode())
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            archive.writestr(
                "artifacts/artifact-1/payload.txt",
                files["artifacts/artifact-1/payload.txt"],
            )

    with pytest.raises(ValueError):
        verify_bundle(mismatch)
