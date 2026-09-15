"""Evidence governance decisions over explicit sensitivity classifications."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .evidence import EvidenceManifest

SENSITIVITY_ORDER = {"public": 0, "internal": 1, "confidential": 2, "restricted": 3}
SENSITIVITIES = tuple(SENSITIVITY_ORDER)


@dataclass(frozen=True, slots=True)
class EvidenceGovernancePolicy:
    """Destination-specific evidence policy with deterministic enforcement."""

    policy_id: str
    storage_max_sensitivity: str = "restricted"
    telemetry_max_sensitivity: str = "internal"
    require_digest_for: tuple[str, ...] = ("restricted",)

    def __post_init__(self) -> None:
        """Validate and normalize the initialized object state."""
        if not self.policy_id.strip():
            raise ValueError("policy_id must not be empty.")
        for field_name in ("storage_max_sensitivity", "telemetry_max_sensitivity"):
            value = getattr(self, field_name)
            if value not in SENSITIVITY_ORDER:
                raise ValueError(
                    f"{field_name} must be one of {', '.join(SENSITIVITIES)}."
                )
        unknown = [
            value for value in self.require_digest_for if value not in SENSITIVITY_ORDER
        ]
        if unknown:
            raise ValueError(
                f"require_digest_for contains unsupported sensitivities: {', '.join(unknown)}"
            )


@dataclass(frozen=True, slots=True)
class EvidenceGovernanceDecision:
    """Auditable storage and telemetry decision for one evidence manifest."""

    policy_id: str
    manifest_id: str
    storage_allowed: bool
    telemetry_allowed: bool
    storage_reasons: tuple[str, ...] = ()
    telemetry_reasons: tuple[str, ...] = ()
    telemetry_visible_evidence_ids: tuple[str, ...] = ()

    @property
    def allowed(self) -> bool:
        """Whether the requested operation is permitted by this policy."""
        return self.storage_allowed and self.telemetry_allowed

    def to_dict(self) -> dict[str, Any]:
        """Serialize this object to its canonical dictionary representation."""
        return {
            "policy_id": self.policy_id,
            "manifest_id": self.manifest_id,
            "storage_allowed": self.storage_allowed,
            "telemetry_allowed": self.telemetry_allowed,
            "storage_reasons": list(self.storage_reasons),
            "telemetry_reasons": list(self.telemetry_reasons),
            "telemetry_visible_evidence_ids": list(self.telemetry_visible_evidence_ids),
        }


def evaluate_evidence_governance(
    manifest: EvidenceManifest,
    policy: EvidenceGovernancePolicy,
) -> EvidenceGovernanceDecision:
    """Evaluate explicit evidence classifications without semantic content inspection."""
    storage_reasons: list[str] = []
    telemetry_reasons: list[str] = []
    visible_ids: list[str] = []

    for item in manifest.items:
        sensitivity = item.sensitivity
        if (
            SENSITIVITY_ORDER[sensitivity]
            > SENSITIVITY_ORDER[policy.storage_max_sensitivity]
        ):
            storage_reasons.append(
                f"evidence {item.evidence_id} exceeds storage sensitivity ceiling {policy.storage_max_sensitivity}."
            )
        if sensitivity in policy.require_digest_for and not item.digest:
            storage_reasons.append(
                f"evidence {item.evidence_id} requires a digest for sensitivity {sensitivity}."
            )

        if (
            SENSITIVITY_ORDER[sensitivity]
            <= SENSITIVITY_ORDER[policy.telemetry_max_sensitivity]
        ):
            visible_ids.append(item.evidence_id)
        else:
            telemetry_reasons.append(
                f"evidence {item.evidence_id} is excluded from telemetry at sensitivity {sensitivity}."
            )

    return EvidenceGovernanceDecision(
        policy_id=policy.policy_id,
        manifest_id=manifest.manifest_id,
        storage_allowed=not storage_reasons,
        telemetry_allowed=True,
        storage_reasons=tuple(storage_reasons),
        telemetry_reasons=tuple(telemetry_reasons),
        telemetry_visible_evidence_ids=tuple(sorted(visible_ids)),
    )


def project_manifest_for_telemetry(
    manifest: EvidenceManifest,
    policy: EvidenceGovernancePolicy,
) -> EvidenceManifest:
    """Return only evidence permitted to appear in telemetry metadata."""
    visible = tuple(
        item
        for item in manifest.items
        if SENSITIVITY_ORDER[item.sensitivity]
        <= SENSITIVITY_ORDER[policy.telemetry_max_sensitivity]
    )
    return EvidenceManifest(manifest.manifest_id, manifest.run_id, visible)
