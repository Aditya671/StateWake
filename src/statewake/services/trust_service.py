"""Loading and verification helpers for reliability attestation trust state."""

from __future__ import annotations

import base64
import json
from collections.abc import Mapping
from pathlib import Path

from statewake.adapters.attestation_trust_history import (
    AttestationTrustHistorySnapshot,
    JsonlAttestationTrustHistoryStore,
    read_attestation_trust_history_snapshot,
)
from statewake.utils.json_support import JsonValue, load_object

from ..domain.attestation_trust import (
    Ed25519AttestationTrustStateVerifier,
    SignedAttestationTrustState,
)
from .persistence import atomic_write_text


def authority_store_from_dict(payload: Mapping[str, JsonValue]) -> dict[str, bytes]:
    """Parse externally managed verification keys from an already-bounded object."""
    keys = payload.get("keys", {})
    if not isinstance(keys, dict):
        raise ValueError("authority store must contain a keys object.")

    result: dict[str, bytes] = {}
    for key_id, encoded in keys.items():
        if not isinstance(key_id, str) or not key_id.strip():
            raise ValueError("authority key identifiers must be non-empty text.")
        if not isinstance(encoded, str) or not encoded:
            raise ValueError(f"authority key {key_id!r} must be base64 text.")
        try:
            result[key_id] = base64.urlsafe_b64decode(
                encoded + "=" * (-len(encoded) % 4)
            )
        except (ValueError, UnicodeEncodeError) as exc:
            raise ValueError(f"authority key {key_id!r} is not valid base64.") from exc
    return result


def load_authority_store(path: Path) -> dict[str, bytes]:
    """Load externally managed verification keys from an authority-store document."""
    return authority_store_from_dict(load_object(path))


def load_attestation_trust_state(path: Path) -> SignedAttestationTrustState:
    """Load a serialized reliability-attestation trust state."""
    payload = load_object(path)
    if not isinstance(payload, dict):
        raise ValueError("attestation trust-state root must be an object.")
    return SignedAttestationTrustState.from_dict(payload)


def verify_attestation_trust_state(
    path: Path,
    authority_store: Mapping[str, bytes],
) -> SignedAttestationTrustState:
    """Verify an attestation trust state against the supplied trust anchors."""
    state = load_attestation_trust_state(path)
    return Ed25519AttestationTrustStateVerifier(authority_store).verify(state)


def load_verified_attestation_trust_states(
    *,
    authority_store: Mapping[str, bytes],
    current_state_path: Path | None = None,
    history_path: Path | None = None,
    max_history_bytes: int,
    max_history_records: int,
) -> tuple[SignedAttestationTrustState, ...]:
    """Load authenticated current/history trust states without duplicating exact records."""
    states: list[SignedAttestationTrustState] = []
    if history_path is not None:
        history = verify_attestation_trust_history(
            history_path,
            authority_store=authority_store,
            max_bytes=max_history_bytes,
            max_records=max_history_records,
        )
        states.extend(history.records)
    if current_state_path is not None:
        current = verify_attestation_trust_state(current_state_path, authority_store)
        if all(
            existing.version != current.version or existing.digest() != current.digest()
            for existing in states
        ):
            states.append(current)
    return tuple(states)


def append_attestation_trust_state(
    state: SignedAttestationTrustState,
    *,
    history_store: JsonlAttestationTrustHistoryStore,
    current_state_path: Path | None = None,
) -> SignedAttestationTrustState:
    """Persist one authenticated trust-state transition and optionally update current state."""
    persisted = history_store.append(state)
    if current_state_path is not None:
        current_state_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(
            current_state_path,
            json.dumps(persisted.to_dict(), indent=2, sort_keys=True) + "\n",
        )
    return persisted


def verify_attestation_trust_history(
    path: Path,
    *,
    authority_store: Mapping[str, bytes],
    max_bytes: int,
    max_records: int,
) -> AttestationTrustHistorySnapshot:
    """Read, authenticate, and return one bounded trust-state history."""
    snapshot = read_attestation_trust_history_snapshot(
        path, max_bytes=max_bytes, max_records=max_records
    )
    verifier = Ed25519AttestationTrustStateVerifier(authority_store)
    for state in snapshot.records:
        verifier.verify(state)
    return snapshot
