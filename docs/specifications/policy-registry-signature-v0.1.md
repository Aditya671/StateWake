> **Specification classification:** Historical reference.
>

# Policy Registry + Signature Verification Specification v0.1

## Scope

The policy registry boundary provides a read-only policy registry boundary and authenticity verification for immutable `PolicyPack` artifacts.

## Envelope

A `SignedPolicyEnvelope` carries:

- signature algorithm (`Ed25519`)
- signing `key_id`
- exact `PolicyPack` JSON payload
- SHA-256 digest of the canonical policy payload
- base64url-encoded signature

The signed bytes are deterministic canonical JSON containing the policy payload and its payload digest.

## Trust boundary

The engine accepts a caller-supplied trust store mapping key identifiers to Ed25519 public keys. Key generation, storage, rotation, revocation, trust-anchor distribution, and key custody remain outside the engine.

## Registry adapters

The domain depends only on a read-only `PolicyRegistry` protocol. Reference adapters are provided for:

- local JSON files
- HTTP(S) read access

The HTTP adapter may attach a bearer token supplied by the host.

## Verification rules

A policy is accepted only when:

1. the envelope uses the supported algorithm;
2. the signing key ID is trusted;
3. the signature verifies over the exact canonical envelope payload;
4. the embedded policy digest is valid;
5. the `PolicyPack` digest is valid;
6. the returned pack ID and version exactly match the registry lookup request.

Signature failure, unknown keys, malformed payloads, digest mismatch, and registry lookup failures are fail-closed errors.

## Non-goals

This phase does not implement a key-management service, certificate authority, remote policy write API, policy revocation registry, or consensus system.
