"""V1 reliability-evidence chain: references, verification state, and decision provenance."""

from __future__ import annotations

# pyright: reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false
# pyright: reportUnknownParameterType=false
# pyright: reportMissingParameterType=false
import json
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from statewake.utils.json_support import JsonValue, string_sequence

_HEX64 = set("0123456789abcdef")
_VERIFICATION = {"unverified", "verified", "failed"}
_RELIABILITY = {"unknown", "reliable", "degraded", "unreliable", "recovered"}
_RECONCILIATION = {"pending", "verified", "stale", "missing", "invalid", "recovered"}
_DECISIONS = {"undecided", "accept", "review", "reject"}


def _digest(value: str, name: str) -> None:
    """Return the deterministic digest for this domain value."""
    if len(value) != 64 or any(ch not in _HEX64 for ch in value):
        raise ValueError(f"{name} must be lowercase SHA-256 hex.")


def _canonical(payload: Mapping[str, JsonValue]) -> bytes:
    """Return the canonical representation used for deterministic identity and signing."""
    return json.dumps(
        dict(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


@dataclass(frozen=True, slots=True)
class EvidenceReference:
    """A stable reference to an artifact already owned by an existing subsystem.

    ``receipt_ref`` optionally binds an evidence artifact to the canonical external
    producer receipt that established its occurrence identity and artifact digest.
    Internal/native evidence may omit it.
    """

    kind: str
    identity: str
    digest: str
    source: str | None = None
    receipt_ref: EvidenceReference | None = None

    def __post_init__(self) -> None:
        """Validate and normalize the initialized object state."""
        if not self.kind.strip() or not self.identity.strip():
            raise ValueError("evidence reference kind and identity must not be empty.")
        _digest(self.digest, "digest")
        if self.source is not None and not self.source.strip():
            raise ValueError("source must not be blank when provided.")
        if self.receipt_ref is not None:
            if self.kind != "evidence":
                raise ValueError("receipt_ref is only valid for evidence references.")
            if self.receipt_ref.kind != "receipt":
                raise ValueError("receipt_ref must have kind 'receipt'.")
            if self.receipt_ref.receipt_ref is not None:
                raise ValueError(
                    "receipt references must not contain nested receipt bindings."
                )

    def to_dict(self) -> dict[str, Any]:
        """Serialize this object to its canonical dictionary representation."""
        return {
            "kind": self.kind,
            "identity": self.identity,
            "digest": self.digest,
            "source": self.source,
            "receipt_ref": None
            if self.receipt_ref is None
            else self.receipt_ref.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class ReliabilityEvidenceChain:
    """One deterministic, evidence-backed V1 reliability decision chain.

    This object stores references and decisions, not copies of producer artifacts. Existing
    run/evidence/provenance/integrity/reconciliation/attestation authorities remain authoritative.
    """

    chain_id: str
    run: EvidenceReference
    state: EvidenceReference
    evidence: tuple[EvidenceReference, ...]
    provenance: EvidenceReference
    integrity: EvidenceReference
    verification_status: str = "unverified"
    reliability_state: str = "unknown"
    reconciliation_state: str = "pending"
    reconciliation_ref: EvidenceReference | None = None
    recovery_ref: EvidenceReference | None = None
    attestation_ref: EvidenceReference | None = None
    decision_basis_ref: EvidenceReference | None = None
    comparison_ref: EvidenceReference | None = None
    reconciliation_binding_ref: EvidenceReference | None = None
    decision: str = "undecided"
    decision_rationale: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Validate and normalize the initialized object state."""
        if not self.chain_id.strip():
            raise ValueError("chain_id must not be empty.")
        if self.run.kind != "run":
            raise ValueError("run reference must have kind 'run'.")
        if self.state.kind != "state":
            raise ValueError("state reference must have kind 'state'.")
        if self.provenance.kind != "provenance":
            raise ValueError("provenance reference must have kind 'provenance'.")
        if self.integrity.kind != "integrity":
            raise ValueError("integrity reference must have kind 'integrity'.")
        if self.decision_basis_ref is not None and self.decision_basis_ref.kind not in {
            "decision-basis",
            "policy",
        }:
            raise ValueError(
                "decision_basis_ref must have kind 'decision-basis' or 'policy'."
            )
        if self.comparison_ref is not None and self.comparison_ref.kind != "comparison":
            raise ValueError("comparison_ref must have kind 'comparison'.")
        if (
            self.reconciliation_binding_ref is not None
            and self.reconciliation_binding_ref.kind != "reconciliation-binding"
        ):
            raise ValueError(
                "reconciliation_binding_ref must have kind 'reconciliation-binding'."
            )
        if not self.evidence:
            raise ValueError("at least one evidence reference is required.")
        if self.verification_status not in _VERIFICATION:
            raise ValueError("unsupported verification_status.")
        if self.reliability_state not in _RELIABILITY:
            raise ValueError("unsupported reliability_state.")
        if self.reconciliation_state not in _RECONCILIATION:
            raise ValueError("unsupported reconciliation_state.")
        if self.decision not in _DECISIONS:
            raise ValueError("unsupported decision.")
        if (
            self.reconciliation_state == "verified"
            and self.verification_status != "verified"
        ):
            raise ValueError("verified reconciliation requires verified chain state.")
        if self.decision == "accept" and not (
            self.verification_status == "verified"
            and self.reconciliation_state in {"verified", "recovered"}
            and self.reliability_state in {"reliable", "recovered"}
        ):
            raise ValueError(
                "accept requires verified evidence, reconciled state, and reliable/recovered state."
            )
        if self.decision == "reject" and self.reliability_state not in {
            "unreliable",
            "degraded",
        }:
            raise ValueError(
                "reject requires unreliable or degraded reliability state."
            )

    def payload(self) -> dict[str, Any]:
        """Return the canonical payload represented by this object."""
        return {
            "chain_id": self.chain_id,
            "run": self.run.to_dict(),
            "state": self.state.to_dict(),
            "evidence": [item.to_dict() for item in self.evidence],
            "provenance": self.provenance.to_dict(),
            "integrity": self.integrity.to_dict(),
            "verification_status": self.verification_status,
            "reliability_state": self.reliability_state,
            "reconciliation_state": self.reconciliation_state,
            "reconciliation_ref": None
            if self.reconciliation_ref is None
            else self.reconciliation_ref.to_dict(),
            "recovery_ref": None
            if self.recovery_ref is None
            else self.recovery_ref.to_dict(),
            "attestation_ref": None
            if self.attestation_ref is None
            else self.attestation_ref.to_dict(),
            "decision_basis_ref": None
            if self.decision_basis_ref is None
            else self.decision_basis_ref.to_dict(),
            "comparison_ref": None
            if self.comparison_ref is None
            else self.comparison_ref.to_dict(),
            "reconciliation_binding_ref": None
            if self.reconciliation_binding_ref is None
            else self.reconciliation_binding_ref.to_dict(),
            "decision": self.decision,
            "decision_rationale": list(self.decision_rationale),
        }

    def digest(self) -> str:
        """Deterministic digest of this object."""
        return sha256(_canonical(self.payload())).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        """Serialize this object with an explicit persisted-format marker.

        ``format_version`` remains outside the canonical digest payload so existing chain
        digests and references remain stable.
        """
        return {"format_version": "1", **self.payload(), "digest": self.digest()}

    @classmethod
    def from_dict(cls, payload: Mapping[str, JsonValue]) -> ReliabilityEvidenceChain:
        """Construct this object from its serialized dictionary representation."""
        format_version = payload.get("format_version")
        if format_version is not None and str(format_version) != "1":
            raise ValueError("unsupported reliability evidence chain format version.")

        def ref(
            value: Any, name: str, *, allow_receipt: bool = True
        ) -> EvidenceReference:
            """Create an evidence reference with its canonical identity and digest."""
            if not isinstance(value, Mapping):
                raise ValueError(f"{name} must be an object.")
            raw_receipt = value.get("receipt_ref")
            receipt = None
            if raw_receipt is not None:
                if not allow_receipt:
                    raise ValueError("nested receipt bindings are not supported.")
                receipt = ref(raw_receipt, f"{name}.receipt_ref", allow_receipt=False)
            return EvidenceReference(
                kind=str(value["kind"]),
                identity=str(value["identity"]),
                digest=str(value["digest"]),
                source=None if value.get("source") is None else str(value["source"]),
                receipt_ref=receipt,
            )

        item = cls(
            chain_id=str(payload["chain_id"]),
            run=ref(payload["run"], "run"),
            state=ref(payload["state"], "state"),
            evidence=tuple(
                ref(value, "evidence")
                for value in payload.get("evidence", [])  # type: ignore
            ),
            provenance=ref(payload["provenance"], "provenance"),
            integrity=ref(payload["integrity"], "integrity"),
            verification_status=str(payload.get("verification_status", "unverified")),
            reliability_state=str(payload.get("reliability_state", "unknown")),
            reconciliation_state=str(payload.get("reconciliation_state", "pending")),
            reconciliation_ref=None
            if payload.get("reconciliation_ref") is None
            else ref(payload["reconciliation_ref"], "reconciliation_ref"),
            recovery_ref=None
            if payload.get("recovery_ref") is None
            else ref(payload["recovery_ref"], "recovery_ref"),
            attestation_ref=None
            if payload.get("attestation_ref") is None
            else ref(payload["attestation_ref"], "attestation_ref"),
            decision_basis_ref=None
            if payload.get("decision_basis_ref") is None
            else ref(payload["decision_basis_ref"], "decision_basis_ref"),
            comparison_ref=None
            if payload.get("comparison_ref") is None
            else ref(payload["comparison_ref"], "comparison_ref"),
            reconciliation_binding_ref=None
            if payload.get("reconciliation_binding_ref") is None
            else ref(
                payload["reconciliation_binding_ref"], "reconciliation_binding_ref"
            ),
            decision=str(payload.get("decision", "undecided")),
            decision_rationale=string_sequence(
                payload.get("decision_rationale", []), field="decision_rationale"
            ),
        )
        supplied = str(payload.get("digest", ""))
        if supplied and supplied != item.digest():
            raise ValueError("reliability evidence chain digest mismatch.")
        return item
