"""Application services for deterministic operational packages."""

# pyright: reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from statewake import __version__
from statewake.utils.time import parse_datetime

from ..domain.operations import (
    OperationalArtifact,
    OperationalBundle,
    RetentionDecision,
    RetentionPolicy,
    assess_retention,
)


def _safe_member_name(name: str) -> str:
    """Validate and normalize a proof-bundle member path."""
    candidate = name.replace("\\", "/")
    if not candidate or candidate.startswith("/") or ".." in candidate.split("/"):
        raise ValueError("artifact path must be relative and must not contain '..'.")
    return candidate


def _safe_artifact_id(value: str) -> str:
    """Validate the artifact identifier used as a ZIP path component."""
    candidate = value.replace("\\", "/")
    if (
        not candidate.strip()
        or candidate.startswith("/")
        or "/" in candidate
        or candidate in {".", ".."}
    ):
        raise ValueError("artifact_id must be a single relative path component.")
    return candidate


def _parse_retention(payload: object) -> RetentionPolicy | None:
    """Parse a retention policy from its persisted representation."""
    if payload is None:
        return None
    if not isinstance(payload, dict):
        raise ValueError("retention_policy must be a JSON object or null.")
    return RetentionPolicy(
        policy_id=str(payload.get("policy_id", "")),
        max_age_days=None
        if payload.get("max_age_days") is None
        else int(payload["max_age_days"]),
        max_sensitivity=str(payload.get("max_sensitivity", "restricted")),
    )


def load_bundle_spec(path: Path) -> dict[str, Any]:
    """Load and validate a persisted proof-bundle specification."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Bundle spec root must be a JSON object.")
    return payload


def build_bundle(spec_path: Path) -> tuple[OperationalBundle, dict[str, bytes]]:
    """Build a verified deterministic operational bundle from a JSON spec."""
    from hashlib import sha256

    payload = load_bundle_spec(spec_path)
    required = ("bundle_id", "agent_name", "created_at", "artifacts")
    missing = [key for key in required if key not in payload]
    if missing:
        raise ValueError(f"Missing required bundle fields: {', '.join(missing)}")
    artifacts_data = payload["artifacts"]
    if not isinstance(artifacts_data, list) or not artifacts_data:
        raise ValueError("artifacts must be a non-empty JSON array.")
    base = spec_path.parent.resolve()
    records: list[OperationalArtifact] = []
    files: dict[str, bytes] = {}
    for item in artifacts_data:
        if not isinstance(item, dict):
            raise ValueError("Each artifact entry must be a JSON object.")
        artifact_id = _safe_artifact_id(str(item.get("artifact_id", "")))
        path_value = _safe_member_name(str(item.get("path", "")))
        source = (base / path_value).resolve()
        if base not in source.parents and source != base:
            raise ValueError(
                f"Artifact path escapes the bundle-spec directory: {path_value}"
            )
        if not source.is_file():
            raise FileNotFoundError(f"Artifact not found: {source}")
        content = source.read_bytes()
        digest = sha256(content).hexdigest()
        expected_digest = item.get("sha256")
        if expected_digest is not None and str(expected_digest) != digest:
            raise ValueError(
                f"Artifact digest mismatch for {artifact_id}:"
                f" expected {expected_digest}, got {digest}"
            )
        records.append(
            OperationalArtifact(
                artifact_id=artifact_id,  # type: ignore
                path=path_value,
                kind=str(item.get("kind", source.suffix.lstrip(".") or "file")),
                sha256=digest,
                size_bytes=len(content),
                sensitivity=str(item.get("sensitivity", "internal")),
                derived_from=tuple(
                    str(value) for value in item.get("derived_from", [])
                ),
            )
        )
        files[f"artifacts/{artifact_id}/{path_value}"] = content

    created_at = parse_datetime(str(payload["created_at"]), field="created_at")
    manifest_id = str(payload.get("manifest_id", "pending"))
    bundle = OperationalBundle(
        bundle_id=str(payload["bundle_id"]),
        manifest_id=manifest_id,
        agent_name=str(payload["agent_name"]),
        engine_version=str(payload.get("engine_version", __version__)),
        created_at=created_at,
        artifacts=tuple(records),
        retention_policy=_parse_retention(payload.get("retention_policy")),
    )
    computed_manifest_id = bundle.computed_manifest_id()
    if manifest_id == "pending":
        bundle = OperationalBundle(
            bundle_id=bundle.bundle_id,
            manifest_id=computed_manifest_id,
            agent_name=bundle.agent_name,
            engine_version=bundle.engine_version,
            created_at=bundle.created_at,
            artifacts=bundle.artifacts,
            retention_policy=bundle.retention_policy,
        )
    elif manifest_id != computed_manifest_id:
        raise ValueError(
            f"manifest_id mismatch: expected {computed_manifest_id}, got {manifest_id}"
        )
    if bundle.bundle_id == "pending":
        bundle = OperationalBundle(
            bundle_id=bundle.computed_bundle_id(),
            manifest_id=bundle.manifest_id,
            agent_name=bundle.agent_name,
            engine_version=bundle.engine_version,
            created_at=bundle.created_at,
            artifacts=bundle.artifacts,
            retention_policy=bundle.retention_policy,
        )
    elif bundle.bundle_id != bundle.computed_bundle_id():
        raise ValueError(
            f"bundle_id mismatch: expected {bundle.computed_bundle_id()}, got {bundle.bundle_id}"
        )
    manifest_bytes = (
        json.dumps(bundle.to_dict(), indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    files["manifest.json"] = manifest_bytes
    return bundle, files


def export_bundle(
    bundle: OperationalBundle, files: dict[str, bytes], output: Path
) -> None:
    """Write a deterministic ZIP with fixed timestamps and sorted members."""
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for name in sorted(files):
            info = ZipInfo(name)
            info.date_time = (1980, 1, 1, 0, 0, 0)
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, files[name])


def _read_manifest(bundle_path: Path) -> tuple[OperationalBundle, dict[str, bytes]]:
    """Read and validate the proof-bundle manifest."""
    with ZipFile(bundle_path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Operational bundle contains duplicate ZIP member names.")
        if "manifest.json" not in names:
            raise ValueError("Operational bundle is missing manifest.json.")
        raw = archive.read("manifest.json")
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Bundle manifest must be a JSON object.")
        policy = _parse_retention(payload.get("retention_policy"))
        artifacts: list[OperationalArtifact] = []
        for item in payload.get("artifacts", []):
            if not isinstance(item, dict):
                raise ValueError("Bundle artifact entry must be a JSON object.")
            artifacts.append(
                OperationalArtifact(
                    artifact_id=_safe_artifact_id(str(item["artifact_id"])),
                    path=_safe_member_name(str(item["path"])),
                    kind=str(item["kind"]),
                    sha256=str(item["sha256"]),
                    size_bytes=int(item["size_bytes"]),
                    sensitivity=str(item["sensitivity"]),
                    derived_from=tuple(str(v) for v in item.get("derived_from", [])),
                )
            )
        bundle = OperationalBundle(
            bundle_id=str(payload["bundle_id"]),
            manifest_id=str(payload["manifest_id"]),
            agent_name=str(payload["agent_name"]),
            engine_version=str(payload["engine_version"]),
            created_at=parse_datetime(str(payload["created_at"]), field="created_at"),
            artifacts=tuple(artifacts),
            retention_policy=policy,
        )
        expected_names = {
            f"artifacts/{item.artifact_id}/{item.path}" for item in bundle.artifacts
        }
        actual_names = set(names) - {"manifest.json"}
        if actual_names != expected_names:
            missing = sorted(expected_names - actual_names)
            unexpected = sorted(actual_names - expected_names)
            raise ValueError(
                f"Bundle contents do not match manifest; missing={missing}, unexpected={unexpected}"
            )
        for item in bundle.artifacts:
            member_name = f"artifacts/{item.artifact_id}/{item.path}"
            info = archive.getinfo(member_name)
            if info.file_size != item.size_bytes:
                raise ValueError(
                    f"ZIP member size mismatch for artifact {item.artifact_id}: "
                    f"manifest={item.size_bytes}, archive={info.file_size}"
                )
        extracted = {name: archive.read(name) for name in sorted(expected_names)}
    return bundle, extracted


def verify_bundle(bundle_path: Path) -> OperationalBundle:
    """Verify the bundle plus its derived provenance integrity."""
    bundle, files = _read_manifest(bundle_path)
    if bundle.manifest_id != bundle.computed_manifest_id():
        raise ValueError("Bundle manifest_id integrity check failed.")
    if bundle.bundle_id != bundle.computed_bundle_id():
        raise ValueError("Bundle bundle_id integrity check failed.")
    expected_names = {
        f"artifacts/{item.artifact_id}/{item.path}" for item in bundle.artifacts
    }
    if set(files) != expected_names:
        missing = sorted(expected_names - set(files))
        unexpected = sorted(set(files) - expected_names)
        raise ValueError(
            f"Bundle contents do not match manifest; missing={missing}, unexpected={unexpected}"
        )
    from hashlib import sha256

    for item in bundle.artifacts:
        content = files[f"artifacts/{item.artifact_id}/{item.path}"]
        if len(content) != item.size_bytes:
            raise ValueError(f"Size mismatch for artifact {item.artifact_id}.")
        digest = sha256(content).hexdigest()
        if digest != item.sha256:
            raise ValueError(
                f"Digest mismatch for artifact {item.artifact_id}: expected {item.sha256}, got {digest}"
            )
    from ..services.provenance_service import verify_bundle_provenance

    verify_bundle_provenance(bundle_path, bundle)
    return bundle


def inspect_bundle(bundle_path: Path) -> OperationalBundle:
    """Verify and return a bundle for operational inspection."""
    return verify_bundle(bundle_path)


def retention_decision(
    bundle_path: Path, policy: RetentionPolicy, *, as_of: datetime
) -> RetentionDecision:
    """Determine the retention decision for the supplied artifact context."""
    bundle = verify_bundle(bundle_path)
    return assess_retention(bundle, policy, as_of=as_of)
