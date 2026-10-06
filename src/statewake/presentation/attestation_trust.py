"""Read-only attestation trust and signing-key lifecycle investigation projections."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256

from statewake.adapters.attestation_trust_history import AttestationTrustHistorySnapshot
from statewake.adapters.reliability_attestation import ReliabilityAttestationSnapshot
from statewake.domain.attestation_trust import SignedAttestationTrustState

ATTESTATION_TRUST_SCHEMA_VERSION = "attestation-trust-investigation.v3"
MAX_ATTESTATION_TRUST_PAGE_LIMIT = 200
MAX_ATTESTATION_TRUST_FILTER_CHARS = 256
MAX_ATTESTATION_TRUST_TEXT_CHARS = 200
ATTESTATION_KEY_STATUSES = (
    "active",
    "revoked",
    "superseded",
    "untrusted",
    "unsigned",
    "trust-state-unauthenticated",
    "trust-state-unconfigured",
)


def _digest(payload: dict[str, object]) -> str:
    """Return the deterministic digest of one JSON-compatible projection."""
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class AttestationTrustAuthentication:
    """Authentication outcome for one structurally valid trust-state snapshot."""

    status: str
    authenticated: bool | None
    reason: str
    authority_key_digest: str | None = None

    def __post_init__(self) -> None:
        """Validate the bounded authentication vocabulary."""
        if self.status not in {
            "verified",
            "failed",
            "not-configured",
            "dependency-unavailable",
        }:
            raise ValueError("unsupported attestation trust authentication status")
        if self.status == "verified" and self.authenticated is not True:
            raise ValueError("verified trust state must be authenticated")
        if self.status == "failed" and self.authenticated is not False:
            raise ValueError("failed trust state must be unauthenticated")
        if self.status in {"not-configured", "dependency-unavailable"} and (
            self.authenticated is not None
        ):
            raise ValueError("unverified trust state must use null authentication")

    def to_dict(self) -> dict[str, object]:
        """Serialize the authentication outcome."""
        return {
            "status": self.status,
            "authenticated": self.authenticated,
            "reason": self.reason,
            "authority_key_digest": self.authority_key_digest,
        }


@dataclass(frozen=True, slots=True)
class SignedAttestationBindingAuthentication:
    """Verification outcome for one recorded signed-attestation trust binding."""

    status: str
    authenticated: bool | None
    reason: str

    def __post_init__(self) -> None:
        """Validate the bounded signed-binding verification vocabulary."""
        allowed = {
            "verified",
            "dependency-unavailable",
            "authority-not-configured",
            "trust-state-unavailable",
            "not-recorded",
            "not-evaluated",
        }
        if self.status not in allowed:
            raise ValueError("unsupported signed attestation binding status")
        if self.status == "verified" and self.authenticated is not True:
            raise ValueError("verified signed attestation binding must authenticate")
        if self.status != "verified" and self.authenticated is not None:
            raise ValueError(
                "unverified signed attestation binding must use null authentication"
            )

    def to_dict(self) -> dict[str, object]:
        """Serialize the signed-binding verification outcome."""
        return {
            "status": self.status,
            "authenticated": self.authenticated,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class AttestationTrustQuery:
    """Allowlisted filters for attestation trust investigation."""

    decision: str | None = None
    reliability_state: str | None = None
    key_status: str | None = None
    text: str | None = None
    limit: int = 50
    offset: int = 0

    def __post_init__(self) -> None:
        """Validate bounded pagination and known enum filters."""
        if self.limit < 1 or self.limit > MAX_ATTESTATION_TRUST_PAGE_LIMIT:
            raise ValueError("attestation trust page limit is out of bounds")
        if self.offset < 0:
            raise ValueError("attestation trust page offset must be non-negative")
        if self.decision is not None and self.decision not in {
            "accept",
            "review",
            "reject",
        }:
            raise ValueError("unsupported attestation decision filter")
        if self.reliability_state is not None and self.reliability_state not in {
            "reliable",
            "degraded",
            "unreliable",
            "recovered",
        }:
            raise ValueError("unsupported attestation reliability-state filter")
        if (
            self.key_status is not None
            and self.key_status not in ATTESTATION_KEY_STATUSES
        ):
            raise ValueError("unsupported attestation key-status filter")
        for value, maximum in (
            (self.decision, MAX_ATTESTATION_TRUST_FILTER_CHARS),
            (self.reliability_state, MAX_ATTESTATION_TRUST_FILTER_CHARS),
            (self.key_status, MAX_ATTESTATION_TRUST_FILTER_CHARS),
            (self.text, MAX_ATTESTATION_TRUST_TEXT_CHARS),
        ):
            if value is not None and (not value.strip() or len(value) > maximum):
                raise ValueError("attestation trust filter is blank or too long")


@dataclass(frozen=True, slots=True)
class AttestationTrustProjection:
    """Bounded read projection of attestation integrity and current signing trust."""

    payload: dict[str, object]

    @property
    def digest(self) -> str:
        """Return a deterministic ETag digest for this projection."""
        return _digest(self.payload)

    def to_dict(self) -> dict[str, object]:
        """Serialize the projection without exposing source paths or raw keys."""
        return dict(self.payload)


def _history_index(
    snapshot: AttestationTrustHistorySnapshot | None,
    *,
    authenticated: bool | None,
) -> dict[str, dict[str, object]]:
    """Build lifecycle observations only from authenticated trust history."""
    if snapshot is None or authenticated is not True:
        return {}
    result: dict[str, dict[str, object]] = {}
    for state in snapshot.records:
        for anchor in state.anchors:
            current = result.setdefault(
                anchor.key_id,
                {
                    "statuses": [],
                    "first_version": state.version,
                    "last_version": state.version,
                    "latest_status": anchor.status,
                    "ever_observed_active": False,
                    "superseded_by": None,
                    "public_key_digest": sha256(anchor.public_key).hexdigest(),
                },
            )
            statuses = current["statuses"]
            assert isinstance(statuses, list)
            if anchor.status not in statuses:
                statuses.append(anchor.status)
            current["last_version"] = state.version
            current["latest_status"] = anchor.status
            current["ever_observed_active"] = bool(
                current["ever_observed_active"] or anchor.status == "active"
            )
            current["superseded_by"] = anchor.superseded_by
    return result


def _historical_context(
    signing_key_id: str | None,
    history_index: dict[str, dict[str, object]],
    *,
    history_authenticated: bool | None,
) -> dict[str, object]:
    """Project bounded lifecycle evidence without inventing attestation-time trust."""
    if signing_key_id is None:
        return {
            "history_authenticated": history_authenticated,
            "observed_in_authenticated_history": False
            if history_authenticated is True
            else None,
            "ever_observed_active": False if history_authenticated is True else None,
            "observed_statuses": [],
            "latest_observed_status": None,
            "first_observed_version": None,
            "last_observed_version": None,
            "attestation_time_binding_recorded": False,
            "attestation_time_status": None,
        }
    observed = history_index.get(signing_key_id)
    if history_authenticated is not True:
        return {
            "history_authenticated": history_authenticated,
            "observed_in_authenticated_history": None,
            "ever_observed_active": None,
            "observed_statuses": [],
            "latest_observed_status": None,
            "first_observed_version": None,
            "last_observed_version": None,
            "attestation_time_binding_recorded": False,
            "attestation_time_status": None,
        }
    if observed is None:
        return {
            "history_authenticated": True,
            "observed_in_authenticated_history": False,
            "ever_observed_active": False,
            "observed_statuses": [],
            "latest_observed_status": None,
            "first_observed_version": None,
            "last_observed_version": None,
            "attestation_time_binding_recorded": False,
            "attestation_time_status": None,
        }
    observed_statuses = observed["statuses"]
    assert isinstance(observed_statuses, list)
    return {
        "history_authenticated": True,
        "observed_in_authenticated_history": True,
        "ever_observed_active": observed["ever_observed_active"],
        "observed_statuses": list(observed_statuses),
        "latest_observed_status": observed["latest_status"],
        "first_observed_version": observed["first_version"],
        "last_observed_version": observed["last_version"],
        "attestation_time_binding_recorded": False,
        "attestation_time_status": None,
    }


def _history_source(
    snapshot: AttestationTrustHistorySnapshot | None,
    state: SignedAttestationTrustState | None,
    *,
    configured: bool,
    read_limit_bytes: int,
    record_limit: int,
    authenticated: bool | None,
    authority_store_configured: bool,
    authentication_status_override: str | None = None,
) -> dict[str, object]:
    """Project authenticated history summaries without raw keys or signatures."""
    records = () if snapshot is None else snapshot.records
    exists = False if snapshot is None else snapshot.exists
    if authentication_status_override is not None:
        authentication_status = authentication_status_override
    elif not configured:
        authentication_status = "not-configured"
    elif not exists:
        authentication_status = "not-present"
    elif not records:
        authentication_status = "empty"
    elif authenticated is True:
        authentication_status = "verified"
    elif not authority_store_configured:
        authentication_status = "authority-not-configured"
    else:
        authentication_status = "unavailable"

    states = [
        {
            "version": item.version,
            "issued_at": item.issued_at,
            "digest": item.digest(),
            "previous_digest": item.previous_digest,
            "authority_key_id": item.authority_key_id,
            "anchor_count": len(item.anchors),
        }
        for item in records
    ]
    transitions: list[dict[str, object]] = []
    if authenticated is True:
        for previous, current in zip(records, records[1:], strict=False):
            old = {anchor.key_id: anchor for anchor in previous.anchors}
            new = {anchor.key_id: anchor for anchor in current.anchors}
            transitions.append(
                {
                    "from_version": previous.version,
                    "to_version": current.version,
                    "from_digest": previous.digest(),
                    "to_digest": current.digest(),
                    "issued_at": current.issued_at,
                    "authority_key_id": current.authority_key_id,
                    "authority_changed": previous.authority_key_id
                    != current.authority_key_id,
                    "activated_key_ids": sorted(key for key in new if key not in old),
                    "revoked_key_ids": sorted(
                        key
                        for key, anchor in new.items()
                        if key in old
                        and old[key].status != "revoked"
                        and anchor.status == "revoked"
                    ),
                    "superseded_keys": [
                        {"key_id": key, "superseded_by": anchor.superseded_by}
                        for key, anchor in sorted(new.items())
                        if key in old
                        and old[key].status != "superseded"
                        and anchor.status == "superseded"
                    ],
                    "removed_key_ids": sorted(key for key in old if key not in new),
                }
            )
    tip = records[-1] if records else None
    tip_alignment: str
    if authenticated is not True or tip is None or state is None:
        tip_alignment = "not-established"
    elif tip.digest() == state.digest():
        tip_alignment = "verified"
    else:
        tip_alignment = "mismatch"
    return {
        "configured": configured,
        "exists": exists,
        "byte_size": 0 if snapshot is None else snapshot.byte_size,
        "read_limit_bytes": read_limit_bytes,
        "record_limit": record_limit,
        "state_count": len(records),
        "chain_integrity": (
            "not-configured"
            if not configured
            else "missing"
            if not exists
            else "verified"
        ),
        "authentication_status": authentication_status,
        "lifecycle_authoritative": authenticated is True,
        "first_version": None if not records else records[0].version,
        "latest_version": None if tip is None else tip.version,
        "tip_digest": None if tip is None else tip.digest(),
        "current_tip_alignment": tip_alignment,
        "states": states,
        "transitions": transitions,
    }


def _key_context(
    signing_key_id: str | None,
    state: SignedAttestationTrustState | None,
    authentication: AttestationTrustAuthentication,
) -> dict[str, object]:
    """Resolve a key reference only as far as authenticated current trust permits."""
    if signing_key_id is None:
        return {
            "signing_key_id": None,
            "key_version": None,
            "recorded_anchor_status": None,
            "effective_current_status": "unsigned",
            "currently_trusted_for_signing": False,
            "superseded_by": None,
            "public_key_digest": None,
            "trust_state_version": None if state is None else state.version,
        }
    if state is None:
        return {
            "signing_key_id": signing_key_id,
            "key_version": None,
            "recorded_anchor_status": None,
            "effective_current_status": "trust-state-unconfigured",
            "currently_trusted_for_signing": None,
            "superseded_by": None,
            "public_key_digest": None,
            "trust_state_version": None,
        }

    anchor = next(
        (item for item in state.anchors if item.key_id == signing_key_id), None
    )
    recorded = None if anchor is None else anchor.status
    digest = None if anchor is None else sha256(anchor.public_key).hexdigest()
    superseded_by = None if anchor is None else anchor.superseded_by
    if authentication.authenticated is not True:
        return {
            "signing_key_id": signing_key_id,
            "key_version": None,
            "recorded_anchor_status": recorded,
            "effective_current_status": "trust-state-unauthenticated",
            "currently_trusted_for_signing": None,
            "superseded_by": superseded_by,
            "public_key_digest": digest,
            "trust_state_version": state.version,
        }
    if anchor is None:
        return {
            "signing_key_id": signing_key_id,
            "key_version": None,
            "recorded_anchor_status": None,
            "effective_current_status": "untrusted",
            "currently_trusted_for_signing": False,
            "superseded_by": None,
            "public_key_digest": None,
            "trust_state_version": state.version,
        }
    return {
        "signing_key_id": signing_key_id,
        "key_version": None,
        "recorded_anchor_status": anchor.status,
        "effective_current_status": anchor.status,
        "currently_trusted_for_signing": anchor.status == "active",
        "superseded_by": anchor.superseded_by,
        "public_key_digest": digest,
        "trust_state_version": state.version,
    }


def _recorded_binding_is_authenticated(row: dict[str, object]) -> bool:
    """Return whether a projected row records an authenticated signed binding."""
    context = row.get("signing_trust_context")
    if not isinstance(context, dict):
        return False
    authentication = context.get("authentication")
    return (
        isinstance(authentication, dict) and authentication.get("authenticated") is True
    )


def build_attestation_trust_projection(
    snapshot: ReliabilityAttestationSnapshot | None,
    state: SignedAttestationTrustState | None,
    authentication: AttestationTrustAuthentication,
    query: AttestationTrustQuery,
    history_snapshot: AttestationTrustHistorySnapshot | None = None,
    history_authenticated: bool | None = None,
    *,
    attestation_configured: bool,
    attestation_read_limit_bytes: int,
    attestation_record_limit: int,
    trust_state_configured: bool,
    authority_store_configured: bool,
    trust_history_configured: bool = False,
    trust_history_read_limit_bytes: int = 0,
    trust_history_record_limit: int = 0,
    trust_state_from_history: bool = False,
    trust_history_authentication_status: str | None = None,
    signed_binding_authentication: Mapping[str, SignedAttestationBindingAuthentication]
    | None = None,
) -> AttestationTrustProjection:
    """Build the bounded operator view without inventing signature authenticity."""
    records = () if snapshot is None else snapshot.records
    signed_binding_authentication = dict(signed_binding_authentication or {})
    history_index = _history_index(
        history_snapshot, authenticated=history_authenticated
    )
    items: list[dict[str, object]] = []
    all_rows: list[dict[str, object]] = []
    for sequence, attestation in enumerate(records):
        key_context = _key_context(attestation.signing_key_id, state, authentication)
        key_context["historical_context"] = _historical_context(
            attestation.signing_key_id,
            history_index,
            history_authenticated=history_authenticated,
        )
        binding = (
            None
            if snapshot is None
            else snapshot.binding_for(attestation.attestation_id)
        )
        if binding is None:
            binding_authentication = SignedAttestationBindingAuthentication(
                "not-recorded",
                None,
                "No canonical signed envelope and trust-context binding is recorded for this attestation.",
            )
            signing_context: dict[str, object] = {
                "recorded": False,
                "authentication": binding_authentication.to_dict(),
                "trust_state_version": None,
                "trust_state_digest": None,
                "signing_key_digest": None,
                "authority_key_id": None,
                "authority_key_digest": None,
                "signing_time_key_status": None,
                "trusted_timestamp_recorded": False,
            }
        else:
            binding_authentication = signed_binding_authentication.get(
                attestation.attestation_id,
                SignedAttestationBindingAuthentication(
                    "not-evaluated",
                    None,
                    "The signed binding is recorded but was not cryptographically evaluated in this projection.",
                ),
            )
            context = binding.trust_context
            signing_context = {
                "recorded": True,
                "authentication": binding_authentication.to_dict(),
                "trust_state_version": context.trust_state_version,
                "trust_state_digest": context.trust_state_digest,
                "signing_key_digest": context.signing_key_digest,
                "authority_key_id": context.authority_key_id,
                "authority_key_digest": context.authority_key_digest,
                "signing_time_key_status": (
                    "active" if binding_authentication.authenticated is True else None
                ),
                "trusted_timestamp_recorded": False,
            }
        row: dict[str, object] = {
            "sequence": sequence,
            "attestation_id": attestation.attestation_id,
            "subject_id": attestation.subject_id,
            "occurred_at": attestation.occurred_at,
            "actor": attestation.actor,
            "evidence_chain_id": attestation.evidence_chain_id,
            "evidence_chain_digest": attestation.evidence_chain_digest,
            "transition_id": attestation.transition_id,
            "transition_digest": attestation.transition_digest,
            "reliability_state": attestation.reliability_state,
            "decision": attestation.decision,
            "verification_status": attestation.verification_status,
            "reconciliation_state": attestation.reconciliation_state,
            "previous_digest": attestation.previous_digest,
            "attestation_digest": attestation.digest,
            "key_context": key_context,
            "signature_envelope_recorded": binding is not None,
            "signing_trust_context": signing_context,
        }
        all_rows.append(row)

    def matches(row: dict[str, object]) -> bool:
        """Return whether one projected attestation satisfies the bounded query."""
        if query.decision is not None and row["decision"] != query.decision:
            return False
        if (
            query.reliability_state is not None
            and row["reliability_state"] != query.reliability_state
        ):
            return False
        key_context = row["key_context"]
        assert isinstance(key_context, dict)
        if (
            query.key_status is not None
            and key_context["effective_current_status"] != query.key_status
        ):
            return False
        if query.text is not None:
            needle = query.text.casefold()
            fields = (
                row["attestation_id"],
                row["subject_id"],
                row["actor"],
                row["evidence_chain_id"],
                row["transition_id"],
                key_context["signing_key_id"],
            )
            if not any(
                needle in str(value).casefold() for value in fields if value is not None
            ):
                return False
        return True

    matched = [row for row in all_rows if matches(row)]
    items.extend(matched[query.offset : query.offset + query.limit])

    anchors: list[dict[str, object]] = []
    if state is not None:
        for anchor in state.anchors:
            anchors.append(
                {
                    "key_id": anchor.key_id,
                    "public_key_digest": sha256(anchor.public_key).hexdigest(),
                    "recorded_status": anchor.status,
                    "superseded_by": anchor.superseded_by,
                    "current_trust_applicable": authentication.authenticated is True,
                }
            )

    status_counts = dict.fromkeys(ATTESTATION_KEY_STATUSES, 0)
    signed_refs = 0
    for row in all_rows:
        row_key_context = row["key_context"]
        assert isinstance(row_key_context, dict)
        status = str(row_key_context["effective_current_status"])
        status_counts[status] += 1
        if row_key_context["signing_key_id"] is not None:
            signed_refs += 1

    state_payload: dict[str, object]
    if state is None:
        state_payload = {
            "configured": trust_state_configured,
            "derived_from_history": False,
            "present": False,
            "version": None,
            "issued_at": None,
            "digest": None,
            "previous_digest": None,
            "authority_key_id": None,
            "authentication": authentication.to_dict(),
            "anchor_count": 0,
            "anchors": [],
        }
    else:
        state_payload = {
            "configured": trust_state_configured,
            "derived_from_history": trust_state_from_history,
            "present": True,
            "version": state.version,
            "issued_at": state.issued_at,
            "digest": state.digest(),
            "previous_digest": state.previous_digest,
            "authority_key_id": state.authority_key_id,
            "authentication": authentication.to_dict(),
            "anchor_count": len(anchors),
            "anchors": anchors,
        }

    returned = len(items)
    payload: dict[str, object] = {
        "schema_version": ATTESTATION_TRUST_SCHEMA_VERSION,
        "sources": {
            "attestation_store": {
                "configured": attestation_configured,
                "exists": False if snapshot is None else snapshot.exists,
                "byte_size": 0 if snapshot is None else snapshot.byte_size,
                "read_limit_bytes": attestation_read_limit_bytes,
                "record_limit": attestation_record_limit,
                "signed_binding_count": (
                    0 if snapshot is None else len(snapshot.signed_bindings)
                ),
                "chain_integrity": (
                    "not-configured"
                    if not attestation_configured
                    else "missing"
                    if snapshot is not None and not snapshot.exists
                    else "verified"
                ),
            },
            "trust_state": state_payload,
            "authority_store": {
                "configured": authority_store_configured,
                "raw_keys_exposed": False,
            },
            "trust_history": _history_source(
                history_snapshot,
                state,
                configured=trust_history_configured,
                read_limit_bytes=trust_history_read_limit_bytes,
                record_limit=trust_history_record_limit,
                authenticated=history_authenticated,
                authority_store_configured=authority_store_configured,
                authentication_status_override=trust_history_authentication_status,
            ),
        },
        "summary": {
            "total_attestations": len(all_rows),
            "signing_key_references": signed_refs,
            "signed_envelope_records": sum(
                1 for row in all_rows if row["signature_envelope_recorded"] is True
            ),
            "verified_signed_bindings": sum(
                1 for row in all_rows if _recorded_binding_is_authenticated(row)
            ),
            "unsigned_attestations": status_counts["unsigned"],
            "active_key_references": status_counts["active"],
            "revoked_key_references": status_counts["revoked"],
            "superseded_key_references": status_counts["superseded"],
            "untrusted_key_references": status_counts["untrusted"],
            "unauthenticated_key_references": status_counts[
                "trust-state-unauthenticated"
            ],
            "unconfigured_trust_state_references": status_counts[
                "trust-state-unconfigured"
            ],
            "historically_observed_key_references": sum(
                1
                for row in all_rows
                if isinstance(row["key_context"], dict)
                and isinstance(row["key_context"].get("historical_context"), dict)
                and row["key_context"]["historical_context"].get(
                    "observed_in_authenticated_history"
                )
                is True
            ),
            "historically_active_key_references": sum(
                1
                for row in all_rows
                if isinstance(row["key_context"], dict)
                and isinstance(row["key_context"].get("historical_context"), dict)
                and row["key_context"]["historical_context"].get("ever_observed_active")
                is True
            ),
        },
        "query": {
            "decision": query.decision,
            "reliability_state": query.reliability_state,
            "key_status": query.key_status,
            "text": query.text,
            "limit": query.limit,
            "offset": query.offset,
        },
        "page": {
            "limit": query.limit,
            "offset": query.offset,
            "returned": returned,
            "matched": len(matched),
            "has_more": query.offset + returned < len(matched),
            "next_offset": (
                query.offset + returned
                if query.offset + returned < len(matched)
                else None
            ),
        },
        "items": items,
        "limitations": [
            "Legacy attestation records remain valid without a signed-envelope binding; absence of a binding is reported explicitly rather than treated as signature failure.",
            "A verified signed binding proves the recorded envelope signature and the exact authenticated trust-state snapshot used for that binding; it does not provide an external trusted timestamp for the attestation occurred_at value.",
            "Raw signed-envelope bytes, signatures, public keys, authority keys, and private key material are not exposed by this read-only projection.",
            "Anchor active/revoked/superseded status affects current signing trust only when the configured trust-state snapshot is independently authenticated.",
            "An unauthenticated trust-state snapshot may be displayed diagnostically, but its recorded anchor status is not treated as current trust authority.",
            "Historical lifecycle claims are derived only from an authenticated canonical trust-history chain when one is configured; structural predecessor links alone are not treated as authority.",
            "SigningKeyReference version/provider fields are not persisted in ReliabilityOutcomeAttestation, so this view does not invent key versions or providers.",
            "Current key trust can differ from the authenticated signing context recorded for a historical signed attestation.",
            "This read-only surface never rotates, revokes, supersedes, signs, publishes, or authorizes an attestation.",
        ],
    }
    return AttestationTrustProjection(payload)
