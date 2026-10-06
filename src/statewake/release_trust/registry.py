"""Canonical registry publication read-back and reconciliation.

A successful publisher action is not itself evidence that the package registry now
serves the authorized bytes. This module independently reads the registry release
record and the public distribution bytes, then binds that observation to the exact
StateWake publication basis and execution permit.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import Literal, cast
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

from filelock import FileLock, Timeout

from statewake.release_trust.publication import (
    PublicationExecutionPermit,
    PublicationTarget,
    ReleasePublicationBasis,
)
from statewake.utils.json_support import JsonValue, require_object, require_string
from statewake.utils.time import parse_datetime

_RECEIPT_SCHEMA = "release-registry-publication-receipt.v1"
_LIFECYCLE_SCHEMA = "release-registry-publication-lifecycle.v1"
_REGISTRY_BASE = {
    "pypi": "https://pypi.org",
    "testpypi": "https://test.pypi.org",
}
_MAX_REGISTRY_JSON_BYTES = 4 * 1024 * 1024
_MAX_DISTRIBUTION_BYTES = 512 * 1024 * 1024


def _canonical(payload: dict[str, object]) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _require_digest(value: str, field: str) -> None:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")


def _normalize_project(value: str) -> str:
    chars: list[str] = []
    separator = False
    for char in value.lower():
        if char in "-_.":
            if not separator:
                chars.append("-")
            separator = True
        else:
            chars.append(char)
            separator = False
    return "".join(chars)


def registry_release_api_url(
    target: PublicationTarget, distribution: str, version: str
) -> str:
    """Return the official release-specific JSON API endpoint for one target."""
    base = _REGISTRY_BASE[target]
    return f"{base}/pypi/{quote(distribution, safe='')}/{quote(version, safe='')}/json"


@dataclass(frozen=True, slots=True)
class RegistryPublishedArtifact:
    """One public registry file verified against the authorized distribution bytes."""

    name: str
    sha256: str
    size_bytes: int
    url: str
    package_type: str
    upload_time: datetime | None
    yanked: bool
    yanked_reason: str | None = None

    def __post_init__(self) -> None:
        """Validate one observed registry artifact."""
        candidate = PurePosixPath(self.name)
        if (
            candidate.is_absolute()
            or candidate.name != self.name
            or self.name in {"", ".", ".."}
            or "\\" in self.name
        ):
            raise ValueError("registry artifact name must be one safe basename")
        _require_digest(self.sha256, "registry_artifact.sha256")
        if self.size_bytes < 0:
            raise ValueError("registry_artifact.size_bytes must be non-negative")
        parsed = urlparse(self.url)
        if parsed.scheme != "https" or not parsed.hostname:
            raise ValueError("registry artifact URL must use HTTPS")
        if not parsed.hostname.endswith("pythonhosted.org"):
            raise ValueError("registry artifact URL must use the Python package CDN")
        if not self.package_type.strip():
            raise ValueError("registry artifact package_type must not be blank")
        if self.upload_time is not None and self.upload_time.tzinfo is None:
            raise ValueError("registry artifact upload_time must be timezone-aware")
        if not self.yanked and self.yanked_reason is not None:
            raise ValueError("unyanked registry artifact cannot carry a yank reason")
        if self.yanked_reason is not None and not self.yanked_reason.strip():
            raise ValueError("registry artifact yanked_reason must not be blank")

    def to_dict(self) -> dict[str, object]:
        """Serialize the verified public registry artifact."""
        return {
            "name": self.name,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "url": self.url,
            "package_type": self.package_type,
            "upload_time": (
                None
                if self.upload_time is None
                else self.upload_time.astimezone(UTC).isoformat()
            ),
            "yanked": self.yanked,
            "yanked_reason": self.yanked_reason,
            "public_bytes_verified": True,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, JsonValue]) -> RegistryPublishedArtifact:
        """Parse one persisted registry artifact observation."""
        size_raw = payload.get("size_bytes")
        if isinstance(size_raw, bool) or not isinstance(size_raw, int):
            raise ValueError("registry artifact size_bytes must be an integer")
        yanked_raw = payload.get("yanked")
        if not isinstance(yanked_raw, bool):
            raise ValueError("registry artifact yanked must be boolean")
        upload_raw = payload.get("upload_time")
        upload_time = (
            None
            if upload_raw is None
            else parse_datetime(
                require_string(upload_raw, field="upload_time"), field="upload_time"
            )
        )
        reason_raw = payload.get("yanked_reason")
        yanked_reason = (
            None
            if reason_raw is None
            else require_string(reason_raw, field="yanked_reason")
        )
        return cls(
            name=require_string(payload.get("name"), field="name"),
            sha256=require_string(payload.get("sha256"), field="sha256"),
            size_bytes=size_raw,
            url=require_string(payload.get("url"), field="url"),
            package_type=require_string(
                payload.get("package_type"), field="package_type"
            ),
            upload_time=upload_time,
            yanked=yanked_raw,
            yanked_reason=yanked_reason,
        )


@dataclass(frozen=True, slots=True)
class RegistryPublicationReceipt:
    """Immutable proof that a registry served the exact authorized release bytes."""

    basis_digest: str
    permit_digest: str
    target_repository: PublicationTarget
    distribution: str
    version: str
    registry_api_url: str
    observed_at: datetime
    artifacts: tuple[RegistryPublishedArtifact, ...]

    def __post_init__(self) -> None:
        """Validate receipt identity and reconciled registry state."""
        _require_digest(self.basis_digest, "registry_receipt.basis_digest")
        _require_digest(self.permit_digest, "registry_receipt.permit_digest")
        if self.target_repository not in _REGISTRY_BASE:
            raise ValueError("registry_receipt target repository is unsupported")
        if not self.distribution.strip() or not self.version.strip():
            raise ValueError("registry receipt distribution/version must not be blank")
        if self.registry_api_url != registry_release_api_url(
            self.target_repository, self.distribution, self.version
        ):
            raise ValueError("registry receipt API URL does not match target identity")
        if self.observed_at.tzinfo is None:
            raise ValueError("registry receipt observed_at must be timezone-aware")
        if not self.artifacts:
            raise ValueError("registry receipt requires published artifacts")
        names = [artifact.name for artifact in self.artifacts]
        if len(set(names)) != len(names):
            raise ValueError("registry receipt artifact names must be unique")
        if any(artifact.yanked for artifact in self.artifacts):
            raise ValueError(
                "registry receipt cannot claim a yanked release as published"
            )

    @property
    def digest(self) -> str:
        """Return the canonical registry-receipt digest."""
        return sha256(_canonical(self.to_dict())).hexdigest()

    def to_dict(self) -> dict[str, object]:
        """Serialize the reconciled registry state without overstating trust."""
        return {
            "schema_version": _RECEIPT_SCHEMA,
            "basis_digest": self.basis_digest,
            "permit_digest": self.permit_digest,
            "target_repository": self.target_repository,
            "distribution": self.distribution,
            "version": self.version,
            "registry_api_url": self.registry_api_url,
            "observed_at": self.observed_at.astimezone(UTC).isoformat(),
            "artifacts": [item.to_dict() for item in self.artifacts],
            "publication_authorized_at_execution": True,
            "release_published": True,
            "registry_reconciled": True,
            "public_bytes_verified": True,
            "limitations": [
                "This receipt proves the registry API and public download bytes matched the exact authorized publication basis at the recorded observation time.",
                "It does not independently authenticate the human approver or registry operator; those remain separate trust boundaries.",
                "It does not guarantee that the registry entry will remain available, unyanked, or unchanged after the observation time.",
            ],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, JsonValue]) -> RegistryPublicationReceipt:
        """Parse and validate one persisted registry publication receipt."""
        if (
            require_string(payload.get("schema_version"), field="schema_version")
            != _RECEIPT_SCHEMA
        ):
            raise ValueError("unsupported registry publication receipt schema")
        target = require_string(
            payload.get("target_repository"), field="target_repository"
        )
        if target not in _REGISTRY_BASE:
            raise ValueError("unsupported registry publication target")
        for field in (
            "publication_authorized_at_execution",
            "release_published",
            "registry_reconciled",
            "public_bytes_verified",
        ):
            if payload.get(field) is not True:
                raise ValueError(f"registry publication receipt requires {field}=true")
        artifacts_raw = payload.get("artifacts")
        if not isinstance(artifacts_raw, list):
            raise ValueError("registry receipt artifacts must be a JSON array")
        return cls(
            basis_digest=require_string(
                payload.get("basis_digest"), field="basis_digest"
            ),
            permit_digest=require_string(
                payload.get("permit_digest"), field="permit_digest"
            ),
            target_repository=cast(PublicationTarget, target),
            distribution=require_string(
                payload.get("distribution"), field="distribution"
            ),
            version=require_string(payload.get("version"), field="version"),
            registry_api_url=require_string(
                payload.get("registry_api_url"), field="registry_api_url"
            ),
            observed_at=parse_datetime(
                require_string(payload.get("observed_at"), field="observed_at"),
                field="observed_at",
            ),
            artifacts=tuple(
                RegistryPublishedArtifact.from_dict(
                    dict(require_object(item, field=f"artifacts[{index}]"))
                )
                for index, item in enumerate(artifacts_raw)
            ),
        )


def _validate_permit_binding(
    basis: ReleasePublicationBasis, permit: PublicationExecutionPermit
) -> None:
    if permit.basis_digest != basis.digest:
        raise ValueError("publication permit is not bound to the registry basis")
    if permit.target_repository != basis.target_repository:
        raise ValueError("publication permit target does not match registry basis")
    if permit.source_revision != basis.source_revision:
        raise ValueError(
            "publication permit source revision does not match registry basis"
        )
    expected = tuple(sorted((item.name, item.sha256) for item in basis.artifacts))
    if tuple(sorted(permit.artifact_sha256)) != expected:
        raise ValueError(
            "publication permit artifact digests do not match registry basis"
        )


def verify_registry_publication_receipt(
    receipt: RegistryPublicationReceipt,
    basis: ReleasePublicationBasis,
    permit: PublicationExecutionPermit,
) -> None:
    """Verify one persisted receipt against its exact basis and execution permit."""
    _validate_permit_binding(basis, permit)
    if receipt.basis_digest != basis.digest:
        raise ValueError(
            "registry receipt basis digest does not match publication basis"
        )
    if receipt.permit_digest != permit.digest:
        raise ValueError(
            "registry receipt permit digest does not match execution permit"
        )
    if receipt.target_repository != basis.target_repository:
        raise ValueError("registry receipt target does not match publication basis")
    if receipt.distribution != basis.distribution or receipt.version != basis.version:
        raise ValueError(
            "registry receipt release identity does not match publication basis"
        )
    expected = {item.name: (item.sha256, item.size_bytes) for item in basis.artifacts}
    observed = {item.name: (item.sha256, item.size_bytes) for item in receipt.artifacts}
    if observed != expected:
        raise ValueError(
            "registry receipt artifact set does not match publication basis"
        )


def reconcile_registry_publication(
    basis: ReleasePublicationBasis,
    permit: PublicationExecutionPermit,
    registry_payload: dict[str, JsonValue],
    public_artifact_bytes: dict[str, bytes],
    *,
    observed_at: datetime | None = None,
) -> RegistryPublicationReceipt:
    """Fail closed unless registry metadata and downloaded bytes match exactly."""
    _validate_permit_binding(basis, permit)
    info = require_object(registry_payload.get("info"), field="registry.info")
    observed_name = require_string(info.get("name"), field="registry.info.name")
    observed_version = require_string(
        info.get("version"), field="registry.info.version"
    )
    if _normalize_project(observed_name) != _normalize_project(basis.distribution):
        raise ValueError("registry project identity does not match publication basis")
    if observed_version != basis.version:
        raise ValueError("registry release version does not match publication basis")
    urls_raw = registry_payload.get("urls")
    if not isinstance(urls_raw, list):
        raise ValueError("registry release urls must be a JSON array")
    expected_by_name = {artifact.name: artifact for artifact in basis.artifacts}
    if len(urls_raw) != len(expected_by_name):
        raise ValueError("registry artifact set does not match publication basis")
    parsed: dict[str, RegistryPublishedArtifact] = {}
    for index, raw in enumerate(urls_raw):
        item = require_object(raw, field=f"registry.urls[{index}]")
        name = require_string(
            item.get("filename"), field=f"registry.urls[{index}].filename"
        )
        if name in parsed:
            raise ValueError("registry returned duplicate artifact filenames")
        expected = expected_by_name.get(name)
        if expected is None:
            raise ValueError("registry contains an unauthorized release artifact")
        digests = require_object(
            item.get("digests"), field=f"registry.urls[{index}].digests"
        )
        digest = require_string(
            digests.get("sha256"), field=f"registry.urls[{index}].digests.sha256"
        )
        size_raw = item.get("size")
        if isinstance(size_raw, bool) or not isinstance(size_raw, int):
            raise ValueError("registry artifact size must be an integer")
        yanked_raw = item.get("yanked", False)
        if not isinstance(yanked_raw, bool):
            raise ValueError("registry artifact yanked must be boolean")
        if yanked_raw:
            raise ValueError(f"registry artifact is yanked: {name}")
        if digest != expected.sha256 or size_raw != expected.size_bytes:
            raise ValueError(
                f"registry metadata does not match authorized artifact: {name}"
            )
        data = public_artifact_bytes.get(name)
        if data is None:
            raise ValueError(f"public registry bytes were not read back: {name}")
        if (
            len(data) != expected.size_bytes
            or sha256(data).hexdigest() != expected.sha256
        ):
            raise ValueError(
                f"public registry bytes do not match authorized artifact: {name}"
            )
        upload_raw = item.get("upload_time_iso_8601")
        upload_time = None
        if upload_raw is not None:
            upload_time = parse_datetime(
                require_string(
                    upload_raw, field=f"registry.urls[{index}].upload_time_iso_8601"
                ),
                field=f"registry.urls[{index}].upload_time_iso_8601",
            )
        artifact = RegistryPublishedArtifact(
            name=name,
            sha256=digest,
            size_bytes=size_raw,
            url=require_string(item.get("url"), field=f"registry.urls[{index}].url"),
            package_type=require_string(
                item.get("packagetype"), field=f"registry.urls[{index}].packagetype"
            ),
            upload_time=upload_time,
            yanked=False,
        )
        parsed[name] = artifact
    if set(parsed) != set(expected_by_name) or set(public_artifact_bytes) != set(
        expected_by_name
    ):
        raise ValueError(
            "registry read-back artifact set does not match publication basis"
        )
    timestamp = observed_at or datetime.now(UTC)
    if timestamp.tzinfo is None:
        raise ValueError("registry reconciliation clock must be timezone-aware")
    return RegistryPublicationReceipt(
        basis_digest=basis.digest,
        permit_digest=permit.digest,
        target_repository=basis.target_repository,
        distribution=basis.distribution,
        version=basis.version,
        registry_api_url=registry_release_api_url(
            basis.target_repository, basis.distribution, basis.version
        ),
        observed_at=timestamp.astimezone(UTC),
        artifacts=tuple(parsed[name] for name in sorted(parsed)),
    )


RegistryLifecycleStatus = Literal[
    "available", "yanked", "partially_available", "unavailable"
]


@dataclass(frozen=True, slots=True)
class RegistryPublicationLifecycleObservation:
    """One immutable point-in-time observation of a published release's registry state."""

    publication_receipt_digest: str
    predecessor_digest: str
    basis_digest: str
    permit_digest: str
    target_repository: PublicationTarget
    distribution: str
    version: str
    registry_api_url: str
    observed_at: datetime
    status: RegistryLifecycleStatus
    artifacts: tuple[RegistryPublishedArtifact, ...]
    missing_artifacts: tuple[str, ...] = ()
    unavailable_reason: str | None = None

    def __post_init__(self) -> None:
        """Validate one append-only registry lifecycle observation."""
        for value, field in (
            (
                self.publication_receipt_digest,
                "registry_lifecycle.publication_receipt_digest",
            ),
            (self.predecessor_digest, "registry_lifecycle.predecessor_digest"),
            (self.basis_digest, "registry_lifecycle.basis_digest"),
            (self.permit_digest, "registry_lifecycle.permit_digest"),
        ):
            _require_digest(value, field)
        if self.target_repository not in _REGISTRY_BASE:
            raise ValueError("registry lifecycle target repository is unsupported")
        if not self.distribution.strip() or not self.version.strip():
            raise ValueError(
                "registry lifecycle distribution/version must not be blank"
            )
        if self.registry_api_url != registry_release_api_url(
            self.target_repository, self.distribution, self.version
        ):
            raise ValueError(
                "registry lifecycle API URL does not match release identity"
            )
        if self.observed_at.tzinfo is None:
            raise ValueError("registry lifecycle observed_at must be timezone-aware")
        object.__setattr__(self, "artifacts", tuple(self.artifacts))
        object.__setattr__(self, "missing_artifacts", tuple(self.missing_artifacts))
        names = [artifact.name for artifact in self.artifacts]
        if len(set(names)) != len(names):
            raise ValueError("registry lifecycle artifact names must be unique")
        if len(set(self.missing_artifacts)) != len(self.missing_artifacts):
            raise ValueError("registry lifecycle missing_artifacts must be unique")
        if any(not name.strip() for name in self.missing_artifacts):
            raise ValueError(
                "registry lifecycle missing_artifacts must not contain blanks"
            )
        if set(names) & set(self.missing_artifacts):
            raise ValueError(
                "observed and missing registry lifecycle artifacts must be disjoint"
            )
        if self.status == "unavailable":
            if self.artifacts or self.missing_artifacts:
                raise ValueError(
                    "unavailable registry lifecycle observation cannot contain artifact state"
                )
            if self.unavailable_reason is None or not self.unavailable_reason.strip():
                raise ValueError(
                    "unavailable registry lifecycle observation requires a reason"
                )
            return
        if self.unavailable_reason is not None:
            raise ValueError(
                "available/yanked/partial registry lifecycle observation cannot carry an unavailable reason"
            )
        if self.status == "partially_available":
            if not self.missing_artifacts:
                raise ValueError(
                    "partially available registry lifecycle observation requires missing artifacts"
                )
        elif self.missing_artifacts:
            raise ValueError(
                "complete registry lifecycle observation cannot report missing artifacts"
            )
        if self.status in {"available", "yanked"} and not self.artifacts:
            raise ValueError(
                "available/yanked registry lifecycle observation requires artifacts"
            )
        yanked_values = {artifact.yanked for artifact in self.artifacts}
        if len(yanked_values) > 1:
            raise ValueError(
                "mixed yanked state is unsupported for the PyPI release lifecycle"
            )
        if self.status == "available" and yanked_values == {True}:
            raise ValueError(
                "available registry lifecycle observation cannot contain yanked artifacts"
            )
        if self.status == "yanked" and yanked_values != {True}:
            raise ValueError(
                "yanked registry lifecycle observation requires yanked artifacts"
            )

    @property
    def digest(self) -> str:
        """Return the canonical lifecycle observation digest."""
        return sha256(_canonical(self.to_dict())).hexdigest()

    @property
    def public_bytes_verified(self) -> bool:
        """Whether the complete authorized public artifact set was read and verified."""
        return self.status in {"available", "yanked"}

    def to_dict(self) -> dict[str, object]:
        """Serialize this point-in-time registry lifecycle observation."""
        return {
            "schema_version": _LIFECYCLE_SCHEMA,
            "publication_receipt_digest": self.publication_receipt_digest,
            "predecessor_digest": self.predecessor_digest,
            "basis_digest": self.basis_digest,
            "permit_digest": self.permit_digest,
            "target_repository": self.target_repository,
            "distribution": self.distribution,
            "version": self.version,
            "registry_api_url": self.registry_api_url,
            "observed_at": self.observed_at.astimezone(UTC).isoformat(),
            "status": self.status,
            "registry_entry_present": self.status != "unavailable",
            "default_install_eligible": self.status == "available",
            "public_bytes_verified": self.public_bytes_verified,
            "missing_artifacts": list(self.missing_artifacts),
            "unavailable_reason": self.unavailable_reason,
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "limitations": [
                "This is a point-in-time registry observation chained to the original publication receipt; it does not mutate historical publication evidence.",
                "A yanked observation records registry selection state, not deletion; exact pins may still resolve yanked files according to installer policy.",
                "A partially available observation proves only that some previously authorized artifacts were absent from the official release endpoint at observation time; it does not prove deletion intent, actor identity, or cause.",
                "An unavailable observation proves only that the official release-specific registry endpoint was unavailable at observation time; it does not prove why the release disappeared or who caused it.",
            ],
        }

    @classmethod
    def from_dict(
        cls, payload: dict[str, JsonValue]
    ) -> RegistryPublicationLifecycleObservation:
        """Parse one persisted lifecycle observation."""
        if (
            require_string(payload.get("schema_version"), field="schema_version")
            != _LIFECYCLE_SCHEMA
        ):
            raise ValueError("unsupported registry publication lifecycle schema")
        target = require_string(
            payload.get("target_repository"), field="target_repository"
        )
        if target not in _REGISTRY_BASE:
            raise ValueError("unsupported registry lifecycle target")
        status = require_string(payload.get("status"), field="status")
        if status not in {"available", "yanked", "partially_available", "unavailable"}:
            raise ValueError("unsupported registry lifecycle status")
        artifacts_raw = payload.get("artifacts")
        if not isinstance(artifacts_raw, list):
            raise ValueError("registry lifecycle artifacts must be a JSON array")
        missing_raw = payload.get("missing_artifacts", [])
        if not isinstance(missing_raw, list):
            raise ValueError(
                "registry lifecycle missing_artifacts must be a JSON array"
            )
        unavailable_raw = payload.get("unavailable_reason")
        unavailable_reason = (
            None
            if unavailable_raw is None
            else require_string(unavailable_raw, field="unavailable_reason")
        )
        observation = cls(
            publication_receipt_digest=require_string(
                payload.get("publication_receipt_digest"),
                field="publication_receipt_digest",
            ),
            predecessor_digest=require_string(
                payload.get("predecessor_digest"), field="predecessor_digest"
            ),
            basis_digest=require_string(
                payload.get("basis_digest"), field="basis_digest"
            ),
            permit_digest=require_string(
                payload.get("permit_digest"), field="permit_digest"
            ),
            target_repository=cast(PublicationTarget, target),
            distribution=require_string(
                payload.get("distribution"), field="distribution"
            ),
            version=require_string(payload.get("version"), field="version"),
            registry_api_url=require_string(
                payload.get("registry_api_url"), field="registry_api_url"
            ),
            observed_at=parse_datetime(
                require_string(payload.get("observed_at"), field="observed_at"),
                field="observed_at",
            ),
            status=cast(RegistryLifecycleStatus, status),
            artifacts=tuple(
                RegistryPublishedArtifact.from_dict(
                    dict(require_object(item, field=f"artifacts[{index}]"))
                )
                for index, item in enumerate(artifacts_raw)
            ),
            missing_artifacts=tuple(
                require_string(item, field=f"missing_artifacts[{index}]")
                for index, item in enumerate(missing_raw)
            ),
            unavailable_reason=unavailable_reason,
        )
        if payload.get("registry_entry_present") is not (
            observation.status != "unavailable"
        ):
            raise ValueError(
                "registry lifecycle registry_entry_present disagrees with status"
            )
        if payload.get("default_install_eligible") is not (
            observation.status == "available"
        ):
            raise ValueError(
                "registry lifecycle default_install_eligible disagrees with status"
            )
        if (
            payload.get("public_bytes_verified")
            is not observation.public_bytes_verified
        ):
            raise ValueError(
                "registry lifecycle public_bytes_verified disagrees with status"
            )
        if payload.get("limitations") != observation.to_dict()["limitations"]:
            raise ValueError(
                "registry lifecycle limitations do not match canonical semantics"
            )
        return observation


def verify_registry_publication_lifecycle_observation(
    observation: RegistryPublicationLifecycleObservation,
    receipt: RegistryPublicationReceipt,
    basis: ReleasePublicationBasis,
    permit: PublicationExecutionPermit,
    *,
    previous: RegistryPublicationLifecycleObservation | None = None,
) -> None:
    """Verify one lifecycle observation against immutable publication evidence and chain tip."""
    verify_registry_publication_receipt(receipt, basis, permit)
    if observation.publication_receipt_digest != receipt.digest:
        raise ValueError(
            "registry lifecycle observation is not bound to the publication receipt"
        )
    if (
        observation.basis_digest != basis.digest
        or observation.permit_digest != permit.digest
    ):
        raise ValueError(
            "registry lifecycle observation is not bound to publication evidence"
        )
    if observation.target_repository != basis.target_repository:
        raise ValueError("registry lifecycle target does not match publication basis")
    if (
        observation.distribution != basis.distribution
        or observation.version != basis.version
    ):
        raise ValueError(
            "registry lifecycle release identity does not match publication basis"
        )
    expected_predecessor = receipt.digest if previous is None else previous.digest
    if observation.predecessor_digest != expected_predecessor:
        raise ValueError(
            "registry lifecycle predecessor digest does not match canonical chain tip"
        )
    previous_time = receipt.observed_at if previous is None else previous.observed_at
    if observation.observed_at < previous_time:
        raise ValueError("registry lifecycle observation time cannot move backwards")
    if observation.status == "unavailable":
        return
    expected = {item.name: (item.sha256, item.size_bytes) for item in basis.artifacts}
    observed = {
        item.name: (item.sha256, item.size_bytes) for item in observation.artifacts
    }
    if any(
        name not in expected or expected[name] != value
        for name, value in observed.items()
    ):
        raise ValueError(
            "registry lifecycle artifact set does not match publication basis"
        )
    missing = tuple(sorted(set(expected) - set(observed)))
    if observation.status == "partially_available":
        if not missing or missing != tuple(sorted(observation.missing_artifacts)):
            raise ValueError(
                "registry lifecycle missing artifact set does not match publication basis"
            )
    elif observed != expected or observation.missing_artifacts:
        raise ValueError(
            "registry lifecycle artifact set does not match publication basis"
        )


def reconcile_registry_publication_lifecycle(
    receipt: RegistryPublicationReceipt,
    basis: ReleasePublicationBasis,
    permit: PublicationExecutionPermit,
    registry_payload: dict[str, JsonValue] | None,
    public_artifact_bytes: dict[str, bytes],
    *,
    previous: RegistryPublicationLifecycleObservation | None = None,
    unavailable_reason: str | None = None,
    observed_at: datetime | None = None,
) -> RegistryPublicationLifecycleObservation:
    """Reconcile one current registry state without rewriting the original publication receipt."""
    verify_registry_publication_receipt(receipt, basis, permit)
    timestamp = observed_at or datetime.now(UTC)
    if timestamp.tzinfo is None:
        raise ValueError("registry lifecycle clock must be timezone-aware")
    predecessor = receipt.digest if previous is None else previous.digest
    if registry_payload is None:
        if public_artifact_bytes:
            raise ValueError(
                "unavailable registry lifecycle observation cannot contain public bytes"
            )
        observation = RegistryPublicationLifecycleObservation(
            publication_receipt_digest=receipt.digest,
            predecessor_digest=predecessor,
            basis_digest=basis.digest,
            permit_digest=permit.digest,
            target_repository=basis.target_repository,
            distribution=basis.distribution,
            version=basis.version,
            registry_api_url=registry_release_api_url(
                basis.target_repository, basis.distribution, basis.version
            ),
            observed_at=timestamp.astimezone(UTC),
            status="unavailable",
            artifacts=(),
            missing_artifacts=(),
            unavailable_reason=unavailable_reason
            or "release-specific registry API returned HTTP 404",
        )
        verify_registry_publication_lifecycle_observation(
            observation, receipt, basis, permit, previous=previous
        )
        return observation

    info = require_object(registry_payload.get("info"), field="registry.info")
    observed_name = require_string(info.get("name"), field="registry.info.name")
    observed_version = require_string(
        info.get("version"), field="registry.info.version"
    )
    if _normalize_project(observed_name) != _normalize_project(basis.distribution):
        raise ValueError("registry project identity does not match publication basis")
    if observed_version != basis.version:
        raise ValueError("registry release version does not match publication basis")
    urls_raw = registry_payload.get("urls")
    if not isinstance(urls_raw, list):
        raise ValueError("registry release urls must be a JSON array")
    expected_by_name = {artifact.name: artifact for artifact in basis.artifacts}
    parsed: dict[str, RegistryPublishedArtifact] = {}
    for index, raw in enumerate(urls_raw):
        item = require_object(raw, field=f"registry.urls[{index}]")
        name = require_string(
            item.get("filename"), field=f"registry.urls[{index}].filename"
        )
        if name in parsed:
            raise ValueError("registry returned duplicate artifact filenames")
        expected = expected_by_name.get(name)
        if expected is None:
            raise ValueError("registry contains an unauthorized release artifact")
        digests = require_object(
            item.get("digests"), field=f"registry.urls[{index}].digests"
        )
        digest = require_string(
            digests.get("sha256"), field=f"registry.urls[{index}].digests.sha256"
        )
        size_raw = item.get("size")
        if isinstance(size_raw, bool) or not isinstance(size_raw, int):
            raise ValueError("registry artifact size must be an integer")
        if digest != expected.sha256 or size_raw != expected.size_bytes:
            raise ValueError(
                f"registry metadata does not match authorized artifact: {name}"
            )
        yanked_raw = item.get("yanked", False)
        if not isinstance(yanked_raw, bool):
            raise ValueError("registry artifact yanked must be boolean")
        reason_raw = item.get("yanked_reason")
        yanked_reason = (
            None
            if reason_raw is None
            else require_string(
                reason_raw, field=f"registry.urls[{index}].yanked_reason"
            )
        )
        if not yanked_raw and yanked_reason is not None:
            raise ValueError(
                "registry artifact cannot carry a yank reason while unyanked"
            )
        data = public_artifact_bytes.get(name)
        if data is None:
            raise ValueError(f"public registry bytes were not read back: {name}")
        if (
            len(data) != expected.size_bytes
            or sha256(data).hexdigest() != expected.sha256
        ):
            raise ValueError(
                f"public registry bytes do not match authorized artifact: {name}"
            )
        upload_raw = item.get("upload_time_iso_8601")
        upload_time = None
        if upload_raw is not None:
            upload_time = parse_datetime(
                require_string(
                    upload_raw, field=f"registry.urls[{index}].upload_time_iso_8601"
                ),
                field=f"registry.urls[{index}].upload_time_iso_8601",
            )
        parsed[name] = RegistryPublishedArtifact(
            name=name,
            sha256=digest,
            size_bytes=size_raw,
            url=require_string(item.get("url"), field=f"registry.urls[{index}].url"),
            package_type=require_string(
                item.get("packagetype"), field=f"registry.urls[{index}].packagetype"
            ),
            upload_time=upload_time,
            yanked=yanked_raw,
            yanked_reason=yanked_reason,
        )
    if set(public_artifact_bytes) != set(parsed):
        raise ValueError(
            "registry lifecycle read-back bytes do not match observed artifact set"
        )
    missing_artifacts = tuple(sorted(set(expected_by_name) - set(parsed)))
    yanked_values = {artifact.yanked for artifact in parsed.values()}
    if len(yanked_values) > 1:
        raise ValueError(
            "mixed yanked state is unsupported for the PyPI release lifecycle"
        )
    status: RegistryLifecycleStatus
    if missing_artifacts:
        status = "partially_available"
    elif yanked_values == {True}:
        status = "yanked"
    else:
        status = "available"
    observation = RegistryPublicationLifecycleObservation(
        publication_receipt_digest=receipt.digest,
        predecessor_digest=predecessor,
        basis_digest=basis.digest,
        permit_digest=permit.digest,
        target_repository=basis.target_repository,
        distribution=basis.distribution,
        version=basis.version,
        registry_api_url=registry_release_api_url(
            basis.target_repository, basis.distribution, basis.version
        ),
        observed_at=timestamp.astimezone(UTC),
        status=status,
        artifacts=tuple(parsed[name] for name in sorted(parsed)),
        missing_artifacts=missing_artifacts,
    )
    verify_registry_publication_lifecycle_observation(
        observation, receipt, basis, permit, previous=previous
    )
    return observation


def _read_registry_release_url(
    url: str, *, timeout: float, max_bytes: int
) -> bytes | None:
    """Read the official release endpoint, distinguishing a real 404 from transport failure."""
    request = Request(
        url, headers={"Accept": "application/json", "User-Agent": "StateWake/0.5.0"}
    )
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - URL is generated from a fixed registry allowlist.
            data = cast(bytes, response.read(max_bytes + 1))
    except HTTPError as exc:
        if exc.code == 404:
            return None
        raise ConnectionError(f"registry lifecycle read-back failed for {url}") from exc
    except (URLError, TimeoutError) as exc:
        raise ConnectionError(f"registry lifecycle read-back failed for {url}") from exc
    if len(data) > max_bytes:
        raise ValueError("registry lifecycle response exceeds configured read bound")
    return data


def fetch_registry_publication_lifecycle(
    receipt: RegistryPublicationReceipt,
    basis: ReleasePublicationBasis,
    permit: PublicationExecutionPermit,
    *,
    previous: RegistryPublicationLifecycleObservation | None = None,
    timeout: float = 30.0,
    max_registry_json_bytes: int = _MAX_REGISTRY_JSON_BYTES,
    max_distribution_bytes: int = _MAX_DISTRIBUTION_BYTES,
    now: datetime | None = None,
) -> RegistryPublicationLifecycleObservation:
    """Fetch and reconcile the current official registry lifecycle state."""
    if timeout <= 0:
        raise ValueError("registry lifecycle timeout must be positive")
    if max_registry_json_bytes <= 0 or max_distribution_bytes <= 0:
        raise ValueError("registry lifecycle byte bounds must be positive")
    verify_registry_publication_receipt(receipt, basis, permit)
    api_url = registry_release_api_url(
        basis.target_repository, basis.distribution, basis.version
    )
    payload_raw = _read_registry_release_url(
        api_url, timeout=timeout, max_bytes=max_registry_json_bytes
    )
    if payload_raw is None:
        return reconcile_registry_publication_lifecycle(
            receipt,
            basis,
            permit,
            None,
            {},
            previous=previous,
            unavailable_reason="release-specific registry API returned HTTP 404",
            observed_at=now,
        )
    try:
        decoded = json.loads(payload_raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("registry lifecycle response is not valid JSON") from exc
    if not isinstance(decoded, dict) or any(
        not isinstance(key, str) for key in decoded
    ):
        raise ValueError("registry lifecycle response root must be an object")
    payload = cast(dict[str, JsonValue], decoded)
    urls_raw = payload.get("urls")
    if not isinstance(urls_raw, list):
        raise ValueError("registry release urls must be a JSON array")
    expected_names = {artifact.name for artifact in basis.artifacts}
    public_bytes: dict[str, bytes] = {}
    for index, raw in enumerate(urls_raw):
        item = require_object(raw, field=f"registry.urls[{index}]")
        name = require_string(
            item.get("filename"), field=f"registry.urls[{index}].filename"
        )
        if name not in expected_names:
            raise ValueError("registry contains an unauthorized release artifact")
        url = require_string(item.get("url"), field=f"registry.urls[{index}].url")
        parsed = urlparse(url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or not parsed.hostname.endswith("pythonhosted.org")
        ):
            raise ValueError("registry artifact URL is outside the Python package CDN")
        public_bytes[name] = _read_url(
            url, timeout=timeout, max_bytes=max_distribution_bytes
        )
    return reconcile_registry_publication_lifecycle(
        receipt,
        basis,
        permit,
        payload,
        public_bytes,
        previous=previous,
        observed_at=now,
    )


class RegistryPublicationLifecycleStore:
    """Append and verify immutable registry lifecycle observations in a bounded JSONL history."""

    def __init__(
        self,
        path: Path,
        *,
        max_bytes: int = 8 * 1024 * 1024,
        max_records: int = 10_000,
        lock_timeout_seconds: float = 5.0,
    ) -> None:
        """Initialize one bounded append-only lifecycle history."""
        self.path = path.expanduser().resolve()
        self.max_bytes = max_bytes
        self.max_records = max_records
        self.lock_timeout_seconds = lock_timeout_seconds
        if max_bytes <= 0 or max_records <= 0 or lock_timeout_seconds <= 0:
            raise ValueError("registry lifecycle store bounds must be positive")
        self._lock_path = self.path.with_suffix(self.path.suffix + ".lock")

    def _read_unlocked(
        self,
        receipt: RegistryPublicationReceipt,
        basis: ReleasePublicationBasis,
        permit: PublicationExecutionPermit,
    ) -> tuple[RegistryPublicationLifecycleObservation, ...]:
        if not self.path.exists():
            return ()
        if self.path.is_symlink():
            raise ValueError("registry lifecycle history cannot be a symlink")
        if self.path.stat().st_size > self.max_bytes:
            raise ValueError("registry lifecycle history exceeds configured read bound")
        lines = self.path.read_text(encoding="utf-8").splitlines()
        if len(lines) > self.max_records:
            raise ValueError(
                "registry lifecycle history exceeds configured record bound"
            )
        observations: list[RegistryPublicationLifecycleObservation] = []
        previous: RegistryPublicationLifecycleObservation | None = None
        for index, line in enumerate(lines):
            if not line.strip():
                raise ValueError("registry lifecycle history contains a blank record")
            raw = json.loads(line)
            if not isinstance(raw, dict) or any(
                not isinstance(key, str) for key in raw
            ):
                raise ValueError("registry lifecycle history record must be an object")
            payload = cast(dict[str, JsonValue], raw)
            observation = RegistryPublicationLifecycleObservation.from_dict(payload)
            digest = require_string(
                payload.get("observation_digest"),
                field=f"record[{index}].observation_digest",
            )
            if digest != observation.digest:
                raise ValueError(
                    "registry lifecycle observation digest does not match contents"
                )
            verify_registry_publication_lifecycle_observation(
                observation, receipt, basis, permit, previous=previous
            )
            observations.append(observation)
            previous = observation
        return tuple(observations)

    def read(
        self,
        receipt: RegistryPublicationReceipt,
        basis: ReleasePublicationBasis,
        permit: PublicationExecutionPermit,
    ) -> tuple[RegistryPublicationLifecycleObservation, ...]:
        """Return a fully verified lifecycle chain."""
        lock = FileLock(str(self._lock_path), timeout=self.lock_timeout_seconds)
        try:
            with lock:
                return self._read_unlocked(receipt, basis, permit)
        except Timeout as exc:
            raise TimeoutError(
                "timed out acquiring registry lifecycle history lock"
            ) from exc

    def append(
        self,
        observation: RegistryPublicationLifecycleObservation,
        receipt: RegistryPublicationReceipt,
        basis: ReleasePublicationBasis,
        permit: PublicationExecutionPermit,
    ) -> bool:
        """Append one verified observation; return False for an exact tail retry."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock = FileLock(str(self._lock_path), timeout=self.lock_timeout_seconds)
        try:
            with lock:
                history = self._read_unlocked(receipt, basis, permit)
                previous = history[-1] if history else None
                if previous is not None and previous.digest == observation.digest:
                    return False
                verify_registry_publication_lifecycle_observation(
                    observation, receipt, basis, permit, previous=previous
                )
                if len(history) >= self.max_records:
                    raise ValueError(
                        "registry lifecycle history exceeds configured record bound"
                    )
                payload = observation.to_dict()
                payload["observation_digest"] = observation.digest
                encoded = _canonical(payload) + b"\n"
                existing_size = self.path.stat().st_size if self.path.exists() else 0
                if existing_size + len(encoded) > self.max_bytes:
                    raise ValueError(
                        "registry lifecycle history exceeds configured write bound"
                    )
                with self.path.open("ab") as handle:
                    handle.write(encoded)
                    handle.flush()
                return True
        except Timeout as exc:
            raise TimeoutError(
                "timed out acquiring registry lifecycle history lock"
            ) from exc


def _read_url(url: str, *, timeout: float, max_bytes: int) -> bytes:
    request = Request(
        url, headers={"Accept": "application/json", "User-Agent": "StateWake/0.5.0"}
    )
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - URL is validated by caller/registry model.
            data = cast(bytes, response.read(max_bytes + 1))
    except (HTTPError, URLError, TimeoutError) as exc:
        raise ConnectionError(f"registry read-back failed for {url}") from exc
    if len(data) > max_bytes:
        raise ValueError("registry response exceeds configured read bound")
    return data


def fetch_registry_publication(
    basis: ReleasePublicationBasis,
    permit: PublicationExecutionPermit,
    *,
    timeout: float = 30.0,
    max_registry_json_bytes: int = _MAX_REGISTRY_JSON_BYTES,
    max_distribution_bytes: int = _MAX_DISTRIBUTION_BYTES,
    now: datetime | None = None,
) -> RegistryPublicationReceipt:
    """Fetch the official registry release record and verify public file bytes."""
    if timeout <= 0:
        raise ValueError("registry read-back timeout must be positive")
    if max_registry_json_bytes <= 0 or max_distribution_bytes <= 0:
        raise ValueError("registry read-back byte bounds must be positive")
    _validate_permit_binding(basis, permit)
    api_url = registry_release_api_url(
        basis.target_repository, basis.distribution, basis.version
    )
    payload_raw = _read_url(api_url, timeout=timeout, max_bytes=max_registry_json_bytes)
    try:
        decoded = json.loads(payload_raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("registry release response is not valid JSON") from exc
    if not isinstance(decoded, dict) or any(
        not isinstance(key, str) for key in decoded
    ):
        raise ValueError("registry release response root must be an object")
    payload = cast(dict[str, JsonValue], decoded)
    urls_raw = payload.get("urls")
    if not isinstance(urls_raw, list):
        raise ValueError("registry release urls must be a JSON array")
    expected_names = {artifact.name for artifact in basis.artifacts}
    public_bytes: dict[str, bytes] = {}
    for index, raw in enumerate(urls_raw):
        item = require_object(raw, field=f"registry.urls[{index}]")
        name = require_string(
            item.get("filename"), field=f"registry.urls[{index}].filename"
        )
        if name not in expected_names:
            raise ValueError("registry contains an unauthorized release artifact")
        url = require_string(item.get("url"), field=f"registry.urls[{index}].url")
        parsed = urlparse(url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or not parsed.hostname.endswith("pythonhosted.org")
        ):
            raise ValueError("registry artifact URL is outside the Python package CDN")
        public_bytes[name] = _read_url(
            url, timeout=timeout, max_bytes=max_distribution_bytes
        )
    return reconcile_registry_publication(
        basis, permit, payload, public_bytes, observed_at=now
    )


def write_registry_publication_receipt(
    receipt: RegistryPublicationReceipt, path: Path
) -> None:
    """Persist one canonical reconciled registry receipt including its digest."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = receipt.to_dict()
    payload["receipt_digest"] = receipt.digest
    path.write_bytes(_canonical(payload) + b"\n")


def load_registry_publication_receipt(path: Path) -> RegistryPublicationReceipt:
    """Load and verify one persisted registry publication receipt."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or any(not isinstance(key, str) for key in raw):
        raise ValueError("registry publication receipt root must be an object")
    payload = cast(dict[str, JsonValue], raw)
    receipt = RegistryPublicationReceipt.from_dict(payload)
    recorded_digest = payload.get("receipt_digest")
    if recorded_digest is not None:
        if require_string(recorded_digest, field="receipt_digest") != receipt.digest:
            raise ValueError(
                "registry publication receipt digest does not match contents"
            )
    return receipt


__all__ = [
    "RegistryLifecycleStatus",
    "RegistryPublicationLifecycleObservation",
    "RegistryPublicationLifecycleStore",
    "RegistryPublicationReceipt",
    "RegistryPublishedArtifact",
    "fetch_registry_publication",
    "fetch_registry_publication_lifecycle",
    "load_registry_publication_receipt",
    "reconcile_registry_publication",
    "reconcile_registry_publication_lifecycle",
    "registry_release_api_url",
    "verify_registry_publication_lifecycle_observation",
    "verify_registry_publication_receipt",
    "write_registry_publication_receipt",
]
