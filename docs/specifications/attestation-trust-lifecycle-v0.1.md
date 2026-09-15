> **Specification classification:** Active V1 specification.
>

# Attestation Trust Lifecycle

The attestation signing trust lifecycle is intentionally distinct from policy-signing trust.

## Model

`SignedAttestationTrustState` contains a versioned, signed snapshot of `AttestationTrustAnchor` entries.
Each anchor is `active`, `revoked`, or `superseded` and supersession names the active replacement key.
Snapshots form a monotonic SHA-256 continuity chain through `previous_digest`.

## Verification

A separately trusted authority verifies the trust-state signature. `Ed25519AttestationVerifier` may consume a verified attestation trust state and then rejects revoked or superseded attestation signing keys. The configured public key must exactly match the active trust anchor.

## Invalidation

A previously valid signed attestation is deterministically invalidated when the trust state supplied for verification marks its signing key revoked or superseded. Policy trust state remains a separate input and is never treated as attestation signing trust.

## Boundaries

Private-key custody, rotation orchestration, trust-anchor distribution, external registries, and time-based key expiry remain host responsibilities.
