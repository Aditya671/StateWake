"""Deterministic data-lifecycle and confidentiality contracts for StateWake."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from .governance import SENSITIVITIES, SENSITIVITY_ORDER


def _validate_sensitivity(value: str, *, field_name: str = "sensitivity") -> None:
    """Validate one explicit StateWake sensitivity value."""
    if value not in SENSITIVITY_ORDER:
        raise ValueError(f"{field_name} must be one of {', '.join(SENSITIVITIES)}.")


def inherit_sensitivity(
    source_sensitivities: tuple[str, ...],
    *,
    requested_sensitivity: str | None = None,
    downgrade_approved: bool = False,
) -> str:
    """Return the inherited sensitivity, rejecting unauthorized downgrades."""
    if not source_sensitivities:
        raise ValueError("source_sensitivities must not be empty.")
    for sensitivity in source_sensitivities:
        _validate_sensitivity(sensitivity, field_name="source sensitivity")
    inherited = max(source_sensitivities, key=SENSITIVITY_ORDER.__getitem__)
    if requested_sensitivity is None:
        return inherited
    _validate_sensitivity(requested_sensitivity, field_name="requested_sensitivity")
    if (
        SENSITIVITY_ORDER[requested_sensitivity] < SENSITIVITY_ORDER[inherited]
        and not downgrade_approved
    ):
        raise ValueError(
            "derived sensitivity cannot be downgraded without explicit approval."
        )
    return requested_sensitivity


@dataclass(frozen=True, slots=True)
class DataLifecyclePolicy:
    """Explicit purpose, retention, disclosure, and confidentiality requirements."""

    policy_id: str
    purpose: str
    max_retention_days: int | None = None
    storage_max_sensitivity: str = "restricted"
    telemetry_max_sensitivity: str = "internal"
    disclosure_max_sensitivity: str = "internal"
    encryption_at_rest_required: bool = False
    tls_required: bool = True

    def __post_init__(self) -> None:
        """Validate the lifecycle policy contract."""
        if not self.policy_id.strip() or not self.purpose.strip():
            raise ValueError("policy_id and purpose must not be empty.")
        if self.max_retention_days is not None and self.max_retention_days < 0:
            raise ValueError("max_retention_days must be non-negative when provided.")
        for field_name in (
            "storage_max_sensitivity",
            "telemetry_max_sensitivity",
            "disclosure_max_sensitivity",
        ):
            _validate_sensitivity(getattr(self, field_name), field_name=field_name)


@dataclass(frozen=True, slots=True)
class DataLifecycleDecision:
    """Deterministic lifecycle and confidentiality decision for one data object."""

    object_id: str
    sensitivity: str
    policy_id: str
    retain_until: str | None
    expired: bool
    storage_allowed: bool
    telemetry_allowed: bool
    disclosure_allowed: bool
    deletion_allowed: bool
    reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Serialize the lifecycle decision without exposing payload content."""
        return {
            "object_id": self.object_id,
            "sensitivity": self.sensitivity,
            "policy_id": self.policy_id,
            "retain_until": self.retain_until,
            "expired": self.expired,
            "storage_allowed": self.storage_allowed,
            "telemetry_allowed": self.telemetry_allowed,
            "disclosure_allowed": self.disclosure_allowed,
            "deletion_allowed": self.deletion_allowed,
            "reasons": list(self.reasons),
        }


def assess_data_lifecycle(
    object_id: str,
    *,
    sensitivity: str,
    created_at: datetime,
    policy: DataLifecyclePolicy,
    now: datetime,
    legal_hold: bool = False,
) -> DataLifecycleDecision:
    """Evaluate retention, disclosure, and confidentiality boundaries."""
    if not object_id.strip():
        raise ValueError("object_id must not be empty.")
    _validate_sensitivity(sensitivity)
    if created_at.tzinfo is None or now.tzinfo is None:
        raise ValueError("created_at and now must be timezone-aware.")

    reasons: list[str] = []
    rank = SENSITIVITY_ORDER[sensitivity]
    storage_allowed = rank <= SENSITIVITY_ORDER[policy.storage_max_sensitivity]
    telemetry_allowed = rank <= SENSITIVITY_ORDER[policy.telemetry_max_sensitivity]
    disclosure_allowed = rank <= SENSITIVITY_ORDER[policy.disclosure_max_sensitivity]
    if not storage_allowed:
        reasons.append("sensitivity exceeds storage policy ceiling")
    if not telemetry_allowed:
        reasons.append("sensitivity excluded from telemetry")
    if not disclosure_allowed:
        reasons.append("sensitivity excluded from disclosure")

    retain_until = None
    expired = False
    if policy.max_retention_days is not None:
        eligible = created_at.astimezone(UTC) + timedelta(
            days=policy.max_retention_days
        )
        retain_until = eligible.isoformat()
        expired = now.astimezone(UTC) >= eligible
        if not expired:
            reasons.append("retention window has not expired")
    else:
        reasons.append("no maximum retention is configured")

    deletion_allowed = expired and not legal_hold
    if legal_hold:
        reasons.append("legal hold blocks deletion")

    return DataLifecycleDecision(
        object_id=object_id,
        sensitivity=sensitivity,
        policy_id=policy.policy_id,
        retain_until=retain_until,
        expired=expired,
        storage_allowed=storage_allowed,
        telemetry_allowed=telemetry_allowed,
        disclosure_allowed=disclosure_allowed,
        deletion_allowed=deletion_allowed,
        reasons=tuple(reasons),
    )


@dataclass(frozen=True, slots=True)
class DeletionRecord:
    """Payload-free tombstone preserving historical claim identity after deletion."""

    object_id: str
    digest: str
    sensitivity: str
    deleted_at: str
    policy_id: str
    reason: str
    derived_from: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Validate the payload-free deletion record."""
        if (
            not self.object_id.strip()
            or not self.reason.strip()
            or not self.policy_id.strip()
        ):
            raise ValueError("object_id, policy_id, and reason must not be empty.")
        if len(self.digest) != 64 or any(
            ch not in "0123456789abcdef" for ch in self.digest
        ):
            raise ValueError("digest must be lowercase SHA-256 hex.")
        _validate_sensitivity(self.sensitivity)
        if not self.deleted_at.strip():
            raise ValueError("deleted_at must not be empty.")
        if any(not value.strip() for value in self.derived_from):
            raise ValueError("derived_from must not contain blank values.")

    def to_dict(self) -> dict[str, Any]:
        """Serialize the tombstone without the deleted payload."""
        return {
            "object_id": self.object_id,
            "digest": self.digest,
            "sensitivity": self.sensitivity,
            "deleted_at": self.deleted_at,
            "policy_id": self.policy_id,
            "reason": self.reason,
            "derived_from": list(self.derived_from),
        }


def build_deletion_record(
    object_id: str,
    *,
    digest: str,
    sensitivity: str,
    deleted_at: datetime,
    policy_id: str,
    reason: str,
    derived_from: tuple[str, ...] = (),
) -> DeletionRecord:
    """Build a historical deletion record containing no deleted payload."""
    if deleted_at.tzinfo is None:
        raise ValueError("deleted_at must be timezone-aware.")
    return DeletionRecord(
        object_id=object_id,
        digest=digest,
        sensitivity=sensitivity,
        deleted_at=deleted_at.astimezone(UTC).isoformat(),
        policy_id=policy_id,
        reason=reason,
        derived_from=derived_from,
    )


def filter_disclosable_ids(
    object_sensitivities: dict[str, str], *, max_sensitivity: str
) -> tuple[str, ...]:
    """Return stable object identifiers permitted by a disclosure ceiling."""
    _validate_sensitivity(max_sensitivity, field_name="max_sensitivity")
    allowed_rank = SENSITIVITY_ORDER[max_sensitivity]
    for object_id, sensitivity in object_sensitivities.items():
        if not object_id.strip():
            raise ValueError("object identifiers must not be empty.")
        _validate_sensitivity(sensitivity, field_name="object sensitivity")
    return tuple(
        sorted(
            object_id
            for object_id, sensitivity in object_sensitivities.items()
            if SENSITIVITY_ORDER[sensitivity] <= allowed_rank
        )
    )
